---
name: discover-events
description: Lists events from configured sources (calendar + unanswered email threads) that occurred since the last Unbound run, compared in the run's timezone, attaches a suggested account slug to email events whose sender confidently matches a known prospect/customer, and surfaces ambiguous events for the rep instead of silently dropping them from either source. Invoked internally by run-unbound as the discovery step.
tier: all
---
# discover-events

Discovery step of an Unbound run (composition slot 1). Given required `last_run`, `timezone`, and
`discovery_until` values passed by the orchestrator, list events from configured sources (calendar +
unanswered email threads) inside the discovery window, classify ambiguity per source with bias
toward listing, attach a `suggested_slug` to email events whose sender confidently matches a
known account, and surface ambiguous events for the rep to judge. Return an in-memory
source-discriminated event working set — each item carrying the durable `event_id` and
`external_ref` the run-state event record is keyed and re-fetched by — carried forward to
`classify-work`. This skill only discovers and returns — it does not fetch
evidence, classify, upsert the event records, advance `last_run`, mint a new slug, or perform
any external write.

## Reads

- `last_run` (ISO 8601 with offset), `timezone` (IANA), and `discovery_until` (resolved ISO 8601 with offset) — all required and passed by the orchestrator; do not re-read `state/run-state.yaml`.
- Logical capability `calendar.list_events_since(ts) -> [event{ title, start, end, attendees, ref }]` — read scope only; never a concrete tool name.
- Logical capability `email.list_unanswered_threads(ts) -> [thread{ thread_ref, subject, participants[], last_message_at (ISO 8601 with offset), latest_external_message_body }]` — read scope only; never a concrete tool name. The hard pre-filter (INBOX-only; skip `CATEGORY_PROMOTIONS` / `CATEGORY_SOCIAL` / `CATEGORY_UPDATES` / `SPAM` / `TRASH`; only threads where the rep has not replied last) lives in the binding's `q` parameter (`runtime/tool-bindings.md`), not in this skill — the skill never re-applies it.
- Optional `accounts/<slug>/context.md` frontmatter (per known account) — `domains:` (optional rep-authored list of email-domain strings), `name`, `stakeholders[].name`, and the `## Summary` body. Read in a **single best-effort pass over every known account, once per run**, to build the prospect-routing index the matching step queries — one read per account for the whole run, never one per account per email candidate. Absence of any field = no signal for that slug (never an error).

## Procedure

**1 — List candidates from both sources, concurrently.** Issue BOTH
`calendar.list_events_since(last_run)` and `email.list_unanswered_threads(last_run)` **together
(parallel where supported)** — neither call takes any input from the other's result, so neither
waits on the other and the step costs about one list call rather than two. Before issuing either
call, validate `last_run`, `timezone`, and `discovery_until`, including that the resolved interval
has `discovery_until > last_run`. If any value is missing or unparseable, or the interval is
invalid, stop and tell the rep — never invent values, default the timezone, or query a partial
window. Never parse `scan_window` here (the orchestrator already resolved the fixed cutoff).

If **either** binding fails or errors, stop and surface the failure, naming whichever source
failed — never silently fall back to the surviving one (that would hide a whole class of events
from the rep without their knowledge). Issuing the two calls together changes **when** they are
sent, never **how** a failure is handled: a failure on either side stops the run on exactly the
terms it would have if the calls had been sent one after the other, and a result already returned
by the surviving source is discarded rather than used alone.

**2 — Apply the discovery window (in-skill date math, in `timezone`).** The window is always
`(last_run, discovery_until]` — strictly after `last_run` and at/before the required fixed cutoff.
For each candidate, its `occurred_at` is the calendar
`event.start` (calendar candidates) OR the email `last_message_at` (email candidates). Apply the
same comparison to BOTH sources uniformly:

1. Interpret `occurred_at`, `last_run`, and `discovery_until` in the run's `timezone`
   (matters at day boundaries — not UTC, not server local).
2. Keep only if `occurred_at` is strictly after `last_run`.
3. Keep only if `occurred_at` is at or before `discovery_until`.
4. Preserve `occurred_at` verbatim as full ISO 8601 with offset — do not reformat or truncate.

A post-cutoff candidate is a normal exclusion, not an error and not a rep-facing warning; because
the committed watermark is this same cutoff, the candidate remains eligible for the next window.

**3 — Match email candidates to known accounts (prospect/customer matching).** Build the routing
index **once**, then match every in-window email candidate against it.

**Build the routing index before the matching loop.** In a single pass over the known accounts,
read each `accounts/<slug>/context.md`'s frontmatter and `## Summary` — and nothing more of the
file; the Activity Log body contributes nothing to the index — exactly once, issuing the
per-account reads as **one batch (parallel where supported)**: each path resolves from the account
listing alone, never from another read's content, so none waits on another and the pass costs
about one read rather than one per account. Fold what they carry into two in-memory maps:

- `domain → slug` — every entry of that account's `domains:` list, lowercased for comparison.
  This is the deterministic path (a) queries.
- `slug → { name, stakeholder names, Summary }` — the frontmatter `name`, the
  `stakeholders[].name` entries, and the `## Summary` body. This is the fuzzy fallback (b)
  queries.

The index is constant for the run — the accounts on disk do not change while the run is in
flight — so it is built once, before the loop, and never rebuilt per candidate. An account
carrying no `domains:`, no `stakeholders`, or no `## Summary` contributes nothing for that field
and is otherwise indexed normally: absence of any field is no signal for that slug, never an
error, and never a reason to stop the pass. Batching moves **when** the account reads are issued,
never what the pass guarantees: the index is not complete, and the matching loop does not begin,
until every account's read has landed or reported absent.

