---
name: write-crm
description: Close-out skill that owns the CRM write/simulate boundary. Invoked by run-unbound at the Step 5 CRM close-out sub-beat (composition slot 8) with the in-memory crm_update object work-account handed back. RESOLVE separates live tool presence from production eligibility (replay-proven or recovery-verified); every unbound, unconfirmed, legacy, or path-unqualified mapping takes the unchanged simulate branch, persisting drafts/YYYY-MM-DD-crm-update.md and rendering "(simulated)". Where a mapping does qualify, an approved update lands at most once — by provider replay or by ledger-plus-read-back recovery — and an interrupted close-out resumes without a second push. NOT part of the run loop's task dispatch and NOT a task-registry handler (external write lives outside the Handler Contract).
tier: all
---
# write-crm

Close-out apply step of an Unbound run (composition slot 8) that owns the **APPLY** half of the CRM
update — the write-vs-simulate boundary concern. `work-account` Step 6.5 computes *what* the CRM
should hold (the grounded `crm_update` object); `write-crm` decides *how* it lands. Invoked by
`run-unbound` at the Step 5 CRM close-out sub-beat (after the email-draft verdict beat), taking the
in-memory `crm_update` object `work-account` handed back.
Names only logical capabilities (ADR-6); it is not a task-registry handler — the external write
lives outside the Handler Contract (a numbered composition-seam slot is not the same as a registry handler).

## Reads

- In-memory `crm_update` object (handed back by `work-account` Step 6.5, forwarded by `run-unbound` Step 5) — `current_stage`, `stage_recommendation { recommendation, to_stage, criteria[], unmet[], reason }`, the verbatim-carried `next_step`, `product_gaps[]`, and the optional `qualification { framework, fields[]: { field, status: captured|missing, evidence?, updated }, gaps[]: { field, coach } }` block when Step 6.5 emitted one. Nothing is re-evaluated here.
- The selected item's `(namespace, slug)` and its `accounts|projects/<slug>/drafts/` path — the persist target on the simulate branch.
- The run's `timezone`, for the filename date — reused in-session from the orchestrator's Step 1 read (the read-once rule, `work-account` Step 1); `state/run-state.yaml` is never opened here for it, and is never written here.
- Logical capability `render.crm_update(crm_view)` — the informational close-out card / Markdown section; never a concrete tool name.

## Procedure

**APPLY (simulate) — the live path.** The verbatim current behavior — persist a local dated draft
and render it informationally. Persist mechanics moved unchanged from `work-account` Step 7:

- Write the `crm_update` object to `accounts|projects/<slug>/drafts/YYYY-MM-DD-crm-update.md`.
  - Date in the run's `timezone`, handled in-skill; create `drafts/` if missing; never repo root or `company/`.
  - The `.md` extension — `.yaml` is reserved for the tasks draft.
  - A same-date re-run overwrites the same-date file — latest synthesis wins, the same authority rule as the tasks draft.
- YAML frontmatter `{ namespace, slug, date, current_stage, recommendation }`, plus `to_stage` only when advancing.
- Markdown body: the three standing sections shaped as the field-level update a CRM would receive, headed by the "(simulated)" marker and an explicit nothing-was-sent-externally note. Unmet criteria render as "no evidence this run" — informational checkboxes, never `render.tasks`; the criteria block is omitted entirely on a `not-applicable` recommendation.
- `## Qualification (<framework>)` — conditional section, present only when the handed-back `crm_update` carries a `qualification` block; placed after `## Stage` (before `## Next Step`). A read-only projection of that block — nothing is re-evaluated, and `company/process.md` is never re-read at render time. First line: `N of M captured`, where `M` is the declared field count (every `fields[]` entry) and `N` the `captured` count — a count, never a percentage, score, or health grade. Then one line per field, in declaration order: a captured field renders `- [x] <field> — <citation>`; a missing field renders `- [ ] Missing: <field> — <coach hint>`, the hint taken verbatim from `gaps[].coach` (already copied byte-for-byte from `company/process.md`'s `Coach:` value by `work-account` Step 6.5) — never generated, never re-worded. When `crm_update` carries no `qualification` key (project, terminal stage, absent or malformed declaration — all decided upstream in Step 6.5, never re-decided here), the section is omitted entirely — never an empty heading, never a `0 of 0` line — the same omit-entirely rule as the criteria block on `not-applicable`.

```markdown
---
namespace: accounts
slug: virgin-atlantic
date: 2026-06-12
current_stage: technical-validation
recommendation: no-change
---
# CRM Update (simulated) — virgin-atlantic — 2026-06-12

> What would be written to the CRM after this session. Nothing has been sent to any
> external system — apply manually if you agree.

## Stage
**Current:** technical-validation · **Recommendation: no change**
- [x] A pilot has hit its agreed success criteria — transcript: "the pilot hit the latency target we agreed on"
- [ ] Technical stakeholders have signed off that the platform meets their requirements — no evidence this run

## Qualification (MEDDPICC)
1 of 2 captured
- [x] Metrics — transcript: "the Monday rebuild takes nine hours"
- [ ] Missing: Decision Criteria — ask what a clear yes looks like on paper, and who wrote it

## Next Step
Schedule the security-review session with their infra team.

## Product Gaps
- No native Okta SSO integration — email: "does the platform support Okta SSO out of the box?"
```

- Hand the object + persisted filename to `render.crm_update(crm_view)` — the interactive informational card on UI-capable runtimes, the plain in-chat **"CRM Updates (simulated)"** Markdown section otherwise (same fields on both). State plainly the persisted filename and that **nothing was written to any external system** — this branch sends nothing, and the rep applies the update to their real CRM manually if they agree.
- Informational only on this branch: it presents the update, it never asks for anything. No `review.collect` call, no verdict, no `capture-feedback` line — silence has no meaning here.

## Writes

- `accounts|projects/<slug>/drafts/YYYY-MM-DD-crm-update.md` — the simulated CRM update (the simulate branch only); same-date re-run overwrites the same-date file.

## Failure rules

- crm-update write failure (simulate branch) → surface it in chat, render the section from the in-memory `crm_update` object, and do **not** roll back the tasks YAML or block ENRICH (`work-account` Step 8), MARK PROCESSED (Step 9), or `run-unbound`'s `last_run` advance — the task plan is the run's primary artifact.
- generation failure (empty/absent `crm_update` object handed back) → replace the sub-beat with one honest close-out line ("no CRM update this run — <reason>"); never block close-out.
- Same-day re-run → overwrite the same-date `crm-update.md` (latest synthesis wins).
- No verdict surface anywhere in this skill → never enters `review.collect`, never writes `feedback-log.jsonl`.
- **File writes are local** — the simulate branch's dated draft under the item's `drafts/` is the only file this skill ever writes, on any branch. Name no concrete MCP/CRM tool — logical capabilities only (ADR-6).
