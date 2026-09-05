---
name: triage-and-execute
description: The run loop's PLAN TRIAGE and EXECUTE TASKS beats stated in full — one comparative batch verdict pass over the whole ranked plan (Step 3.5), then the sequential, registry-dispatched walk of accepted executable tasks, each gated at its own turn before dispatch (Step 4). Invoked internally by run-unbound when work-account hands back its plan, or at a resume jump to planned or triaged — never a public entry point.
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
keep it, kill it, or fix it, made with every task visible at once:

- Collect every verdict in **one** pass: assemble `checkpoint_view = { items: <all retained tasks,
  in priority order — never the dropped set>, open_questions: [] }` (`item = { task_id, title,
  rationale, evidence, kind: task, mode }`, `mode` read from the task's `task-registry.md` Part A
  row — the same lookup Step 4 filters and dispatches on, resolved once here so the walk and the
  card's rep-owned type pill read one value) and make a **single**
  `review.collect(checkpoint_view)` call.
  - This call is the plan's first rep-facing surface — no separate plan render precedes it.
  - **Zero retained tasks → make no call and render nothing** (never present an empty
    checkpoint); continue to Step 4 with an empty walk.
- The rep's three outcomes are **Accept**, **Reject** and **Edit**, with a free-text edit input
  alongside. This gate shapes the list and decides nothing about execution — every card carries the
  same three, and the affordance vocabulary is the bindings authority's
  (`runtime/tool-bindings.md` `## review.collect`), restated none of it here.
- **Fan out the returned `item_verdicts[]` in priority order** — P1 first, ties by task id — so
  the appended feedback lines are reproducible for a given submission:
  - **Accept** → one `capture-feedback` line; the plan file is not touched. What being kept then
    means is the task's registry `mode` and nothing else: an **`execute`** row enters Step 4's walk
    and meets its own gate at its turn; a **`define-only`** row takes no turn at all — it stands as
    rep-owned work, keeps `status: not-done`, is recapped at Step 5 as a rep-owned action item,
    listed by `collect-tasks`, and carried into the next cycle as a live card (carry matrix row 5).
    A verdict is **never a status write** — the rep-declared `deferred` status is a different fact,
    SET-STATUS's alone.
  - **Reject** → apply via `cancel-task` (work-account Step 15.5): the plan file is rewritten
    first — the task moves out of `tasks[]` into `dropped[]` reading `rejected by rep on <date>` —
    and the one `reject` line is logged only on success. Off the list, not deleted: the rep can ask
    what was dropped and promote it back.
  - **Edit** (free-text) → apply via `apply-edit` (work-account Step 15): the plan file is
    rewritten first, and the one `edit` line is logged only on success.
  - **No verdict** — the rep left that card untouched → write nothing for it (see Invariants —
    silence); it is never handled.
  - Each task's fan-out is **independent**: a plan-file write failure on one edit or cancel is
    surfaced, that line is not logged, and the remaining verdicts still fan out.
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

**4 — EXECUTE TASKS (accepted executable tasks only, sequential, gated at each turn).** Runs on the
one selected item after the Step 3.5 triage, before NEXT STEPS:

- Open the beat by filtering the retained tasks to those carrying **both** a triage `accept` on
  record — accept, or accept-after-edit — **and** a `task-registry.md` Part A row reading
  `mode: execute`. Both tests, every time. That subset is the walk's whole input; a rejected task,
  a `define-only` task, and a task carrying no verdict at all are never walked.
- Walk that subset strictly sequentially in priority order, P1 first, ties by task id. Finish
  one task (handling done, outcome narrated tersely — including its artifact-verdict cycle below,
  where one runs) before touching the next; never fan out, never pre-generate an artifact before
  its task's turn.
- At each task's turn: resolve the task's handling per the registry row. The Step 3.5 `accept`
  admitted the task to the walk; the 4a gate below is what decides whether it runs.
- **Before handling, check `handled_on`. Set → skip the task with one terse line** ("t2 — already
  handled 2026-08-01") **and do not invoke its handler.** The marker says the loop already gave this
  task its turn in this cycle, so handing it to a handler a second time would spend the turn twice.
  The task **still appears in the Step 5 recap with its outcome** — a skip is never a silent
  omission. An accepted task with no `handled_on` is walked exactly as normal. The test is
  `handled_on` and nothing else: never `status`, which is rep-declared and tracks a different fact
  entirely, so a task can carry a handled marker and still read `not-done`. This rule names **no**
  task type, which is what keeps it correct for every handler the registry can dispatch — the ones
  in this corpus and the ones a client pack adds.
- **4a — TASK GATE (this task's own decision, before any handler is invoked).** Make a
  **single-item** `review.collect` call carrying this one task **with its typed `context` block** —
  the depth the batch card withheld — and collect one verdict. Every card the walk reaches offers
  the same four: **Execute**, **Defer**, **Edit** and **Cancel Task**.
  - **Execute** → one `capture-feedback` line; dispatch the registry handler as below.
  - **Defer** → one `capture-feedback` line; no handler runs and `handled_on` stays **absent** —
    the turn was offered, not spent. The task keeps `status: not-done` and lands in the Step 5
    recap as a rep-owned action item, exactly as a define-only task does.
  - **Cancel Task** → apply via `cancel-task`: the plan file is rewritten first — the task moves
    into `dropped[]` reading `cancelled by rep on <date>` — and the one `cancel` line is logged
    only on success. No handler runs.
  - **Edit** (free-text) → apply via `apply-edit`: the task's instructions are rewritten first and
    the one `edit` line logged only on success, then **re-present this card** — re-rendered, never
    appended to, so the rep always sees one current card — and collect a fresh verdict, repeating
    until execute, defer, cancel, or silence. A rewrite that fails is surfaced, is not logged, and
    presents no revised card that was never written.
  - **Silence** → write nothing, run nothing, mark nothing; named per the held-gate rule below, and
    recapped again at Step 5.
- When an **executed** turn ends, invoke `mark-handled(namespace, slug, source_task.id)` — whether the handler
  produced an artifact **or** no-oped cleanly on its trigger contract. The turn was spent either
  way, and that is the whole fact the marker records. For a `once-per-run` type whose siblings fold
  into the one artifact, each folded sibling is marked at its own turn. Never invoke it for a
  `define-only` task, or for a task deferred, cancelled or left silent at 4a — none of them spent
  the turn.
- **Present the artifact and collect its verdict — at this task's own turn, not at NEXT STEPS.**
  When the handler wrote an artifact this turn, present it via its designated render capability
  (`task-registry.md` Part B's Output-edit obligation) — the handler's own more specific capability
  where it names one (`draft-followup` names `render.email_draft`), else the default
  `render.artifact` — and route the returned verdict immediately, before the walk moves on:
  - **Accept** or **reject** → one `capture-feedback` line. The artifact gate keeps the
    accept/edit/reject enum — an artifact is judged, never executed, deferred or cancelled; the
    task verdict already happened at 4a.
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
- **Define-only tasks are recapped, not walked.** The Step 3.5 batch pass *is* the read — a second
  stop here would buy nothing. After triage the task stands documented in the plan and
  is the rep's to execute (see Invariants); `proposed_action` is recorded intent, not a trigger;
  the Step 5 recap carries it as a rep-owned action item. A task **deferred at 4a** reaches that
  same recap by the same words.
- **Rejected, cancelled and no-verdict tasks are never walked.** Each outcome is narrated in the
  Step 5 recap, never silently skipped: a no-verdict task stays documented in the plan, a rejected
  or cancelled one is already in `dropped[]` carrying the reason it left.
- **Execute: `followup_email` → `draft-followup`.**
  - Invoke exactly once per run, at the **first** `followup_email` task the rep verdicts `execute`
    at its own 4a gate (execute, or execute-after-edit) — one deferred, cancelled or left silent
    there never claims the invocation, however high its priority.
  - Pass `selected_item`, the full `work-account` output (read-only grounding), and that task as
    `source_task`.
  - Any later `execute`-verdicted `followup_email` task folds into the same single email (one
    email per item per run) — at its turn, confirm it is covered, mark it handled, and move on.
  - The email's content contract — the questions, the content, and the next steps including the
    meeting ask — is `draft-followup`'s (see it); the loop restates none of it.
- **At the walk's close**, invoke `advance-phase(…, executed)` — **including with an empty walk
  set**, when nothing was walked at all. An account whose plan the rep rejected wholesale, and one
  whose whole plan is rep-owned, are both done rather than stuck. NEXT STEPS then runs through `resources/close-out.md`, read in full before any
  close-out beat renders (the orchestrator's phase-loading invariant).

## Writes

None of its own. Every write these beats drive — the per-verdict `feedback-log.jsonl` appends, the
`apply-edit` plan-file rewrites, the `advance-phase` / `mark-handled` cycle writes, the email draft
`draft-followup` owns — is authored elsewhere and invoked by name; the orchestrator's Writes
section and no-new-writer invariant state that boundary once.

## Invariants

- **Auto-start guard:** no handler is invoked before that task's own 4a `execute` verdict arrives.
  The Step 3.5 submission admits a task to the walk and starts nothing; displaying a plan, or a
  card, is not a start signal.
- **The held-gate rule — ask once, or skip loudly.** A reply that sounds like consent but names no
  offered outcome ("continue", "go ahead", "next") is never mapped to one. At a gate holding an
  **external write**, ask once, in one line, naming both readings and nothing else — "continue =
  skip the deploy, or approve it?" — then hold there; a vague word never fires an external call. At
  a gate holding only **local** work — 4a, an artifact verdict — it reads as move-on, exactly as
  silence does. And any step the run moves past carrying **no verdict**, however it got there, is
  named in the **next** rep-facing message — the step, and what its not happening means — never
  held for the Step 5 recap alone.
- Silence stays **per task inside a batch**: a task absent from the returned `item_verdicts[]`
  has no verdict; nothing is written for it and nothing is handled for it. One submission carries
  as many verdicts as the rep marked and no more.
- Define-only types are never executed (no draft, no external call) until their registry row is
  switched on — which is why a define-only task never enters the walk.
