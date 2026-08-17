---
name: select-and-resume
description: The run loop's Step 3.2 resume procedure — verifies an interrupted cycle's plan file, rehydrates the plan, evidence and verdicts in memory while writing nothing, counts new events without folding them in, and jumps to the beat the open work record's phase names. Invoked internally by run-unbound at Step 3.2, only when the selected item carries an open work record — never a public entry point.
tier: all
---
# select-and-resume

The resume path of `run-unbound` Step 3.2, stated in full. The orchestrator owns **(a) Detect** —
the `work[]` lookup after selection — and opens this file only when a record is present, so this
procedure begins at (b). The no-record case never opens this file.

## Reads

- The selected item's open `work` record — already in hand from the orchestrator's Step 3.2 detect; this file re-reads nothing to find it.
- `drafts/<plan_date>-tasks.yaml` — read-only, at Step 3.2's rehydrate: the pinned plan of an interrupted cycle, read verbatim and never rewritten from here.
- `state/feedback-log.jsonl` — read-only and additive-only, at Step 3.2's rehydrate: the cycle's standing verdicts, filtered to the item and to the lines whose `ts` is at or after the record's `started_at`. This is the only beat in the run loop that reads the log; every line appended to it is still `work-account`'s `capture-feedback`.

## Procedure

**3.2 — RESUME (pick an interrupted cycle back up at the beat it stopped on).** Runs on the one
selected item after selection, before PLAN TRIAGE. **This step writes nothing at all** — no record
update, no plan rewrite, no log line, no persisted `evidence_status`, nothing. Everything it
reconstructs is held in memory for the rest of the run. That single property is what lets the
mismatch branch below *ask* instead of act, what makes an abandoned resume cost nothing, and it is
why the orchestrator's Writes section is unchanged by this step:

- **(b) Verify (record present).** Confirm `drafts/<plan_date>-tasks.yaml` **exists** and is the
  item's **latest-dated** tasks file. On either mismatch — the file is missing, or a later-dated
  tasks file is present — **surface which of the two fired** and **ask the rep**: finish from the
  later file, or restart. **Write nothing until the rep answers.** Never guess, never silently
  re-plan, never pick a file by inference. The two conditions get distinguishable lines; a rep who
  cannot tell which one fired cannot make the choice being asked of them.
- **(c) Rehydrate (three reconstructions, every one of them in memory).** Each names its own source
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
  - **`crm_update`** — nothing to rehydrate. `close-out` derives it unconditionally at NEXT STEPS,
    on this path and the fresh one alike; the resume carries no variant of its own.
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

  Whichever beat the jump names, enter it through its phase file — `skills/loop/triage-and-execute.md`
  for Steps 3.5 and 4, `skills/loop/close-out.md` for Step 5 — read in full before the beat runs
  (the orchestrator's phase-loading invariant).
- **Say what was rehydrated and where the run is resuming from — one line, always.** A resume is
  never silent. It is never automatic either: the rep chose this card at selection, and nothing in
  this step selects, ranks or advances on its own.
- **Triage silence, disambiguated by phase.** Phase resolves the ambiguity silence carries on its
  own. At `planned`, silence means triage **never reached** that card, so the full re-triage the
  jump performs is the correct reading. At `triaged` or later, silence means the rep **deliberately
  passed over** it, and the standing per-task semantics hold exactly as written in
  `skills/loop/triage-and-execute.md` — never handled, never re-asked, recapped in Step 5.
- **(e) Restart — on the rep's explicit ask only.** Never inferred from a (b) mismatch, which asks
  rather than acts. On that ask, re-run `work-account` in full for the item: its Step 9 RECORD WORK
  **rewrites** the existing record rather than adding a second one — that rule is authored there and
  is not restated here. A same-date restart **overwrites** the same-date tasks file; latest
  synthesis wins, consistent with every other same-date artifact in this corpus.
- **A resume never re-dates the plan.** Because no synthesis runs on a resume, the `plan_date` file
  stays the item's latest-dated tasks file — so the standing latest-dated authority rule targets it
  naturally, and SET-STATUS, APPLY-EDIT and MARK-HANDLED all land on the right file with no
  special-casing anywhere. A new dated tasks file appears **only** through an explicit restart.

## Writes

None. This step performs no write of any kind — see the invariant below.

## Invariants

- **Step 3.2 is read-only.** The resume step writes nothing at all: it reconstructs the plan, the
  evidence and the verdicts in memory and persists none of them, and it never creates,
  advances or removes a work record. That is what lets its verify branch ask the rep rather than
  act, and it is why the only local write the orchestrator owns is still advancing `last_run` at
  session end.
