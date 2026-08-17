#!/usr/bin/env python3
"""prepare-slate.py — the closed deterministic pre-slate helper (ADR-1 amendment, 2026-08-16).

Protocol v1, four commands, each reading one JSON object from stdin and writing one JSON object
to stdout. Diagnostics (human-readable, never the caller's contract) go to stderr only.

  prepare     read-only. Resolves the discovery window, known anchors, exact-domain routes and
              collisions, and display context. Writes nothing.
  normalize   pure. Filters raw calendar/email candidates to the discovery window and emits the
              unified event shape with stable IDs and collision-free domain suggestions.
  materialize --apply. The one atomic mutation: upserts classified events into
              state/run-state.yaml's top-level `events` value only, and derives slate_view.
  render      read-only, and the only command guaranteed to need no PyYAML: fills the pinned
              runtime/templates/slate-widget.html layout from a slate_view materialize already
              derived, and returns the finished widget fragment. Re-derives no display string.

This helper makes NO ambiguity, fuzzy-identity, namespace, entity-resolution, ranking, selection,
rep-decision, connector-access, or external-write judgment — every one of those stays with the
owning skill (see notes/architecture.md ADR-1 amendment and CONSTITUTION.md Article I). It holds no
credential and makes no network call.

Exit codes (this repo's existing gate idiom — see runtime/plugin-parity.py):
  0  ok                     — stdout carries {"status": "ok", ...}
  1  refusal                — a data/state/input fault; the run must STOP, never fall back silently.
                              stdout carries {"status": "error", "error": "<code>", "message": "..."}
  2  unavailable            — PyYAML is missing, the caller's contract_version is unsupported, or
                              (render only) the pinned template file cannot be read. stdout carries
                              {"status": "unavailable", "reason": "..."}. The caller loads
                              skills/pipeline/pre-slate-fallback.md instead — this is the ONLY
                              exit code that licenses fallback.

A missing executable surface or a missing resource (the other two availability conditions the tech
spec names) are the caller's own detection, not this script's — if it cannot run at all, it never
emits anything.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import zoneinfo

try:
    import yaml
except ImportError:  # pragma: no cover - exercised via the PyYAML-missing availability path
    yaml = None

CONTRACT_VERSION = 1
SAFE_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DURATION_RE = re.compile(r"^(\d+)(h|d)$")
VALID_EVIDENCE = ("present", "missing", "unknown")
VALID_PROCESSING = ("pending", "processed")
VALID_PHASE = ("planned", "triaged", "executed")


class Refusal(Exception):
    """A data/state/input fault. The caller must stop the run — never fallback-eligible."""

    def __init__(self, code, message, **fields):
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = fields


class Unavailable(Exception):
    """PyYAML missing or unsupported contract_version. The ONLY fallback-eligible condition."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# ── duplicate-key-rejecting YAML loader ────────────────────────────────────────────────────────
# PyYAML's default SafeLoader silently keeps the LAST of two duplicate keys (the exact hazard
# sprint-status.yaml's own header warns about). A hand-edited run-state.yaml is exactly the kind of
# file that accretes a duplicate key by mistake, so this loader raises instead of picking a winner.
#
# It also disables SafeLoader's implicit `timestamp` resolver: YAML 1.1 auto-converts an
# ISO-8601-shaped scalar into a Python datetime/date object, which is exactly the kind of silent
# reformatting "preserve occurred_at/last_run verbatim" exists to forbid (a round-tripped datetime
# does not necessarily print back byte-identical to what was written). Every timestamp field stays
# a plain string here; this module parses it explicitly, on its own terms, wherever it needs one.
if yaml is not None:

    class _NoDupeSafeLoader(yaml.SafeLoader):
        pass

    _NoDupeSafeLoader.yaml_implicit_resolvers = {
        first: [(tag, regexp) for tag, regexp in resolvers if tag != "tag:yaml.org,2002:timestamp"]
        for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }

    def _construct_mapping_no_dupes(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping", node.start_mark,
                    f"found duplicate key {key!r}", key_node.start_mark)
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    _NoDupeSafeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping_no_dupes)


def load_yaml_no_dupes(text):
    return yaml.load(text, Loader=_NoDupeSafeLoader)


# ── small validation helpers ───────────────────────────────────────────────────────────────────
def require_str(payload, key):
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise Refusal("bad_request", f"{key!r} is required and must be a non-empty string")
    return value


def parse_offset_datetime(value, field, code):
    if not isinstance(value, str):
        raise Refusal(code, f"{field} must be a string")
    try:
        dt = datetime.datetime.fromisoformat(value)
    except ValueError:
        raise Refusal(code, f"{field} {value!r} is not a valid ISO 8601 timestamp")
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise Refusal(code, f"{field} {value!r} must carry an explicit UTC offset")
    return dt


def load_zoneinfo(name):
    if not isinstance(name, str) or not name:
        raise Refusal("invalid_state", "timezone must be a non-empty IANA zone name")
    try:
        return zoneinfo.ZoneInfo(name)
    except Exception as exc:  # ZoneInfoNotFoundError, ValueError, etc.
        raise Refusal("invalid_state", f"timezone {name!r} is not a recognized IANA zone: {exc}")


def check_contract_version(payload):
    if not isinstance(payload, dict):
        raise Refusal("bad_request", "input must be a JSON object")
    if "contract_version" not in payload:
        raise Refusal("bad_request", "'contract_version' is required")
    if payload["contract_version"] != CONTRACT_VERSION:
        raise Unavailable(
            f"unsupported contract_version {payload['contract_version']!r}; "
            f"this helper implements {CONTRACT_VERSION}")


