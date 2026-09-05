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
  inventory observation supports it; every other row is marked **UNRESOLVED**, naming the gate that settles it. G0's
  live observations record install and routing only — no tool inventory. That enumeration belongs to Epic 3's
  `connect-tools` binding test gate, so no concrete ChatGPT tool name appears anywhere below, and none may be added
  without its observation.

## Resolution precedence — the working tree's file wins

- **This file, in the rep's working tree, is the resolution authority** for every capability below. `connect-tools` is
  its sole writer and it holds the current binding state, so a row the rep rebinds there takes effect at every beat —
  the pre-slate ones included.
- **A bundled `resources/bindings/*.md` fragment is a read-cost fast path, never a second authority.** It is a slice of
  the bundled *reference* that ships beside it, and a reference is not a rep's state. It resolves a capability only
  where the working tree carries no bindings file at all, which is why a fresh tree keeps the whole fragment win.
- **Divergence is the rep's binding, not drift.** A working-tree row that differs from the fragment is used as written
  — never reconciled against the fragment, never reported as a fault.

## Security posture (ADR-4)

Every **read** binding in this file is **read-scope only**, and external **writes are never implicit**: a write can
occur only through a capability this file *explicitly declares* with a write scope, and only when that capability's
own ADR-4 conditions hold. No
capability acquires a write scope by turning up in a runtime's tool list, and where none is declared or bound this
file requests and configures no write scope at all. In this runtime that bar is doubly unreachable today: no
external capability is positively confirmed bound, because no tool inventory has been enumerated.
The `render.*`, `review.collect` and `input.collect` capabilities are **local render/capture surfaces, not external
reads or writes**:
none introduces a new writer or write scope; the only writes they can lead to are the existing local authorities in
`skills/pipeline/work-account.md` — SET-STATUS, `capture-feedback`, and APPLY-EDIT — plus, for the setup-time
`review.collect` item kinds, the invoking skill's local file write (see `## review.collect`). `input.collect` leads to
none of them: its answers are held in-session and returned to the caller (see `## input.collect`).

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
| `transcript.list_since(ts)` — provider set **unresolved** in this runtime, exactly as for the fetch half: rows are added one per observed connector at the Epic 3 gate. Metadata only in every runtime — a listing carries no transcript text | read | **UNRESOLVED** — no recording connector observed. Until at least one provider row is confirmed bound the capability reports itself **unavailable**: recording discovery is unavailable, stated to the rep, and discovery proceeds from whichever other sources bind, or reports an empty discovery honestly. No provider name, listing tool or window semantics is recorded here before its observation. | — |
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
write-then-reference protocol owned by `## Visualize protocol — write-then-reference` below. **BOUND (protocol)** in
a row means exactly that observation: the beat composes per that protocol, instantiating the row's pinned template
under its fragment-projection rules. Per the resolution rule below, a surface that cannot be session-confirmed still
resolves to its documented fallback — never assumed. The pinned template named in each row is the layout authority
on a confirmed surface; layout minutiae live in the template, never in prose.

