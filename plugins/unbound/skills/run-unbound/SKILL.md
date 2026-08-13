---
name: run-unbound
description: Entry point and orchestrator for an Unbound working session. Use when the rep starts their daily event-processing ritual — reads run state, discovers events (calls + unanswered inbound emails) since the last run, presents the annotated slate, and walks the rep through one account or project at a time.
tier: all
---
# run-unbound

Manual entry point and orchestrator for an Unbound working session — the rep's deliberate
sit-down to process recent events (calls + unanswered inbound emails); it never wakes up on its
own. It reads the run state, composes the downstream skills in a fixed order, and walks the rep
through one account or project at a time. The only local write it owns is advancing `last_run` at session end; every other write
is owned by the skills it composes.

## Reads

- `state/run-state.yaml` — `last_run` (ISO 8601 with offset, required), `timezone` (IANA, required), optional `scan_window`; the optional `context_stamp`, read at Step 1.5's compare; and the optional `work` list of open cycle records, read at Step 3.2's detect to tell whether the selected item is mid-cycle. The durable `events` list is read by the slots that own it — `build-slate` at upsert, `fetch-transcript` at evidence recovery.
- `resources/context/STAMP` and `resources/context/{process,messaging,assets}.md` — bundled-resource reads at Step 1.5, performed by `managed-context-apply`; an absent `STAMP` is the unmanaged path. Neither is capability-mediated: no `runtime/tool-bindings.md` row, and nothing for `connect-tools` to report. The bundle ships this skill the shared apply resource and its bodies now too, so this loop can apply new context itself rather than only detecting it.
- `drafts/<plan_date>-tasks.yaml` — read-only, at Step 3.2's rehydrate: the pinned plan of an interrupted cycle, read verbatim and never rewritten from here.
- `state/feedback-log.jsonl` — read-only and additive-only, at Step 3.2's rehydrate: the cycle's standing verdicts, filtered to the item and to the lines whose `ts` is at or after the record's `started_at`. This is the only beat in the run loop that reads the log; every line appended to it is still `work-account`'s `capture-feedback`.
- In-memory outputs of every downstream skill it composes.

## Procedure

**1 — Read state and set up the session (silent — see Invariants, narration discipline).**

1. Open `state/run-state.yaml` as-is and read `last_run`, `timezone`, and optional `scan_window`.
  - Do not recreate, reshape, or write the file.
  - If the file is missing, or is not valid YAML with both `last_run` and `timezone`, stop and
     tell the rep — never invent values or create the file.
2. Parse and validate `scan_window` in `timezone`; do not sample the clock yet:
  - Absent or `now` → retain unbounded mode.
  - `<n>h`/`<n>d` → retain the parsed duration `W` for the final pre-query beat.
  - Unparseable → stop and surface to the rep; never guess, never silently fall back to `now`.

**1.5 — Managed context apply (slot).** Runs after Step 1's state read, before Step 2's discovery — see Invariants (managed context).

1. **Invoke** `managed-context-apply` (`skills/pipeline/managed-context-apply.md`) in full — it is the sole owner of detect → compare → note → apply whole → stamp → report replaced edits → report stage-rename fallout → state the asset-link assumption; this beat restates none of its clauses and never enters `setup-unbound`'s steps 1–8.
2. **Consume** the returned report unchanged.
  - `unmanaged` or `current` ⇒ no write occurred: end here in silence.
  - `applied` ⇒ narrow the report to silence: it renders only where it names an account (the stage-rename fallout), never the "none do" line, and the asset-link statement belongs to `setup-unbound`'s own entry and does not render here.
  - `failed` ⇒ the tree keeps its prior `context_stamp`.
  - A clean apply on an untouched tree therefore emits nothing at all.
3. **Continue** into Step 2 whichever way step 1.5.2 resolved, including on an apply that failed.

**2 — Compose the run.** Hand off to these skills in this fixed order. The discovery half (slots
1–3) carries the in-memory bag of source-discriminated `discovered_events` (each `{ event_id,
source: "call"|"email", external_ref, occurred_at, ... }`); everything from selection on works the
one item the rep picked.

**Final pre-query beat.** After Step 1.5 has returned and immediately before slot 1, sample the
current instant exactly once as full ISO 8601 with offset in `timezone`. Resolve the immutable
in-memory `discovery_until`: unbounded mode uses that sample; duration mode uses the earlier of
`last_run + W` and that same sample. If the resolved interval is invalid, stop before either source
query. Carry the exact scalar unchanged through the session; no later clock read participates in
the discovery watermark.

| Slot | Skill | What it contributes |
| --- | --- | --- |
| 1 | `discover-events` | Find events in the discovery window; always pass `last_run`, `timezone`, and the exact resolved `discovery_until`. |
| 2 | `classify-work` | Route each event to its owning account or project, honoring upstream `suggested_slug` hints. |
| 3 | `build-slate` | Upsert each discovered event into `events` and present the annotated, unranked slate derived from the pending ones. |
| — | **Selection** | The rep picks one item (Step 3 below). A beat, not a slot: it retrieves nothing and ships no skill file. |
| 4 | `fetch-transcript` | Recover the selected item's evidence. Hand it the selected `(namespace, slug)`; it returns `evidence[]` and `event_ids[]`. That skill owns the retrieval rules — which events it takes, how each source is fetched, and how a gap is marked — and this loop restates none of them. |
| 5 | `bootstrap-context` | On first encounter only, create the selected item's context.md, grounded in the evidence just recovered. |
| 6 | `work-account` | Synthesize the task list for the one selected item, taking `selected_item = { namespace, slug, context_ref, evidence[], event_ids[] }`, and record the item's cycle over those events; they stay `pending` until the cycle's close-out. |
| 7 | `draft-followup` | The `followup_email` handler, opened at that task's turn inside EXECUTE TASKS. |
| 8 | `write-crm` | The CRM close-out apply, opened at the CRM sub-beat inside NEXT STEPS. |