# ── state/run-state.yaml parsing + validation (shared by prepare and materialize) ─────────────
def parse_and_validate_state(raw_text):
    try:
        data = load_yaml_no_dupes(raw_text)
    except Refusal:
        raise
    except yaml.YAMLError as exc:
        raise Refusal("invalid_state", f"state file is not valid YAML: {exc}")
    if not isinstance(data, dict):
        raise Refusal("invalid_state", "state file top level must be a YAML mapping")
    if "queue" in data:
        raise Refusal("invalid_state",
                       "state file carries the legacy 'queue' key — migrate to 'events' first")
    for key in ("last_run", "timezone"):
        if key not in data:
            raise Refusal("invalid_state", f"state file is missing required key {key!r}")
    parse_offset_datetime(data["last_run"], "last_run", "invalid_state")
    load_zoneinfo(data["timezone"])

    events = data.get("events") if data.get("events") is not None else []
    if not isinstance(events, list):
        raise Refusal("invalid_state", "'events' must be a list")
    validated_events, seen_ids = [], set()
    for i, ev in enumerate(events):
        record = validate_state_event(ev, i)
        if record["event_id"] in seen_ids:
            raise Refusal("invalid_state", f"duplicate event_id in state at events[{i}]")
        seen_ids.add(record["event_id"])
        validated_events.append(record)

    work = data.get("work") if data.get("work") is not None else []
    if not isinstance(work, list):
        raise Refusal("invalid_state", "'work' must be a list")
    validated_work = [validate_work_record(w, i) for i, w in enumerate(work)]

    scan_window = data.get("scan_window")
    if scan_window is not None and not isinstance(scan_window, str):
        raise Refusal("invalid_state", "'scan_window' must be a string when present")

    return {
        "last_run": data["last_run"], "timezone": data["timezone"], "scan_window": scan_window,
        "events": validated_events, "work": validated_work,
    }


def validate_state_event(ev, index):
    if not isinstance(ev, dict):
        raise Refusal("invalid_state", f"events[{index}] is not a mapping")
    event_id, source = ev.get("event_id"), ev.get("source")
    external_ref, occurred_at = ev.get("external_ref"), ev.get("occurred_at")
    namespace, slug = ev.get("namespace"), ev.get("slug")
    evidence_status, processing_status = ev.get("evidence_status"), ev.get("processing_status")
    if not isinstance(event_id, str) or not event_id:
        raise Refusal("invalid_state", f"events[{index}].event_id must be a non-empty string")
    if source not in ("call", "email"):
        raise Refusal("invalid_state", f"events[{index}].source must be 'call' or 'email'")
    if "external_ref" not in ev or (external_ref is not None and not isinstance(external_ref, str)):
        raise Refusal("invalid_state", f"events[{index}].external_ref must be a string or null")
    parse_offset_datetime(occurred_at, f"events[{index}].occurred_at", "invalid_state")
    if namespace not in ("accounts", "projects"):
        raise Refusal("invalid_state", f"events[{index}].namespace must be 'accounts' or 'projects'")
    if not isinstance(slug, str) or not SAFE_SLUG_RE.match(slug):
        raise Refusal("invalid_state", f"events[{index}].slug is not a valid kebab-case slug")
    if evidence_status not in VALID_EVIDENCE:
        raise Refusal("invalid_state", f"events[{index}].evidence_status must be one of {VALID_EVIDENCE}")
    if processing_status not in VALID_PROCESSING:
        raise Refusal("invalid_state", f"events[{index}].processing_status must be one of {VALID_PROCESSING}")
    record = {
        "event_id": event_id, "source": source, "external_ref": external_ref,
        "occurred_at": occurred_at, "namespace": namespace, "slug": slug,
        "evidence_status": evidence_status, "processing_status": processing_status,
    }
    if ev.get("call_type") is not None:
        record["call_type"] = ev["call_type"]
    if ev.get("subject") is not None:
        record["subject"] = ev["subject"]
    return record


def validate_work_record(w, index):
    if not isinstance(w, dict):
        raise Refusal("invalid_state", f"work[{index}] is not a mapping")
    namespace, slug, phase = w.get("namespace"), w.get("slug"), w.get("phase")
    plan_date, started_at, event_ids = w.get("plan_date"), w.get("started_at"), w.get("event_ids")
    if namespace not in ("accounts", "projects"):
        raise Refusal("invalid_state", f"work[{index}].namespace must be 'accounts' or 'projects'")
    if not isinstance(slug, str) or not SAFE_SLUG_RE.match(slug):
        raise Refusal("invalid_state", f"work[{index}].slug is not a valid kebab-case slug")
    if phase not in VALID_PHASE:
        raise Refusal("invalid_state", f"work[{index}].phase must be one of {VALID_PHASE}")
    if not isinstance(plan_date, str) or not plan_date:
        raise Refusal("invalid_state", f"work[{index}].plan_date must be a non-empty string")
    parse_offset_datetime(started_at, f"work[{index}].started_at", "invalid_state")
    if not isinstance(event_ids, list) or not event_ids:
        raise Refusal("invalid_state", f"work[{index}].event_ids must be a non-empty list")
    return {"namespace": namespace, "slug": slug, "phase": phase, "plan_date": plan_date,
            "started_at": started_at, "event_ids": event_ids}


# ── path resolution + file IO ──────────────────────────────────────────────────────────────────
def resolve_state_path(workspace_root):
    if not isinstance(workspace_root, str) or not workspace_root:
        raise Refusal("bad_request", "workspace_root must be a non-empty string")
    root_abs = os.path.realpath(workspace_root)
    state_path = os.path.realpath(os.path.join(root_abs, "state", "run-state.yaml"))
    if os.path.commonpath([root_abs, state_path]) != root_abs:
        raise Refusal("path_escape", "resolved state path escapes workspace_root")
    return root_abs, state_path


def read_text_and_bytes(path):
    try:
        with open(path, "rb") as fh:
            raw_bytes = fh.read()
    except FileNotFoundError:
        raise Refusal("invalid_state", f"state file not found at {path}")
    except OSError as exc:
        raise Refusal("invalid_state", f"cannot read state file: {exc}")
    try:
        raw_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal("invalid_state", f"state file is not valid UTF-8: {exc}")
    return raw_text, raw_bytes