| Logical capability | Scope | Interactive surface (pinned template) | Fallback | Consumed by |
| --- | --- | --- | --- | --- |
| `render.tasks(task_view)` | render, no capture | **BOUND (protocol)** — card stack, one card per task — `resources/templates/task-plan-widget.html` | plain Markdown checklist in chat | `skills/pipeline/work-account.md` (re-render after SET-STATUS / APPLY-EDIT), `skills/standalone/collect-tasks.md` (roundup) |
| `review.collect(checkpoint_view)` | render/capture (local verdicts only) | **Stays on the typed fallback** — evidence-cited 2026-08-12 (G1, story 3.1): the observed `visualize` surface runs client-side JS but no channel from a rendered fragment back into the conversation has been observed, and this capability's whole value **is** capture — a card stack whose controls capture nothing invites clicks that silently mean nothing. Flips only on a later G1 observation of such a channel, its grammar recorded from observation, never designed in advance | in-chat `accept \| edit \| reject` prompt per item | `skills/run-unbound.md` (Step 3.5 batch triage + Step 3.5 material-edit re-confirm + Step 5 close-out open questions + qualification gaps) |
| `input.collect(ask_view)` | render/capture (local answers only) | **Stays on the typed fallback** — same evidence and the same reason as `review.collect` (2026-08-12, G1, story 3.1): no channel from a rendered fragment back into the conversation has been observed, and this capability's whole value **is** capture — a form whose Submit reaches nothing invites a click that silently means nothing. Flips only on a later G1 observation of such a channel, its grammar recorded from observation, never designed in advance | the same fields asked in chat, one numbered line each, every default stated as the proposed answer | `skills/handlers/draft-followup.md` (SCHEDULING-CONFIRM), and any `execute` handler per `task-registry.md` Part B's Input-collection obligation |
| `render.slate(slate_view)` | render, no capture | **BOUND (protocol)** — card grid — `resources/templates/slate-widget.html`; selection stays typed (the fallback's own rule) | plain annotated slate lines | `skills/pipeline/build-slate.md` Step 4 (via `run-unbound` Steps 2–3) |
| `render.email_draft(draft_view)` | render/capture (the draft's own verdict) | **BOUND (protocol) — display half only** — mail-client preview — `resources/templates/email-draft-widget.html`; the verdict footer is stripped by projection and the three verdicts are typed in chat (see `## render.email_draft`) | cited filename + draft body in chat, with the same three verdicts invited in chat | `skills/handlers/draft-followup.md`, at the EXECUTE TASKS artifact-verdict gate (`triage-and-execute.md` Step 4) |
| `render.artifact(artifact_view)` | render/capture (the artifact's own verdict) | **BOUND (protocol) — display half only** — generic artifact preview — `resources/templates/artifact-widget.html`; the verdict footer is stripped by projection and the three verdicts are typed in chat (see `## render.artifact`) | cited filename + `body_blocks[]` content in chat, with the same three verdicts invited in chat | any `execute` handler per `task-registry.md` Part B's Output-edit obligation (default render capability) |
| `render.crm_update(crm_view)` | render, no capture | **BOUND (protocol)** — informational CRM card — `resources/templates/crm-update-widget.html` | plain in-chat CRM-updates Markdown section, its heading naming `state` | `skills/pipeline/write-crm.md` (APPLY) |
| `render.task_push(task_push_view)` | render, no capture | **BOUND (protocol)** — informational card — `resources/templates/task-push-widget.html` | the same payloads in full as a plain in-chat Markdown section | the task-manager push seam's per-payload approval walk (composition slot 9) |
| `render.connections(connections_view)` | render, no capture | **BOUND (protocol)** — capability status board — `resources/templates/connections-widget.html` | plain Markdown capability table + verdict line in chat | `resources/connect-tools.md` (both entries) |
| `render.setup_progress(progress_view)` | render, no capture | **BOUND (protocol)** — section checklist card — `resources/templates/setup-progress-widget.html` | plain Markdown section-status list in chat | `skills/setup-unbound.md` (progress + resume + audit views) |
| `render.context_preview(preview_view)` | render, no capture | **BOUND (protocol)** — formatted artifact preview — `resources/templates/context-preview-widget.html` | plain Markdown artifact section in chat | `skills/setup-unbound.md` (section-loop previews) |
| `render.source_intake(intake_view)` | render, no capture | **BOUND (protocol)** — source-catalog checklist card — `resources/templates/source-intake-widget.html` | plain Markdown item-status list in chat | `skills/setup-unbound.md` (step-2 intake, re-rendered after each answer) |

## API contract — logical capability signatures (stable across runtimes)

Per the architecture record's API Contracts; the signatures are **runtime-invariant** — only the binding tables change
per runtime. `[target-parity]` parses this block and the live file's and fails on any missing, extra, or changed
signature; the comment tails are runtime commentary and are outside that comparison. Render view shapes live in their
capability sections below.

```
calendar.list_events_since(ts)  -> [event]               # read
calendar.availability(attendees, window) -> [open_slot]  # read; open_slot = { start, end } (ISO 8601 with offset, in the run's timezone); an attendee whose free/busy is unreadable is reported unreadable, never guessed
transcript.get(call_ref)        -> { text, provider } | missing  # read; provider set unresolved in this runtime — rows are added per observed connector, and until one is bound every call resolves `missing` => never silently drop (Pattern 2)
transcript.list_since(ts)       -> [recording] | unavailable     # read; METADATA ONLY, never transcript text — nothing is retrieved before selection; a body is recovered later, by transcript.get. unavailable ⇒ recording discovery is unavailable, stated to the rep, and discovery proceeds from the other sources alone.
                                                          # recording = { title, start, end, attendees[], ref, provider, calendar_ref? }
                                                          # truncated names the oldest instant actually read, present only when the
                                                          #           bounded paging loop could not reach back as far as ts
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
input.collect(ask_view)         -> answers                                      # render/capture; asks for a fact the run cannot derive, never for a verdict; one answer per field id
ask_view = { title, context_line, fields[] }
field = { id, label, kind: choice | multi_choice | text | list, options?[], default?, basis? }   # options[] on the two choice kinds only; basis names where a derived default came from, so a pre-filled answer is never unexplained
answers = { field_answers[]: { field_id, value } }                              # submit returns every filled field, untouched pre-filled ones included; no submit returns nothing at all
render.slate(slate_view)        -> slate_cards | annotated_lines                 # render; interactive card grid, fallback = plain annotated slate lines
render.email_draft(draft_view)  -> { preview, item_verdict }                     # render/capture; interactive mail-client preview + verdict footer, fallback = cited filename + body in chat with the verdict invited in chat
render.artifact(artifact_view)  -> { preview, item_verdict }                     # render/capture; generic artifact preview + verdict footer, fallback = cited filename + body_blocks[] in chat with the verdict invited in chat
render.crm_update(crm_view)     -> crm_card | markdown_block                     # render; informational CRM-update card, state-keyed; fallback = plain in-chat CRM-updates Markdown section carrying the same fields, state included
render.task_push(task_push_view) -> task_push_card | markdown_block              # render, no capture; informational queued-payload card carrying every payload in full, fallback = the same payloads in full as a plain in-chat Markdown section
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
   fragment-projection rules below. For `render.slate` that instantiation is **helper-first**: the bundled helper's
   `render` command for this surface returns the fragment already projected under those same rules; hand instantiation
   is the **availability** fallback. The rules below stay normative — the helper implements them.
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
"task" | "context_section", mode?, body? }` — `context` is the task's typed execution-context block on
`kind: "task"` items, and `mode ∈ { execute | define-only }` is that task's registry execution mode, carried as the
Step 4 walk filter and the card's rep-owned type pill — never an affordance switch (below). The produced email draft is **not** an item kind here: it
carries its own verdict on its own
surface (see `## render.email_draft`). Returns `verdicts = { item_verdicts[], open_answers[],
qualification_answers?[] }`; `item_verdict = { task_id, verdict, note }`;
`open_answer = { question, answer }`; `qualification_answer = { field, answer }`.

**The verdict enum is scoped by call site, not by `kind` alone** — a `kind: "task"` item returns a different set at
the plan gate than at the per-task gate, the two asking different questions:

| Scope | Where | Enum |
| --- | --- | --- |
| plan verdict | `run-unbound` Step 3.5 — the batch triage and its material-edit re-confirm | `accept \| reject \| edit` |
| task verdict | `run-unbound` Step 4a — the per-task gate, before dispatch | `execute \| defer \| cancel \| edit` |
| artifact verdict | the handler's own output gate (see `## render.artifact`) | `accept \| edit \| reject` |
| context section | `setup-unbound`, outside the run loop | `accept \| edit \| reject` |

The sets never mix — a value from the wrong one is an out-of-enum write (ask, never guess).

**Call-site policy — batch or single-item, fixed per site.** `items[]` was always a list; which mode a site uses is
settled here, never chosen by the caller:

| Call site | Mode | `items[]` | `open_questions[]` | `qualification_gaps[]` |
| --- | --- | --- | --- | --- |
| `run-unbound` Step 3.5 — plan triage | **batch** | all retained tasks, in priority order | `[]` | `[]` |
| `run-unbound` Step 3.5 — material-edit re-confirm | single-item | the one re-shaped task | `[]` | `[]` |
| `run-unbound` Step 4a — per-task gate (`mode: execute` tasks only) | single-item | the one task at its turn, **with** its typed `context` block | `[]` | `[]` |
| `run-unbound` Step 5 — close-out questions + qualification | no items | this run's list | `crm_update.qualification.gaps[]` or `[]` (one call when either list is non-empty; skip only when both are empty) |
| `setup-unbound` — `context_section` | single-item | one previewed section | `[]` | `[]` |

A **batch** return simply carries N `item_verdict`s. **An omitted `task_id` in a batch return is an omitted verdict**
— silence stays per-task inside a batch, and nothing is written for a card the rep never touched. A batch of one is
still a batch; **zero retained tasks means no call at all** (never render an empty checkpoint).

**No card ever hides a button.** Every plan card carries the same three and every 4a card the same four: the walk
admits `mode: execute` tasks alone, so an Execute affordance at 4a is always a real option and `mode` never switches
what a card offers.

Verdict mapping:
at the **plan** gate, Accept → `accept` and Reject → `reject`; at the **4a task** gate, Execute → `execute`, Defer →
`defer` and Cancel Task → `cancel`. Everywhere, a free-text edit → `edit` with the text captured
**verbatim** as `note`. **No
answer for an item → no verdict for that item** (silence is not a verdict); hand-typed equivalents map identically
("keep it" → accept, "not a real task" → reject, "run it" → execute, "later"/"I'll do it" → defer, "drop it" → cancel);
ambiguous free text that cannot map to that site's enum → ask, never an out-of-enum write. A hand-typed `execute`
against a `mode: define-only` task is out of enum wherever it arrives — no surface offered it and that task never
reaches the 4a gate at all: surface it and re-ask, never invent a handler or a turn for it. Verdicts route through the
existing write authorities — no new writer: one `capture-feedback(namespace, slug, task_id, verdict, note)` line per
verdict to `state/feedback-log.jsonl`; a **task** `edit` is applied via work-account's APPLY-EDIT, and a `reject` or a
`cancel` via its CANCEL-TASK, which stamps the reason word its caller passes — `rejected by rep on <date>` or
`cancelled by rep on <date>` (an **output**
`edit` is applied by the artifact's own handler — see `## render.email_draft`); verdicts never touch task `status`
(SET-STATUS's domain), whose `not-done` value is what a deferred task simply keeps. `open_questions[]` and `qualification_gaps[]` are **never widget-rendered** — they remain
in-chat free text; `open_answers[]` are echoed in chat and held in-session with nothing written for them, and each
non-empty `qualification_answer` routes through exactly one work-account `capture-qualification` invocation. The
checkpoint itself is write-free.

Setup-time item kinds (outside the run loop): `context_section` — one previewed context section, its `task_id` slot
carrying the section id (`process | messaging | assets | voice | state`); consumed by `skills/setup-unbound.md`.
There is **no binding-change item kind**: `connect-tools` binds every row it can resolve on its own and asks nothing,
so no binding edit passes through this surface (see that skill's Procedure). One item per
call, never batched, same `accept | edit | reject` enum. **Routing outside the run loop:** accept ⇒ the invoking
skill performs its local file write; edit ⇒ the note is applied to the draft/proposal and re-presented; reject ⇒ the
section is re-entered / the proposal dropped. **No `feedback-log.jsonl` line is written** — `capture-feedback`
remains exclusively the run loop's prioritization instrument.

## input.collect

`ask_view = { title, context_line, fields[] }`; each `field = { id, label, kind: choice | multi_choice | text | list,
options?[], default?, basis? }`. Returns `answers = { field_answers[] }`; `field_answer = { field_id, value }` — one
answer per field id, in `fields[]` order. `options[]` belongs to `choice` / `multi_choice` alone; a `text` or `list`
field carrying one is a caller bug, never rendered as a control it did not ask for.

**This surface asks for a fact, never for a verdict.** `review.collect` puts something the run already built in front
of the rep to judge; `input.collect` asks for what the run could not derive and cannot proceed without — who is on the
call and when, which companies may see a shared room, how a named tool connects. The two are never substituted for each
other, and a question of this shape gets this surface rather than a newly invented one.

**Every field accepts a `default`, and that is the whole point.** Where the run can already work the answer out, the
ask arrives pre-filled and the rep confirms it in one action instead of composing a reply. A default the run *derived*
carries a `basis` naming what it came from, so a pre-filled answer is never an unexplained one (Article IV — cite it or
do not offer it); a default the caller was simply given carries none. A `default` is a **proposal, not a recorded
answer**: it becomes the rep's answer only when the rep confirms it.

**On this runtime the whole ask is typed, and the contract survives that intact.** With no capture channel observed
here, the fields are asked in chat — one numbered line each, every default stated as the proposed answer — and the rep
confirms in one reply. Confirming every proposal at once is one turn, exactly as pressing Submit is one click, so the
capability's promise holds on the fallback rather than depending on a widget. **An answer given is an answer; no reply
is no answer.** A rep who confirms returns every field, the pre-filled ones included; an ask that draws no reply
returns **no** `field_answers[]` at all and is never filled in from its own defaults. A field left unanswered that
carries no default returns **no entry** — unanswered, never an empty string. Free text that cannot be read as its
field's `kind` → ask, never a guess.

**Write-free, like every other capture surface.** This capability introduces no writer and no write scope: the answers
are held in-session and handed back to the calling skill, which may do with them only what its own declared authorities
already allow. **No `feedback-log.jsonl` line is written** — `capture-feedback` remains exclusively the run loop's
prioritization instrument. ADR-1 field parity holds: the same fields, the same order, the same stated defaults on
whichever surface the ask arrives.

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
line stands); the `dropped` set is **never** widget-rendered (inspect-on-request stays chat-based). The written fragment
is helper-first per `## Visualize protocol — write-then-reference` step 2.

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

## render.artifact

`artifact_view = { kind, title, filename, body_blocks[], source_task }`, read from the artifact file the handler
already wrote under the item's `drafts/` — nothing is regenerated or altered at render time. `kind` is a short label
naming the artifact type for card framing only, never a dispatch key; `body_blocks[]` is the artifact's content,
chunked for display — **shaped like itself**, the same principle `render.context_preview`'s `drafted_content`
already states. **Render/capture:** the surface carries the artifact plus its verdict — Accept / Reject / free-text
edit — and returns `item_verdict = { task_id, verdict ∈ {accept|edit|reject}, note }`, where `task_id` is
`source_task`. The artifact and the decision on it are **one surface**; no separate checkpoint card follows it. On
the fallback the cited filename and `body_blocks[]` content appear in chat with the same three verdicts invited
there. The boundary holds on every surface: nothing is applied, sent, or renamed, and the artifact is stated as
`draft · not applied`. An **`edit` verdict is applied**, not merely recorded: the handler's own
`apply-<artifact>-edit(namespace, slug, source_task, note)` rewrites the artifact file — bounded to the fields the
handler's own content contract declares — **first**, appends exactly one `edit` line via `capture-feedback` **only**
on success, and re-renders through this capability so a fresh verdict is collected. The cycle repeats until accept or
abandon; one log line per cycle, append-only, rep-bounded. Silence after a re-render writes nothing. This capability
adds **no** writer: the artifact file is one its own handler already owns. **On this runtime's bound surface the
verdict stays typed:** the fragment projection strips the verdict footer (no channel from a rendered fragment back
into the conversation has been observed — see the binding table row), so the preview renders inline and the same
three verdicts are invited in chat. The "one surface" rule holds — the fragment plus its accompanying chat turn
**is** the surface, and no separate checkpoint card follows it. Each applied-edit cycle re-renders by emitting a
fresh fragment. `render.artifact` is the **default** render capability every `execute` handler inherits per
`task-registry.md` Part B's Output-edit obligation; a handler naming a more specific capability (`draft-followup`
keeps `render.email_draft`) uses that one instead.

## render.crm_update

`crm_view` = the in-memory `crm_update` object `work-account` Step 6.5 handed back (`current_stage`,
`stage_recommendation { recommendation, to_stage, criteria[], unmet[], reason }`, the verbatim-carried `next_step`,
`product_gaps[]`, and the optional `qualification { framework, fields[]: { field, status: captured|missing,
evidence?, updated }, gaps[]: { field, coach } }` block when Step 6.5 emitted one) plus the persisted
`drafts/YYYY-MM-DD-crm-update.md` `filename` and `state: simulated | pending | synced`. On a write branch it also carries
`target?: { object, crm_ref }`, `payload_fields[]?: { api_field, mode: replace | append, value, truncated }`,
`dropped[]?: { field, reason, defect }` and `receipt?: { provider, receipt_id, target_ref, applied_at }` — every one a
projection of what BIND and APPLY already produced, absent on `simulated`; nothing is re-evaluated at render time. **Informational only:** zero
affordances, returns nothing; no `review.collect` call follows, no `capture-feedback` line is written, and silence
has no meaning here. Content rules: exactly one recommendation — `advance to <stage>` / `no change` /
`not applicable — <reason>`; a met exit criterion carries its source-prefixed citation, an unmet one reads
`no evidence this run`, and the criteria block is omitted entirely on `not-applicable`; when `crm_view` carries a
`qualification` block, a `Qualification (<framework>)` section renders between the stage/criteria content and the
next step, headed by an `N of M captured` count line (a count, never a percentage, score, or health grade), one line
per field in declaration order, coach hints verbatim from `gaps[].coach`; with no `qualification` block the section
is omitted entirely; the carried `next_step` renders in one line (or its explicit no-next-step reason); one cited
bullet per product gap, or the honest `none raised this run` line when empty. Exactly one header pill, keyed to
`state`: amber `simulated · not written`, amber `pending approval · nothing written yet`, teal `synced · written to CRM`
— amber for the first two because both carry the same fact, that nothing has left the machine. Those six blocks are
**branch-invariant**: same order, same positions, on every state. Three blocks **trail** them, each **omitted entirely**
where its state or its list says so — never an empty heading, never a placeholder line. `state` is always `simulated`
on this runtime, because no CRM write capability is confirmed bound here (see the write row below): every optional field
is absent, the three trailing blocks do not render, and the persisted filename is cited in chat with the explicit
statement that **nothing was written to any external system**. Should a write branch ever be reached here, `pending` and `synced` render the payload — one row per
`payload_fields[]` entry under this CRM's own API field name with its `mode` named beside it, an append rendering the
**complete composed value** and a truncated value stating the truncation — then the **complete** drop list beneath it
under a heading stating these were not written by this deployment, one line per `dropped[]` entry naming the field and
the reason, a `defect` entry marked distinctly from an ordinary drop, never summarised to a count, nothing at all where
the list is empty; and on `synced` only, the normalized `receipt` in one compact muted audit block, last. `state` is the
consuming skill's to pass and is never inferred here: a decline or silence renders `simulated` and never leaves a
`pending` pill standing, and `synced` renders **only** once a sync record has been written. The stage recommendation
stays advisory — ENRICH remains the sole stage writer — and this capability carries **no** affordance on any state.

## render.task_push

`task_push_view = { destination { container_id, container_name? }, payloads[]: { task_id, operation: create | update,
title, body_lines[], outbound_status, marker, unresolved_prior_attempt } }` — a projection of the payloads the
task-manager push seam's PREPARE beat already built; nothing is re-read, re-derived or re-evaluated at render time, and
the link table is never re-consulted for `operation`. `title` is the **outbound** title under the declared naming
convention, placeholders resolved — the card must show what lands. `body_lines[]` is the outbound body **verbatim, in
send order**, and renders **complete** — never elided, never summarised, never truncated. `outbound_status` is the image
of the local status under the map in force; a status with no image renders the honest `no image in the map — status not
sent` line rather than a guess. `marker` renders **last**, because it is the last line of the body. `container_name` is
narration; `container_id` is the only addressing value, and shows alone where it is all that is known.
**Informational only:** zero affordances, returns nothing; no `review.collect` call follows, no `capture-feedback` line
is written, and silence has no meaning here — the approval stays typed, one payload at a time, at the walk's own ask.
Card text rules: a header carrying the `Tasks to push` label, the destination line and an amber `queued · nothing sent`
pill; then one block per payload **in the plan's priority order** — an operation pill, the outbound title as its
heading, the distinctly-marked unresolved-prior-attempt row where that flag is set, every `body_lines[]` entry whole,
the `will land as <outbound_status>` line, and the muted marker line last; then an `N tasks queued` footer — a count,
never a percentage, score, or health grade. An **empty candidate set renders no widget at all**, the rule `render.slate`
already carries for an empty slate. Fallback, ADR-1 field parity: the same payloads **in full** — every body line and
every marker, one section per payload, in the same priority order. It is never a summary.
## render.connections

`connections_view = { capabilities[]: { capability, status: connected|missing|degraded, tool?, consequence, connect? },
connect = { what, where, unlocks }; write_policy?: { authority: verified|mismatch|unverified|absent, declared?, observed?,
findings[]: { name, declared, observed, consequence, severity: gap|note } }; verdict: { ready: true } | { ready: false, exceptions[]: { what, unlocks } } }` — the capability status board
`resources/connect-tools.md` assembles from its introspection pass (both entries); nothing is re-evaluated
at render time. `tool` is a concrete name arriving **from the live environment** (environment → conversation → this
file — never from skill prose, ADR-6); `consequence` is the run-time cost of a gap in the honest-degradation voice.
Board content rules: one status row per capability — name, status (`connected | missing | degraded`), the serving
`tool` when bound, the muted `consequence` line on `missing`/`degraded` rows; the `verdict` banner closes the board —
`READY TO RUN`, or `READY EXCEPT` with one what/unlocks line per exception. Run against this file **before the Epic 3
enumeration records observations**, the honest board reports every external read `missing` with its degradation as
the consequence — that verdict is the truth about an unenumerated runtime, not a defect. **Render-only, conveys
nothing back:** zero affordances, no verdict, no write. There are no binding verdicts to carry — `connect-tools` binds
what it can resolve without asking (see that skill's Procedure).

`connect` is present on every `missing` row and on any `degraded` row a connector would fix, and it is the actionable
half of the board: `what` names the connector in the words the rep will see in their own settings UI (never a raw tool
name), `where` is the concrete place they go to add it on this runtime, and `unlocks` is the capability they get back,
stated as behavior. It is guidance the rep can follow without a further question — never a prompt, and never a step the
skill waits on. A row with no available connector carries no `connect` and says so in its `consequence` instead.


## render.setup_progress

`progress_view = { mode: first-run|refresh|resume, sections[]: { id: process|messaging|assets|voice|state,
status: done|active|pending | proposed-changes(n), title?, why?, coverage_note? } }` — the section checklist
`skills/setup-unbound.md` renders at its opening, after each section, on resume, and as the refresh audit view;
nothing is re-evaluated at render time. The section-id enum is fixed in D9 order — `state` is
progress-only, never a `review.collect` `task_id`.
`title` and `why` are optional rep-facing strings owned by
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