**Nothing is retrieved before selection.** Slots 1–3 issue no `transcript.get` and no
`email.get_thread`: the slate is built from event metadata alone, and slot 4 is the run's only
evidence retrieval — paid once, for the one item the rep picked, rather than for every item they
did not. The licence for that ordering is the window-independence invariant below: a durable
`external_ref` recovers an event however many runs later the rep gets to it, so recovering it
ninety seconds later is the same operation.

After slot 6 hands back its plan, three loop beats close the run, each defined in its own step
below:

- PLAN TRIAGE — one comparative verdict pass over the whole ranked plan, collected in a single
  batch, before anything is handled (Step 3.5).
- EXECUTE TASKS — walk the accepted, executable tasks, sequentially in priority order (Step 4).
- NEXT STEPS — close-out: prescribed next step, outcome recap, email-draft verdict, open
  questions, then the CRM Updates sub-beat (Step 5).

**The resume fork.** Immediately after selection, Step 3.2 looks for an open work record on the
selected item, and the composition takes one of two shapes:

- **Normal path (no record)** — slots 4, 5 and 6 all run exactly as written, and nothing changes.
- **Resume path (record present)** — Step 3.2 **supersedes slots 4 and 6**. It re-fetches the
  evidence itself, bounded to the record's `event_ids[]` rather than to every pending event for the
  item, and it reads the cycle's plan off disk instead of synthesizing one — so `work-account` does
  **not** re-run for this item and no second dated tasks file is created. PLAN TRIAGE, EXECUTE TASKS
  and NEXT STEPS are then entered at whichever beat the record's `phase` names.

Side entry (not part of this loop): `collect-tasks` is rep-invoked and pure-read; the
orchestrator never invokes it.

**3 — Selection (rep picks one).**

- Present the unranked slate and let the rep choose one item; do not auto-rank or auto-select.
- If ambiguous, ask — proceed only once exactly one item is identified.
- Items whose evidence is `missing` remain selectable, as are email-grounded items (see
  Invariants).
- Selecting does not mark anything `processed` — that is `work-account`'s job, and it flips only
  the contributing `event_ids[]`, at the cycle's close-out rather than anywhere earlier. Unselected
  items keep every pending event they had and reappear next run.

**3.2 — RESUME (pick an interrupted cycle back up at the beat it stopped on).** Runs on the one
selected item after selection, before PLAN TRIAGE. **This step writes nothing at all** — no record
update, no plan rewrite, no log line, no persisted `evidence_status`, nothing. Everything it
reconstructs is held in memory for the rest of the run. That single property is what lets the
mismatch branch below *ask* instead of act, what makes an abandoned resume cost nothing, and it is
why this skill's Writes section is unchanged by this step:

- **(a) Detect.** Look up `work[]` in `state/run-state.yaml` for the selected `(namespace, slug)`.
  **No record → the normal path**: state nothing and **run nothing else in this step** — the
  composition continues to slots 4, 5 and 6 exactly
  as it does today. That is the ordinary case, not a failure: an absent record simply means nothing
  is in flight for this item, which is also what a hand-deleted record honestly means. Only a
  present record reaches (b).
- **(b) Verify (record present).** Confirm `drafts/<plan_date>-tasks.yaml` **exists** and is the
  item's **latest-dated** tasks file. On either mismatch — the file is missing, or a later-dated
  tasks file is present — **surface which of the two fired** and **ask the rep**: finish from the
  later file, or restart. **Write nothing until the rep answers.** Never guess, never silently
  re-plan, never pick a file by inference. The two conditions get distinguishable lines; a rep who
  cannot tell which one fired cannot make the choice being asked of them.
- **(c) Rehydrate (four reconstructions, every one of them in memory).** Each names its own source
  and its own behavior when that source fails:
  - **Plan** — read the `plan_date` file **verbatim**; that is the cycle's plan. **No synthesis runs
    on a resume**: the plan is read off disk, never re-derived, so no second dated tasks file can
    appear. **Carry-forward therefore never fires on a resume** — the carry matrix belongs to
    `work-account` Step 2, and Step 2 does not run here. That is correct rather than an omission:
    the plan the rep is resuming is the plan they left, and work carried into it mid-cycle would
    be work they never triaged.
  - **Evidence** — re-fetch each of the record's `event_ids[]` members by its stored `external_ref`,
    `source: "call"` → `transcript.get`, `source: "email"` → `email.get_thread`. That is the same
    recovery path slot 4's `fetch-transcript` owns — invoked by reference here, with none of its
    clauses restated — and it refreshes each entry's `evidence_status` **in memory only**. A
    re-fetch that comes back with nothing is surfaced and marked `evidence_status: missing`: honest,
    **never blocking**, and never a reason to abandon the resume. The plan is already on disk and is
    not derived from evidence at this point, so even a re-fetch that fails on every event still
    leaves a usable resume.
  - **Verdicts** — read `state/feedback-log.jsonl`, keep the lines matching this
    `(namespace, slug)` whose `ts` is at or after the record's `started_at`, and take the **latest
    line per `task_id`** as that task's standing verdict. That window is what `started_at` is for:
    it separates this cycle's verdicts from every prior cycle's on the same item. A `task_id` with
    no line in the window has no verdict, and silence keeps its standing meaning.
  - **`crm_update`** — re-derive it by invoking `work-account` **Step 6.5 CRM UPDATE** by name,
    evaluate-only, over the rehydrated evidence and the item's current context.md. That step already
    states its object is handed back in memory and is not written there, which is exactly what makes
    it safe inside a step that writes nothing; its clauses are not restated here. Qualification
    capture therefore self-heals on resume: an answer persisted before interruption evaluates
    captured from current context.md, falls out of the re-derived `qualification.gaps[]`, and only
    the remaining gaps reach Step 5.
