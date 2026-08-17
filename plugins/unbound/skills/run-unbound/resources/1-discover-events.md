---
name: discover-events
description: Lists events from configured sources (calendar + unanswered email threads) that occurred since the last Unbound run, delegates window filtering and exact-domain routing to the bundled deterministic helper, attaches a suggested account slug via fuzzy match when the helper's exact match misses, and surfaces ambiguous events for the rep instead of silently dropping them from either source. Invoked internally by run-unbound as the discovery step.
tier: all
---
# discover-events

Discovery step of an Unbound run (composition slot 1). Given the `prepare` snapshot from
run-unbound's final pre-query beat, list events from configured sources (calendar + unanswered
email threads), hand the raw results to the helper's `normalize` command (or its fallback) for
window filtering, ID derivation and exact-domain routing, then apply the two judgment calls that
stay with this skill: a fuzzy name/domain match when the exact match missed, and per-source
ambiguity classification biased toward listing. Return an in-memory source-discriminated event
working set, carried forward to `classify-work`. This skill only discovers and returns — it does
not fetch evidence, classify, upsert the event records, advance `last_run`, mint a new slug, or
perform any external write.

## Reads

- The `prepare` snapshot from run-unbound's final pre-query beat — `last_run`, `discovery_until`,
  `domain_routes`, `domain_collisions`, and `context` (per-slug name/stakeholder/summary, for the
  fuzzy match below) — required, passed by the orchestrator; do not re-derive any of it and do not
  re-read `state/run-state.yaml` or any `context.md`. Also carried: whether run-unbound is using the
  helper or its loaded fallback — never re-probe.
- Logical capability `calendar.list_events_since(ts) -> [event{ title, start, end, attendees, ref }]`, resolved from `resources/bindings/pre-slate-discovery.md` — read scope only; never a concrete tool name.
- Logical capability `email.list_unanswered_threads(ts) -> [thread{ thread_ref, subject, participants[], last_message_at (ISO 8601 with offset), latest_external_message_body }]`, same fragment — read scope only; never a concrete tool name. The hard pre-filter (INBOX-only; skip `CATEGORY_PROMOTIONS` / `CATEGORY_SOCIAL` / `CATEGORY_UPDATES` / `SPAM` / `TRASH`; only threads where the rep has not replied last) lives in the binding's `q` parameter, not in this skill — the skill never re-applies it.
- `resources/helpers/prepare-slate.py`'s `normalize` command, or `resources/pre-slate-fallback.md`'s `normalize` section — whichever run-unbound already resolved.

## Procedure

**1 — List candidates from both sources, concurrently.** Issue BOTH
`calendar.list_events_since(last_run)` and `email.list_unanswered_threads(last_run)` **together
(parallel where supported)** — neither call takes any input from the other's result, so neither
waits on the other and the step costs about one list call rather than two.

If **either** binding fails or errors, stop and surface the failure, naming whichever source
failed — never silently fall back to the surviving one (that would hide a whole class of events
from the rep without their knowledge). Issuing the two calls together changes **when** they are
sent, never **how** a failure is handled: a result already returned by the surviving source is
discarded rather than used alone.

**2 — Normalize.** Invoke `normalize` — the bundled helper's command, or `pre-slate-fallback.md`'s
section, matching whichever run-unbound already resolved — with the `prepare` snapshot plus both
raw candidate arrays. It enforces `(last_run, discovery_until]`, preserves every timestamp and
reference string verbatim, derives each `event_id` as `"<source>:<external_ref>"`, and attaches
`suggested_slug` only where the sender's domain hits `domain_routes` uniquely. It returns the
unified event shape (`event_id, source, external_ref, occurred_at, title, participants,
suggested_slug?, latest_message_body?`), a `collisions` list (email domains it recognized but could
not route to one slug), and a `faults` list (candidates missing their durable reference). Take its
event list as-is — do not re-filter, re-derive an ID, or re-apply the domain match.

A `faults` entry is surfaced to the rep by index and source — the durable-reference invariant below
— never silently dropped and never given a synthesized `event_id`.