# ── known anchors, context reading, domain routing (prepare only) ─────────────────────────────
def collect_anchors(workspace_root, events):
    anchors = set()
    for ns in ("accounts", "projects"):
        ns_dir = os.path.join(workspace_root, ns)
        if os.path.isdir(ns_dir):
            for entry in os.scandir(ns_dir):
                if entry.is_dir() and SAFE_SLUG_RE.match(entry.name):
                    anchors.add((ns, entry.name))
    for ev in events:
        anchors.add((ev["namespace"], ev["slug"]))
    return anchors


def split_frontmatter_and_summary(body):
    """(frontmatter_text_or_None, summary_text_or_None) — the `## Summary` body only."""
    frontmatter, rest = None, body
    if body.startswith("---\n") or body.startswith("---\r\n"):
        end = body.find("\n---", 4)
        if end != -1:
            frontmatter = body[4:end].lstrip("\n")
            nl = body.find("\n", end + 1)
            rest = body[nl + 1:] if nl != -1 else ""
    m = re.search(r"^##\s+Summary\s*$", rest, re.MULTILINE)
    summary = None
    if m:
        start = m.end()
        nxt = re.search(r"^##\s+", rest[start:], re.MULTILINE)
        summary_text = rest[start:start + nxt.start()] if nxt else rest[start:]
        summary = summary_text.strip() or None
    return frontmatter, summary


def fold_domain(raw):
    """Lowercase and strip exactly one trailing dot — the one normalization exact-domain
    matching applies, shared by context-domain indexing and sender-domain extraction so the two
    sides of a comparison can never drift apart."""
    key = raw.strip().lower()
    if key.endswith("."):
        key = key[:-1]
    return key


def read_known_contexts(workspace_root, anchors):
    """Returns (context, domain_index): context[ns][slug] = display data; domain_index maps a
    lowercased, trailing-dot-stripped domain to the set of account slugs that claim it."""
    context = {"accounts": {}, "projects": {}}
    domain_index = {}
    for ns, slug in sorted(anchors):
        path = os.path.join(workspace_root, ns, slug, "context.md")
        entry = {"name": None, "stage": None, "stakeholder_names": [], "summary": None, "domains": []}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    body = fh.read()
            except OSError as exc:
                raise Refusal("invalid_state", f"cannot read {ns}/{slug}/context.md: {exc}")
            frontmatter_text, summary = split_frontmatter_and_summary(body)
            fm = {}
            if frontmatter_text is not None:
                try:
                    fm = load_yaml_no_dupes(frontmatter_text) or {}
                except yaml.YAMLError as exc:
                    raise Refusal("invalid_state", f"{ns}/{slug}/context.md frontmatter is invalid YAML: {exc}")
                if not isinstance(fm, dict):
                    raise Refusal("invalid_state", f"{ns}/{slug}/context.md frontmatter must be a mapping")
            entry["name"] = fm.get("name")
            entry["stage"] = fm.get("stage")
            stakeholders = fm.get("stakeholders") or []
            entry["stakeholder_names"] = [
                s.get("name") for s in stakeholders if isinstance(s, dict) and s.get("name")
            ]
            entry["domains"] = [d for d in (fm.get("domains") or []) if isinstance(d, str)]
            entry["summary"] = summary
            if ns == "accounts":
                for d in entry["domains"]:
                    key = fold_domain(d)
                    if key:
                        domain_index.setdefault(key, set()).add(slug)
        context[ns][slug] = entry
    return context, domain_index


def resolve_domain_routes(domain_index):
    routes, collisions = {}, []
    for domain, slugs in sorted(domain_index.items()):
        if len(slugs) == 1:
            routes[domain] = next(iter(slugs))
        else:
            collisions.append({"domain": domain, "slugs": sorted(slugs)})
    return routes, collisions


# ── discovery window resolution (prepare only) ─────────────────────────────────────────────────
def check_sampled_at_matches_timezone(sampled_at, tz):
    expected_offset = sampled_at.astimezone(tz).utcoffset()
    if sampled_at.utcoffset() != expected_offset:
        raise Refusal(
            "invalid_window",
            f"sampled_at offset {sampled_at.utcoffset()} does not match timezone {tz.key} "
            f"at that instant (expected {expected_offset})")


def resolve_discovery_until(last_run, scan_window, sampled_at):
    if scan_window is None or scan_window == "now":
        return sampled_at
    m = DURATION_RE.match(scan_window)
    if not m:
        raise Refusal("invalid_window", f"scan_window {scan_window!r} is not 'now', '<n>h', or '<n>d'")
    n, unit = int(m.group(1)), m.group(2)
    delta = datetime.timedelta(hours=n) if unit == "h" else datetime.timedelta(days=n)
    return min(last_run + delta, sampled_at)


# ── command: prepare ────────────────────────────────────────────────────────────────────────────
def cmd_prepare(payload):
    check_contract_version(payload)
    workspace_root = require_str(payload, "workspace_root")
    sampled_at_raw = require_str(payload, "sampled_at")

    workspace_root_abs, state_path = resolve_state_path(workspace_root)
    raw_text, raw_bytes = read_text_and_bytes(state_path)
    state_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    state = parse_and_validate_state(raw_text)

    last_run = parse_offset_datetime(state["last_run"], "last_run", "invalid_state")
    tz = load_zoneinfo(state["timezone"])
    sampled_at = parse_offset_datetime(sampled_at_raw, "sampled_at", "invalid_window")
    check_sampled_at_matches_timezone(sampled_at, tz)

    discovery_until = resolve_discovery_until(last_run, state["scan_window"], sampled_at)
    if discovery_until <= last_run:
        raise Refusal("invalid_window", "discovery_until must be strictly after last_run")

    anchors = collect_anchors(workspace_root_abs, state["events"])
    context, domain_index = read_known_contexts(workspace_root_abs, anchors)
    domain_routes, domain_collisions = resolve_domain_routes(domain_index)

    return {
        "last_run": state["last_run"],
        "timezone": state["timezone"],
        "discovery_until": sampled_at_isoformat(discovery_until),
        "state_sha256": state_sha256,
        "known_anchors": [{"namespace": ns, "slug": sl} for ns, sl in sorted(anchors)],
        "domain_routes": domain_routes,
        "domain_collisions": domain_collisions,
        "context": context,
    }


