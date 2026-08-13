---
name: build-slate
description: Upserts each discovered call and email as a durable event record in run-state.yaml and presents the annotated, unranked slate — one card per account, derived by grouping that account's pending events. Annotates call and email signals when both are present for the same slug. Invoked internally by run-unbound before selection.
tier: all
---
# build-slate

Presentation + persistence step of an Unbound run (composition slot 3). Given the classified
source-discriminated `discovered_events` working set, upsert each event as its own durable record
into `events` in `state/run-state.yaml` keyed by `event_id`, then present the annotated, unranked
slate — one card per `(namespace, slug)`, **derived** by grouping that item's
`processing_status: pending` events. Annotation surfaces both call and email signals when both are
present for the same slug, only the call signal when call-only, and only the email signal when
email-only. The event upsert is the only write; a new event is always `processing_status: pending`
here. This skill only upserts events and presents the slate — it does not select, single-thread, or
advance `last_run`.

## Reads

- `state/run-state.yaml` — existing `events` (coverage baseline; the schema doc-comment in that file is authoritative), `last_run`/`timezone` (read-only for recency annotation), and the optional `work` list of open cycle records (read-only — the resume pill's only input; this skill never writes, creates, advances or removes one).
- `accounts/<slug>/context.md` and `projects/<slug>/context.md` — read-only referential integrity check (optional). Optional in the load-bearing sense now: `bootstrap-context` runs post-selection, so a first-encounter item has **no** context.md when the slate is built. That is a normal state, not a gap — an absent file simply yields no stage, and the existing absent-field rule takes it from there.
- In-memory classified events from `classify-work` — source-discriminated. Each item carries `{ event_id, source: "call"|"email", namespace, slug, external_ref, occurred_at, title, participants, call_type? (call-only), latest_message_body? (email-only), suggested_slug?, ... }`. Accept as-is; use `event_id`/`external_ref`/`namespace`/`slug` verbatim. No transcript field arrives here — nothing is fetched before selection.
- Logical capability `render.slate(slate_view)` — interactive slate card grid or plain annotated lines; never a concrete tool name.

## Procedure

**1 — Read the existing events.** Open `state/run-state.yaml`; read the current `events` list as
the coverage baseline. Every existing `processing_status: pending` event must survive, and every
`processed` one must stay processed. An absent or empty `events` list is a clean starting point,
not an error. Read other top-level keys read-only; do not reshape them.

**2 — Upsert each classified event, keyed by `event_id`.** One discovered call or email = one
durable event record. Never collapse two events onto one record, and never key a record by
`(namespace, slug)` — the account is a *grouping* of events (Step 4), never a stored row:

- Match by `event_id` (`"<source>:<external_ref>"`, minted by `discover-events` and carried
  verbatim). Nothing else is the key.
- Re-discovered (`event_id` already in `events`) → update `occurred_at` and the
  optional display annotation in place; **preserve `processing_status` verbatim** — a processed
  event re-discovered in a later run stays processed — and **preserve a resolved `evidence_status`
  verbatim** too, per the derivation table below.
- New → append with `processing_status: pending`.

The event record's authoritative schema is the doc-comment at the head of `state/run-state.yaml`;
populate it from the classified event:

```
{ event_id,           # verbatim from the classified event — the upsert key
  source,             # call | email, verbatim
  external_ref,       # verbatim — the durable re-fetch pointer evidence recovery depends on
  occurred_at,        # ISO 8601 with offset, verbatim (never reformatted or truncated)
  namespace, slug,    # verbatim from classify-work
  evidence_status,    # present | missing | unknown — see the derivation below
  processing_status,  # pending on a new record; preserved verbatim on re-discovery
  call_type?,         # call-only display annotation, verbatim
  subject? }          # email-only display annotation, verbatim from the thread subject
```

**`evidence_status` derivation.** Nothing is fetched before selection, so this skill writes what
the run actually knows at slate time and no more:

| Case | Value | Why |
| --- | --- | --- |
| `source: email`, any record | `present` | The latest external message body arrives inline with the discovery list call — no fetch, so the evidence is already in hand. |
| `source: call`, **new** record | `unknown` | No transcript has been fetched and none will be before selection. `unknown` says *we have not looked yet*, which is the truth. |
| `source: call`, **re-discovered** record already carrying `present` or `missing` | **preserved verbatim** | A run that resolved this call did look. Overwriting a resolved answer with `unknown` would discard a known fact and assert a false one. |

`unknown` is the honest third value, not a placeholder: it is never fabricated, never inverted to
hide a gap, and never rendered as either of the other two. A record can sit at `unknown`
indefinitely — that is correct, and it is exactly what "we have not looked yet" means. Its event
stays pending, stays on the slate, and stays selectable; the answer arrives after selection, where
`fetch-transcript` resolves it in memory for that cycle.

Idempotent by construction: repeated runs over the same source objects mint the same `event_id`s
and converge with no duplicates.

**3 — Honor the coverage guarantee (at event granularity).** Every prior `pending` event stays in
`events`, unchanged except for the in-place annotation refresh above — never removed, never
rewritten to `processed` here. An event this run did not re-discover is left exactly as it was:
its stored `external_ref` is what makes it recoverable later, so an untouched event is a fully
working event, not a stale one. Keep events with annotation gaps annotated rather than dropping
them. No event is ever deleted by this skill, and the only `processing_status` write it makes is
`pending` on a brand-new record; flipping an event to `processed` is `work-account`'s, on the
specific `event_id`s that were actually worked.

**4 — Derive the slate and present it.** The slate is **computed here, never stored**: group the
full `events` list — every `processing_status: pending` record, whichever run discovered it — by
`(namespace, slug)`, and emit **one card per group**. Same slug + different namespace = distinct
groups. A group's signals are read off its members:

- **Call signal** — present when the group has any `source: call` member. Its date is the most
  recent such member's `occurred_at` (formatted YYYY-MM-DD in the run's `timezone` for the recency
  rule below); its topic is that same member's `call_type`; its evidence flag is that same member's
  `evidence_status`.
