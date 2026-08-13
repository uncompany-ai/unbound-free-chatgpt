---
name: work-account
description: Synthesizes a grounded, prioritized task list for the single selected account or project by referencing its context.md and relevant company knowledge, then emitting evidence-cited tasks. Invoked after the rep selects one item from the slate.
tier: all
---
# work-account

Synthesis step of an Unbound run. Invoked by `run-unbound` after selection produces **exactly one**
item, with one argument `selected_item` (`{ namespace, slug, context_ref, evidence[], event_ids[] }`).
Turns that item into a short, ruthlessly prioritized, evidence-grounded task list; then persists it,
enriches the item's context, and records the item's in-flight cycle. Also authors the shared rep-driven
procedures — `capture-feedback`, verdict capture, dropped-set inspection, promotion, SET-STATUS,
APPLY-EDIT (Steps 10–15) — plus the loop-invoked ADVANCE-PHASE, MARK-HANDLED, and
CAPTURE-QUALIFICATION procedures (Steps 16–18).

## Reads

- `accounts/<slug>/context.md` (or `projects/<slug>/context.md`) — frontmatter, `## Summary`, `## Activity Log`.
- `company/process.md` — canonical stage enum + stage definitions; the current stage's `**Exit criteria:**` bullets and the optional declaration-driven `## Qualification` section are Step 6.5's evaluation inputs.
- `company/messaging.md` — positioning, differentiation pillars, proof points, objection handling; grounds what an email/content task idea should say.
- `rep/voice.md` — voice/tone; grounds how an email/content task idea should sound.
- `company/assets.md` — asset index; informs content (`create_deck`/`create_one_pager`) and `followup_email` task ideas.
- In-memory `selected_item.evidence[]` — the per-`(namespace, slug)` union of grounding artifacts the orchestrator recovered for this slug from its durable pending events:
  - Each entry is `{ event_id, source: "call"|"email", external_ref, occurred_at, kind: "transcript"|"email_body", content, evidence_status, ...source-specific-fields }` (e.g. `call_type`, `title`, `participants[]` for calls; `subject`, `participants[]` for emails).
  - One entry per pending event for the slug — including events discovered in an **earlier** run and recovered by re-fetch, not only this run's. One entry when a single event contributed; two or more when both kinds, or multiple events of one kind, did.
  - `content` is the verbatim grounding payload — transcript text for `kind: "transcript"`, email body for `kind: "email_body"`.
  - An entry with `evidence_status: missing` carries no `content` — see Invariants.
- In-memory `selected_item.event_ids[]` — the ids of exactly those pending events, and the exact set RECORD WORK (Step 9) records and the cycle flips at its close-out. Accept verbatim; never widen it to the slug's other events.
- `state/run-state.yaml` — the item's event records. The run's `timezone` (filename/log dates) is reused in-session from the orchestrator's Step 1 read — see the read-once rule in Step 1 — never a fresh open of this file.
- The item's `drafts/*-tasks.yaml` — latest-dated is authoritative; read as the prior cycle's plan by Step 2's carry evaluation, and by SET-STATUS and dropped-set inspect/promote.
  - The same glob also lists the item's `drafts/`, used only to decide whether a row-4 carry reminder may name an artifact file (Step 2). That listing widens a read already performed; it is not a history read — no tasks file but the latest-dated one is ever opened.
- `state/feedback-log.jsonl` — read-only, filtered to this `(namespace, slug)`; the **latest line per `task_id`** is that task's standing verdict, Step 2's third carry signal.
  - A **new coupling for this skill**: it authors `capture-feedback` (Step 10) but has never read the log back — today only `run-unbound`'s resume beat reads it.
- Logical capability `render.tasks(task_view)`.

## Procedure

Run Steps 1–9 in this fixed order; Steps 10–15 are later, rep-driven beats, and Steps 16–18 are
shared procedures invoked by name at their owning loop beats. Step 18 also accepts an explicit
rep-stated qualification fact at close-out; it is never volunteered as another ask.
**Reference precedes all synthesis** — no task is produced before grounding is loaded.

**1 — REFERENCE.** Load all grounding before producing any task:

- Load the seven grounding files as **one batch (parallel where supported)** — the item's `context.md` (stakeholders, stage, what was promised, what is open), `company/process.md` (stage enum + what the current stage implies), `company/messaging.md` (positioning, pillars, proof points, objections — what to say), `rep/voice.md` (how the rep sounds), `company/assets.md` (existing assets a task could point at), the item's latest-dated `drafts/*-tasks.yaml` (the prior cycle's plan, with the same glob's `drafts/` listing), and `state/feedback-log.jsonl` filtered to this `(namespace, slug)`. They are mutually independent: every path resolves from the selected item's own slug or a fixed location, never from another read's content, so none waits on another and the load costs about one read rather than seven.
- Batching moves **when** the seven reads are issued, never what the step guarantees: REFERENCE is not complete, and Step 2 does not begin, until all seven have landed — see "Reference precedes all synthesis" above.
- An absent, empty, or unparseable prior tasks file does not hold REFERENCE open: land the other six and let Step 2's carry evaluation degrade (see Invariants — failure handling).
- **Read once, then reuse (the read-once rule).** Four of the seven are immutable for the life of the run: the managed apply (`run-unbound` Step 1.5) is the only in-run writer of `company/process.md`, `company/messaging.md`, and `company/assets.md`, and it has already run by the time any item is selected; `rep/voice.md` has no in-run writer at all. They load once, in the session's **first** REFERENCE batch; every later consumer — a later selected item's REFERENCE, `draft-followup`'s MATCH-ASSET and DRAFT — reuses this session's load rather than re-opening them. The per-item three (`context.md`, the prior tasks file with its `drafts/` listing, the feedback log) are per-item state and stay freshly read each selection. The run's `timezone` follows the same rule: read by `run-unbound` at its Step 1, written by nothing until the run ends, it is reused in-session wherever a later beat needs a date — never a reason to re-open `state/run-state.yaml`.
- Hold `selected_item.evidence[]` ready as the primary source of what was said / written.
- Iterate every evidence entry as a peer grounding source: call transcripts and email bodies carry equal weight, not a primary/secondary hierarchy.
- Treat each `content` payload as verbatim signal — do not paraphrase, truncate, or normalize.
- With two or more entries for the slug, treat the union of their `content` as one grounding pool; the plan must cohere across all of it.
- An `evidence_status: missing` entry contributes no `content` — synthesize from the remaining grounding (see Invariants).

**2 — SYNTHESIZE.** Derive candidate actions and emit them as `tasks[]` in the canonical task
schema (below):