def sampled_at_isoformat(dt):
    # datetime.isoformat() already renders an explicit +HH:MM/-HH:MM offset for an aware datetime
    # with a fixed-offset tzinfo (min() over two fromisoformat() results always has one) — verbatim
    # preservation of precision, never truncated or reformatted beyond what isoformat() produces.
    return dt.isoformat()


# ── command: normalize ─────────────────────────────────────────────────────────────────────────
def cmd_normalize(payload):
    check_contract_version(payload)
    prepare_out = payload.get("prepare")
    if not isinstance(prepare_out, dict):
        raise Refusal("bad_request", "'prepare' must be the prior prepare output object")
    last_run = parse_offset_datetime(require_str(prepare_out, "last_run"), "prepare.last_run", "bad_request")
    discovery_until = parse_offset_datetime(
        require_str(prepare_out, "discovery_until"), "prepare.discovery_until", "bad_request")
    domain_routes = prepare_out.get("domain_routes") or {}
    domain_collision_domains = {c["domain"] for c in (prepare_out.get("domain_collisions") or [])}

    calendar_candidates = payload.get("calendar_candidates")
    email_candidates = payload.get("email_candidates")
    if not isinstance(calendar_candidates, list) or not isinstance(email_candidates, list):
        raise Refusal("bad_request", "'calendar_candidates' and 'email_candidates' must be lists")

    events_out, collisions, faults = [], [], []

    for i, cand in enumerate(calendar_candidates):
        if not isinstance(cand, dict):
            faults.append({"index": i, "source": "call", "reason": "not_an_object"})
            continue
        start = cand.get("start")
        if not isinstance(start, str) or not start:
            faults.append({"index": i, "source": "call", "reason": "missing_occurred_at"})
            continue
        occurred_at = parse_offset_datetime(start, f"calendar_candidates[{i}].start", "invalid_input")
        if not (last_run < occurred_at <= discovery_until):
            continue  # a normal exclusion, not a fault — remains eligible next run
        ref = cand.get("ref")
        if not isinstance(ref, str) or not ref:
            faults.append({"index": i, "source": "call", "reason": "missing_external_ref"})
            continue
        events_out.append({
            "event_id": f"call:{ref}", "source": "call", "external_ref": ref,
            "occurred_at": start, "title": cand.get("title"),
            "participants": cand.get("attendees") or [],
        })

    for i, cand in enumerate(email_candidates):
        if not isinstance(cand, dict):
            faults.append({"index": i, "source": "email", "reason": "not_an_object"})
            continue
        last_message_at = cand.get("last_message_at")
        if not isinstance(last_message_at, str) or not last_message_at:
            faults.append({"index": i, "source": "email", "reason": "missing_occurred_at"})
            continue
        occurred_at = parse_offset_datetime(
            last_message_at, f"email_candidates[{i}].last_message_at", "invalid_input")
        if not (last_run < occurred_at <= discovery_until):
            continue
        thread_ref = cand.get("thread_ref")
        if not isinstance(thread_ref, str) or not thread_ref:
            faults.append({"index": i, "source": "email", "reason": "missing_external_ref"})
            continue
        event_id = f"email:{thread_ref}"
        out = {
            "event_id": event_id, "source": "email", "external_ref": thread_ref,
            "occurred_at": last_message_at, "title": cand.get("subject"),
            "participants": cand.get("participants") or [],
            "latest_message_body": cand.get("latest_external_message_body") or "",
        }
        sender_email = cand.get("sender_email")
        if isinstance(sender_email, str) and "@" in sender_email:
            domain = fold_domain(sender_email.rsplit("@", 1)[-1])
            if domain in domain_routes:
                out["suggested_slug"] = domain_routes[domain]
            elif domain in domain_collision_domains:
                collisions.append({"event_id": event_id, "domain": domain})
        events_out.append(out)

    return {"events": events_out, "collisions": collisions, "faults": faults}


# ── label derivation (materialize only — build-slate.md Rules 1-4, restated mechanically) ──────
def humanize_token(token):
    if not token or token == "unknown":
        return None
    s = re.sub(r"[-_]+", " ", token)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return None
    return s[0].upper() + s[1:]


def recency_label(d, today):
    delta = (today - d).days
    if delta == 0:
        return "today"
    if delta == 1:
        return "yesterday"
    if 2 <= delta <= 29:
        return f"{delta} days ago"
    return f"{d.strftime('%b')} {d.day}"


def build_slate_view(events, work, context_in, display_names, tz, today):
    groups, order = {}, []
    for ev in events:
        if ev["processing_status"] != "pending":
            continue
        key = (ev["namespace"], ev["slug"])
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(ev)

    work_by_key = {(w["namespace"], w["slug"]): w["phase"] for w in work}

    result = []
    for key in order:
        namespace, slug = key
        members = groups[key]
        calls = [m for m in members if m["source"] == "call"]
        emails = [m for m in members if m["source"] == "email"]

        ctx = (context_in.get(namespace) or {}).get(slug) or {}
        name = display_names.get(key) or ctx.get("name") or humanize_token(slug) or slug
        stage_label = humanize_token(ctx.get("stage"))

        call_pill, call_topic_label = None, None
        if calls:
            latest_call = max(calls, key=lambda m: m["occurred_at"])
            call_topic_label = humanize_token(latest_call.get("call_type"))
            call_date = parse_offset_datetime(
                latest_call["occurred_at"], "events[].occurred_at", "invalid_state").astimezone(tz).date()
            call_recency = recency_label(call_date, today)
            evidence = latest_call["evidence_status"]
            if evidence == "missing":
                call_pill = f"Call · {call_recency} · no recording"
            else:  # present or unknown — clause omitted on unknown, never fabricated
                call_pill = f"Call · {call_recency}"

        email_pill = None
        if emails:
            latest_email = max(emails, key=lambda m: m["occurred_at"])
            email_date = parse_offset_datetime(
                latest_email["occurred_at"], "events[].occurred_at", "invalid_state").astimezone(tz).date()
            email_recency = recency_label(email_date, today)
            n = len(emails)
            email_pill = f"{n} unanswered email{'s' if n > 1 else ''} · {email_recency}"

        phase = work_by_key.get(key)
        if phase is None:
            resume_pill = None
        elif phase == "planned":
            resume_pill = "Resume · plan ready"
        elif phase == "triaged":
            resume_pill = "Resume · triaged"
        elif phase == "executed":
            resume_pill = "Resume · awaiting close-out"
        else:  # pragma: no cover - parse_and_validate_state already rejects any other phase
            raise Refusal("invalid_state", f"unexpected work.phase {phase!r} for {namespace}/{slug}")

        if stage_label and call_topic_label:
            subtitle = f"{stage_label} · {call_topic_label}"
        elif stage_label:
            subtitle = stage_label
        elif call_topic_label:
            subtitle = call_topic_label
        else:
            subtitle = "Account" if namespace == "accounts" else "Project"

        clauses = [c for c in (call_pill, email_pill, resume_pill) if c]
        plain_line = f"{name} — {subtitle} — " + "; ".join(clauses) if clauses else f"{name} — {subtitle}"

        result.append({
            "namespace": namespace, "slug": slug, "name": name, "stage": ctx.get("stage"),
            "subtitle": subtitle, "call_pill": call_pill, "email_pill": email_pill,
            "resume_pill": resume_pill, "plain_line": plain_line,
        })
    return result


