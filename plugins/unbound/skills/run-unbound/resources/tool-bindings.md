# Tool Bindings — ChatGPT Work (app-backed, pre-enumeration)

> **What this file is.** The single source of truth mapping each **logical capability** a skill may call to its
> resolution on **ChatGPT Work** — the third bindings authority beside `runtime/tool-bindings.md` (live, Claude Cowork)
> and `runtime/demo/tool-bindings.md` (fixture-backed demo). The build's `BINDINGS_SRC` seam selects it for the ChatGPT
> target (story 1.2, architecture D1 / ADR-CG2); together with `resources/tool-bindings.md` it is
> the entire runtime-specific surface of the port (ADR-6 / Pattern 4). Parity with the live contract is **derived,
> never asserted**: `lint.sh`'s `[target-parity]` check parses the capability names and signatures from this file and
> the live file and diffs them, so drift cannot hide behind a prose count (FR7, D4) — and neither file maintains one.

## The indirection rule (ADR-6)

- Skills under `skills/` reference **only logical capability names**; they never name a concrete tool. Concrete tool
  and connector names live only in the runtime's bindings file and its adapter.
- Porting = one bindings file + one adapter; nothing under `skills/` changes (Pattern 4). This file is that port's
  bindings half, authored **before** this runtime's tool inventory has been observed — which is why its resolution
  column is honest about that, rather than guessed.
- **Two states only: evidence-cited or UNRESOLVED.** A concrete resolution appears here only when a G0 gate or a live
  inventory observation supports it; every other row is marked **UNRESOLVED**, naming the gate that settles it. As of
  authoring, G0.1 and G0.2 have zero live observations, and this runtime's tool enumeration belongs to Epic 3's
  `connect-tools` binding test gate — so no concrete ChatGPT tool name appears anywhere below, and none may be added
  without its observation. Guessing a tool name into a row is the dated-documentation failure Epic 0 exists to prevent.

## Security posture (ADR-4)

Every **read** binding in this file is **read-scope only**, and external **writes are never implicit**: a write can
occur only through a capability this file *explicitly declares* with a write scope, and only when that capability's
own ADR-4 conditions hold. No
capability acquires a write scope by turning up in a runtime's tool list, and where none is declared or bound this
file requests and configures no write scope at all. In this runtime that bar is doubly unreachable today: no
external capability is positively confirmed bound, because no tool inventory has been enumerated.
The `render.*` / `review.collect` capabilities are **local render/capture surfaces, not external reads or writes**:
none introduces a new writer or write scope; the only writes they can lead to are the existing local authorities in
`skills/pipeline/work-account.md` — SET-STATUS, `capture-feedback`, and APPLY-EDIT — plus, for the setup-time
`review.collect` item kinds, the invoking skill's local file write (see `## review.collect`).

## Binding table — external reads

No external-read resolution exists yet for this runtime: G0.1's live observations (install and routing, dated
2026-08-11) include no tool inventory, which is enumerated only at Epic 3's `connect-tools` binding test gate, never
guessed here. Every row below is
therefore **UNRESOLVED** — the row records the capability's contract (shape, scope, degradation), and the resolution
cell records what evidence will fill it. Until a row is positively confirmed bound, the consuming skill treats the
capability as unavailable and takes the degradation path stated in its row.