- **New events, counted and stated — never folded.** Pending events for this `(namespace, slug)`
  that are **not** in the record's `event_ids[]` are **counted and stated plainly** — "<N> new
  events for <Name> — next cycle after close-out" — and are **never** folded into the in-flight
  plan, never verdicted, and never re-planned around. They stay `pending` straight through the
  close-out, so the item correctly reopens as a fresh cycle on the next run. This is the one place
  the resume path's event scope differs from slot 4's, and the difference is
  deliberate: that slot recovers **every** pending event for the item, while this step re-fetches
  **only** the record's `event_ids[]` and counts the remainder. The plan the rep is resuming is the
  plan they left, unchanged by anything that arrived since.
- **(d) Jump — the record's `phase` picks the beat.** Three cases, and no others:
  - `planned` → **Step 3.5**, the full batch over all retained tasks. Earlier partial verdicts stand
    and re-verdicts append: the log is append-only and the latest line per `task_id` wins, so
    re-triaging a card the rep already marked costs one repeated question, never a lost answer.
  - `triaged` → **Step 4**, with the accepted set taken from the rehydrated verdicts.
  - `executed` → **Step 5**, close-out only.
- **Say what was rehydrated and where the run is resuming from — one line, always.** A resume is
  never silent. It is never automatic either: the rep chose this card at selection, and nothing in
  this step selects, ranks or advances on its own.
- **Triage silence, disambiguated by phase.** Phase resolves the ambiguity silence carries on its
  own. At `planned`, silence means triage **never reached** that card, so the full re-triage the
  jump performs is the correct reading. At `triaged` or later, silence means the rep **deliberately
  passed over** it, and the standing per-task semantics hold exactly as written below — never
  handled, never re-asked, recapped in Step 5.
- **(e) Restart — on the rep's explicit ask only.** Never inferred from a (b) mismatch, which asks
  rather than acts. On that ask, re-run `work-account` in full for the item: its Step 9 RECORD WORK
  **rewrites** the existing record rather than adding a second one — that rule is authored there and
  is not restated here. A same-date restart **overwrites** the same-date tasks file; latest
  synthesis wins, consistent with every other same-date artifact in this corpus.
- **A resume never re-dates the plan.** Because no synthesis runs on a resume, the `plan_date` file
  stays the item's latest-dated tasks file — so the standing latest-dated authority rule targets it
  naturally, and SET-STATUS, APPLY-EDIT and MARK-HANDLED all land on the right file with no
  special-casing anywhere. A new dated tasks file appears **only** through an explicit restart.

**3.5 — PLAN TRIAGE (one comparative gate on the whole plan).** Runs on the one selected item
after `work-account` hands back its plan, before EXECUTE TASKS. Triage is a breadth decision —
keep, kill, or fix, made with every task visible at once:

- Collect every verdict in **one** pass: assemble `checkpoint_view = { items: <all retained tasks,
  in priority order — never the dropped set>, open_questions: [] }` (`item = { task_id, title,
  rationale, evidence, kind: task }`) and make a **single** `review.collect(checkpoint_view)`
  call.
  - This call is the plan's first rep-facing surface — no separate plan render precedes it.
  - **Zero retained tasks → make no call and render nothing** (never present an empty
    checkpoint); continue to Step 4 with an empty walk.