# ── classified_events validation (materialize only) ────────────────────────────────────────────
def validate_classified_event(item, index):
    if not isinstance(item, dict):
        raise Refusal("invalid_classified_event", f"classified_events[{index}] is not an object")
    event_id, source = item.get("event_id"), item.get("source")
    external_ref, occurred_at = item.get("external_ref"), item.get("occurred_at")
    namespace, slug = item.get("namespace"), item.get("slug")
    display_name = item.get("display_name")
    if not isinstance(event_id, str) or not event_id:
        raise Refusal("invalid_classified_event", f"classified_events[{index}].event_id must be a non-empty string")
    if source not in ("call", "email"):
        raise Refusal("invalid_classified_event", f"classified_events[{index}].source must be 'call' or 'email'")
    if not event_id.startswith(source + ":"):
        raise Refusal("invalid_classified_event",
                       f"classified_events[{index}].event_id must be '{source}:<external_ref>'")
    if external_ref is not None and not isinstance(external_ref, str):
        raise Refusal("invalid_classified_event", f"classified_events[{index}].external_ref must be a string or null")
    parse_offset_datetime(occurred_at, f"classified_events[{index}].occurred_at", "invalid_classified_event")
    if namespace not in ("accounts", "projects"):
        raise Refusal("invalid_classified_event", f"classified_events[{index}].namespace must be 'accounts' or 'projects'")
    if not isinstance(slug, str) or not SAFE_SLUG_RE.match(slug):
        raise Refusal("invalid_classified_event", f"classified_events[{index}].slug is not a valid kebab-case slug")
    if not isinstance(display_name, str) or not display_name.strip():
        raise Refusal("invalid_classified_event",
                       f"classified_events[{index}].display_name is required and must be non-empty "
                       f"(never persisted — see notes/tech-spec-deterministic-pre-slate.md Semantic Handoff)")
    call_type, subject = item.get("call_type"), item.get("subject")
    if call_type is not None and not isinstance(call_type, str):
        raise Refusal("invalid_classified_event", f"classified_events[{index}].call_type must be a string")
    if subject is not None and not isinstance(subject, str):
        raise Refusal("invalid_classified_event", f"classified_events[{index}].subject must be a string")
    return {
        "event_id": event_id, "source": source, "external_ref": external_ref, "occurred_at": occurred_at,
        "namespace": namespace, "slug": slug, "display_name": display_name.strip(),
        "call_type": call_type, "subject": subject,
    }


# ── targeted YAML surgery: replace ONLY the top-level `events` value ───────────────────────────
def _yaml_flow_scalar(value):
    return json.dumps(value, ensure_ascii=False)


def dump_event_flow(ev):
    parts = [
        "event_id: " + _yaml_flow_scalar(ev["event_id"]),
        "source: " + ev["source"],
        "external_ref: " + (_yaml_flow_scalar(ev["external_ref"]) if ev["external_ref"] is not None else "null"),
        "occurred_at: " + ev["occurred_at"],
        "namespace: " + ev["namespace"],
        "slug: " + ev["slug"],
        "evidence_status: " + ev["evidence_status"],
        "processing_status: " + ev["processing_status"],
    ]
    if ev.get("call_type") is not None:
        parts.append("call_type: " + _yaml_flow_scalar(ev["call_type"]))
    if ev.get("subject") is not None:
        parts.append("subject: " + _yaml_flow_scalar(ev["subject"]))
    return "{ " + ", ".join(parts) + " }"


def render_events_value(events):
    """The VALUE only (no 'events:' key, no leading/trailing newline) — for replacing an existing
    value's mark range. replace_events_in_yaml adds whichever boundary whitespace the surrounding
    bytes do not already supply; baking a fixed convention in here is exactly what broke the
    flow-style `events: []` case (its end_mark, unlike a block sequence's, does not consume the
    newline that follows it — see the module's compose()-mark investigation)."""
    if not events:
        return "[]"
    lines = []
    for i, ev in enumerate(events):
        prefix = "" if i == 0 else "  "
        lines.append(prefix + "- " + dump_event_flow(ev))
    return "\n".join(lines)


def render_events_block(events):
    """The full 'events: ...' block including the key — for inserting where none existed."""
    if not events:
        return "events: []\n"
    lines = ["events:"]
    for ev in events:
        lines.append("  - " + dump_event_flow(ev))
    return "\n".join(lines) + "\n"


