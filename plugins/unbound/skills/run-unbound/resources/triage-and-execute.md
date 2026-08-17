---
name: triage-and-execute
description: The run loop's PLAN TRIAGE and EXECUTE TASKS beats stated in full — one comparative batch verdict pass over the whole ranked plan (Step 3.5), then the sequential, registry-dispatched walk of accepted tasks only (Step 4). Invoked internally by run-unbound when work-account hands back its plan, or at a resume jump to planned or triaged — never a public entry point.
tier: all
---
# triage-and-execute

The approval and execution beats of `run-unbound`, stated in full. Opened at PLAN TRIAGE entry —
when `work-account` hands back its plan, or when a resume jumps to `planned` or `triaged` (a
`triaged` resume enters directly at Step 4). The approval-gate and write-boundary invariants stay
stated once, in the orchestrator; this file is the procedure they gate.

## Procedure

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
  one task (handling done, outcome narrated tersely — including its artifact-verdict cycle below,
  where one runs) before touching the next; never fan out, never pre-generate an artifact before
  its task's turn.
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
- **Present the artifact and collect its verdict — at this task's own turn, not at NEXT STEPS.**
  When the handler wrote an artifact this turn, present it via its designated render capability
  (`task-registry.md` Part B's Output-edit obligation) — the handler's own more specific capability
  where it names one (`draft-followup` names `render.email_draft`), else the default
  `render.artifact` — and route the returned verdict immediately, before the walk moves on:
  - **Accept** or **reject** → one `capture-feedback` line.
  - **Edit** (free-text) → apply via the handler's own `apply-<artifact>-edit` procedure: the
    artifact file is rewritten first, the one `edit` line logged only on success, the revised
    artifact re-presented, and a fresh verdict collected — repeating until accept, reject, or
    silence.
  - **Silence after a render** → write nothing further; the artifact stays at its last applied
    state, narrated as abandoned, never as accepted.
  - The handler wrote no artifact (a clean no-op) → skip this beat entirely, no render call — the
    same "when no draft exists, present nothing" invariant every render capability already
    follows, now stated for any artifact.

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
  not stuck. NEXT STEPS then runs through `skills/loop/close-out.md`, read in full before any
  close-out beat renders (the orchestrator's phase-loading invariant).

## Writes

None of its own. Every write these beats drive — the per-verdict `feedback-log.jsonl` appends, the
`apply-edit` plan-file rewrites, the `advance-phase` / `mark-handled` cycle writes, the email draft
`draft-followup` owns — is authored elsewhere and invoked by name; the orchestrator's Writes
section and no-new-writer invariant state that boundary once.

## Invariants

- **Auto-start guard:** no task is handled and no handler is invoked before the Step 3.5 triage
  submission arrives. Displaying the plan is not a start signal — there is nothing to walk until
  the verdicts are in.
- Silence stays **per task inside a batch**: a task absent from the returned `item_verdicts[]`
  has no verdict; nothing is written for it and nothing is handled for it. One submission carries
  as many verdicts as the rep marked and no more.
- Define-only types are never executed (no draft, no external call) until their registry row is
  switched on.