- Emit **all** sound candidates here — the 80/20 cut is Step 3's job, not this step's.
- Cite as you go: ground every task in some evidence entry or in `context.md`.
- Where an action is sound but un-cited, set `evidence` to the `inferred: <reasoning>` marker (see Invariants).
- Type each candidate from the canonical type set in `task-registry.md` (Part A) — the registry is the type authority — honoring each row's `when` precondition, which states when that type is the right typing for an observed action. Where two rows' preconditions both fit and neither settles it, type the likelier candidate and name the competing type in that task's `rationale` (Step 4), so the rep meets the tie at triage; never resolve a sibling tie silently.
- A sound action that fits no registry type is emitted as `internal`, never as an invented type.
- Admit the prior cycle's unfinished work as candidates **alongside** the evidence-derived ones: classify every task in the prior plan through the carry matrix below and emit the ones it carries.
- A carried candidate is a **re-presentation, not a re-synthesis**: nothing about it is re-derived here, and Step 4 copies its fields rather than authoring them.
- Never emit a scheduling task: a needed call/meeting is Step 6's `next_step`, folded into the follow-up email by `draft-followup` (meeting ask + attendee availability).
- If the union of all evidence warrants no clear action, emit a short or empty list (see Invariants — honest empties).

**The carry matrix.** Classify each task in the item's latest-dated prior `drafts/*-tasks.yaml` on
three signals and nothing else: the rep-owned `status`, the loop-owned `handled_on`, and the task's
**standing verdict** — the latest `feedback-log.jsonl` line for its `task_id` under this
`(namespace, slug)`. Rows are evaluated **in this order, first match wins**:

| # | Prior task state | Outcome |
| --- | --- | --- |
| 1 | `status: done` | **Drop.** The rep declared it finished; never carried. |
| 2 | standing verdict `reject` | **Drop.** A reject is durable — re-proposing it is nagging. |
| 3 | `status: deferred` | **Suppress:** one `dropped[]` entry reading `carried, deferred by rep on <date>`; never a plan card, and recoverable via PROMOTE (Step 13). |
| 4 | `handled_on` set + `status: not-done` | **A reminder line only, never a task** — the loop already spent this task's turn (wording rule below). |
| 5 | standing `accept` (or accept-after-edit) + no `handled_on` + `status: not-done` | **Carry as a task.** The rep took it on and it is not finished. |
| 6 | no standing verdict + no `handled_on` | **Carry as a task.** Silence is not a verdict: it still means never handled, and now also means never lost. |

- Rows 1 and 2 are the only drops; row 3 is the only write to `dropped[]`; rows 5 and 6 are the only rows that produce a plan card; row 4 produces prose and nothing else.
- Two ordering rules carry the matrix. A task that is both `done` and `reject`ed resolves at **row 1** — the rep finished it whatever they said at triage. And `handled_on` is tested **before** the verdict rows, because the loop having spent the turn is the stronger fact.
- The matrix names **no task type and consults no registry field** — not even `mode`. Row 4 can only ever match an `execute` type **by construction**: `run-unbound`'s task-execution loop and MARK-HANDLED (d) both forbid writing `handled_on` for a `define-only` task, so a `mode` test would be redundant.
  - Row 5 therefore covers **both** rep-owned `define-only` work **and** an `execute` task whose turn never came — an interrupted walk, or a surfaced ADVANCE-PHASE failure the session continued past (Step 16(e)). A `mode`-aware row 4 would leave that state matching no row at all.
  - A client pack flipping a type from `define-only` to `execute` therefore changes nothing about carry behavior.
- **Row 4's reminder never asserts an artifact.** `handled_on` is set for a clean handler no-op too (see the schema below), so the line is phrased from the marker: it states that the task took its turn on `<date>`.
  - Name an artifact filename **only** where Step 1's `drafts/` listing attributes a file to that task unambiguously — a draft dated `handled_on` that no other task's turn also claims. A clean no-op names none, and so does an ambiguous listing.
  - Emit **no** in-memory task for row 4 and render nothing: hand the reminder's content back with the plan for `run-unbound`'s recap to state. A card would invite an accept that re-drafts, which is what row 4 exists to prevent.
- A prior file that parses but resolves no standing verdicts is not a degradation: every task falls to row 6 and carries, which is the conservative direction. An absent, empty, or unparseable file is (see Invariants — failure handling).

**3 — PRIORITIZE (80/20).** Reduce the candidates to the few highest-leverage actions:

- Emit a short `tasks[]` ranked by `priority` (1 = highest).
- Record **every** suppressed candidate in `dropped[]` with a brief reason.
- Partition exhaustively: each candidate lands in exactly one of `tasks`/`dropped` — never silently drop.
- Over-suppression is the dangerous failure: when genuinely unsure an action is critical, keep it in `tasks`; anything cut must appear in `dropped`.
- A **carry-in bypasses the cut** and always lands in `tasks[]`. It survived this cut once already and the rep accepted it; and because `dropped[]` is never volunteered (Step 12), re-cutting it would discard it invisibly — recreating the loss the carry matrix exists to close.
  - The cut still governs every evidence-derived candidate exactly as above, and the exhaustive partition holds: a carry-in lands in `tasks`, so it is still in exactly one place.
  - A row-3 carried-deferred entry joins `dropped[]` here carrying the reason the matrix gave it; it is never a candidate for `tasks`.
  - The cost is plan size and the bound is the rep's own verdict, not a cap: every carried card states its carry count on its `evidence` line and meets triage like anything else, where a `reject` kills it permanently via row 2.
  - Recorded alternative, deferred rather than rejected: carry-ins go through the cut and a cut carry-in is named in the recap instead of filed silently. Revisit after the first account worked across several cycles.
- Retained tasks keep their Step 2 fields unchanged.

**4 — RATIONALE + EVIDENCE + CONTEXT.** Annotate **only** the retained tasks — leave `dropped`
alone; add, remove, re-rank nothing. For each retained task, finalize:

- A non-empty, stage-aware `rationale` tying the action to the deal stage / next milestone per `company/process.md` — specific to this item, not boilerplate.
  - For a project, ground the rationale on the project's context + next milestone; never invent a stage.
  - Where Step 2 left a sibling tie unresolved — two registry rows' `when` preconditions both fit and neither settled the typing — the rationale also names the competing type, so the tie reaches the rep on the triage card instead of being resolved silently. No new field: the clause rides in `rationale`, which is required, non-empty, and rep-mutable.