Then, for each in-window email candidate, run this algorithm in order and stop at the first
confident match:

a. **Domain match (preferred — deterministic).** Parse the external sender's email and extract
   the domain (the substring after `@`, lowercased for comparison). On a hit in the index's
   `domain → slug` map, attach `suggested_slug: <slug>` to the candidate and stop.
b. **Fuzzy name match (fallback — best-effort).** If no domain match, fuzzy-match the sender's
   domain stem (e.g. `persgroep` parsed from `persgroep.com`) AND the sender display name
   against each indexed slug's `name`, its stakeholder names, and its `Summary`. A confident
   match (a clear lexical/identity overlap, not a one-token coincidence) → attach
   `suggested_slug: <slug>` and stop. An inconclusive match → do not attach.
c. **No match.** Leave `suggested_slug` absent. The candidate's downstream routing will be
   decided by `classify-work` (rep judges).

Matching semantics are unchanged by the index: the domain path still precedes the fuzzy path,
the first confident match still wins, and an inconclusive match still attaches nothing. Only
**when** the account files are read moves — one read per account per run instead of one per
account per candidate.

This skill **never mints a new slug at discovery time** — slug creation remains
`classify-work` / rep-driven. The `suggested_slug` is a confident hint only; the rep can still
override downstream.

**4 — Classify ambiguity per source (bias toward listing).** A false-exclude is the dangerous
failure — when in doubt, list it. Never silently drop a candidate from either source.

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
(prospect match did not confirm a known account) is at minimum `ambiguous: true` so the rep
disambiguates downstream — never auto-confident on an unknown sender.

**5 — Build and return the unified in-memory working set.** For each surviving event from
either source, emit the source-discriminated unified shape:

```
{ event_id,                           # "<source>:<external_ref>" — derived here, see below
  source: "call" | "email",
  external_ref,                       # verbatim: calendar event ref OR email thread_ref
  occurred_at,                        # ISO 8601 with offset, verbatim from event.start or last_message_at
  title,                              # calendar title OR email subject (verbatim)
  participants: [{ name?, email? }],  # calendar attendees OR thread participants (verbatim)
  ambiguous,                          # true | false
  suggested_slug?,                    # email-only; present on confident prospect match
  call_type?,                         # call-only; best-effort label, "unknown" when unsure
  latest_message_body? }              # email-only; verbatim from the email binding
```

Calendar items use the unified keys (`occurred_at` not `start`; `participants` not `attendees`;
`external_ref` not `call_ref`). `external_ref` is the **durable re-fetch pointer** — the one field
that lets a later run recover this event's evidence after `last_run` has advanced past it — so it
is carried verbatim from the source and never normalized, shortened, or re-derived.

`event_id` is the string `"<source>:<external_ref>"` (e.g. `call:calendar-event-123`,
`email:thr_acme_20260718`) — deterministic and stable, so the same source object discovered again
in a later run mints the **same** key and updates its record in place instead of duplicating it.
Derive it here, once, and carry it unchanged downstream; a source object with no `external_ref` is
a source-binding fault, surfaced per the Failure rules, never a synthesized key.

Carry every preserved field verbatim — correlation to transcripts (calls) and routing/grounding
(emails) are validated downstream, not here. The set is in-memory only, not persisted to its own
file: `build-slate` owns the upsert of these events into `state/run-state.yaml`.

**6 — Zero events.** If no events survive from EITHER source (zero in window, or every
candidate excluded by the confident-non-call rule for calendar), return an empty list and a
single clean "nothing new since `<last_run>`" message. Do not error, retry, fall back to one
source, or advance `last_run`.

## Writes

None. This skill performs no write of any kind — no file, no external action, no event upsert,
no `last_run` advance, no new account slug, no Gmail label/reply/draft. Re-running leaves the
working tree (and the rep's Gmail inbox) unchanged.

## Failure rules

- Missing/unparseable `last_run`, `timezone`, or `discovery_until`, or
  `discovery_until <= last_run` → stop before either query and surface; never invent or default.
- Either source binding fails or errors → stop and surface; never silently fall back to the
  other source (would hide events from the rep).
- Never silently drop an in-window event during ambiguity classification — anything not
  confidently excluded is listed (ambiguous if necessary). Post-cutoff candidates are outside the
  current window and defer normally.
- Never re-apply the email hard pre-filter inside the skill body — it lives in the binding's
  `q` parameter (ADR-6 / Pattern 4 — runtime details stay out of skill prose).
- Never mint a new slug at discovery — `classify-work` / rep-driven creation handles unknown
  senders; the email event surfaces with `ambiguous: true` and no `suggested_slug` instead.
- Never reformat or truncate `occurred_at` (or any `last_message_at` / `event.start`); carry
  verbatim ISO 8601 with offset.
- Never reformat, truncate, or invent an `external_ref` — it is the durable re-fetch pointer, and a
  rewritten one silently breaks a later run's evidence recovery. A source object arriving with no
  ref is surfaced as a source-binding fault; never mint a placeholder `event_id` around it.
- Never parse `scan_window` (the orchestrator resolves `discovery_until` before invoking this
  skill).
- Never name a concrete MCP tool inside this skill — both logical capabilities resolve via
  `runtime/tool-bindings.md` (ADR-6).