def replace_events_in_yaml(raw_text, new_events):
    root = yaml.compose(raw_text)
    if root is None or not isinstance(root, yaml.MappingNode):
        raise Refusal("invalid_state", "state file top level is not a YAML mapping")
    events_key_node, events_value_node, work_key_node = None, None, None
    for key_node, value_node in root.value:
        if key_node.value == "events":
            events_key_node, events_value_node = key_node, value_node
        elif key_node.value == "work":
            work_key_node = key_node
    if events_value_node is not None:
        start = events_value_node.start_mark.index
        end = events_value_node.end_mark.index
        value_text = render_events_value(new_events)
        # Leading edge: a block sequence cannot sit inline after "events:" the way flow "[]" can
        # (e.g. a freshly scaffolded "events: []"). Detect "already on its own line" by checking
        # for a newline between the KEY's end and the OLD value's start, and prefix one if absent
        # — "events: \n  - {...}" is valid YAML; a bare space before the newline is harmless.
        gap_before = raw_text[events_key_node.end_mark.index:start]
        if new_events and "\n" not in gap_before:
            value_text = "\n  " + value_text
        # Trailing edge: only supply a newline if one is not already sitting right after the old
        # value. A block sequence's last item consumes it (end_mark lands at the next key); an
        # inline flow value like "[]" does not (end_mark lands right after "]", newline still
        # ahead) — verified empirically against PyYAML 6.0.3's compose() marks for both shapes.
        if not (end < len(raw_text) and raw_text[end] == "\n"):
            value_text += "\n"
        return raw_text[:start] + value_text + raw_text[end:]
    block = render_events_block(new_events)
    if work_key_node is not None:
        pos = work_key_node.start_mark.index
        return raw_text[:pos] + block + raw_text[pos:]
    sep = "" if raw_text == "" or raw_text.endswith("\n") else "\n"
    return raw_text + sep + block


def atomic_write_state(state_path, new_text):
    dir_ = os.path.dirname(state_path)
    try:
        orig_mode = stat.S_IMODE(os.stat(state_path).st_mode)
    except OSError as exc:
        raise Refusal("write_failed", f"cannot stat {state_path}: {exc}")

    try:
        fd, tmp_path = tempfile.mkstemp(prefix=".prepare-slate-", dir=dir_)
    except OSError as exc:
        raise Refusal("write_failed", f"cannot create temp file in {dir_}: {exc}")

    try:
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
                fh.write(new_text)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError as exc:
            raise Refusal("write_failed", f"temp write failed: {exc}")

        try:
            os.chmod(tmp_path, orig_mode)
        except OSError as exc:
            raise Refusal("write_failed", f"could not preserve file mode: {exc}")

        try:
            os.replace(tmp_path, state_path)
        except OSError as exc:
            raise Refusal("replace_failed", f"atomic replace failed — original bytes untouched: {exc}")

        try:
            dir_fd = os.open(dir_, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as exc:
            # The rename itself already landed; only the directory-entry durability fsync is
            # uncertain. Per contract this still STOPS rather than claims success — never fallback.
            raise Refusal("replace_failed", f"directory fsync failed after replace — outcome uncertain: {exc}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ── command: materialize --apply ────────────────────────────────────────────────────────────────
def cmd_materialize(payload, apply_flag):
    check_contract_version(payload)
    if not apply_flag:
        raise Refusal("bad_request", "materialize requires --apply")

    workspace_root = require_str(payload, "workspace_root")
    expected_sha = require_str(payload, "state_sha256")
    sampled_at_raw = require_str(payload, "sampled_at")
    classified_in = payload.get("classified_events")
    if not isinstance(classified_in, list):
        raise Refusal("bad_request", "'classified_events' must be a list")

    workspace_root_abs, state_path = resolve_state_path(workspace_root)
    raw_text, raw_bytes = read_text_and_bytes(state_path)
    actual_sha = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha != expected_sha:
        raise Refusal("stale_state", "state_sha256 does not match the current state file — nothing written",
                       state_sha256_before=actual_sha)

    state = parse_and_validate_state(raw_text)
    sampled_at = parse_offset_datetime(sampled_at_raw, "sampled_at", "invalid_window")

    seen_ids, events_in = set(), []
    for i, item in enumerate(classified_in):
        ev = validate_classified_event(item, i)
        if ev["event_id"] in seen_ids:
            raise Refusal("duplicate_event_id", f"duplicate classified_events[{i}].event_id {ev['event_id']!r}")
        seen_ids.add(ev["event_id"])
        events_in.append(ev)

    updated_events = list(state["events"])
    index_by_id = {e["event_id"]: idx for idx, e in enumerate(updated_events)}
    display_names = {}

    for ev in events_in:
        display_names[(ev["namespace"], ev["slug"])] = ev["display_name"]
        idx = index_by_id.get(ev["event_id"])
        if idx is not None:
            merged = dict(updated_events[idx])
            merged["occurred_at"] = ev["occurred_at"]
            if ev.get("call_type") is not None:
                merged["call_type"] = ev["call_type"]
            if ev.get("subject") is not None:
                merged["subject"] = ev["subject"]
            updated_events[idx] = merged
        else:
            record = {
                "event_id": ev["event_id"], "source": ev["source"], "external_ref": ev["external_ref"],
                "occurred_at": ev["occurred_at"], "namespace": ev["namespace"], "slug": ev["slug"],
                "evidence_status": "present" if ev["source"] == "email" else "unknown",
                "processing_status": "pending",
            }
            if ev.get("call_type") is not None:
                record["call_type"] = ev["call_type"]
            if ev.get("subject") is not None:
                record["subject"] = ev["subject"]
            updated_events.append(record)
            index_by_id[ev["event_id"]] = len(updated_events) - 1

    new_text = replace_events_in_yaml(raw_text, updated_events)
    new_bytes = new_text.encode("utf-8")
    new_sha = hashlib.sha256(new_bytes).hexdigest()

    atomic_write_state(state_path, new_text)

    tz = load_zoneinfo(state["timezone"])
    today = sampled_at.astimezone(tz).date()
    context_in = payload.get("context") or {}
    slate_view = build_slate_view(updated_events, state["work"], context_in, display_names, tz, today)

    return {
        "state_sha256_before": actual_sha,
        "state_sha256_after": new_sha,
        "slate_view": slate_view,
    }


# ── command: render ─────────────────────────────────────────────────────────────────────────────
# Deterministic substitution into the pinned layout, nothing more. Every display string arrives on
# the slate_view materialize already derived and passes through VERBATIM — this command re-derives
# no label, re-orders no row, and writes nothing. The template file stays the layout authority: its
# own markup lines are the format strings below, so a template edit reaches the fragment without a
# code edit here.

SLATE_TEMPLATE_RELPATH = ("..", "templates", "slate-widget.html")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
PILL_SPAN_RE = re.compile(r"^(\s*<span\b[^>]*>).*(</span>)\s*$")
TABLER_ICON_RE = re.compile(r'<i class="ti ti-([a-z0-9-]+)"[^>]*></i>')
UNFALLBACKED_VAR_RE = re.compile(r"var\(--([a-z0-9-]+)\)")
VALID_SURFACES = ("cowork", "chatgpt")

# Icon circle, keyed by the row's signal mix — the template header's icon key, mechanically.
ICON_KEY = {
    (True, False): ("video", "purple", "#EEEDFE", "#3C3489"),
    (False, True): ("mail", "teal", "#E1F5EE", "#085041"),
    (True, True): ("users", "coral", "#FAECE7", "#712B13"),
}

# ChatGPT projection (runtime/chatgpt/tool-bindings.md "Fragment projection"): the five theme
# variables that ship no hex fallback, and the text stand-ins for the one external asset family.
NEUTRAL_THEME_VALUES = {
    "surface-2": "#FFFFFF", "border": "#E3E3E3", "text-muted": "#6B7280",
    "border-strong": "#9CA3AF", "border-accent": "#6366F1",
}
ICON_TEXT_EQUIVALENTS = {"video": "🎥", "mail": "✉️", "users": "👥"}
VISUALLY_HIDDEN_STYLE = ("position:absolute; width:1px; height:1px; padding:0; margin:-1px; "
                         "overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0;")

NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
                6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def escape_display(value):
    """Element-text escaping, plus the template's own `&middot;` spelling for the separator the
    slate_view strings carry as a literal `·`. quote=False deliberately: these land between tags,
    never inside an attribute, and escaping apostrophes there would diverge from the pinned capture."""
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                 .replace("·", "&middot;"))


def flatten_for_send_prompt(name):
    """The template's punctuation-flattening rule: inside sendPrompt('…') the name must stay valid
    JS and typable by hand — `&` becomes the word, quotes and backslashes go, whitespace collapses."""
    flat = name.replace("&", " and ")
    flat = re.sub(r"[\"'\\]", "", flat)
    flat = re.sub(r"\s+", " ", flat).strip()
    return flat.replace("<", "&lt;").replace(">", "&gt;")


def resolve_slate_template_path():
    """Relative to this file — the same shape in the corpus (runtime/helpers → runtime/templates)
    and in a built bundle (resources/helpers → resources/templates)."""
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), *SLATE_TEMPLATE_RELPATH))