- A non-empty `evidence` value — a source-prefixed citation or the literal `inferred: <reasoning>` marker, cross-checked per the citation discipline (see Invariants).
- A **carried** task is finalized by copying, never by re-deriving: take `title`, `type`, `rationale` and `context` from the prior task **verbatim**, and give it a **fresh** `t<n>` in this plan.
  - Its `evidence` reads `carried from <plan_date> (<task_id>, <n>th carry) · <original evidence value verbatim>` — the prior value survives whole after the separator, source-kind prefix and all.
  - `<n>` is `carried_from.count` and `<n>th` is its ordinary English ordinal — `1st carry`, `2nd carry`, `3rd carry` — never the literal `th`.
  - Exactly **one** prefix, never a chain: when the prior value already carries one, this prefix **replaces** it and the part after `·` is the original citation, not the prior compound. The count states the history, so the line never nests.
  - Re-deriving any of it is what would risk a fabricated citation; the prior value is still true and the fresh id keeps the audit trail through `carried_from` (schema below).
- A typed, grounded `context` block — the documentation of what executing the task requires, by type:
  - `followup_email` → `{ recipients[], asks[] }`; when Step 6 proposes a meeting, also an optional `next_call: { purpose, required_attendees[] }` sub-block (grounded like every other field) — `draft-followup` reads it alongside `next_step` for the meeting ask.
  - `answer_questions` → `{ questions[] }`, aligned to Step 5's final list.
  - `create_deck`/`create_one_pager` → `{ audience, angle, pain_point, source_pointers[] }`.
  - `create_proposal` → `{ audience, scope, pricing_inputs[], success_metrics[] }`.
  - `prepare_demo` → `{ audience, use_case, data_sources[], success_criteria[] }`.
  - `internal` → `{ note }`.
  - Ground every `context` field in the evidence or `context.md`; omit an ungrounded field — the rep fills gaps at `run-unbound`'s in-loop checkpoint, where edits land via APPLY-EDIT (Step 15).

Then **hand the ranked plan back** to `run-unbound` — do not render it here. The plan's first
rep-facing surface is `run-unbound`'s Step 3.5 triage, where each task carries its own verdict
controls; a render at synthesis time would only duplicate it, buttonless, one beat early:

- The handback carries the ranked `tasks`, plus `dropped`, `open_questions`, `next_step`, and `crm_update` — the same in-memory channel as before, with no surrounding narration.
- The `inferred:` marker stays distinct from a citation wherever it is later surfaced.
- The handed-back plan and the persisted `tasks.yaml` describe the same tasks (same content, two surfaces).
- Surface `dropped` only on demand (Step 12); list `open_questions` after the tasks; state `next_step` in one sentence after the open questions.

`render.tasks(task_view)` survives in this skill for **re-renders only** — after SET-STATUS
(Step 14) and after APPLY-EDIT (Step 15) — plus the `collect-tasks` roundup, which uses the same
path. Those cards convey nothing back: status changes remain explicit chat asks.

**5 — OPEN QUESTIONS.** Extract-only:

- Emit `open_questions[]`: questions **actually raised and left unanswered** across all `evidence[]` sources for this slug.
- A question counts only if it was not answered elsewhere in `evidence[]` or in `context.md` — an answered question is not open.
- Boundary: this list is **this run's extraction only**. `context.md` is consulted solely to disqualify an already-answered question, never to source one — carrying a still-unanswered prior question forward is ENRICH's union (Step 8), not this step's.
- Iterate every `evidence[]` entry: questions can come from any source, call or email.
- Phrase each as a clear, self-contained question faithful to what was asked, whatever its source.
- When the retained plan carries an `answer_questions` task, copy the final `open_questions[]` verbatim into that task's `context.questions` — the one permitted alignment write, pre-persist.
- Touch nothing else in `tasks`/`dropped`/`rationale`/`evidence`/`next_step`.

**6 — NEXT STEP.** Decision-only:

- Read stage + the union of all evidence sources + context together.
- Emit `next_step` as **either** `{ proposed: true, description }` **or** `{ proposed: false, reason }` — an explicit none with a reason.
- A proposed step is concrete — often the next call/meeting, which lives here and in the follow-up email, never as a task.
- Suggest timing only where the evidence/context supports it; never manufacture a step or a date to look thorough.
- Touches nothing else.

**6.5 — CRM UPDATE (simulated).** Extract-and-evaluate only. Emit the in-memory `crm_update`
object (schema below) — the field-level update a CRM *would* receive — handed back in-memory for
`write-crm` to apply at close-out (persist + render on its simulate branch; **not** written here).
Touches nothing in `tasks`/`dropped`/`open_questions`/
`next_step`; the recommendation is advisory only (see Invariants — ENRICH is the sole stage
writer). Four blocks:

- **`stage_recommendation`** — evaluate the REFERENCE-time stage (the `stage:` loaded from `context.md` in Step 1, before ENRICH runs) against that stage's `**Exit criteria:**` bullets in `company/process.md`:
  - Enum-validate the stage first — never evaluate criteria against an invented stage:
    - A project (null stage) → `recommendation: not-applicable`, `reason: "project — no sales stage"`.
    - A terminal stage (`closed-won` / `closed-lost`) → `not-applicable`, `reason: "terminal stage"`.
    - An out-of-enum stage → `not-applicable`, carrying the out-of-enum flag's wording.
  - In all three `not-applicable` cases skip the criteria evaluation; `next_step` and `product_gaps` are still produced.
  - Otherwise evaluate each `**Exit criteria:**` bullet against the union of this run's `evidence[]` `content` payloads and `context.md` (Summary + Activity Log).
  - A criterion is `met: true` **only** with a citable basis, recorded per the citation discipline (see Invariants — source-prefixed, cross-checked, unlocatable → `inferred:`).
  - No grounding for a criterion → `met: false`, `evidence: null`; an `evidence_status: missing` entry contributes nothing.
  - **Advancement gate:** recommend `advance` **only when every criterion is `met: true` with a non-`inferred` citation**; an `inferred:` basis is recorded on its criterion but counts as **unmet** for the gate.
    - When advancing, `to_stage` = the next stage in `company/process.md`'s documented order (`discovery → demo → technical-validation → proposal → negotiation → closed-won`).
  - Anything less → `recommendation: no-change` with `unmet[]` listing the outstanding criterion texts verbatim.
  - Only the next sequential stage is ever proposed; skips and reverts are rep judgment, never recommended.
- **`next_step`** — copied **verbatim** from Step 6's object; never re-decided, never reworded. This is the one permitted carry.
- **`product_gaps[]`** — extract-only: iterate every `evidence[]` entry as a peer source and collect the capability gaps, unsupported asks, and feature requests the prospect **actually raised**.
  - Phrase each as a self-contained statement faithful to the source, with a source-prefixed citation.
  - A gap is something the prospect needs that the product/deal cannot currently satisfy — distinct from `open_questions[]` (things to answer) and never duplicated into tasks.