- **Email signal** — present when the group has any `source: email` member. `<N>` is the count of
  `source: email` members in the group — a literal count of pending email events, not a count of
  this run's discoveries; its date is the most recent such member's `occurred_at`.
- A group with **no** pending members does not exist and produces no card: that is exactly how a
  fully-worked account leaves the slate, and how one new pending event brings it straight back.

Assemble those groups as `slate_view` (per group: name, namespace, stage-if-known, call signal,
email signal, evidence flag, plus the display strings derived below) and present it via the logical
`render.slate(slate_view)` capability — never a concrete tool name (ADR-6). Interactive runtimes
render the pinned slate card grid (one card per group: signal-keyed icon, name, muted subtitle, one
pill per signal, a full-width "Work <Name>" selection button); non-UI or unknown-capability runtimes
fall back to the plain annotated line per item below. Same cards, signals, and words on both
surfaces (ADR-1) — the card contract is unchanged by the derivation; selection stays rep-owned on
both — never auto-select. An **empty slate renders nothing** — no widget and no lines (the run-level
"nothing new since `<last_run>`" line is `run-unbound`'s).

**Label derivation** — applied here, once, as `slate_view` is assembled; both surfaces consume
the same derived strings, and nothing is re-derived at render time:

*Rule 1 — Humanize a token.* Given a token (a `kebab-case` or `snake_case` identifier): replace
every `-` and `_` with a single space; collapse runs of whitespace to one space and trim;
uppercase the first character only, **leaving every other character exactly as it was** — no
title casing, no dictionary, no acronym expansion. A token that is empty, absent, or the literal
`unknown` humanizes to an **absent** label — never the string `"Unknown"`. Worked examples:

| Token | Humanized |
| --- | --- |
| `discovery-and-install-scope` | `Discovery and install scope` |
| `pre-proposal-discovery` | `Pre proposal discovery` |
| `discovery-and-evaluation-scope` | `Discovery and evaluation scope` |
| `exec-readout` | `Exec readout` |
| `technical-validation` | `Technical validation` |
| `negotiation` | `Negotiation` |
| `demo` | `Demo` |
| `unknown` | *(absent — the subtitle omits the topic)* |

`pre-proposal-discovery` → `Pre proposal discovery` is explicitly accepted: that hyphen is
intra-word, not a separator, and no rule can tell those apart without a dictionary. The fix, if
ever wanted, is editorial (re-author the token) — do **not** add a dictionary.

*Rule 2 — Recency label.* Given a date `D` (`YYYY-MM-DD`, already in the run's `timezone`) and
today's date in that same `timezone`, let `d` = whole calendar days from `D` to today:

| Condition | Label | Example |
| --- | --- | --- |
| `d == 0` | `today` | `Call · today` |
| `d == 1` | `yesterday` | `Call · yesterday` |
| `2 ≤ d ≤ 29` | `<d> days ago` | `Call · 6 days ago` |
| `d ≥ 30` | `<Mon> <DD>` | `Call · Jun 22` |
| `d < 0` (future-dated) | `<Mon> <DD>` | `Call · Aug 14` |

Calendar days, not elapsed 24-hour periods — a call at 23:00 yesterday reads `yesterday`, not
`today`. An absent date omits the recency clause entirely — no separator, no dangling `·`; it is
never guessed and never rendered as `unknown`.

*Rule 3 — Card composition.* Per group:

- **Subtitle** (the muted line under the name): both stage and call topic known →
  `<Humanized stage> · <Humanized topic>`; only one known → that one alone; neither known → the
  humanized namespace singular (`Account` / `Project`) — the line is never empty, so card height
  stays uniform across the grid.
- **Call pill** (present only when the group carries a call signal): `Call · <recency>`, with the
  recording clause decided by that call event's `evidence_status`:

  | `evidence_status` | Call pill |
  | --- | --- |
  | `present` | `Call · <recency>` |
  | `missing` | `Call · <recency> · no recording` — the `" · no recording"` clause **verbatim** |
  | `unknown` | `Call · <recency>` — clause omitted, no placeholder, no `·` left dangling |

  On `missing` this is Pattern 2's honest surfacing, inside the pill, never outside, never omitted
  when the flag says `missing`. On `unknown` the clause is omitted for the same reason: the run has
  not looked, so it has nothing to report, and the existing absent-field rule applies unchanged — an
  absent fact yields an absent label, never a guessed one. Because a newly-discovered call is
  `unknown`, a missing recording now surfaces **after** selection, where evidence recovery reports
  it, rather than on the card. The clause still fires for a call a previous run resolved.
- **Email pill** (present only when the group carries an email signal):
  `<N> unanswered email<s> · <recency>` (`<s>` = `s` when `N > 1`, empty when `N == 1`).
- **Resume pill** (present only when the group's `(namespace, slug)` carries an open record in
  `work`): `Resume · plan ready` at `phase: planned`, `Resume · triaged` at `triaged`,
  `Resume · awaiting close-out` at `executed`. Those three texts verbatim — there is no fourth text
  and no fallback label for an unexpected phase; a phase outside that set is a state defect to
  surface, never a rendering decision.
- Both-signal groups show both pills, **call pill first**. The resume pill, when present, renders
  **last** — after every signal pill — because it reports where a cycle stopped rather than what
  came in, so the signals stay the first thing the rep reads.

The plain annotated line per item (the fallback surface) carries the same words in the same
order (*Rule 4 — parity*, ADR-1), laid out linearly as
`<Name> — <subtitle> — <clauses joined by "; ">` — `—` separates the three segments, `·`
separates within a segment, and `;` joins the clauses of the final segment: every signal clause
first, in the same order as the pills, then the resume clause when the group has an open record.
The resume clause reports state rather than a signal, and this surface has no colour to say so —
its position last is the only thing that marks it, which is why the clause order and the pill
order are the same order. When no subtitle is derivable, the middle segment and its surrounding
`—` are omitted entirely:

- Call-only signal for this group → `"<Name> — <subtitle> — Call · <recency>"` (append
  `" · no recording"` where applicable) — e.g., `"Brightwater Media Group — Technical validation ·
  Discovery and install scope — Call · 6 days ago"`.
- Email-only signal for this group → `"<Name> — <subtitle> — <N> unanswered email<s> · <recency>"`
  — e.g., `"Calla & Vale — Negotiation — 1 unanswered email · 8 days ago"`; no subtitle
  derivable → `"Acme — 1 unanswered email · today"`.
- Both signals present in the group → both signal clauses joined by `"; "`, call clause first —
  e.g., `"Goldspire Resorts & Gaming — Demo · Exec readout — Call · 7 days ago · no recording;
  1 unanswered email · 8 days ago"`.
- An open record for this group appends its resume clause **last**, after the signal clauses and
  joined the same way — e.g., `"Acme — Negotiation — Call · 6 days ago; 1 unanswered email · 8 days
  ago; Resume · triaged"`, and on a single-signal group `"Calla & Vale — Negotiation — 1 unanswered
  email · 8 days ago; Resume · awaiting close-out"`.

Do not auto-rank, score, or label a "top pick" — the rep decides. Present a complete, unranked
view so the rep can trust nothing slipped.

**5 — Hand off.** Stop after presenting. Do not select, advance `last_run`, or mark processed.

## Writes

- `state/run-state.yaml` — `events` upsert only (append a new record, or refresh an existing one's annotation in place). Never advance `last_run`, never set `processing_status: processed`, never delete an event, never create/modify context.md.

## Failure rules

- Never remove or silently drop a pending event; keep events with gaps annotated. Deletion is not a
  path this skill has — an event leaves the slate only by being flipped to `processed`.
- Never key a record by `(namespace, slug)` or write a per-account status flag: the account row is
  derived at Step 4 and stored nowhere. A stored per-account flag is precisely what let a
  previously-worked account mask its own new activity.
- Never overwrite `processing_status` on re-discovery — a processed event stays processed, and its
  slug reappears on the slate only through a *different*, still-pending event.
- Never advance `last_run`; never set `processing_status: processed`; never create/modify context.md.
- Never write, create, advance or remove a `work` record. This skill reads that list to label a card
  and does nothing else with it; starting, advancing and clearing a cycle are `work-account`'s, at
  its own beats. A slate that renders a resume pill has changed no state by rendering it.
- Never auto-rank the slate; never fabricate `call_type`, `subject`, `evidence_status`, or an event
  count. `<N>` is a literal count of the group's pending `source: email` events, and every date is
  derived verbatim from a member's `occurred_at` — never invented.
- Never rewrite an `external_ref` or an `occurred_at`; both are carried verbatim, and a rewritten
  ref silently breaks a later run's evidence recovery.
- Label derivation is render-time only: derived display strings live in `slate_view` and are never written back to `events` **or** to `work` — `call_type` and `occurred_at` stay verbatim at rest, and the resume pill is a label derived from a record's `phase` at assembly time, never a value stored onto one.
- An absent field yields an absent label, never a guessed or placeholder one — an `unknown` token humanizes to absent, never the string `"Unknown"`; an absent date omits the recency clause, never a dangling `·`.
- Never render `evidence_status: unknown` as either `present` or `missing`. It is a third state, not a synonym: rendering it as `present` claims a recording nobody looked for, rendering it as `missing` claims one is absent when nobody knows. Both are the fabrication Pattern 2 exists to prevent; the pill simply omits its clause.
- Never downgrade a resolved `evidence_status` to `unknown` on re-discovery, and never write `unknown` onto an email record — an email's body arrives inline, so its evidence is known at discovery.
- Never treat an absent `context.md` as an error or a reason to drop a card: a first-encounter item has none until `bootstrap-context` runs after selection, and its stage is simply absent.
