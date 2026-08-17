---
name: build-slate
description: Invokes the bundled helper's materialize --apply (or its fallback) to upsert each discovered call and email as a durable event record in run-state.yaml and derive the annotated, unranked slate — one card per account, grouping that account's pending events — then renders the result unchanged. Invoked internally by run-unbound before selection.
tier: all
---
# build-slate

Presentation + persistence step of an Unbound run (composition slot 3). Given the classified
source-discriminated `discovered_events` working set, hand it to the helper's `materialize --apply`
command (or its fallback) to upsert each event as its own durable record into `events` in
`state/run-state.yaml` keyed by `event_id` and derive `slate_view`, then render the annotated,
unranked slate unchanged. This skill only invokes materialization and presents the result — it does
not decide evidence status, group events, derive labels, select, single-thread, or advance
`last_run`; every one of those is `materialize`'s contract (full rules in
`notes/tech-spec-deterministic-pre-slate.md` and, for the equivalent prose, `pre-slate-fallback.md`).

## Reads

- In-memory classified events from `classify-work` — source-discriminated, each carrying `{ event_id, source: "call"|"email", namespace, slug, external_ref, occurred_at, title, display_name, call_type? (call-only), latest_message_body? (email-only), suggested_slug?, ambiguous, ... }`. Accept as-is; use `event_id`/`external_ref`/`namespace`/`slug`/`display_name` verbatim.
- The `prepare` snapshot from run-unbound's final pre-query beat — `context` (passed straight through to `materialize`) and, on the helper path, `state_sha256` (the write precondition) — required, passed by the orchestrator; do not re-derive either by reading `state/run-state.yaml` or any `context.md` directly.
- `resources/helpers/prepare-slate.py`'s `materialize --apply` and `render` commands, or `resources/pre-slate-fallback.md`'s `materialize` and `render` sections — whichever run-unbound already resolved.
- Logical capability `render.slate(slate_view)`, resolved from `resources/bindings/pre-slate-slate.md` — interactive slate card grid or plain annotated lines; never a concrete tool name.

## Procedure

**1 — Materialize.** Construct `classified_events` from `classify-work`'s output — `event_id,
source, external_ref, occurred_at, namespace, slug, display_name`, plus the one source-specific
display annotation (`call_type` for a call, or the email's `title` carried across as `subject`); no
other field crosses into this payload. Invoke `materialize --apply` — the bundled helper's command,
or `pre-slate-fallback.md`'s `materialize` section, matching whichever run-unbound already resolved
— with that array, the `prepare` snapshot's `context`, and (helper path only) its `state_sha256` as
the write precondition. It matches by `event_id`, preserves `processing_status` and a resolved
`evidence_status` verbatim on rediscovery, deletes nothing, derives `slate_view` fresh, and
atomically replaces only the top-level `events` value in `state/run-state.yaml` — this skill touches
no other byte of that file, directly or otherwise.

- **Success** → take the returned `slate_view` as-is; proceed to Step 2.
- **`stale_state`** (helper path only — the file changed since `prepare`'s hash was taken) → stop
  and surface; never retry with a fresh `prepare`, never fall back — this is a genuine state race to
  report, not an availability problem.
- **`invalid_classified_event`** (a missing `display_name`, a duplicate `event_id`, a malformed
  field) → stop and surface; this is a defect in this run's own classified batch, never a reason to
  fall back.
- **A write or replace failure** → stop and surface; the original file is untouched on every
  pre-replace failure, and an uncertain replace outcome stops rather than guesses that it landed.

**2 — Render.** Pass `slate_view` to `render.slate(slate_view)` **unchanged** — never a concrete
tool name (ADR-6), never re-derived, re-sorted, re-labeled, or filtered before rendering. On a
confirmed interactive surface the fragment comes from `render` — the bundled helper's command, or
`pre-slate-fallback.md`'s `render` section, matching whichever run-unbound resolved — and is handed
on unchanged; hand-assemble no card on the helper path. It returns the pinned slate card grid (one
card per group: signal-keyed icon, name, muted subtitle, one pill per signal, a full-width
"Work `<Name>`" selection button); non-UI or unknown-capability runtimes skip `render` and fall back
to each group's `plain_line` verbatim. Same words on both surfaces (ADR-1) — `materialize` derives
every display string, so nothing is re-derived at render time. An **empty `slate_view` renders nothing** — no widget and no lines (the
run-level "nothing new since `<last_run>`" line is `run-unbound`'s). Selection stays rep-owned on
both surfaces — never auto-rank, auto-select, or label a "top pick."

**3 — Hand off.** Stop after presenting. Do not select, advance `last_run`, or mark processed.

## Writes

- `state/run-state.yaml` — `events` upsert only, performed by `materialize --apply` (or its
  fallback's `materialize` section) on this skill's invocation; this skill never mutates the file
  directly, and neither path ever advances `last_run`, sets `processing_status: processed`, deletes
  an event, or creates/modifies a `context.md`.

## Failure rules

- A `materialize` refusal (`stale_state`, `invalid_classified_event`, a write/replace failure) always
  stops the run — never treat a refusal as unavailability, and never fall back on one; the identical
  fault would reproduce under the fallback's prose.
- Never modify, re-rank, re-sort, re-label, or filter `slate_view` before rendering — pass through
  exactly what `materialize` returned, and the fragment exactly as `render` returned it.
- Only `render`'s **unavailable** result licenses the fallback's `render` section; a refusal stops.
- Never auto-rank, auto-select, or label a "top pick" — the rep decides; present a complete,
  unranked view so the rep can trust nothing slipped.
- Never construct `classified_events` with any field beyond `event_id, source, external_ref,
  occurred_at, namespace, slug, display_name, call_type|subject` — extra fields do not belong in the
  persisted record, and `title` never crosses into it under that name.
- An empty `slate_view` renders nothing on its own — no widget, no lines, no placeholder card.