- **`qualification`** — declaration-driven and conditional; emit `{ framework, fields[], gaps[] }` only when the selected item is an account, its REFERENCE-time stage is not `closed-won` or `closed-lost`, and `company/process.md` has one well-formed `## Qualification` section. Qualification applicability is independent of the stage enum: an out-of-enum account stage still evaluates this block even though `stage_recommendation` is `not-applicable`.
  - A well-formed declaration has exactly one non-empty `**Framework:**` line and one or more distinct bold-term field bullets, each with exactly one non-empty `Evidence:` child and one non-empty `Coach:` child. Field text is the verbatim join key; never normalize, case-fold, or fuzzy-match it.
  - An absent section omits this block entirely. For a project or terminal account, omit it entirely. A malformed section is skipped and its exact defect is surfaced plainly; none of these paths changes, retries, or suppresses `stage_recommendation`, `next_step`, or `product_gaps`.
  - For every declared field, in declaration order, evaluate its `Evidence:` criterion against the union of this run's `evidence[]` `content` payloads, `context.md` Summary and Activity Log, and the existing `qualification:` frontmatter block.
  - Emit each field as `{ field, status, evidence?, updated }`, where `status` is exactly `captured | missing`. `captured` requires a source-prefixed citation cross-checked against the corresponding source under the standing citation discipline. If a basis cannot be located, record `evidence: "inferred: <reasoning>"` and keep `status: missing`; with no basis, omit `evidence` and keep `status: missing`.
  - Captured is durable: when current sources are silent, a prior entry with the same verbatim field key and `status: captured` stays captured. Cite it through the existing context kind as `context.md: "<prior evidence value verbatim>"`, preserving that prior evidence value inside the citation and preserving the prior `updated` date. Only an explicit rep edit may downgrade a captured field.
  - `gaps[]` is exactly the `fields[]` entries whose status is `missing`, in declaration order. Each gap is `{ field, coach }`, with `coach` copied byte-for-byte from that field's `Coach:` value in `company/process.md`; never generate, normalize, or reword coaching text.
  - Qualification never gates: the advancement gate above continues to use only the REFERENCE-time stage's `**Exit criteria:**` bullets. Even with qualification gaps, all exit criteria met still yields `recommendation: advance`.

```yaml
crm_update:
  current_stage: technical-validation        # REFERENCE-time stage from context.md; null for projects
  stage_recommendation:
    recommendation: no-change                # advance | no-change | not-applicable
    to_stage: null                           # next sequential stage token, only when advance
    criteria:                                # one entry per Exit-criteria bullet of current_stage
      - criterion: "Technical stakeholders have signed off that the platform meets their requirements, OR"
        met: false
        evidence: null                       # source-prefixed citation when met (or inferred:)
      - criterion: "A pilot has hit its agreed success criteria"
        met: true
        evidence: "transcript: 'the pilot hit the latency target we agreed on'"
    unmet:                                   # criterion texts verbatim, only when no-change
      - "Technical stakeholders have signed off that the platform meets their requirements, OR"
    reason: null                             # only when not-applicable (project / terminal / out-of-enum)
  next_step:                                 # verbatim from Step 6 — never re-decided
    proposed: true
    description: "Schedule the security-review session with their infra team"
  product_gaps:                              # extract-only; honest empty list when none
    - gap: "No native Okta SSO integration"
      evidence: "email: 'does the platform support Okta SSO out of the box?'"
  qualification:                             # optional; omitted when not applicable
    framework: MEDDPICC                      # example only; value comes from process.md
    fields:
      - field: Metrics
        status: captured
        evidence: "transcript: 'the Monday rebuild takes nine hours'"
        updated: 2026-08-05
      - field: Decision Criteria
        status: missing
        evidence: "inferred: security and adoption likely matter, but no source states the criteria"
        updated: 2026-08-05
    gaps:                                    # exact missing-field projection
      - field: Decision Criteria
        coach: "ask what a clear yes looks like on paper, and who wrote it"
```

**7 — PERSIST.** Run only after a grounded task list exists:

- Write the in-memory task object as **valid pure YAML** to `accounts|projects/<slug>/drafts/YYYY-MM-DD-tasks.yaml`.
  - Date in the run's `timezone`, handled in-skill; create `drafts/` if missing; never repo root or `company/`.
  - The `.yaml` extension is unique to the task-list draft; every other draft kind is `.md`.
- Persist Steps 2–6 output unchanged, plus `status: not-done` on each task — do not re-rank, re-suppress, re-annotate, or re-decide.
- A carried task also persists its `carried_from` block (schema below) alongside `status: not-done`. This is the only site that writes the field.
  - A same-date re-run overwrites the same file, so `count` always derives from the **prior** file and is never incremented in place.
- The YAML and the chat-rendered list describe the same content.
- Step 7 persists **only** the tasks YAML. The Step 6.5 `crm_update` object is **not** written here — it rides back on the in-memory handback; `write-crm` (invoked by `run-unbound` at close-out) owns its persist + render on the simulate branch.

```yaml
tasks:
  - id: t1
    title: Send the security questionnaire
    type: followup_email
    priority: 1
    rationale: "Stage is technical-validation; security review gates the next milestone"
    evidence: "transcript: 'send the security questionnaire by Friday'"
    context:
      recipients: ["Jane (Acme, security lead)"]
      asks: ["attach/send the security questionnaire", "confirm the review timeline"]
    proposed_action: draft_email
    status: not-done
  - id: t2
    title: "Answer outstanding questions (pricing tiers above 1M records; SSO support)"
    type: answer_questions
    priority: 2
    rationale: "Open buyer questions stall technical-validation until answered"
    evidence: "carried from 2026-07-28 (t3, 2nd carry) · transcript: 'what are the volume tiers?' / email: 'does it support SSO?'"
    context:
      questions:
        - "What are the volume-based pricing tiers above 1M records?"
        - "Does the platform support SSO?"
    proposed_action: draft_answers
    status: not-done
    carried_from:                            # optional; present only on a carried task
      plan_date: 2026-07-28
      task_id: t3
      count: 2
dropped:
  - "Send a thank-you note (low leverage at this stage)"
open_questions:
  - "What are the volume-based pricing tiers above 1M records?"
next_step:
  proposed: true
  description: "Schedule the technical deep-dive call for next week"
```