def read_slate_template():
    path = resolve_slate_template_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise Unavailable(f"slate template unreadable at {path}: {exc}")


def parse_slate_template(text):
    """Strip the header/inline comments and split what remains into its structural parts. The
    comments ARE the contract prose, so they never reach the fragment; the markup lines beneath
    them are what gets filled."""
    lines = [ln for ln in HTML_COMMENT_RE.sub("", text).split("\n") if ln.strip()]
    if len(lines) < 6 or lines[0].strip() != "<div>" or "sr-only" not in lines[1]:
        raise Refusal("bad_template", "slate template does not open with <div> + h2.sr-only")
    if "display:grid" not in lines[2] or lines[-1].strip() != "</div>" or lines[-2].strip() != "</div>":
        raise Refusal("bad_template", "slate template does not wrap a grid div in a root div")
    card_lines = lines[3:-2]
    if not any("{{NAME}}" in ln for ln in card_lines):
        raise Refusal("bad_template", "slate template card block carries no {{NAME}} placeholder")
    return {"root_open": lines[0], "sr_heading": lines[1], "grid_open": lines[2],
            "card_lines": card_lines, "grid_close": lines[-2], "root_close": lines[-1]}


def validate_slate_row(row, index):
    if not isinstance(row, dict):
        raise Refusal("bad_row", f"slate_view[{index}] is not an object")
    for field in ("name", "subtitle"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise Refusal("bad_row", f"slate_view[{index}].{field} is required and must be non-empty")
    for field in ("call_pill", "email_pill", "resume_pill"):
        value = row.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise Refusal("bad_row", f"slate_view[{index}].{field} must be a non-empty string or null")
    if not row.get("call_pill") and not row.get("email_pill"):
        raise Refusal("bad_row",
                       f"slate_view[{index}] carries neither a call nor an email signal — "
                       f"a row with no pending signal produces no card")
    return row


def sr_description(rows):
    """Names the surface and the row count for screen readers. The noun follows the rows' own
    namespaces; the count is spelled out through ten, as the pinned capture does."""
    n = len(rows)
    namespaces = {row.get("namespace") for row in rows}
    if namespaces == {"accounts"}:
        noun = "account" if n == 1 else "accounts"
    elif namespaces == {"projects"}:
        noun = "project" if n == 1 else "projects"
    else:
        noun = "item" if n == 1 else "items"
    count = NUMBER_WORDS.get(n, str(n))
    return (f"Unbound run slate: {count} {noun} with new call or email activity since the last "
            f"run, each shown as a card you can select")


def render_card(card_lines, row):
    icon, color, bg_hex, fg_hex = ICON_KEY[(bool(row.get("call_pill")), bool(row.get("email_pill")))]
    pill_by_marker = (("{{CALL_RECENCY}}", row.get("call_pill")),
                      ("{{EMAIL_COUNT}}", row.get("email_pill")),
                      ("{{RESUME_LABEL}}", row.get("resume_pill")))
    out = []
    for line in card_lines:
        pill = next((p for marker, p in pill_by_marker if marker in line), False)
        if pill is not False:                      # a pill line: included only when the row has it
            if not pill:
                continue
            match = PILL_SPAN_RE.match(line)
            if not match:
                raise Refusal("bad_template", f"pill line is not a single <span> element: {line.strip()!r}")
            out.append(match.group(1) + escape_display(pill) + match.group(2))
            continue
        out.append(line
                   .replace("{{ICON_COLOR}}", color).replace("{{ICON_BG_HEX}}", bg_hex)
                   .replace("{{ICON_FG_HEX}}", fg_hex).replace("{{ICON}}", icon)
                   .replace("{{NAME_FLATTENED}}", flatten_for_send_prompt(row["name"]))
                   .replace("{{NAME}}", escape_display(row["name"]))
                   .replace("{{SUBTITLE}}", escape_display(row["subtitle"])))
    return out


def project_for_chatgpt(fragment):
    """The four fragment-projection rules from runtime/chatgpt/tool-bindings.md, applied
    mechanically to the cowork assembly. Their prose there stays the normative contract."""
    lines = [ln for ln in fragment.split("\n") if "onclick=" not in ln]      # 1. strip controls
    out = "\n".join(lines)

    def substitute_icon(match):                                             # 2. no external asset
        return ('<span style="font-size:18px;" aria-hidden="true">'
                f'{ICON_TEXT_EQUIVALENTS.get(match.group(1), "•")}</span>')

    out = TABLER_ICON_RE.sub(substitute_icon, out)

    def substitute_var(match):                                              # 3. neutral theme values
        name = match.group(1)
        if name not in NEUTRAL_THEME_VALUES:
            raise Refusal("bad_template",
                           f"theme variable --{name} carries no hex fallback and no neutral value")
        return NEUTRAL_THEME_VALUES[name]

    out = UNFALLBACKED_VAR_RE.sub(substitute_var, out)
    return out.replace('class="sr-only"', f'style="{VISUALLY_HIDDEN_STYLE}"')  # 4. resolve sr-only


def cmd_render(payload):
    check_contract_version(payload)
    surface = payload.get("surface")
    if surface not in VALID_SURFACES:
        raise Refusal("bad_request", f"'surface' must be one of {VALID_SURFACES}, got {surface!r}")
    slate_view = payload.get("slate_view")
    if not isinstance(slate_view, list):
        raise Refusal("bad_request", "'slate_view' must be a list")

    rows = [validate_slate_row(row, i) for i, row in enumerate(slate_view)]
    if not rows:
        return {"fragment": None}   # empty slate renders no widget — the call site's chat line stands

    template = parse_slate_template(read_slate_template())
    lines = [template["root_open"],
             template["sr_heading"].replace("{{SR_DESCRIPTION}}", escape_display(sr_description(rows))),
             template["grid_open"]]
    for row in rows:                                        # slate_view order, never re-ranked
        lines.extend(render_card(template["card_lines"], row))
    lines.extend([template["grid_close"], template["root_close"]])

    fragment = "\n".join(lines)
    if surface == "chatgpt":
        fragment = project_for_chatgpt(fragment)
    return {"fragment": fragment}


# ── CLI wiring ──────────────────────────────────────────────────────────────────────────────────
def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def run_command(command, apply_flag):
    try:
        raw_stdin = sys.stdin.read()
    except Exception as exc:
        emit({"contract_version": CONTRACT_VERSION, "command": command, "status": "error",
              "error": "bad_request", "message": f"cannot read stdin: {exc}"})
        return 1
    try:
        payload = json.loads(raw_stdin)
    except json.JSONDecodeError as exc:
        emit({"contract_version": CONTRACT_VERSION, "command": command, "status": "error",
              "error": "bad_request", "message": f"stdin is not valid JSON: {exc}"})
        return 1

    try:
        if command == "prepare":
            result = cmd_prepare(payload)
        elif command == "normalize":
            result = cmd_normalize(payload)
        elif command == "materialize":
            result = cmd_materialize(payload, apply_flag)
        elif command == "render":
            result = cmd_render(payload)
        else:  # pragma: no cover - argparse closes this off
            raise Refusal("bad_request", f"unknown command {command!r}")
    except Unavailable as exc:
        print(f"[prepare-slate] unavailable: {exc.reason}", file=sys.stderr)
        emit({"contract_version": CONTRACT_VERSION, "command": command, "status": "unavailable",
              "reason": str(exc.reason)})
        return 2
    except Refusal as exc:
        print(f"[prepare-slate] {command} refused ({exc.code}): {exc.message}", file=sys.stderr)
        obj = {"contract_version": CONTRACT_VERSION, "command": command, "status": "error",
               "error": exc.code, "message": exc.message}
        obj.update(exc.fields)
        emit(obj)
        return 1
    except Exception as exc:  # last-resort — the caller always gets parseable JSON, never a traceback
        print(f"[prepare-slate] {command} internal error: {exc}", file=sys.stderr)
        emit({"contract_version": CONTRACT_VERSION, "command": command, "status": "error",
              "error": "internal_error", "message": str(exc)})
        return 1

    out = {"contract_version": CONTRACT_VERSION, "command": command, "status": "ok"}
    out.update(result)
    emit(out)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="prepare-slate.py")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("normalize")
    materialize_parser = sub.add_parser("materialize")
    materialize_parser.add_argument("--apply", action="store_true")
    sub.add_parser("render")
    args = parser.parse_args(argv)
    return run_command(args.command, getattr(args, "apply", False))


if __name__ == "__main__":
    _cmd = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    # `render` touches no YAML at all (pure json + string work over a slate_view the caller already
    # holds), so a PyYAML-less environment does not make it unavailable — every other command reads
    # or writes state/run-state.yaml and does.
    if yaml is None and _cmd != "render":
        print("[prepare-slate] unavailable: PyYAML is not installed", file=sys.stderr)
        emit({"contract_version": CONTRACT_VERSION, "command": _cmd, "status": "unavailable",
              "reason": "pyyaml_missing"})
        sys.exit(2)
    sys.exit(main())