- **Fan out the returned `item_verdicts[]` in priority order** — P1 first, ties by task id — so
  the appended feedback lines are reproducible for a given submission:
  - **Accept** → one `capture-feedback` line.
  - **Reject** → one `capture-feedback` line; nothing is executed; the task stays in the plan with
    its verdict on record (removal only on the rep's explicit ask).
  - **Edit** (free-text) → apply via `apply-edit` (work-account Step 15): the plan file is
    rewritten first, and the one `edit` line is logged only on success.
  - **No verdict** — the rep left that card untouched → write nothing for it (see Invariants —
    silence); it is never handled.
  - Each task's fan-out is **independent**: a plan-file write failure on one edit is surfaced,
    that `edit` is not logged, and the remaining verdicts still fan out.
- **Re-confirm an edit in proportion to what it changed:**
  - An edit that changes **what the task is** — its scope or its deliverable (e.g. "make this a
    proposal instead of an email", "cover the security review too") → one **single-item**
    `review.collect` call for that one re-shaped task, and its verdict is handled like any other.
  - Every other edit — a wording tighten, a narrowed ask (e.g. "tighten the ask to one
    sentence") → one terse confirmation line in chat, and nothing more.
- Confirm the pass tersely when the fan-out completes, then invoke `advance-phase(…, triaged)` —
  **regardless of how many verdicts came back**, zero included, and on the zero-retained-tasks
  branch above that made no call and rendered nothing. The pass happened; the cycle moves. Only
  then does Step 4 begin.

**4 — EXECUTE TASKS (accepted only, sequential, type-dispatched).** Runs on the one selected
item after the Step 3.5 triage, before NEXT STEPS:

- Open the beat by filtering the retained tasks to those with a triage accept on record —
  accept or accept-after-edit. That subset is the walk's whole input; a task with no accept is
  never handled.
- Walk that subset strictly sequentially in priority order, P1 first, ties by task id. Finish
  one task (handling done, outcome narrated tersely) before touching the next; never fan out,
  never pre-generate an artifact before its task's turn.
- At each task's turn: resolve the task's handling per the registry row. The Step 3.5 accept
  **is** the gate; there is no second one.
- **Before handling, check `handled_on`. Set → skip the task with one terse line** ("t2 — already
  handled 2026-08-01") **and do not invoke its handler.** The marker says the loop already gave this
  task its turn in this cycle, so handing it to a handler a second time would spend the turn twice.
  The task **still appears in the Step 5 recap with its outcome** — a skip is never a silent
  omission. An accepted task with no `handled_on` is walked exactly as normal. The test is
  `handled_on` and nothing else: never `status`, which is rep-declared and tracks a different fact
  entirely, so a task can carry a handled marker and still read `not-done`. This rule names **no**
  task type, which is what keeps it correct for every handler the registry can dispatch — the ones
  in this corpus and the ones a client pack adds.
- When the turn ends, invoke `mark-handled(namespace, slug, source_task.id)` — whether the handler
  produced an artifact **or** no-oped cleanly on its trigger contract. The turn was spent either
  way, and that is the whole fact the marker records. For a `once-per-run` type whose siblings fold
  into the one artifact, each folded sibling is marked at its own turn. Never invoke it for a
  `define-only` task, a rejected task, or a task with no verdict — none of them takes a turn.

**Registry dispatch (point, don't copy).** `type` is the dispatch key. At each task's turn,
resolve the task's handling from its row in `task-registry.md` Part A:

- An **`execute`** row → invoke the row's named handler per its `invocation` policy.
- A **`define-only`** row → **not walked**: the task takes no turn and gates nothing here; it
  surfaces in the Step 5 recap as a categorized, rep-owned action item.
- A `type` with **no row** → the registry's unknown-type rule (define-only, surfaced honestly) —
  never invent a handler, an artifact, or a type.

The registry is the sole statement of the type set and its per-type facts; this loop restates
none of them.
- **Define-only accepted tasks are recapped, not walked.** The Step 3.5 batch pass *is* the read
  — a second stop here would buy nothing. After triage the task stands documented in the plan and
  is the rep's to execute (see Invariants); `proposed_action` is recorded intent, not a trigger;
  the Step 5 recap carries it as a rep-owned action item.
- **Rejected and no-verdict tasks are never walked.** Each one's outcome is narrated in the
  Step 5 recap — never silently skipped — and it stays documented in the plan with its verdict
  on record (removal only on the rep's explicit ask).
- **Execute: `followup_email` → `draft-followup`.**
  - Invoke exactly once per run, at the highest-priority **accepted** `followup_email` task
    (accept or accept-after-edit) — a rejected or unmarked one earlier in the order never
    claims the invocation.
  - Pass `selected_item`, the full `work-account` output (read-only grounding), and that task as
    `source_task`.
  - Any lower-priority accepted `followup_email` task folds into the same single email (one
    email per item per run) — at its turn, confirm it is covered, mark it handled, and move on.
  - The email's content contract — the questions, the content, and the next steps including the
    meeting ask — is `draft-followup`'s (see it); the loop restates none of it.
- **At the walk's close**, invoke `advance-phase(…, executed)` — **including with an empty accepted
  set**, when nothing was walked at all. An account whose plan the rep rejected wholesale is done,
  not stuck.

**5 — NEXT STEPS (close-out).** Runs on the one selected item, after the task-execution loop,
before session end. Single-threaded, never fans out. The plan review already happened at Step 3.5 —
do **not** re-review tasks here.

- **Next step (headline).** Read `work-account`'s `next_step` and present it first and
  prominently as the single forward-moving action.
  - `{ proposed: true, description }` → "**Next step:** <description>", with suggested timing
    only where the call/context supports it.
  - `{ proposed: false, reason }` → "**No next step** — <reason>." State it honestly; never
    manufacture a step or a date.
- **Outcome recap.** One terse line per ranked task carrying its triage verdict (accepted /
  edited / rejected / no verdict) **and** its execution result: for the walked `followup_email`
  task, the draft filename; for an accepted define-only task, an explicit rep-owned action item
  (this is where it surfaces — it took no turn in the walk); for a rejected or no-verdict task,
  its outcome stated plainly, never silently skipped. No re-ranking, no re-presenting of full
  task bodies, no re-review — the review already happened at Step 3.5.
  - **A carried task names its origin on that same line** — the plan date it came from and its
    carry count, read off the `carried_from` block the plan carries ("carried from 2026-07-28,
    2nd carry"), alongside the verdict and execution result every other task gets. A carried task
    is **never** silently omitted from the recap: it is old work resurfacing, and how long it has
    been resurfacing is the fact the rep is owed. This is one more clause on the line, not a
    second presentation of the task — the no-re-review rule above is unchanged.
  - **A prior task whose turn the loop already spent gets a reminder line and no card.**
    `work-account`'s carry matrix emits no task for that case and hands its reminders back with
    the plan; state each as one line naming the **turn date** — "given its turn 2026-07-28 —
    draft `2026-07-28-email.md`, not marked sent" — and name an artifact file **only** where the
    handback names one, degrading to "given its turn 2026-07-28 — no artifact written" where it
    does not. Never derive an artifact claim from the marker alone: `handled_on` is set for a
    clean handler no-op too (Step 4), so it says the turn was spent and nothing more.
    - **Informational only:** no `review.collect` call, no verdict, no `capture-feedback` line;
      silence has no meaning here. It stays prose because a card would invite an accept that
      re-drafts what the spent turn already produced.
- **Act-ready draft + its verdict — one combined gate.** When the loop produced an email draft,
  the draft and the decision on it arrive on the **same** surface; no separate checkpoint follows
  it:
  - Present and collect in one call: the logical `render.email_draft(draft_view)` capability
    (`draft_view = { to[], subject, body, filename }` from the persisted draft file) both renders
    the draft — mail-client preview on UI-capable runtimes, the cited filename + draft body in
    chat otherwise (filename cited either way) — and returns the draft's `item_verdict`. The
    draft's `task_id` is its `source_task`.
  - **On a resume, a standing verdict covers this beat.** When the rehydrated verdict set already
    **covers** the draft's `source_task` — covers meaning it holds at least one line for that
    `task_id` — **skip the verdict beat** and **cite the standing verdict in the recap** rather than
    collecting a fresh one. The draft is **still presented and its filename still cited** either
    way; only the ask is dropped. With no covering line, the beat runs exactly as below.
    - Own the consequence rather than leaving it to be discovered. Because the draft's `task_id`
      **is** its `source_task`, a triage accept on the source task and an output-gate verdict on its
      draft are keyed to the *same* `task_id`, and nothing on disk distinguishes them — so a resume
      that lands here at `executed` treats the triage accept as covering the draft, and the output
      gate is not re-run. That is the deliberate reading of *never re-ask a question the rep already
      answered*: the rep accepted this work once inside this cycle, and an interruption is not a
      reason to re-litigate it. A fresh verdict stays available the moment the rep asks for one —
      the log is append-only and the latest line per `task_id` wins.
  - State explicitly it is a draft only — nothing sent or queued. The verdict controls are not a
    send affordance.
  - Map the returned `item_verdict` to exactly one outcome:
    - **Accept** → one `capture-feedback(namespace, slug, task_id, verdict, note)` line; the loop
      ends.
    - **Reject** → one `capture-feedback` line; the loop ends. `status: draft` preserved either
      way.
    - **Edit** (free-text) → apply via `apply-draft-edit` (`draft-followup` Step 8): the draft
      file is rewritten first, the one `edit` line is logged only on success, and the revised
      draft is re-rendered with its verdict controls — then collect a **fresh** verdict on it.
  - The edit cycle repeats until accept or abandon and is **rep-bounded by construction** — each
    cycle takes a rep turn, so there is no agent-side iteration and no cap to invent. Exactly one
    `capture-feedback` line per cycle, append-only.
  - **Silence after a re-render ends it:** write nothing further, leave the draft at its last
    applied state, and state that in the recap as abandoned — never as accepted.
  - When no draft exists, present nothing here.
  - **Open questions + qualification gaps stay one in-chat beat.** Assemble one
    `checkpoint_view = { items: [], open_questions: <work-account Step 5 list>,
    qualification_gaps: <crm_update.qualification.gaps[] or []> }`. When either list is
    non-empty, make exactly one logical `review.collect(checkpoint_view)` call carrying both;
    when both are empty, skip the call entirely — never present an empty checkpoint.
    On an `executed` resume, use the gaps from Step 3.2's by-name Step 6.5 re-derivation, so an
    already-persisted answer is never re-asked and only remaining gaps appear.
    Surface returned `open_answers[]` in chat and hold them in-session — write nothing for
    them. Each returned `qualification_answer` with a non-empty `answer` is an account fact:
    route that entry through exactly one `capture-qualification(namespace, slug, answers[])`
    invocation (a singleton `answers[]` for that entry). An empty answer or an unanswered gap
    invokes nothing and writes nothing. The checkpoint only collects; it never writes either
    answer kind itself.
    - An explicit rep-stated qualification fact during close-out may route through the same
      `capture-qualification` procedure by name. Step 18 owns its ambiguity and rep-driven-only
      rules; this is never volunteered as a second structured ask.
- **CRM Updates — final sub-beat.** After the email-draft verdict beat completes, invoke
  `write-crm` with the in-memory `crm_update` object `work-account` handed back (the same in-memory
  channel `next_step` rides) plus the selected item's `(namespace, slug)`. `write-crm` owns the
  sub-beat's persist and render: on its simulate path it persists
  `drafts/YYYY-MM-DD-crm-update.md` and renders via `render.crm_update`. Which path it takes is
  `write-crm`'s to resolve, never the orchestrator's to assume.
  - The orchestrator does **not** render or persist the CRM update inline — that is `write-crm`'s
    job. It hands off the object and lets `write-crm` complete the sub-beat, then continues.
  - **No verdict here:** this sub-beat captures nothing — no `review.collect` call, no verdict, no
    `capture-feedback` line; silence has no meaning here. `write-crm` owns its own render and any
    conversation it needs with the rep; the orchestrator adds no verdict surface and reads none. The
    email-draft verdict and open-questions flows above are unchanged by this sub-beat.
  - **On a resume this sub-beat is unconditional** — `write-crm` runs whatever was skipped above,
    and runs on the `crm_update` object the resume re-derived. Its same-date artifact is rewritten
    in place, so re-running it after an interruption is safe, and running it is the only way the
    close-out completes. Being unconditional is why the beat **repeats work rather than inheriting
    decisions**: `write-crm` re-derives and re-presents on every resume and never treats a previous
    run's outcome as already settled.
  - Immediately after `write-crm` hands back, invoke `advance-phase(…, closed)`. That is the
    cycle's terminal transition and the one beat at which this item's events flip; nothing else in
    this step advances the cycle.
- On request: route dropped-set inspect to `work-account` Step 12; promote to Step 13 (see
  Invariants — never volunteer).
- Confirm each captured verdict tersely.

**6 — Advance `last_run` at session end.**

- Advance exactly once, at session end — never mid-run. The precondition: the slate was fully
  presented and selection resolved, where "resolved" means the rep selected an item, the rep
  explicitly declined or deferred every item, or the slate was empty (nothing to select). All
  three paths advance.
- Write the exact `discovery_until` scalar handed to slot 1, verbatim. Do not read the clock again,
  reformat, truncate, normalize its offset, or derive a replacement at commit time.
- Write only `last_run` in `state/run-state.yaml`; do not touch
  `timezone` or any event record. Advancing `last_run` past an un-worked event costs nothing now:
  its `external_ref` is durable, so `fetch-transcript` recovers it whenever the rep gets to it.

## Writes

- `state/run-state.yaml` — advance `last_run` only, at session end; Step 6 defines the value.
- Orchestrates (does not itself author) the Step 1.5 managed apply's writes — the three `company/*` files plus run-state's `context_stamp` and `context_applied_at` — owned by `managed-context-apply` and invoked there directly.
- Orchestrates (does not itself author) the selected item's `context.md` on first encounter
  (`bootstrap-context`), the upserted `events` records (`build-slate`), `feedback-log.jsonl`
  appends, the plan-file rewrites, and the worked item's cycle record and its close-out flip, plus
  qualification-answer updates to the account's `context.md` — those writes live in
  `work-account`'s `capture-feedback` / APPLY-EDIT / promotion / SET-STATUS / ADVANCE-PHASE /
  MARK-HANDLED / CAPTURE-QUALIFICATION, each invoked here by name — plus the draft file
  `draft-followup` owns (its DRAFT phase and its `apply-draft-edit` rewrite) and the simulated CRM
  draft `write-crm` owns.

## Invariants

- **Narration discipline — the discovery half runs silent.** Step 1 and composition slots 1–3
  (`discover-events` → `classify-work` → `build-slate`) emit **no** rep-facing narration: no
  state-validity line, no `last_run` echo,
  no framing sentence, no per-step status, no "Let me…" preambles, no demo/fixtures commentary,
  no tool-by-tool play-by-play. The first rep-facing output of a normal run is the slate. Exactly five pre-slate
  outputs stay loud: Step 1 stop conditions, a `discover-events` source-binding failure, an
  ambiguous-classification ask in `classify-work`, the empty-slate "nothing new since
  `<last_run>`" line, and Step 1.5's two apply reports where they name something. Silence covers the happy path only — it never suppresses an error.
- **Managed context is applied, never negotiated.** Step 1.5 takes no verdict, renders no widget, makes no `review.collect` call, and offers the rep no way to decline — the ownership rule that licenses this is `setup-unbound`'s to state. It is never a reason a rep cannot work: an unreadable `STAMP` is read as unmanaged rather than surfaced as a parse error, and an apply that fails part-way leaves `context_stamp` at its prior value for the next run to retry — Step 1.5's continue clause carries the run past both.
- Drafts and plans only, and **nothing leaves the machine that the rep did not approve in this
  session**: no email is ever sent or queued, and the loop itself performs no external action. The
  one place an external write can occur at all is the Step 5 CRM close-out, which `write-crm` owns
  and gates on its own explicit per-payload approval — the orchestrator never sends anything, and
  never carries an approval forward from an earlier beat, item, or run.
- Never name a concrete UI mechanism (ADR-6): call the logical `review.collect` / `render.*`
  capabilities; the runtime resolves them (interactive or in-chat fallback).
- Approval gates execution: the Step 3.5 triage submission is the bar — a task executes only on
  its explicit accept (or accept-after-edit) in that submission; on reject or silence nothing is
  executed — the outcome is narrated, never silently skipped, and the task stays documented in
  the plan.
- **Auto-start guard:** no task is handled and no handler is invoked before the Step 3.5 triage
  submission arrives. Displaying the plan is not a start signal — there is nothing to walk until
  the verdicts are in.
- Silence stays **per task inside a batch**: a task absent from the returned `item_verdicts[]`
  has no verdict; nothing is written for it and nothing is handled for it. One submission carries
  as many verdicts as the rep marked and no more.
- Define-only types are never executed (no draft, no external call) until their registry row is
  switched on.
- **Step 3.2 is read-only.** The resume step writes nothing at all: it reconstructs the plan, the
  evidence, the verdicts and `crm_update` in memory and persists none of them, and it never creates,
  advances or removes a work record. That is what lets its verify branch ask the rep rather than
  act, and it is why the only local write this skill owns is still advancing `last_run` at session
  end.
- Neither PLAN TRIAGE, the task-execution loop, nor NEXT STEPS re-ranks, re-suppresses
  `tasks`/`dropped`, sets task status, or re-runs synthesis; their only writes are the per-verdict `feedback-log.jsonl`
  appends, the `apply-edit`/promotion plan-file rewrites, and the `advance-phase`/`mark-handled`
  cycle writes (all via `work-account`'s shared procedures), plus the email draft `draft-followup`
  owns — written by its DRAFT phase and rewritten in place by its `apply-draft-edit` — and the
  account-only qualification updates `work-account`'s CAPTURE-QUALIFICATION owns. The Step 5
  checkpoint remains a write-free collector: open answers persist nowhere, and qualification
  persistence routes only through that named authority. No new writer exists at either gate.
- **An output edit is applied, not merely recorded.** An `edit` verdict on the produced draft
  rewrites the draft file via `draft-followup`'s `apply-draft-edit` before anything is logged; on
  a draft-file write failure the failure is surfaced and the `edit` is never logged. Nothing is
  sent, queued, or renamed by an edit — the write boundary is unchanged.
- Silence is not a verdict: wherever a verdict is collected, no rep reaction → write nothing.
- Never volunteer the dropped set or a promotion — rep ask only.
- Verdict/promotion/apply-edit write failures are surfaced in chat; on a plan-file write failure,
  the `edit` is never logged.
- **Evidence recovery is window-independent.** Slot 4 recovers from durable `pending` records, so an
  account discovered in an earlier run — now sitting behind `last_run` and therefore never
  re-discovered — is still fully recoverable and still yields a grounded plan. That guarantee is
  what licenses retrieving nothing before selection. `fetch-transcript` states how the recovery
  works; this loop restates none of it. An empty `evidence[]` on an item that has pending events is
  a fault to surface, never a normal outcome.
- **The watermark never advances beyond discovery coverage.** Every successful advance writes the
  exact fixed `discovery_until` that bounded slot 1; activity after that cutoff remains strictly
  after the next run's `last_run`, including activity arriving during triage, execution, or
  close-out.
- Missing evidence is surfaced, never silently dropped, and never blocks: an event whose evidence
  could not be recovered stays selectable and stays in the plan with its gap surfaced. Which
  failures produce a gap, and how each source degrades, are `fetch-transcript`'s to state — read
  them there.
- **`unknown` is not `missing`.** A call the run has not fetched carries `evidence_status: unknown`
  in `events`, and that is what "we have not looked yet" honestly means. It is never rendered as
  `present`, never rendered as `missing`, and never fabricated into either — `build-slate` owns the
  slate consequence, `fetch-transcript` owns the resolution.
- The CRM Updates sub-beat's failure handling is `write-crm`'s: a simulate-branch write failure
  renders from the in-memory `crm_update` object with the failure surfaced; a generation failure
  (empty/absent object) becomes one honest line ("no CRM update this run — <reason>"). In both
  cases NEXT STEPS completes and Step 6's `last_run` advance proceeds unaffected — the sub-beat
  never blocks close-out.
- `capture-feedback` is referenced by name (authored in work-account), never re-authored here. So
  are `advance-phase`, `mark-handled`, `capture-qualification`, and the Step 6.5 CRM evaluation
  Step 3.2 re-derives on a resume: this skill names the beat each one attaches to and restates no
  clause of any of them.

---

## Bundled run order (Cowork)

> This skill is the **bundled** Cowork build: the eight in-loop downstream steps of the composition
> seam are shipped as numbered `resources/` files in this same skill folder and loaded **in order**
> as each phase is reached (progressive disclosure). Do **not** wait for a separate skill to be
> routed — open the next resource file yourself. All file paths (`state/`, `company/`,
> `accounts|projects/`) are relative to the working directory Cowork is operating in (the `unbound/`
> tree).
>
> **Side entry (rep-invoked only):** `resources/side-collect-tasks.md` — cross-item task roundup.
> Never auto-run; invoke only when the rep explicitly requests it. Not part of the single-item loop.
>
> **Managed-context apply (Step 1.5, shared resource):** `resources/managed-context-apply.md` —
> invoke it directly and in full; it is the sole owner of detect/compare/apply/stamp/report and the
> sole writer of `company/*`, `context_stamp` and `context_applied_at` on the managed path.
> `setup-unbound` bundles the identical byte-for-byte copy for its own step 0 — never invoke that
> skill by name from here.
>
> **CRM close-out apply (slot 8, internal):** `resources/8-write-crm.md` — the CRM close-out apply
> step invoked by Step 5's NEXT STEPS close-out (row 10) with the in-memory `crm_update` object.
> Open it yourself at the close-out CRM sub-beat; it owns the draft persist + the
> `render.crm_update` render on its live simulate path (nothing written externally — that file's
> own procedure is authoritative). The numbered slot-8 close-out step; never rep-invoked directly.
>
> **Task-type registry:** `resources/task-registry.md` — the canonical, closed set of task types
> with each type's `mode` (`execute` | `define-only`), handler, invocation policy, and expected
> `proposed_action` (Part A), plus the Handler Contract every execute handler honors (Part B).
> Resolve any task-type question from that file; no type list in this map is authoritative.

| # | Phase | Procedure to follow | Notes |
|---|-------|---------------------|-------|
| 1 | Set up (silent) | *(this SKILL.md, Steps 1 and 1.5)* | Hydrate the working tree, then read `state/run-state.yaml` and resolve the optional `scan_window` (absent/`now` ⇒ unbounded to now; `<n>h`/`<n>d` ⇒ window capped at now; unparseable ⇒ STOP, surface, never guess) **silently** — no `last_run` echo, no framing sentence, no status line. The discovery half runs silent through slot 3; the window appears to the rep only with the slate (row 4), not before it. If run state is missing/invalid, STOP and surface — do not invent it. **Then Step 1.5's managed-context beat:** invoke `resources/managed-context-apply.md` directly and in full; no `resources/context/STAMP` in this bundle ⇒ the beat ends in silence and nothing below changes; a `STAMP` differing from run-state's `context_stamp` ⇒ the resource applies the team's context and this skill persists on success. It never blocks, never asks, and speaks only to name a replaced local edit or a stage rename's orphaned accounts. |
| 2 | Discover events | `resources/1-discover-events.md` | Resolve logical capabilities via `resources/tool-bindings.md`. |
| 3 | Classify work | `resources/2-classify-work.md` | Route to `accounts/` or `projects/`; assign/reuse slug. Routes on event metadata — no evidence has been fetched yet. |
| 4 | Build slate | `resources/3-build-slate.md` | Upsert the `events`; present the annotated slate via the logical `render.slate` capability (interactive card grid on rich-UI runtimes, plain annotated lines otherwise — resolved in `resources/tool-bindings.md`). A newly-discovered call is `evidence_status: unknown` and its card carries no recording clause. |
| 5 | Select | *(this SKILL.md, Step 3)* | Rep picks exactly one item; defer the rest (single-threading). **Nothing has been retrieved up to this point** — rows 2-4 issue no transcript or thread fetch at all. |
| 6 | Recover evidence | `resources/4-fetch-transcript.md` | The run's only evidence retrieval, for the selected item alone. Resolve `transcript.get` and `email.get_thread` via `resources/tool-bindings.md` (native Granola MCP connector for transcripts, read-only). Input is the item's durable `pending` events, so an event behind `last_run` recovers exactly like one found minutes ago. `missing` is first-class. |
| 7 | Bootstrap context | `resources/5-bootstrap-context.md` | Create `context.md` only if absent, grounded in the evidence just recovered. Selected item only. |
| 8 | Work the item | `resources/6-work-account.md` | REFERENCE → SYNTHESIZE (→ prioritize/etc. per that skill). |
| 9 | Plan triage, then execute tasks | *(this SKILL.md, Steps 3.5 and 4)* | **One comparative gate on the whole plan first (Step 3.5):** a single **batch** `review.collect` call carrying every retained task, each card carrying its own Accept / Reject / free-text edit controls (triage card stack on rich-UI runtimes, in-chat prompt otherwise — resolved in `resources/tool-bindings.md`). One submit returns every verdict; fan out in priority order — one `capture-feedback` line per verdict, an edit applied to the plan file first via work-account's APPLY-EDIT then logged, an untouched card writing nothing at all. **Then walk accepted, executable tasks only (Step 4)**, sequentially P1 first, with no second gate — the triage accept is the gate. Only `followup_email` executes today → follow `resources/7-draft-followup.md` at that task's turn (one email per item per run, covering questions / content / next steps incl. meeting availability); every other type is define-only per `resources/task-registry.md` — not walked, recapped as a rep-owned action item. |
| 10 | NEXT STEPS | *(this SKILL.md, Step 5)* | Close-out (no task re-review): lead with the prescribed `next_step`, terse per-task outcome recap, then present the act-ready email draft via the logical `render.email_draft` — now **render/capture**: the preview carries its own Accept / Reject / free-text-edit footer (or the cited filename + body in chat with the same three verdicts invited there), so the draft and the decision on it are **one surface** and no checkpoint card follows it. An **edit is applied, not merely recorded** — `resources/7-draft-followup.md`'s `apply-draft-edit` rewrites the draft file first (bounded to recipients / subject / body; nothing sent, queued, or renamed), logs one `edit` line only on success, and re-renders for a fresh verdict, looping until accept or abandon (one log line per cycle, rep-bounded). Any open questions are collected separately via the logical `review.collect` (in-chat free text; skipped entirely when there are none); close the CRM sub-beat by opening `resources/8-write-crm.md` and handing it the in-memory `crm_update` object — following that file's own procedure, it applies the update on its live simulate path: persists the simulated draft and renders via `render.crm_update` (informational-only — zero affordances, nothing written externally). All resolved in `resources/tool-bindings.md`; verdicts drive `feedback-log.jsonl` appends (via resources 6/7). |
| 11 | Close | *(this SKILL.md, Step 6)* | Advance `last_run` in `state/run-state.yaml` — the only end-of-session write. |