The Step 6.5 `crm_update` object is **not** persisted here — it rides back on the in-memory
handback for `write-crm` (invoked by `run-unbound` at close-out) to apply. Persisting
`drafts/YYYY-MM-DD-crm-update.md` and rendering it is `write-crm`'s job on its simulate branch;
a downstream crm-update failure there never rolls back this tasks YAML or blocks ENRICH (Step 8) /
RECORD WORK (Step 9) — the task plan is the run's primary artifact.

**8 — ENRICH.** Update the item's `context.md`:

- Append a **new** dated `## Activity Log` entry — append-only: preserve all prior entries; add the heading if absent.
- In the entry, reference the just-written draft by filename and note notable call facts and the stage change ("stage to X" or "unchanged").
- Refresh frontmatter: `updated` = the session date; `open_questions` = the union defined in the next bullet; `last_next_step` = this run's `next_step` description (or the top task's title when `proposed` is false).
- `open_questions` is a **union, never a replacement**: this run's Step 5 list plus every prior frontmatter entry, minus any entry this run's `evidence[]` or `context.md` **answers**. A question the counterparty did not re-raise therefore survives the cycle instead of being overwritten out of the file. The prior entries are the ones Step 1 already loaded with `context.md` — this adds no read.
  - Dropping the answered entries is what bounds the list — it accumulates open questions only, never answered ones — so no cap and no age rule is needed.
  - De-duplicate on question text: a prior entry and a Step 5 question asking the same thing appear **once**, carrying the **prior phrasing verbatim**. A carried question is never re-worded and never duplicated.
- Refresh the `stage` field only on explicit transcript evidence of a transition, and only to a value in `company/process.md`'s enum — else leave it unchanged.
- When Step 6.5 emitted `qualification`, create the optional frontmatter `qualification: { framework, fields[] }` block on first evaluation or merge it by the fields' verbatim join keys thereafter. Persist the emitted framework and fields; `gaps[]` is a derived in-memory handback and is not stored. For a prior captured field carried through current silence, the in-memory result exposes the carry as a `context.md:` citation, but the stored field keeps its pre-run `evidence` value and `updated` date byte-for-byte rather than persisting or nesting that wrapper; only an explicit rep edit may downgrade it.
  - When Step 6.5 omitted qualification because the declaration was absent or inapplicable, write no qualification block and leave any existing block byte-unchanged. Never bootstrap, migrate, backfill, or add a compatibility shim: the block is absent until the first applicable evaluation.
- Projects leave `stage`/`competitive_threats` null.
- Writes only the local `context.md`; does not re-extract or re-decide upstream outputs.

**9 — RECORD WORK.** Open the item's cycle on the record — **one** record written, **no** event
flipped:

- Write one `work[]` record to `state/run-state.yaml` for this `(namespace, slug)`: `phase: planned`; `plan_date` = the same `YYYY-MM-DD` in the run's `timezone` Step 7's filename used, so the record pins the plan file just written; `started_at` = ISO 8601 with offset (same format as `last_run`); `event_ids` = `selected_item.event_ids[]` **verbatim**, matched by `event_id` and never widened to the slug's other events.
- Flip **no** event here. The recorded set is exactly what this cycle flips at its close-out and nothing wider: an event of the same slug that is **not** in `event_ids[]` — one discovered after evidence recovery ran, or one the orchestrator did not hand over — stays `pending` regardless, keeps the account on the slate, and is worked next run. There is no per-account flag to set, which is why later activity can never be masked by earlier work.
- Recorded = task list generated, and that is a strictly weaker claim than processed, which only the close-out makes once the cycle actually completes. Neither ever means "follow-up sent".
- At most **one** record per `(namespace, slug)`: an explicit rep restart **rewrites** the existing record — fresh `plan_date`, `started_at` and `event_ids`, back at `phase: planned` — rather than adding a second.
- An empty or absent `event_ids[]` writes nothing: say so plainly rather than recording a cycle no event grounds.
- Leave `last_run`, `timezone`, and every event record untouched.
- Narrate the terminal transition (tasks draft written, log appended, frontmatter refreshed, the cycle recorded with its events still `pending` until close-out) and hand back to `run-unbound` — including the in-memory `crm_update` object for `write-crm` to apply at close-out. The "CRM update written" narration moves to `write-crm`.

**10 — capture-feedback (shared procedure).** Authored here once; reused by name (never
re-authored) by `draft-followup` and `run-unbound`. Records **one** verdict:
`capture-feedback(namespace, slug, task_id, verdict, note="")` appends **one** validated JSON line
to `state/feedback-log.jsonl`:

- Build the object `{ts, namespace, slug, task_id, verdict, note}` and **serialize it** — never hand-concatenate a string.
- `ts` = ISO 8601 with offset in the run's timezone (same format as `run-state.yaml`'s `last_run`).
- `namespace`/`slug`/`task_id` are the join key; `task_id` is a task's `t<n>` or a draft's `source_task`.
- `verdict` is exactly one of `accept | edit | reject` — normalize natural language ("looks good" → accept, "tighten the ask" → edit with the request in `note`, "drop it" → reject).
- A reply that can't be confidently mapped → ask rather than write an out-of-enum value.
- `note` is the rep's text verbatim or `""` — always present.
- Create the file on the first verdict; append-only thereafter — one verdict = one line; a changed mind is a new line, never a rewrite.
- **Verdicts arriving together append together.** When one rep submission carries several `accept`/`reject` verdicts — `run-unbound`'s Step 3.5 triage fan-out — build, validate, and serialize each line exactly as above, then append them all in **one** write, in the fan-out's priority order. One verdict = one line is about the log's shape, never the write count: a single append carrying five lines satisfies it identically, and the latest-line-per-`task_id` read rule is untouched. `edit` verdicts never join the batch — each `edit` line appends individually, and only after its plan-file or draft-file rewrite succeeded (the APPLY-EDIT / APPLY-DRAFT-EDIT ordering).
- Its only effect is the local append — no external action. On write failure the caller surfaces it in chat.

**11 — TASK VERDICT CAPTURE.** Runs only when the rep actually reacts to a presented task:

- Tie the reply to a presented task by its `t<n>` — ask if ambiguous.
- Normalize the reply to the verdict enum.
- For `accept`/`reject`: call `capture-feedback` once per verdict.
- For a task `edit`: route through APPLY-EDIT (Step 15) — the plan-file write happens first; the one `edit` line is logged only after it succeeds.
- Confirm tersely.
- Never re-rank or re-suppress `tasks`/`dropped`; the only mutation path is APPLY-EDIT's bounded field set.