**3 — Fuzzy name match (fallback path, this skill's own judgment).** For each email event
`normalize` returned **without** a `suggested_slug` (a domain miss, or one of its `collisions`),
fuzzy-match the sender's domain stem (e.g. `persgroep` parsed from `persgroep.com`) and display name
against the `prepare` snapshot's `context` — each known slug's `name`, `stakeholder_names`, and
`summary`. A confident match (a clear lexical/identity overlap, not a one-token coincidence) →
attach `suggested_slug`. An inconclusive match → leave it absent; `classify-work` decides downstream
(rep judges). Calendar events never receive a `suggested_slug` — `normalize` does not produce one for
them, and this step does not either. This skill **never mints a new slug at discovery time** — slug
creation remains `classify-work` / rep-driven; the hint is confidence only, and the rep can still
override it downstream.

**4 — Assign `call_type` (this skill's own judgment).** For each surviving call, assign a
best-effort label (`demo`, `discovery`, `exec-readout`, and similar) from its title and
participants when the signal supports one; leave it `unknown` rather than guess. `normalize` does
not produce this field — it is not a closed transform.

**5 — Classify ambiguity per source (bias toward listing).** A false-exclude is the dangerous
failure — when in doubt, list it. Never silently drop a candidate `normalize` returned.

For **calendar candidates**, exclude only confident non-calls: attendee-less focus blocks,
personal holds with no external attendees, all-day events, obvious self-reminders. List
everything else. Mark each surviving event `ambiguous: false` (confident call) or
`ambiguous: true` (kept for rep judgment).

For **email candidates**, the hard pre-filter (INBOX-only; skip promotions/social/updates/spam/
trash; rep-not-last) was already applied at the binding layer — this skill does **not** re-apply
those. Apply a single soft-judgment layer that answers *"does this thread require a follow-up
or response?"*: a clear human ask, question, business signal, or unanswered prospect/customer
inquiry → `ambiguous: false`. Borderline cases (transactional patterns that leaked through the
hard filter, unclear asks, an unknown sender with no prospect match, anything where the
follow-up signal is uncertain) → `ambiguous: true`. An email candidate with no `suggested_slug`
(neither the exact nor the fuzzy match confirmed a known account) is at minimum `ambiguous: true`
so the rep disambiguates downstream — never auto-confident on an unknown sender.

**6 — Return the augmented in-memory working set.** Each surviving event from `normalize`, carrying
its added `ambiguous` (Step 5), and — for calls — `call_type` (Step 4), and — where Step 3 found one
— `suggested_slug`. The set is in-memory only, not persisted to its own file: `build-slate` owns the
upsert of these events into `state/run-state.yaml`.

**7 — Zero events.** If no events survive from EITHER source (zero from `normalize`, or every
surviving calendar candidate excluded by the confident-non-call rule), return an empty list and a
single clean "nothing new since `<last_run>`" message. Do not error, retry, fall back to one
source, or advance `last_run`.

## Writes

None. This skill performs no write of any kind — no file, no external action, no event upsert,
no `last_run` advance, no new account slug, no Gmail label/reply/draft. Re-running leaves the
working tree (and the rep's Gmail inbox) unchanged.

## Failure rules

- Either source binding fails or errors → stop and surface; never silently fall back to the
  other source (would hide events from the rep).
- Never silently drop an in-window event during ambiguity classification — anything not
  confidently excluded is listed (ambiguous if necessary).
- A `normalize` fault (a candidate missing its durable reference) is surfaced by index and source —
  never silently dropped, never given a synthesized `event_id`.
- Never re-apply the email hard pre-filter inside the skill body — it lives in the binding's
  `q` parameter (ADR-6 / Pattern 4 — runtime details stay out of skill prose).
- Never mint a new slug at discovery — `classify-work` / rep-driven creation handles unknown
  senders; the email event surfaces with `ambiguous: true` and no `suggested_slug` instead.
- Never re-filter, re-derive an `event_id`, or re-run the exact-domain match after `normalize` —
  take its output as-is; only the fuzzy match and `call_type` are this skill's own to add.
- Never name a concrete MCP tool inside this skill — the Reads fragment binds both (ADR-6).