| Logical capability | Scope | ChatGPT resolution (evidence-cited or UNRESOLVED — no third state) | Consumed by |
| --- | --- | --- | --- |
| `calendar.list_events_since(ts)` — `ts` is an ISO-8601 timestamp | read | **UNRESOLVED** — no calendar tool observed (enumeration is Epic 3's gate, G2). Degradation until bound: calendar discovery is unavailable, stated to the rep; discovery proceeds from the mail source alone when that binds first, or reports an empty discovery honestly. | `skills/pipeline/discover-events.md` |
| `calendar.availability(attendees, window)` — `attendees` = the rep + the named stakeholders; `window` = start/end ISO 8601, resolved in-skill; bounded to one query per draft. Honest degradation: unreadable attendee → rep-only slots phrased as offers to confirm; capability unavailable → the meeting ask carries no concrete times | read | **UNRESOLVED** — no free/busy surface observed. The degradation contract already covers the unbound state: the meeting ask carries no concrete times. Open-slot derivation stays in-skill (pure date math, run `timezone`) whenever a source binds. | `skills/handlers/draft-followup.md` (AVAILABILITY) |
| `transcript.get(call_ref)` — provider set **unresolved** in this runtime: provider rows are added one per observed connector at the Epic 3 gate, exactly as the live file's rows were | read | **UNRESOLVED** — no transcript connector observed. Until at least one provider row is confirmed bound, every call resolves `missing`; the consuming skill marks the call `transcript: missing`, surfaces it, never fabricates (Pattern 2). No provider name is recorded here before its observation. | `skills/pipeline/fetch-transcript.md` |
| `content.search(query)` — returns opaque `ref`s | read | **UNRESOLVED** — no content-store tool observed. Degradation until bound: MATCH-ASSET reports `none` and drafts proceed with no asset named; setup's asset intake proceeds from files shared in chat and the interview. | `skills/handlers/draft-followup.md`, `skills/setup-unbound.md` (asset intake) |
| `content.get(ref)` — resolves a `ref` to its content | read | **UNRESOLVED** — same evidence gap and gate as `content.search`; an unbound pair degrades together. | `skills/handlers/draft-followup.md`, `skills/setup-unbound.md` (asset intake + asset-link verification) |
| `web.fetch(url)` — resolves a public web page URL to its readable content | read | **UNRESOLVED** — this runtime may expose a browse surface, but none has been observed and none is assumed. **Optional-degraded:** capability unavailable ⇒ the website intake path is unavailable, stated to the user; setup proceeds via chat files, the asset index, or the interview. | `skills/setup-unbound.md` (website intake) |
| `email.list_unanswered_threads(ts)` — all thread fields carried verbatim: `thread_ref` (opaque correlation key), `subject`, `participants[]` (`{ name?, email? }`), `last_message_at` (ISO 8601 with offset; compared in the run's `timezone`, never reformatted); `latest_external_message_body` is inline | read | **UNRESOLVED** — no mail tool observed. The **hard pre-filter** (inbox-only; promotional, social, automated, spam and trashed traffic excluded; the rep has not replied last) is owned by this binding, not by the skill; its concrete query form is recorded at the same gate that binds the tool. Degradation until bound: mail discovery is unavailable, stated to the rep. | `skills/pipeline/discover-events.md` |
| `email.list_sent_threads(ts, limit)` — the rep's **own** outbound messages, read for voice extraction only. Each carries `message_ref` (opaque), `subject`, `recipients[]` (`{ name?, email? }`), `sent_at` (ISO 8601 with offset) and `body`; `limit` caps the read at the most recent N (default 25), and `ts` is its lower bound | read | **UNRESOLVED** — same mail-surface evidence gap. **Optional-degraded:** capability unavailable ⇒ the sent-mail voice path is unavailable, stated to the user; setup proceeds from the writing samples the rep provides and the voice interview. | `skills/setup-unbound.md` (voice intake) |
| `email.get_thread(thread_ref)` — get-by-ref: resolve ONE stored `thread_ref` to its thread, for evidence recovery on a later run. Same thread shape as the list capability; **no window, no search** — the ref is the whole query | read | **UNRESOLVED** — binds at the same gate as the mail list capability and rides the same read scope. A ref that no longer resolves returns `missing` — never a nearest-match thread, never a fabricated body (Pattern 2). | `skills/pipeline/fetch-transcript.md` (evidence recovery) |

> **Unresolved is a state, not a promise.** A row leaves UNRESOLVED in exactly one way: the Epic 3 `connect-tools`
> binding test gate observes the live inventory and records the concrete tool (or its confirmed absence) with one-line
> live-call evidence, the same discipline the live file's own test-gate notes follow. Absence is a first-class answer:
> a capability this runtime cannot serve keeps its degradation path permanently, stated rather than papered over.

## Binding table — render/capture surfaces

An inline render surface **was observed live in this runtime on 2026-08-12** (G1, story 3.1): the `visualize`
skill — an instruction set the agent reads, not a callable tool — rendered a written HTML fragment inline via the
write-then-reference protocol owned by `## Visualize protocol — write-then-reference` below. The rows below carry
that observation where it covers them; per the resolution rule below, a surface that cannot be session-confirmed
still resolves to its documented fallback — never assumed. The pinned template named in each
row is the layout authority on a confirmed surface; layout minutiae live in the template, never in prose.

| Logical capability | Scope | Interactive surface (pinned template) | Fallback | Consumed by |
| --- | --- | --- | --- | --- |
| `render.tasks(task_view)` | render, no capture | **BOUND (protocol)** — observed 2026-08-12 (G1, story 3.1): composed per `## Visualize protocol — write-then-reference` below; card stack, one card per task, pinned to `resources/templates/task-plan-widget.html` under that section's fragment-projection rules | plain Markdown checklist in chat | `skills/pipeline/work-account.md` (re-render after SET-STATUS / APPLY-EDIT), `skills/standalone/collect-tasks.md` (roundup) |
| `review.collect(checkpoint_view)` | render/capture (local verdicts only) | **Stays on the typed fallback** — evidence-cited 2026-08-12 (G1, story 3.1): the observed `visualize` surface runs client-side JS but no channel from a rendered fragment back into the conversation has been observed, and this capability's whole value **is** capture — a card stack whose controls capture nothing invites clicks that silently mean nothing. Flips only on a later G1 observation of such a channel, its grammar recorded from observation, never designed in advance | in-chat `accept \| edit \| reject` prompt per item | `skills/run-unbound.md` (Step 3.5 batch triage + Step 3.5 material-edit re-confirm + Step 5 close-out open questions + qualification gaps) |
| `render.slate(slate_view)` | render, no capture | **BOUND (protocol)** — observed 2026-08-12 (G1, story 3.1): composed per `## Visualize protocol — write-then-reference` below; card grid pinned to `resources/templates/slate-widget.html` under that section's fragment-projection rules; selection stays typed (the fallback's own rule) | plain annotated slate lines | `skills/pipeline/build-slate.md` Step 4 (via `run-unbound` Steps 2–3) |
| `render.email_draft(draft_view)` | render/capture (the draft's own verdict) | **BOUND (protocol) — display half only** — observed 2026-08-12 (G1, story 3.1): mail-client preview composed per `## Visualize protocol — write-then-reference` below, pinned to `resources/templates/email-draft-widget.html`; the verdict footer is stripped by projection and the three verdicts are typed in chat (see `## render.email_draft`) | cited filename + draft body in chat, with the same three verdicts invited in chat | `skills/run-unbound.md` (Step 5 combined output gate) |
| `render.crm_update(crm_view)` | render, no capture | **BOUND (protocol)** — observed 2026-08-12 (G1, story 3.1): composed per `## Visualize protocol — write-then-reference` below; informational CRM card pinned to `resources/templates/crm-update-widget.html` under that section's fragment-projection rules | plain in-chat "CRM Updates (simulated)" Markdown section | `skills/pipeline/write-crm.md` (APPLY) |
| `render.connections(connections_view)` | render, no capture | **BOUND (protocol)** — observed 2026-08-12 (G1, story 3.1): composed per `## Visualize protocol — write-then-reference` below; capability status board pinned to `resources/templates/connections-widget.html` under that section's fragment-projection rules | plain Markdown capability table + verdict line in chat | `skills/standalone/connect-tools.md` (both entries) |
| `render.setup_progress(progress_view)` | render, no capture | **BOUND (protocol)** — observed 2026-08-12 (G1, story 3.1): composed per `## Visualize protocol — write-then-reference` below; section checklist card pinned to `resources/templates/setup-progress-widget.html` under that section's fragment-projection rules | plain Markdown section-status list in chat | `skills/setup-unbound.md` (progress + resume + audit views) |
| `render.context_preview(preview_view)` | render, no capture | **BOUND (protocol)** — observed 2026-08-12 (G1, story 3.1): composed per `## Visualize protocol — write-then-reference` below; formatted artifact preview pinned to `resources/templates/context-preview-widget.html` under that section's fragment-projection rules | plain Markdown artifact section in chat | `skills/setup-unbound.md` (section-loop previews) |
| `render.source_intake(intake_view)` | render, no capture | **BOUND (protocol)** — observed 2026-08-12 (G1, story 3.1): composed per `## Visualize protocol — write-then-reference` below; source-catalog checklist card pinned to `resources/templates/source-intake-widget.html` under that section's fragment-projection rules | plain Markdown item-status list in chat | `skills/setup-unbound.md` (step-2 intake, re-rendered after each answer) |

## API contract — logical capability signatures (stable across runtimes)

Per `notes/architecture.md#API-Contracts`; the signatures are **runtime-invariant** — only the binding tables change
per runtime. `[target-parity]` parses this block and the live file's and fails on any missing, extra, or changed
signature; the comment tails are runtime commentary and are outside that comparison. Render view shapes live in their
capability sections below.

```
calendar.list_events_since(ts)  -> [event]               # read
calendar.availability(attendees, window) -> [open_slot]  # read; open_slot = { start, end } (ISO 8601 with offset, in the run's timezone); an attendee whose free/busy is unreadable is reported unreadable, never guessed
transcript.get(call_ref)        -> { text, provider } | missing  # read; provider set unresolved in this runtime — rows are added per observed connector, and until one is bound every call resolves `missing` => never silently drop (Pattern 2)
content.search(query)           -> [ref]                  # read
content.get(ref)                -> content                # read
web.fetch(url)                  -> page_content | unavailable  # read; optional-degraded — unavailable ⇒ website intake unavailable (stated), setup proceeds via files/assets/interview
email.list_unanswered_threads(ts) -> [thread]            # read; threads where the rep has not replied last
                                                          # thread = { thread_ref, subject, participants[],
                                                          #            last_message_at (ISO 8601 with offset),
                                                          #            latest_external_message_body }
email.list_sent_threads(ts, limit) -> [sent_message] | unavailable  # read; optional-degraded — the rep's own outbound mail, read at
                                                          # setup for voice extraction only, capped at the most recent `limit`
                                                          # (default 25); unavailable ⇒ sent-mail voice path unavailable (stated),
                                                          # setup proceeds from provided samples + the voice interview
                                                          # sent_message = { message_ref, subject, recipients[],
                                                          #                  sent_at (ISO 8601 with offset), body }
email.get_thread(thread_ref)    -> thread | missing       # read; get-by-ref, same thread shape, no window and no search — the
                                                          # email counterpart of transcript.get for evidence recovery; a ref that
                                                          # no longer resolves => missing (Pattern 2 — surfaced, never fabricated)
render.tasks(task_view)         -> interactive_checklist | markdown_checklist   # render, no capture
review.collect(checkpoint_view) -> verdicts                                     # render/capture; verdicts route to capture-feedback
render.slate(slate_view)        -> slate_cards | annotated_lines                 # render; interactive card grid, fallback = plain annotated slate lines
render.email_draft(draft_view)  -> { preview, item_verdict }                     # render/capture; interactive mail-client preview + verdict footer, fallback = cited filename + body in chat with the verdict invited in chat
render.crm_update(crm_view)     -> crm_card | markdown_block                     # render; informational CRM-update card, fallback = plain in-chat "CRM Updates (simulated)" Markdown section
render.connections(connections_view) -> connections_board | markdown_table       # render, no capture
render.setup_progress(progress_view) -> progress_card | markdown_list            # render, no capture
render.context_preview(preview_view) -> artifact_preview | markdown_section      # render, no capture
render.source_intake(intake_view)   -> intake_card | markdown_list               # render, no capture
```


## Resolution rule — all render capabilities

Interactive mode is used **only** on positive evidence from the live environment — **never assumption**. This
runtime's render surface is a skill, not a tool, so "present in the tool list" cannot be the test; the confirmation
that preserves the rule's intent has two levels, and both are required:

- **Corpus-level (once, at the gate).** A row may say **BOUND** only after a recorded live observation proves the
  full round-trip: fragment written, reference emitted, widget rendered inline. That is G1 evidence, owned by the
  story the adapter's gate ledger names; the 2026-08-12 observation satisfies its reference-syntax half.
- **Session-level (once per session, at the first render beat).** The probe: **locate and read the `visualize`
  skill's instructions in the live environment**. Readable instructions stating the write-then-reference procedure
  = confirmed; instructions absent, unreadable, or describing a different procedure = fallback.

When either level is unmet, resolve to the capability's documented fallback, which is a complete and honest run,
not a degraded demo of one.

**Resolve once per session, then reuse.** The session-level confirmation is performed **once**, at the session's
first render/capture beat, and its answer is reused at every later `render.*` and `review.collect` call site.
Caching the resolution never upgrades it: a surface that was absent or
could not be confirmed caches the **fallback**, and "could not confirm" never becomes an assumed rich UI at a later
beat. Both modes carry the same content — no field dropped or invented on either surface (ADR-1); an `inferred:`
evidence/basis marker renders as-is, never dressed as a citation. The operative widget mechanics for this runtime —
render procedure, fragment projection, failure handling — are owned by `## Visualize protocol — write-then-reference`
below: adapters ship in no bundle, so this file is the only viable owner of protocol prose a running agent must
execute.

## Visualize protocol — write-then-reference

The render path observed live 2026-08-12 (G1, story 3.1). This runtime's inline render surface is the `visualize`
**skill** — an instruction set the agent locates and reads, not a callable tool. On a session-confirmed surface
(resolution rule above), each bound `render.*` beat renders in three steps:

1. **Read** the `visualize` skill's instructions in the live environment. The session-level probe already did this
   once; those instructions are the syntax authority for everything below.
2. **Write** the HTML fragment to disk at the location the instructions specify (observed:
   `~/.codex/visualizations/YYYY/MM/DD/<uuid>/<name>.html`), instantiated from the row's pinned template under the
   fragment-projection rules below.
3. **Emit the content reference exactly as the instructions specify** — plain assistant text in the message, never
   a tool call and never a file write. This file records no reference syntax of its own: the live instructions own
   it, so a host-side syntax change degrades to fallback at the session probe instead of emitting a broken
   reference. The verbatim reference that proved the round-trip is gate evidence in the G1 story record, never the
   operative spec.

**Fragment projection.** The pinned templates are layout authorities the agent instantiates at render time, never
files handed to the surface verbatim. Projecting one into a `visualize` fragment:

- **Strip every `onclick` control.** The host function those handlers call does not exist here; where a control
  expressed a typed utterance, that utterance is invited in chat instead — the fallback grammar, unchanged.
- **Supply neutral inline values for the unfallbacked theme variables** (`--surface-2`, `--border`, `--text-muted`,
  `--border-strong`, `--border-accent`); the `--c-*` color pairs already carry hex fallbacks and stay as-is.
- **No external asset of any kind.** Replace Tabler icon elements with their visible text/emoji equivalent, or
  omit the icon circle entirely.
- **Resolve `sr-only`:** the class is undefined CSS here — replace it with an inline visually-hidden style.
- **Honor the live instructions' own fragment constraints**, whatever they state — they were read this session.

**Failure honesty.** A render that produces no inline widget at any beat resolves that beat to its documented
fallback and the run continues — never retry in a loop, never skip the beat.

## render.tasks

`task_view` = canonical tasks (`id`/`title`/`priority`/`type`/`status`/`evidence`), optionally grouped by item
`namespace/slug`. Presentation only: the cards carry **no checkbox and no buttons** — verdicts happen at the Step 3.5
`review.collect` triage; the card's evidence line shows the cited quote or the `inferred:` marker; the roundup
(`collect-tasks`) adds a status pill and groups cards under `namespace/slug` headers. `render.tasks` conveys nothing
back and introduces no writer — task status changes are explicit chat asks applied via SET-STATUS, the single status
write authority. Display labels are presentation-only (`not-done → "open"`, `done → "done"`, `deferred → "deferred"`;
Markdown fallback: `- [x]` done, `- [ ]` otherwise); the persisted enum `not-done | done | deferred` is never changed
by rendering.

## review.collect

`checkpoint_view = { items[], open_questions[], qualification_gaps?[] }`; each
`qualification_gap = { field, coach }`; each `item = { task_id, title, rationale, evidence, context?, kind:
"task" | "context_section" | "binding_change", body? }` — `context` is the task's typed execution-context block on
`kind: "task"` items. The produced email draft is **not** an item kind here: it carries its own verdict on its own
surface (see `## render.email_draft`). Returns `verdicts = { item_verdicts[], open_answers[],
qualification_answers?[] }`; `item_verdict = { task_id, verdict ∈ {accept|edit|reject}, note }`;
`open_answer = { question, answer }`; `qualification_answer = { field, answer }`.

**Call-site policy — batch or single-item, fixed per site.** `items[]` was always a list; which mode a site uses is
settled here, never chosen by the caller:

| Call site | Mode | `items[]` | `open_questions[]` | `qualification_gaps[]` |
| --- | --- | --- | --- | --- |
| `run-unbound` Step 3.5 — plan triage | **batch** | all retained tasks, in priority order | `[]` | `[]` |
| `run-unbound` Step 3.5 — material-edit re-confirm | single-item | the one re-shaped task | `[]` | `[]` |
| `run-unbound` Step 5 — close-out questions + qualification | no items | this run's list | `crm_update.qualification.gaps[]` or `[]` (one call when either list is non-empty; skip only when both are empty) |
| `setup-unbound` — `context_section` | single-item | one previewed section | `[]` | `[]` |
| `connect-tools` — `binding_change` | single-item | one proposed row edit | `[]` | `[]` |

A **batch** return simply carries N `item_verdict`s. **An omitted `task_id` in a batch return is an omitted verdict**
— silence stays per-task inside a batch, and nothing is written for a card the rep never touched. A batch of one is
still a batch; **zero retained tasks means no call at all** (never render an empty checkpoint). Verdict mapping:
Accept → `accept`; Reject → `reject`; a free-text edit → `edit` with the text captured **verbatim** as `note`. **No
answer for an item → no verdict for that item** (silence is not a verdict); hand-typed equivalents map identically;
ambiguous free text that cannot map to the enum → ask, never an out-of-enum write. Verdicts route through the
existing write authorities — no new writer: one `capture-feedback(namespace, slug, task_id, verdict, note)` line per
verdict to `state/feedback-log.jsonl`; a **task** `edit` is applied via work-account's APPLY-EDIT (an **output**
`edit` is applied by the artifact's own handler — see `## render.email_draft`); verdicts never touch task `status`
(SET-STATUS's domain). `open_questions[]` and `qualification_gaps[]` are **never widget-rendered** — they remain
in-chat free text; `open_answers[]` are echoed in chat and held in-session with nothing written for them, and each
non-empty `qualification_answer` routes through exactly one work-account `capture-qualification` invocation. The
checkpoint itself is write-free.

Setup-time item kinds (outside the run loop): `context_section` — one previewed context section, its `task_id` slot
carrying the section id (`process | messaging | assets | voice | state`); consumed by `skills/setup-unbound.md`.
`binding_change` — one proposed row edit to this file; consumed by `skills/standalone/connect-tools.md`. One item per
call, never batched, same `accept | edit | reject` enum. **Routing outside the run loop:** accept ⇒ the invoking
skill performs its local file write; edit ⇒ the note is applied to the draft/proposal and re-presented; reject ⇒ the
section is re-entered / the proposal dropped. **No `feedback-log.jsonl` line is written** — `capture-feedback`
remains exclusively the run loop's prioritization instrument.

## render.slate

`slate_view` = the annotated per-account groups `build-slate` Step 4 **derives** by grouping the run-state events
with `processing_status: pending` by `(namespace, slug)` (name, namespace, stage-if-known, call signal, email
signal, evidence flag, plus the display strings its label-derivation rules produce — subtitle and recency labels;
nothing is re-derived at render time). One card (or one annotated line, on the fallback) per group. Pure render;
selection stays rep-owned. Pill text rules: call pill `"Call · <recency>"`, appending `" · no recording"`
**verbatim** when that call event's `evidence_status` is `missing`, and appending **nothing** when it is `unknown` —
no clause, no placeholder, no dangling `·`; `unknown` is never rendered as `present` or as `missing`. Email pill
`"<N> unanswered email<s> · <recency>"`; both-signal groups show both pills, call pill first; an absent date omits
the recency clause entirely. The muted subtitle reads `<Humanized stage> · <Humanized topic>`, or whichever single
part is known, or the humanized namespace singular (`Account` / `Project`) when neither is. Selection is the rep's
turn — on the fallback surface the rep types the item's name; the match is case-insensitive and ambiguity → ask.
`render.slate` causes no write of any kind. An **empty slate renders no widget** (the existing "empty slate" chat
line stands); the `dropped` set is **never** widget-rendered (inspect-on-request stays chat-based).

## render.email_draft

`draft_view = { to[], subject, body, filename }`, read from the draft file `draft-followup` already wrote under the
item's `drafts/` — nothing is regenerated or altered at render time. **Render/capture:** the surface carries the
draft plus its verdict — Accept / Reject / free-text edit — and returns the draft's `item_verdict = { task_id,
verdict ∈ {accept|edit|reject}, note }`, where `task_id` is the draft's `source_task`. The draft and the decision on
it are **one surface**; no separate checkpoint card follows it. On the fallback the cited filename and draft body
appear in chat with the same three verdicts invited there. The boundary holds on every surface: nothing is sent,
queued, or renamed, and the draft is stated as `draft · not sent`. An **`edit` verdict is applied**, not merely
recorded: `draft-followup`'s `apply-draft-edit(namespace, slug, source_task, note)` rewrites the draft file — bounded
to `to[]`, `subject`, `body` — **first**, appends exactly one `edit` line via `capture-feedback` **only** on success,
and re-renders through this capability so a fresh verdict is collected. The cycle repeats until accept or abandon;
one log line per cycle, append-only, rep-bounded. Silence after a re-render writes nothing. This capability adds
**no** writer: the draft file is one `draft-followup` already owned. **On this runtime's bound surface the verdict
stays typed:** the fragment projection strips the verdict footer (no channel from a rendered fragment back into the
conversation has been observed — see the binding table row), so the preview renders inline and the same three
verdicts are invited in chat. The "one surface" rule holds — the fragment plus its accompanying chat turn **is**
the surface, and no separate checkpoint card follows it. Each applied-edit cycle re-renders by emitting a fresh
fragment.

## render.crm_update

`crm_view` = the in-memory `crm_update` object `work-account` Step 6.5 handed back (`current_stage`,
`stage_recommendation { recommendation, to_stage, criteria[], unmet[], reason }`, the verbatim-carried `next_step`,
`product_gaps[]`, and the optional `qualification { framework, fields[]: { field, status: captured|missing,
evidence?, updated }, gaps[]: { field, coach } }` block when Step 6.5 emitted one) plus the persisted
`drafts/YYYY-MM-DD-crm-update.md` `filename`; nothing is re-evaluated at render time. **Informational only:** zero
affordances, returns nothing; no `review.collect` call follows, no `capture-feedback` line is written, and silence
has no meaning here. Content rules: exactly one recommendation — `advance to <stage>` / `no change` /
`not applicable — <reason>`; a met exit criterion carries its source-prefixed citation, an unmet one reads
`no evidence this run`, and the criteria block is omitted entirely on `not-applicable`; when `crm_view` carries a
`qualification` block, a `Qualification (<framework>)` section renders between the stage/criteria content and the
next step, headed by an `N of M captured` count line (a count, never a percentage, score, or health grade), one line
per field in declaration order, coach hints verbatim from `gaps[].coach`; with no `qualification` block the section
is omitted entirely; the carried `next_step` renders in one line (or its explicit no-next-step reason); one cited
bullet per product gap, or the honest `none raised this run` line when empty. Because no write capability is
confirmed bound in this runtime, this surface is always reached through `write-crm`'s **simulate** branch: the
persisted filename is cited in chat with the explicit statement that **nothing was written to any external system**.
The stage recommendation stays advisory — ENRICH remains the sole stage writer.

## render.connections

`connections_view = { capabilities[]: { capability, status: connected|missing|degraded, tool?, consequence },
verdict: { ready: true } | { ready: false, exceptions[]: { what, unlocks } } }` — the capability status board
`skills/standalone/connect-tools.md` assembles from its introspection pass (both entries); nothing is re-evaluated
at render time. `tool` is a concrete name arriving **from the live environment** (environment → conversation → this
file — never from skill prose, ADR-6); `consequence` is the run-time cost of a gap in the honest-degradation voice.
Board content rules: one status row per capability — name, status (`connected | missing | degraded`), the serving
`tool` when bound, the muted `consequence` line on `missing`/`degraded` rows; the `verdict` banner closes the board —
`READY TO RUN`, or `READY EXCEPT` with one what/unlocks line per exception. Run against this file **before the Epic 3
enumeration records observations**, the honest board reports every external read `missing` with its degradation as
the consequence — that verdict is the truth about an unenumerated runtime, not a defect. **Render-only, conveys
nothing back:** binding-change verdicts flow through `review.collect` items of kind `binding_change`, never through
this surface. For a declared write-scoped row, `tool` reports live inventory presence independently of the status:
a present tool with missing replay/receipt evidence renders `degraded` with production writes disabled and close-out
simulated; `connected` is reserved for a positively confirmed, production-eligible mapping.

## render.setup_progress

`progress_view = { mode: first-run|refresh|resume, sections[]: { id: process|messaging|assets|voice|state,
status: done|active|pending | proposed-changes(n), title?, why?, coverage_note? } }` — the section checklist
`skills/setup-unbound.md` renders at its opening, after each section, on resume, and as the refresh audit view;
nothing is re-evaluated at render time. The section-id enum is fixed in D9 order — the same enum `review.collect`'s
`context_section` `task_id` slot carries. `title` and `why` are optional rep-facing strings owned by
`skills/setup-unbound.md`'s step-1 table; this file never restates them. Content rules: one mode line at the top;
one row per section in D9 order, carrying the section `title` as its heading (the `id` verbatim when absent), its
status, the muted `why` line when present, and the muted `coverage_note` beneath it when present; an absent optional
field omits its line entirely. The plain-Markdown fallback carries every field under those same absent-field rules —
ADR-1 field parity. **Render-only, conveys nothing back:** section verdicts flow through `review.collect` items of
kind `context_section`, never through this surface.

## render.context_preview

`preview_view = { section_id, title?, why?, drafted_content, provenance[]: { block_ref, label }, gaps[] }` — the
drafted artifact `skills/setup-unbound.md` previews in its section loop, before each verdict; nothing is regenerated
or altered at render time. `drafted_content` is the artifact **shaped like itself** — a positioning block for
`messaging`, the stage-ladder pipeline for `process`, the six-column asset table for `assets`. `title` and `why` are
optional rep-facing strings owned by `skills/setup-unbound.md`'s step-1 table; this file never restates them, and
the absent-field rules of `render.setup_progress` apply unchanged. Provenance labels
(`Evidence · <source> <locator>` / `Answer · rep`) are a **preview overlay only, never written to files** — the
accepted artifact strips them, and `title` and `why` are overlays under that same rule; gaps render in the D13
blockquote voice and are the only overlay content that persists (as D13 blockquotes in the written file). The
plain-Markdown fallback carries every field — ADR-1 field parity. **Render-only, conveys nothing back:** verdicts
belong to `review.collect` items of kind `context_section`, never to this surface.

## render.source_intake

`intake_view = { mode: first-run|resume|refresh, items[]: { id: sales-process|pitch-deck|positioning|brand|
messaging-guide|website|asset-list|own-writing, ask, why, status: pending|provided|interview|skipped, note? } }` —
the source-catalog checklist `skills/setup-unbound.md` renders when its step-2 intake opens and re-renders after
each item's answer; nothing is re-evaluated at render time. The item-id enum is the step-2 catalog's ids, in table
order. `ask` and `why` are required rep-facing strings owned by `skills/setup-unbound.md`'s step-2 catalog table;
this file never restates them. `note` is an optional muted annotation — the role `coverage_note` plays on
`render.setup_progress`. Content rules: one mode line at the top; one row per item in catalog order, carrying that
item's `ask` as its heading, its status (`pending | provided | interview | skipped` — required; an item carrying
none is a caller bug, never a render-time default), the muted `why` line beneath it, and the muted `note` beneath
that when present; an absent `note` omits its line entirely. A narrowed view — the managed path's single
`own-writing` row, or resume's remaining items — is an ordinary use of this shape, never a variant. The
plain-Markdown fallback carries every field — ADR-1 field parity. **Render-only, conveys nothing back:** intake
answers are given in chat, and this surface produces no `review.collect` item of any kind.

## transcript.get (providers unresolved)

- **Provider set.** **UNRESOLVED** — empty until observed. In the live file the provider rows were recorded from the
  host's actual connector inventory; this runtime's inventory has not been enumerated (G2 open), so this file
  records no provider row yet. Each future row is a single-row edit recorded at the Epic 3 `connect-tools` gate with
  its live-call evidence — the skill never changes (ADR-6).
- **Match policy, held invariant for whenever rows exist.** For each `call_ref`: issue every configured provider's
  correlation + transcript-fetch sequence; keep **confident matches only** — fuzzy or uncertain candidates and
  transcripts returned without a confidence signal are discarded (Pattern 2 — never mis-attribute); rank by native
  confidence, tie-break by the rep-editable `provider_priority` line; return `{ text: <verbatim transcript>,
  provider: <winning key> }`, or **`missing`** when none is confident. With an empty provider set every call resolves
  `missing`; the consuming skill marks the call `transcript: missing`, surfaces it, never fabricates.
- **Two concurrency axes — do not conflate them.** *Within* one `call_ref` the fan-out is across providers and is
  this file's concern, bounded by the provider set (today: empty). *Across* the independent events of one selected
  item the fan-out belongs to `skills/pipeline/fetch-transcript.md`, which states its own numeric bound. The two nest
  rather than compete, and neither bound is derived from the other.
- **`provider` carried verbatim.** A short kebab-case key from the provider rows; never `null` on present, never
  present on `missing`; carried verbatim onto every `transcript: present` record. This file names **no** provider
  values before their observation — the live environment is their only source (ADR-6).
- **ADR-6 grep gate (load-bearing).** `skills/pipeline/fetch-transcript.md` and its mirror MUST contain zero concrete
  provider or tool names. Unchanged in force for this runtime.
- **Write boundary.** Every future provider row is read-scope only; no transcript source acquires a write scope by
  appearing in the inventory (ADR-4).

## Out of scope (do NOT add here)

- Any **external write-scoped** capability beyond the ones a binding table above *explicitly declares*:
  `email.queue_draft`, `email.send`, `email.modify`, `email.label` (Growth FR28–FR34). The mail source is
  list-and-read only — the discovery window in the run loop, the rep's own SENT mail at setup — never send, reply,
  draft into the mailbox, label, archive, or modify.
- Any concrete tool name recorded without a G0 or live-inventory observation — an unresolved row is filled by
  evidence at the Epic 3 `connect-tools` gate, never by plausibility.
- Bindings/adapters for other runtimes (Copilot) — deferred, per the indirection rule.
- Any capability name that is not in `runtime/tool-bindings.md`, and any omission of one that is: the name set is
  parsed from both authorities and diffed by `[target-parity]` — derived by a machine, never counted in prose.