**12 — DROPPED-SET INSPECTION.** Runs only on a rep ask ("what did you drop?", "show
suppressed", ...):

- Render each `dropped[]` entry with its brief reason; write nothing.
- When `dropped[]` is empty, say "nothing was suppressed for this plan" plainly.

**13 — PROMOTE-A-DROPPED-ITEM.** Runs only on a rep promotion request, in this exact order:

- (a) tie it to a real `dropped[]` entry (ask if ambiguous).
- (b) build a promoted task at the **next free `t<n>`**: `type` inferred (default `internal`); `priority` a sensible rank without re-ranking others; `rationale` = the rep's reason; `evidence` = the honest provenance "Promoted from dropped by rep on `<date>`" (never a fabricated citation); `proposed_action` as implied (default `none`); `context` holding only what the rep stated; `status: not-done`.
- (c) move it into `tasks[]` and remove it from `dropped[]`.
- (d) **rewrite the local `drafts/YYYY-MM-DD-tasks.yaml` FIRST** — if that write fails, report it and do **not** log the edit.
- (e) **only then** append exactly one `edit` via `capture-feedback(namespace, slug, task_id=<new t<n>>, verdict="edit", note="promoted from dropped: '<entry>' - <rep reason>")`.
- (f) announce + confirm tersely.
- No other task is re-ranked.
- Clause (b)'s value and Step 4's `carried from <plan_date> …` form are one convention, not two exceptions: both state honest provenance in place of a citation the task never earned, and the citation discipline admits both (see Invariants).

**14 — SET-STATUS** `set-status(namespace, slug, task_id, new_status)`. The rep-driven, reusable
local write primitive for a task's lifecycle status. In this exact order:

- (a) map phrasing to `(task_id, new_status)` — "mark t3 done" → `(t3, done)`, "defer t5" → `(t5, deferred)`, "reopen t2" → `(t2, not-done)`; ask if the value is ambiguous; write the enum value, never a display label ("open"/checked/pill are presentation-only).
- (b) enum-validate `new_status` against `{ not-done | done | deferred }` **before any write** — reject an out-of-enum value (e.g. "finished"/"complete"/"close") with an explanation and write nothing (file stays byte-identical).
- (c) resolve the item's **latest-dated** `drafts/*-tasks.yaml` (the authority rule).
- (d) locate the task by `id` — on an unknown id (e.g. `t99`) say so honestly and write nothing; never fabricate or renumber.
- (e) write **only** that task's `status` as valid pure YAML — every other field and task is write-once and left unchanged, consistent with hand edits.
- (f) announce + tersely confirm exactly what changed.
- `status` is a local declaration — never an external action, never a feedback verdict (see Invariants — `status` never lands in `feedback-log.jsonl`).
- Status changes are **explicit chat asks** ("mark t2 done") — the task-plan card carries no checkbox; after applying, re-render via `render.tasks`.

**15 — APPLY-EDIT (shared procedure).** Authored here once; reused by name (never re-authored) by
`run-unbound`'s plan-triage fan-out (once per edited task) and by any later rep edit request. Applies **one** rep
`edit` verdict to a task via `apply-edit(namespace, slug, task_id, edits, note)`, in this exact
order:

- (a) tie the edit to a real task by `id` in the item's **latest-dated** `drafts/*-tasks.yaml` (the same authority rule as SET-STATUS); ask if ambiguous; on an unknown id say so honestly and write nothing — never invent or renumber.
- (b) bound the edit to the **rep-mutable annotation fields only** — `title`, `rationale`, `context` (field-level merge: only the fields the rep actually changed); `id`, `type`, `priority`, `evidence`, `proposed_action`, and `status` are out of scope.
  - A type change is a reject + a new/promoted task; a rank change is a re-prioritization ask; status is SET-STATUS's; a factual correction touching `evidence` is surfaced and held for the rep, never silently rewritten.
- (c) **rewrite the local plan file FIRST** as valid pure YAML, every other task and field byte-unchanged — if that write fails, report it and do **not** log the edit.
- (d) **only then** append exactly one `edit` line via `capture-feedback(namespace, slug, task_id, verdict="edit", note=<the rep's text verbatim>)`.
- (e) re-present the revised task tersely (re-render via `render.tasks` where active) and confirm.
- Its only writes are the one plan-file rewrite and the one log line — never an external action, never executed content.

**16 — ADVANCE-PHASE (shared procedure).** Authored here once; reused by name (never re-authored)
by `run-unbound` at each of its three cycle beats. Moves the item's `work[]` record forward through
the cycle via `advance-phase(namespace, slug, to_phase)`, in this exact order:

- (a) locate the record in `work[]` by `(namespace, slug)` — on a missing record say so plainly and write nothing; never create one here, creation is RECORD WORK's (Step 9).
- (b) permit **strictly forward** movement only, along `planned → triaged → executed → closed` — a backwards request, and a request for the phase the record already carries, are each surfaced and write nothing. A repeated beat is therefore a visible no-op line, never a silent one and never a rewrite.
- (c) `to_phase` of `triaged` or `executed` → rewrite **only** that record's `phase` in place; every other field, every other record, and every event record stay byte-unchanged.
- (d) `to_phase` of `closed` → in **one** write: set `processing_status: processed` on every `events[]` record whose `event_id` appears in this record's `event_ids[]`, **and** remove the record from `work[]`. This is **the only place in the corpus where an event flips to `processed`**. `closed` is a transition, never a resting value — no record is ever left carrying it. An `event_id` the record names that is no longer in `events[]` (a hand edit removed it) → flip the ones actually found, surface the miss, and never abort the close-out.
- (e) a write failure at any clause is surfaced in chat and the session **continues** — never halted, never silently retried.
- Why continuing is safe: every beat this procedure punctuates is idempotent. Triage verdicts append and the latest per `task_id` wins; the walk passes over tasks already carrying `handled_on` and re-runs the rest against handlers that rewrite their own same-date artifact; `write-crm` rewrites its same-date file; and clause (b)'s forward guard turns a repeated advance into a surfaced no-op. A failed phase write therefore costs the rep one repeated beat on the next run, never a corrupted cycle.

**17 — MARK-HANDLED (shared procedure).** Authored here once; reused by name (never re-authored) by
`run-unbound`'s task-execution loop. Records the single fact that the loop gave one task its turn,
via `mark-handled(namespace, slug, task_id)`, in this exact order:

- (a) resolve the item's **latest-dated** `drafts/*-tasks.yaml` — the same authority rule SET-STATUS (c) and APPLY-EDIT (a) already state; it is not re-derived here.
- (b) locate the task by `id` — on an unknown id say so honestly and write nothing; never fabricate or renumber.
- (c) write **only** that task's `handled_on: YYYY-MM-DD` (the run's `timezone`) as valid pure YAML — every other field, and every other task, byte-unchanged.
- (d) never write it for a `define-only` task, a rejected task, or a task carrying no verdict: none of the three takes a turn. The registry's mode word is the whole test and no task type is named here, which is what keeps this correct for any handler a client pack adds.
- (e) never write it from inside a handler, never append it to `feedback-log.jsonl`, and never read it as the rep-owned `status`: a task can carry `handled_on: 2026-08-01` and `status: not-done` at once — the loop drafted the email, the rep has not sent it.
- Log nothing: this procedure's whole write is the one single-field plan-file rewrite.

