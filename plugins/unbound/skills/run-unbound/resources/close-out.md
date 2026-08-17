---
name: close-out
description: The run loop's NEXT STEPS close-out beat stated in full (Step 5) — the prescribed next step, the outcome recap (citing each walked task's already-captured verdict), the open-questions and qualification checkpoint, the CRM Updates sub-beat, and the cycle's terminal advance-phase. Invoked internally by run-unbound after the task walk, or at a resume jump to executed — never a public entry point.
tier: all
---
# close-out

The final rep-facing pass of `run-unbound`, stated in full. Opened at NEXT STEPS entry — after the
task walk completes, or when a resume jumps to `executed` — and runs single-threaded to the
cycle's terminal transition. The write boundary stays stated once, in the orchestrator.

## Procedure

**5 — NEXT STEPS (close-out).** Runs on the one selected item, after the task-execution loop,
before session end. Single-threaded, never fans out. The plan review already happened at Step 3.5 —
do **not** re-review tasks here — and any artifact verdict already happened during the walk
(EXECUTE TASKS): it is **not** re-collected here either, only cited in the recap below.

- **Next step (headline).** Read `work-account`'s `next_step` and present it first and
  prominently as the single forward-moving action.
  - `{ proposed: true, description }` → "**Next step:** <description>", with suggested timing
    only where the call/context supports it.
  - `{ proposed: false, reason }` → "**No next step** — <reason>." State it honestly; never
    manufacture a step or a date.
- **Outcome recap.** One terse line per ranked task carrying its triage verdict (accepted /
  edited / rejected / no verdict) **and** its execution result: for a walked task whose handler
  wrote an artifact, that artifact's filename plus its verdict, already captured at the task's own
  turn (see EXECUTE TASKS); for an accepted define-only task, an explicit rep-owned action item
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
- **Derive the CRM evaluation — first, before anything that reads it.** Invoke `work-account`
  **Step 6.5 CRM UPDATE** by name, evaluate-only, over this run's `evidence[]`, the item's current
  `context.md` and `company/process.md`, producing the in-memory `crm_update` object. This is
  **unconditional and identical on every path** — a fresh run, or a resume that jumped to
  `planned`, `triaged` or `executed` — and it happens **exactly once** per close-out: there is no
  inherited object, no second derivation, and no path-dependent variant. It runs *here*, after plan
  triage and the task walk, so the stage recommendation grades what the rep actually decided — a
  criterion that an untriaged card existed to satisfy can no longer be graded before that card got
  its verdict. All three consumers sit below it in this beat: the qualification persist, the
  `checkpoint_view` assembly, and the `write-crm` sub-beat. Because it reads **current**
  `context.md`, a gap answered and persisted before an interruption evaluates `captured`, falls out
  of `qualification.gaps[]`, and is never re-asked. Step 6.5 owns its own clauses; none is restated
  here.
- **Persist the qualification evaluation — first, before the checkpoint.** When the `crm_update`
  object carries a `qualification` block, route its emitted `fields[]` through exactly one
  `capture-qualification(namespace, slug, evaluation)` invocation in evaluation mode. This persist
  runs **before** the `checkpoint_view` assembly below, and therefore before every
  `capture-qualification` call the checkpoint's returned answers make. That order is not
  incidental and is never relaxed: the evaluation's `status: missing` verdict for a field the rep
  is about to answer must land **first**, so the rep's answer overwrites the verdict — never the
  verdict overwriting the answer. An omitted `qualification` block (project, terminal stage, or an
  absent or malformed declaration) routes nothing, writes nothing, and leaves any existing block
  byte-unchanged.
  - **An interruption between triage and close-out costs a recompute, not data.** The evaluation
    is durable only from this beat, so a run that dies before it loses the evaluation — and a
    resume re-derives it and persists it here. No rep-supplied fact is ever at risk, because rep
    answers arrive only at the checkpoint below, which is after this persist. Never "fix" this by
    reinstating the `work-account` ENRICH write: removing it is what makes the ordering above
    safe.
- **Open questions + qualification gaps stay one in-chat beat.** Assemble one
  `checkpoint_view = { items: [], open_questions: <work-account Step 5 list>,
  qualification_gaps: <crm_update.qualification.gaps[] or []> }`. When either list is
  non-empty, make exactly one logical `review.collect(checkpoint_view)` call carrying both;
  when both are empty, skip the call entirely — never present an empty checkpoint.
  Surface returned `open_answers[]` in chat and hold them in-session — write nothing for
  them. Each returned `qualification_answer` with a non-empty `answer` is an account fact:
  route that entry through exactly one `capture-qualification(namespace, slug, answers[])`
  invocation (a singleton `answers[]` for that entry). An empty answer or an unanswered gap
  invokes nothing and writes nothing. The checkpoint only collects; it never writes either
  answer kind itself.
  - An explicit rep-stated qualification fact during close-out may route through the same
    `capture-qualification` procedure by name. Step 18 owns its ambiguity and rep-driven-only
    rules; this is never volunteered as a second structured ask.
- **CRM Updates — final sub-beat.** After the outcome recap and the open-questions +
  qualification checkpoint complete, invoke `write-crm` with the in-memory `crm_update` object
  `work-account` handed back (the same in-memory channel `next_step` rides) plus the selected
  item's `(namespace, slug)`. `write-crm` owns the
  sub-beat's persist and render: on its simulate path it persists
  `drafts/YYYY-MM-DD-crm-update.md` and renders via `render.crm_update`. Which path it takes is
  `write-crm`'s to resolve, never the orchestrator's to assume.
  - The orchestrator does **not** render or persist the CRM update inline — that is `write-crm`'s
    job. It hands off the object and lets `write-crm` complete the sub-beat, then continues.
  - **No verdict here:** this sub-beat captures nothing — no `review.collect` call, no verdict, no
    `capture-feedback` line; silence has no meaning here. `write-crm` owns its own render and any
    conversation it needs with the rep; the orchestrator adds no verdict surface and reads none. The
    open-questions flow above is unchanged by this sub-beat.
  - **On a resume this sub-beat is unconditional** — `write-crm` runs whatever was skipped above,
    and runs on the `crm_update` object this beat derived above. Its same-date artifact is rewritten
    in place, so re-running it after an interruption is safe, and running it is the only way the
    close-out completes. Being unconditional is why the beat **repeats work rather than inheriting
    decisions**: `write-crm` re-derives and re-presents on every resume and never treats a previous
    run's outcome as already settled.
  - Immediately after `write-crm` hands back, invoke `advance-phase(…, closed)`. That is the
    cycle's terminal transition and the one beat at which this item's events flip; nothing else in
    this step advances the cycle.
- On request: route dropped-set inspect to `work-account` Step 12; promote to Step 13 (never
  volunteered — the orchestrator's invariant).
- Confirm each captured verdict tersely.

## Writes

None of its own. The qualification updates belong to `work-account`'s CAPTURE-QUALIFICATION, the
CRM draft and the sub-beat's apply to `write-crm`, and the cycle transition to `advance-phase` —
each invoked here by name; the orchestrator's Writes section and no-new-writer invariant state that
boundary once.

## Invariants

- The CRM Updates sub-beat's failure handling is `write-crm`'s: a simulate-branch write failure
  renders from the in-memory `crm_update` object with the failure surfaced; a generation failure
  (empty/absent object) becomes one honest line ("no CRM update this run — <reason>"). In both
  cases NEXT STEPS completes and Step 6's `last_run` advance proceeds unaffected — the sub-beat
  never blocks close-out.
