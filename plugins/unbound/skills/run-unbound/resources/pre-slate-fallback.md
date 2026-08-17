---
name: pre-slate-fallback
description: Lazy mechanical fallback for runtime/helpers/prepare-slate.py's prepare/normalize/materialize/render commands. Loaded only when the helper is unavailable — missing, no PyYAML 6.0.3, or an unsupported contract_version — never on the happy path. Contains the displaced deterministic transforms only; every ambiguity, fuzzy-identity, namespace, entity-resolution, ranking, selection, and rep-decision rule stays with discover-events.md, classify-work.md, and build-slate.md.
tier: all
contract_version: 1
---
# pre-slate-fallback

Version-matched prose equivalent of `prepare-slate.py` protocol `contract_version: 1`. The four
sections below match its four commands exactly — same inputs, same outputs, same failure
behavior — so a run under this fallback and a run under the helper are indistinguishable to the
rep. This file carries no semantic policy: every decision here is closed (same input always
produces the same output) and mechanical. Confident non-call exclusion, ambiguity labeling, fuzzy
name/domain matching, entity resolution, near-duplicate escalation, and every rep-facing question
stay exactly where they already are, in the owning skill.

## prepare

Read-only. Given `last_run`, `timezone`, optional `scan_window`, and one already-sampled
`sampled_at` (full ISO 8601 with an explicit offset that represents `timezone` at that instant):

1. Resolve the discovery window without sampling the clock again: absent/`now` → `discovery_until
   = sampled_at`; `<n>h`/`<n>d` → `discovery_until = min(last_run + <n>, sampled_at)`. Require
   `discovery_until > last_run`. An unparseable `scan_window`, a `sampled_at` with no explicit
   offset, or one that does not represent `timezone` at that instant — stop and surface; never
   guess or default.
2. Build known anchors: every `accounts/<slug>/` and `projects/<slug>/` directory on disk, plus
   every distinct `(namespace, slug)` pair already present in `events`. An item discovered but
   never selected has no directory yet — the `events` pair is what keeps its slug stable.
3. For each known anchor, read its `context.md` once: frontmatter `name`, `stage`,
   `stakeholders[].name`, `domains` (accounts only), and the `## Summary` body. An absent file
   yields an absent value for every field — never an error, never a guess.
4. Build the domain-routing index from every account's `domains:` list: lowercase each domain and
   strip exactly one trailing dot. A domain claimed by exactly one slug routes to it; a domain
   claimed by two or more slugs is a collision and routes to none of them.
5. Report the resolved window, the known anchors, the domain routes and collisions, and the
   per-slug display data. Write nothing.

## normalize

Pure. Given the `prepare` output above plus raw calendar candidates (`{ title, start, end,
attendees, ref }`) and raw email candidates (`{ thread_ref, subject, participants, last_message_at,
latest_external_message_body, sender_email }`):

1. For each candidate, in its own source's input order, compare its own timestamp
   (`start` for calendar, `last_message_at` for email) to the window: keep only strictly after
   `last_run` and at or before `discovery_until`. A candidate outside the window is a normal
   exclusion — it remains eligible next run, never an error.
2. Preserve `occurred_at`, the durable reference, titles, participants, and email body strings
   verbatim — never reformatted, truncated, or invented.
3. A retained candidate with no durable reference (`ref` / `thread_ref`) is a fault on that one
   item, surfaced by index and source — never silently dropped, never given a synthesized
   reference.
4. Emit `event_id = "<source>:<external_ref>"` for every retained candidate — the same key on
   rediscovery, always.
5. For each retained email, lowercase its sender's domain and strip one trailing dot. A unique
   domain-route hit attaches `suggested_slug`; a domain-collision hit attaches no suggestion and is
   reported as a collision diagnostic instead. Calendar candidates never receive a suggested slug.
6. Emit no `ambiguous` decision and no fuzzy name match — those stay with `discover-events.md`.
7. Preserve stable order in the output: every surviving calendar candidate first, in input order,
   then every surviving email candidate, in input order. Never rank by business signal.

## materialize

The one mutation, equivalent to `materialize --apply`. Given classified events — each carrying
`event_id`, `source`, `external_ref`, `occurred_at`, `namespace`, `slug`, a required in-memory
`display_name`, and the optional display annotation (`call_type` for calls, `subject` for emails)
— upsert them into `state/run-state.yaml`'s `events` list:

1. Match by `event_id` only. Rediscovered (already in `events`) → update `occurred_at` and the
   optional display annotation in place; preserve `processing_status` and `evidence_status`
   verbatim. New → append with `processing_status: pending` and `evidence_status: unknown` for a
   call, `present` for an email (an email's body arrives inline with discovery; a call's
   transcript is not fetched before selection, so "not looked yet" is the honest answer).
2. Never delete an event. Every `pending` event this batch does not touch stays exactly as it was;
   every `processed` event stays processed regardless of rediscovery. Duplicate `event_id` values
   within one batch are a refusal, not a last-write-wins merge.
3. Write only the top-level `events` value — every other key, comment, and byte in the file is
   untouched.
4. Derive `slate_view`, computed fresh and never stored: group every `processing_status: pending`
   event by `(namespace, slug)`; a group with no pending members does not exist and produces no
   card.
   - **Name.** The group's `display_name` from this batch if any member was touched; otherwise the
     slug's known `name` from context; otherwise the slug humanized (Rule 1) — never fabricated.
   - **Subtitle.** Humanized stage (account only) and humanized call topic, `<stage> ·
     <topic>` when both are known, whichever one alone when only one is, else the humanized
     namespace singular (`Account` / `Project`) — never empty.
   - **Call pill** (present only when the group has a call member, from its most recent one by
     `occurred_at`): `Call · <recency>`; append literal `" · no recording"` only when that call's
     `evidence_status` is `missing`. `unknown` gets no clause — the run has not looked yet, so it
     has nothing to report, exactly like `present`.
   - **Email pill** (present only when the group has an email member): `<N> unanswered
     email<s> · <recency>`, `<N>` the literal count of the group's email members, `<s>` = `s` when
     `N > 1`, recency from the most recent member's `occurred_at`.
   - **Resume pill** (present only when `(namespace, slug)` carries an open `work` record):
     `Resume · plan ready` at `planned`, `Resume · triaged` at `triaged`, `Resume · awaiting
     close-out` at `executed` — those three texts verbatim, nothing else. An unexpected phase is a
     state defect to surface, never a label to invent.
   - **Order.** Call pill first, then email pill, then resume pill last (it reports where a cycle
     stopped, not what came in).
   - **Plain line** (the non-interactive surface, same words as the pills):
     `<Name> — <subtitle> — <clauses joined by "; ">`, clauses in the same order as the pills;
     when no subtitle is derivable, that segment and its surrounding `—` are omitted entirely.
   - **Humanize a token** (Rule 1): replace every `-`/`_` with one space, collapse repeated
     whitespace, uppercase only the first character. Empty, absent, or the literal `unknown` →
     absent, never the string `"Unknown"`.
   - **Recency label** (Rule 2), given a date already in the run's `timezone` and today in the
     same zone, `d` = whole calendar days between them: `d == 0` → `today`; `d == 1` → `yesterday`;
     `2 ≤ d ≤ 29` → `<d> days ago`; `d ≥ 30` or `d < 0` (future-dated) → `<Mon> <D>`.
5. Persist the replacement so a reader never observes a partial write: same-directory temp file,
   preserve the original file's mode, flush, `fsync`, atomic rename, `fsync` the directory. Leave
   the original bytes untouched on every failure before the rename; if the rename's own durability
   is uncertain, stop and surface it — never guess that it landed.

## render

Read-only. Fill `resources/templates/slate-widget.html` from the `slate_view` rows in the given
order and project it per the bindings file's `render.slate` section — the hand assembly this beat
has always used. Reproduce every display string verbatim. An empty `slate_view` renders no widget.

## Failure rules

- Malformed state YAML, a duplicate key, a missing `last_run`/`timezone`, an unrecognized
  `evidence_status`/`processing_status`/`work.phase`, or the legacy `queue` key in place of
  `events` — stop before any write and surface the exact field.
- An unparseable `scan_window`, a `sampled_at` with no explicit offset, or a resolved
  `discovery_until` not strictly after `last_run` — stop before either source query.
- A materialize precondition mismatch (the state changed since the paired `prepare`) — stop and
  write nothing; never merge blind.
- A duplicate `event_id` inside one classified batch, or a classified event with no
  `display_name` — stop before any upsert.
- A write or rename failure, or an uncertain rename outcome — stop; leave prior bytes as they
  were; never enter a second fallback layer.
- Never invent a resume label, a display name, an `evidence_status`, or an event count — every
  value here is read off a record or a directory, never guessed.