**18 — CAPTURE-QUALIFICATION (shared procedure).** Authored here once; reused by name (never
re-authored) by `run-unbound`'s Step 5 close-out beat. Persist explicit rep answers through
`capture-qualification(namespace, slug, answers[])`, where each answer is `{ field, answer }`, in
this exact order:

- (a) require `namespace: accounts` before reading or writing anything. A project or any other
  namespace is surfaced as inapplicable and writes nothing; never create account state under a
  different namespace.
- (b) load the current `company/process.md` declaration and the account's `context.md`. Require the
  same one well-formed `## Qualification` section Step 6.5 defines. An absent or malformed
  declaration is surfaced and writes nothing; never infer a framework or field set.
- (c) validate every input entry independently against the declaration. The `field` must equal one
  declared bold-term field **verbatim** — no trim, normalization, case-folding, alias, or fuzzy
  match. Surface each unknown field and omit it from the write. An absent answer or one containing
  no non-whitespace characters is empty and is skipped; an accepted answer is stored byte-for-byte,
  including its original capitalization and punctuation.
- (d) build one candidate rewrite in memory. Create the optional `qualification:` block when it is
  absent; otherwise rewrite it in place. Set its `framework` from the current declaration. For each
  valid non-empty answer, create or replace the single `fields[]` entry with the same verbatim field
  key as `{ field, status: captured, evidence: 'rep-stated (YYYY-MM-DD): "<verbatim>"', updated:
  YYYY-MM-DD }`, using the run's timezone date. Preserve every unaddressed field entry and every
  unrelated frontmatter/body byte. Re-answering a field replaces that keyed entry — including when
  a field repeats in one input array — and never appends a duplicate; input order makes the last
  valid answer for that key the final value.
- (e) when at least one valid non-empty answer remains, perform **one** `context.md` rewrite and in
  that same write append exactly one dated `## Activity Log` line for the invocation, naming the
  captured field or fields. An invocation containing only project input, unknown fields, or empty
  answers writes nothing and appends no log line. Never partially apply the candidate rewrite.
- (f) surface per-entry outcomes plainly. On the `context.md` write failing, surface the failure,
  leave the pre-invocation file authoritative, claim no capture, do not retry silently, and let
  close-out continue.
- (g) write no task, status, work record, CRM draft, or `state/feedback-log.jsonl` line. A
  qualification answer is an account fact, not a verdict; never call `capture-feedback` from this
  procedure.
- (h) the same procedure may be invoked when the rep explicitly states a qualification fact at
  close-out (for example, "the EB is Dana") only when that utterance maps unambiguously to one
  declared field. If more than one field could fit, ask which field before invoking and write
  nothing until the rep disambiguates. This path is rep-driven and is never volunteered as a second
  structured ask.

## Writes

- `accounts|projects/<slug>/drafts/YYYY-MM-DD-tasks.yaml` — PERSIST (Step 7); also the single-field SET-STATUS write, the promotion rewrite, the APPLY-EDIT rewrite (Step 15), and MARK-HANDLED's single-field `handled_on` write (Step 17).
- `accounts|projects/<slug>/context.md` — ENRICH (Step 8): appended `## Activity Log` entry + frontmatter refresh, including the optional account-only `qualification:` create/merge after evaluation. Account-only CAPTURE-QUALIFICATION (Step 18) is the second named authority on the same optional block and appends one Activity Log line in its single successful rewrite.
- `state/run-state.yaml` — the item's `work[]` record: created by RECORD WORK (Step 9), its `phase` rewritten in place by ADVANCE-PHASE (Step 16), and removed by that same procedure at `closed` — which, in the very same write, sets `processing_status: processed` on the event records that removed record named. No other record and no other field; `last_run` and `timezone` are never touched here.
- `state/feedback-log.jsonl` — `capture-feedback` append, one line per verdict / one `edit` per promotion; Step 18 never writes it.

### Canonical task object schema (the write-site schema)

`{ id: t<n>, title, type, priority, rationale, evidence, context, proposed_action, status, handled_on?, carried_from? }`:

- `type` — the valid set is defined in `task-registry.md` (Part A); that registry is the canonical authority, and this skill emits **only** types in that set, re-asserting no independent list here (point, don't copy).
- `type` is the **task-type registry key** `run-unbound`'s task-execution loop dispatches on; each type's execution mode (`execute` / `define-only`), handler, invocation, and `when` precondition live in the registry — read them there rather than restating them here. Step 2 reads `when` when typing a candidate; the loop reads `mode` and `invocation` only.
- At most **one** `answer_questions` task per plan: it groups ALL outstanding questions to answer for the audience — never one task per question.
- `proposed_action ∈ { draft_email | ideate_content | draft_proposal | prep_demo | draft_answers | none }` — a recorded downstream intent, not executed here. `draft_email` on `followup_email` is the only intent currently executed; `ideate_content` on `create_deck`/`create_one_pager`, `draft_proposal` on `create_proposal`, `prep_demo` on `prepare_demo`, and `draft_answers` on `answer_questions` are recorded for future execution; `none` = nothing to execute.
- `context` — the typed execution-context block; the per-type field map lives in Step 4 (stated once there) — grounded fields only.
- `status ∈ { not-done | done | deferred }` — default `not-done` at synthesis; rep-mutable via SET-STATUS.
- `handled_on` — **optional**, `YYYY-MM-DD` in the run's `timezone`; absent until set, and **written only by the loop** (never by this skill), recording exactly one fact: the loop gave this task its turn. It is **not** a rep declaration — `status` is that and stays rep-owned; **not** a feedback verdict — `feedback-log.jsonl` is that; and **not** an assertion that an artifact exists, since a turn that ends in a clean no-op sets it too.
- `carried_from` — **optional**, `{ plan_date, task_id, count }`; absent unless the task was carried, and **written only at PERSIST** (Step 7). On the `handled_on` precedent it is **not** a rep declaration — `status` is that and stays rep-owned; **not** a feedback verdict — `feedback-log.jsonl` is that; and never read as `status`.
  - `plan_date` and `task_id` name the prior plan file and this task's id inside it; `count` is that prior task's own `carried_from.count` **plus one**, an absent prior value reading as `0`.
  - The count therefore chains through the latest-dated file alone: **no tasks file but the latest-dated one is ever opened**, and the `drafts/` listing Step 2's row 4 uses is a directory listing, not a history read.
- `title`, `rationale`, and `context` are rep-mutable via APPLY-EDIT (Step 15); all other fields are write-once (`id`/`type` never change — a type change is a reject plus a new/promoted task).
- The object also carries `dropped[]`, `open_questions[]`, and `next_step`.
- Feedback line: `{ts, namespace, slug, task_id, verdict, note}` under `state/`.

## Invariants

**Grounding**

- Never fabricate: no invented commitment, date, stakeholder, quote, question, gap, task, dropped entry, or stage — everything emitted traces to an `evidence[]` entry, `context.md`, company knowledge, or — for a carried task's copied fields only — the item's **prior plan file**.
  - That fourth provenance is a verbatim copy off disk, stronger grounding than the `inferred:` marker this discipline already permits. It licenses copying and nothing else: no re-derivation, no new citation, no field the prior file does not carry.
- Citation discipline: every task `evidence` value, stage-criterion basis, and captured qualification basis is **either** a citation identifying the source kind explicitly — `transcript: "<quote or locus>"` for a call transcript, `email: "<quote or locus>"` for an email body, `context.md: "<fact or prior qualification evidence value verbatim>"` for a context.md Summary, Activity Log, or existing qualification fact — **or** the literal `inferred: <reasoning>` marker; never empty when present.
  - The compound carried form `carried from <plan_date> (<task_id>, <n>th carry) · <original value verbatim>` satisfies this: the source-kind prefix (or the `inferred:` marker) survives intact after the separator, so the value stays exactly one of the permitted kinds.
- `rep-stated (YYYY-MM-DD): "<verbatim>"` is durable provenance for an explicit rep edit, not a new citation kind. When a prior qualification value carries it, preserve the value verbatim inside a `context.md:` citation; never fabricate or paraphrase it.
- Cross-check every citation against its corresponding source: transcript/email citations against an `evidence[]` entry's `content`, and context citations against `context.md` Summary, Activity Log, or the existing qualification block. A citation that cannot be located in any corresponding source is downgraded to `inferred`, never left unverifiable.
  - The cross-check governs citations this run derives. A carried value is not re-checked: it was checked in the cycle that produced it, and this run's evidence pool does not hold the call it quotes.
- Source-kind mis-attribution is the dangerous failure: an email-derived statement is cited `email:`, a call-derived one `transcript:`. When unsure which source contributed, downgrade to `inferred:` rather than guess a prefix.
- `evidence_status: missing` is first-class: do not re-fetch (recovery already ran once, upstream), do not fabricate; synthesize from the remaining `evidence[]` entries and/or `context.md` where possible, and surface the gap. If nothing is groundable across ANY evidence source and `context.md` is thin: say so, emit no tasks, and flip **no** event to processed.
- Honest empties, never pad: thin input yields a short-or-empty `tasks` list; `dropped` reflects only genuine suppression; `open_questions` and `product_gaps` stay empty when nothing qualifies.
- Thin `company/process.md` stage definitions → surface the thinness; never fabricate a richer stage story. An out-of-enum account `stage` is flagged, never treated as a new stage.

**Mutation boundaries**

- No state mutation (PERSIST / ENRICH / RECORD WORK) before a grounded task list exists: no grounded list → no draft, no enrich, no record, every event stays `pending`, and the item stays on the slate annotated.
- The recorded `event_ids[]` bound is never widened: RECORD WORK copies exactly the ids it was handed, so what the record carries is what the close-out flips — per `event_id`, never per slug, and an event absent from that list is left `pending` even when it shares the worked item's slug.
- All writes are local; no external write ever (Drive / Gmail / CRM untouched); name no concrete MCP tool — logical capabilities only.
- ENRICH (Step 8) is the sole stage writer: the Step 6.5 recommendation is advisory and never mutates a `stage:` value anywhere.
- Qualification fields and gaps are never advancement inputs: only the current stage's exit criteria feed `stage_recommendation`; a company that wants a field to gate must declare it as an exit criterion.
- The plan file and the feedback log never disagree: promotion and APPLY-EDIT rewrite the plan file first and never half-apply — on a plan-write failure, nothing is logged.
- `status` is never written to `feedback-log.jsonl` — lifecycle status and feedback verdicts stay distinct. `handled_on` inherits that same separation exactly: it is never a verdict, never lands in `feedback-log.jsonl`, and is never read or written as `status`.
- ADVANCE-PHASE (Step 16) clause (d), at `to_phase` of `closed`, is the **only** site in this corpus at which an event flips to `processed` — no other step, no other skill, and no handler writes that value.
- Type-set alignment (explicit & checkable): `task-registry.md` (Part A) is the single authority for the `type` set; every type this skill can emit appears in the registry (a type with no registry row degrades to `internal`, never invented), and every `execute` row names a resolvable handler — the emitted types are a guaranteed subset of the registry's canonical set, inspectable by hand against Part A.
- Single-threaded: operate on exactly one selected item end-to-end, then hand back; never fan out; accept `namespace`/`slug` verbatim — never re-discover, re-fetch, re-classify, or re-derive the slug.

**Interaction**

- Steps 11–15 are rep-driven only — never volunteered. Steps 16–17 are the loop's, invoked by name at their own beats. Step 18 is invoked only for a returned Step 5 qualification answer or an explicit rep-stated close-out fact; the latter path is never volunteered as another ask.
- Silence is not a verdict: no rep reaction → write nothing.
- Ambiguity → ask; never guess or invent the referent — a task id, dropped entry, verdict, or status value.
- An `edit` verdict on a **task** is recorded and applied only through APPLY-EDIT's bounded field set; an **email-draft** `edit` is applied by `draft-followup`'s APPLY-DRAFT-EDIT (its own artifact, its own bounded field set, the same write-first-then-log discipline) — never by this skill.

**Failure handling**

- Every write failure — persist, enrich, record-work, capture-feedback, capture-qualification, promotion, set-status, apply-edit, advance-phase, mark-handled — is surfaced in chat, never silently dropped. (The crm-update persist failure moved to `write-crm`.)
- A prior plan file that is absent, empty, or unparseable is surfaced the same way and blocks nothing: synthesis continues from this run's evidence alone and **no carry is fabricated** — no invented task, id, count, or provenance line.
