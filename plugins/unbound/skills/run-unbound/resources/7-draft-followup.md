---
name: draft-followup
description: The followup_email task-type handler — the only task type run-unbound's loop executes. Invoked when the loop reaches a followup_email task the rep accepted in the plan-triage submission and that carries proposed_action draft_email. Drafts the single follow-up email for the selected account or project in rep/voice.md voice, covering — where evidence grounds each — the outstanding questions, the best-fit existing asset (or planned content), and the next step. When the next step is a meeting, it confirms attendees, their emails, and candidate times with the rep before drafting. Writes a local draft only; nothing is ever sent or queued. One email per item per run.
tier: all
---
# draft-followup

The `followup_email` task-type handler — the **only** task type the run currently executes (every
other type is define-only; see `run-unbound` Step 4). Turns the plan into the **one** act-ready
follow-up email for the selected item: what the call or email left to follow up on — questions to
answer, content to provide, next steps to lock in. Works a single item end-to-end, then hands back
to the loop; never fans out. Phase order is fixed: GATE → MATCH-ASSET → AVAILABILITY →
SCHEDULING-CONFIRM → DRAFT → PROPOSE-CONTENT, plus DRAFT VERDICT CAPTURE and its APPLY-DRAFT-EDIT
procedure — where AVAILABILITY and SCHEDULING-CONFIRM run only on the meeting path (see
Invariants).

## Reads

- in-memory `selected_item` (incl. its `evidence[]`), the handed `source_task`, and the `work-account` output `tasks[]` / `open_questions[]` / `next_step` — read-only grounding.
- internal-attendee identities and emails for a required meeting — from the originating event/thread participants surfaced in `selected_item` evidence, the `source_task` (incl. `context.next_call.required_attendees[]`), and `context.md`. In-hand evidence only; a non-derivable address is held as `[email unknown]`.
- `rep/voice.md` — voice/tone.
- `company/messaging.md` — positioning, differentiation pillars, proof points, objection handling, and the default follow-up shape (incl. the optional single asset link).
- `company/assets.md` — asset index / matcher: `Asset | Vertical | Use case | Stage | Pain point | Link`.
- `company/process.md` — canonical stage enum (validates the `Stage` column and the item's `stage`).
  - `rep/voice.md`, `company/messaging.md`, `company/assets.md`, and `company/process.md` are **reused from this session's one REFERENCE load** — immutable in-run per the read-once rule (`work-account` Step 1); this handler re-opens none of them.
- `accounts|projects/<slug>/context.md` — `stakeholders` (greeting + required attendees), `stage`, accumulated reality.
- `state/run-state.yaml` — the item's row, only. The run's `timezone` is reused in-session per the same read-once rule, never re-opened from this file.
- `state/feedback-log.jsonl` — this item's (and the rep's recent) `edit` / `reject` entries with their notes, read at DRAFT as style steering only; an absent file means no steering.
- logical Drive read capabilities `content.search(query) -> [ref]` and `content.get(ref) -> content` — read-scope, bounded (one search + ~one get), to verify existence not to ingest.
- logical Calendar read capability `calendar.availability(attendees, window) -> [open_slot]` — read-scope, bounded (one query), only on the meeting path; slots are held for SCHEDULING-CONFIRM, never written into a draft before approval.

## Procedure

**1 — GATE.** Runs first; no draft is composed before it proceeds.

- Precondition: the rep accepted this task (or accepted it after an edit) in `run-unbound`'s plan-triage submission. The loop never invokes this skill on a reject or no verdict, and this skill never drafts without that accept.
- Verify the handed `source_task` is `type: followup_email` carrying `proposed_action: draft_email` — the trigger contract.
- If invoked without a handed task, scan `tasks[]` and hold the highest-priority such task as `source_task`.
- If the contract does not hold (wrong type, or `proposed_action: none`), no-op: write no draft, leave `drafts/` untouched, say briefly in chat that no follow-up email was warranted, hand back.
- Collect any other `followup_email` tasks in `tasks[]`; their asks become material for this same email.

**2 — MATCH-ASSET.** Resolves the email's *content* component before composing.

- From the in-session `company/assets.md` (the read-once rule — never re-opened here), shortlist rows whose `Stage` matches the item's deal `stage` or is `any`.
- Pick the single row whose `Pain point` best matches the stated pain (`Vertical` is a tiebreaker, not a hard filter); prefer dropping a low-confidence match.
- Verify it in Drive: `content.search(query)` scoped by the asset's identity + stage/pain terms, then `content.get(ref)` to confirm the `ref` resolves (bounded: one search + typically one get; never crawl).
- The outcome is exactly one of:
  - **verified asset** — hold the one `Link` + a one-line rationale tied to stage + pain for DRAFT to embed; `asset_referenced` will carry the chosen asset;
  - **planned content** — no asset fits or verifies, but the plan carries a `create_deck` / `create_one_pager` task: hold it so DRAFT names the forthcoming content tentatively (what it is and what it addresses); `asset_referenced: none`;
  - **none** — no asset and no planned content task: no content component; `asset_referenced: none`; PROPOSE-CONTENT decides whether a genuine gap exists.
- Narrate the outcome (which asset and why / planned content named / none fit).

**3 — AVAILABILITY.** Runs only when `next_step` is `{ proposed: true }` and the step is (or includes)
a meeting; otherwise skip silently. This is the next-call substep — a required next call is never a
discrete task; it is handled here, inside the follow-up email. Resolve candidate attendees and
times and hold them for SCHEDULING-CONFIRM's one presentation; write nothing yet.

- **Determine the required attendees, split by side.** Vendor/internal: the rep plus the internal colleagues the evidence / `next_step` / `source_task.context.next_call.required_attendees[]` name (e.g. an SE or a manager). Counterparty: the stakeholder(s) from `context.md` `stakeholders`.
- **Resolve each internal attendee's email** from the originating event/thread participants in `selected_item` evidence, the `source_task`, or `context.md`. A non-derivable address is held as `[email unknown]`. Never guess an attendee or silently omit one.
- **Find times.** Read `calendar.availability(candidate_attendees, window)` once across every candidate with a known address (membership open or not), windowed to the evidence-supported timing (else the coming two weeks), and hold 2–3 candidate slots. A slot free for the union stays free for any subset the rep keeps, so narrowing at the gate never invalidates a presented time.
- **Degrade honestly.** An unreadable attendee calendar (an `[email unknown]` candidate is one) → fall back to the readable attendees' (at minimum the rep's) open slots, phrased as offers to confirm. Capability unavailable or no open slots → carry the meeting ask without concrete times (still confirm attendees at the gate).

**4 — SCHEDULING-CONFIRM.** Runs only when AVAILABILITY ran; skipped silently otherwise. A hard
gate: no draft file is written until the rep approves here. This is scheduling logistics — who and
when — distinct from the task approval `run-unbound`'s plan triage already owns.

- Present in chat, as one ask: the candidate vendor/internal attendees with emails — asking the rep to confirm membership where ambiguous and supply any `[email unknown]` — and the 2–3 candidate slots (or, on a degraded read, the meeting ask without times).
- Wait for a real reaction, then normalize it to `approve | edit | reject` (as DRAFT VERDICT CAPTURE normalizes):
  - `edit` → apply the change to attendees and/or slots (re-run `calendar.availability` if the set changed) and re-present this gate;
  - `reject` → write no draft; loop or close per the rep;
  - `approve` → carry the confirmed attendees + emails + approved slot(s) to DRAFT. Only then does DRAFT run.

**5 — DRAFT.** Compose the one follow-up email in `rep/voice.md` voice and `company/messaging.md`'s default shape.

- Before composing, read this item's recent `edit` / `reject` notes from `state/feedback-log.jsonl` and apply their recurring patterns (e.g. the rep keeps shortening drafts, keeps cutting the recap) — style steering only, never grounding for a factual claim.
- Derive the greeting from `context.md` `stakeholders`; address a real stakeholder. If `stakeholders` is empty, use a neutral placeholder like `Hi [name — no stakeholder on file]` and flag it in chat.
- Include each of the three components **only where evidence grounds it** (omit, never pad, a component with nothing grounded):
  - **opener + recap** — a warm one-line opener referencing the actual call/email, with a 2–4 bullet recap grounded in the `source_task` evidence (plus the other `followup_email` tasks' evidence and `context.md`). Keep an `inferred:`-grounded point tentative.
  - **questions** — from the plan's `answer_questions` task / `open_questions[]`: acknowledge each and commit to how and when it will be answered. Relay an answer inline only when `context.md` or company material already contains it (cited).
  - **content** — the MATCH-ASSET outcome: embed the one verified asset `Link` with its rationale, or name the planned content tentatively, or omit the component.
  - **next step** — one clear ask from `next_step`. On a meeting, offer only the SCHEDULING-CONFIRM-approved slots (phrased per Step 3's degradations when times were unavailable) and CC the confirmed internal attendees on the `cc:` frontmatter line, naming them in the body where the voice suits it. On `{ proposed: false, reason }`, do not manufacture an ask — close warmly and note in chat that no next step was proposed.
  - a plain sign-off.
- Craft the prose to land, not just to be accurate:
  - keep the body near 150 words, one idea per paragraph; when questions, content, and a meeting all fire, compress rather than enumerate;
  - reuse the stakeholder's own phrasing from the evidence for pains and commitments — never paraphrase them into sales-speak;
  - the subject names the concrete value or next step (e.g. "Security one-pager + Thursday times"), never a "Following up" / "Checking in" construction;
  - no stock filler: "Just checking in", "Hope you're well", "touching base", "I hope this finds you well" and kin are banned regardless of voice;
  - litmus: an email that would still read sensibly sent to a different account is not done — rewrite until it could only be for this one.
- Write the draft to `accounts|projects/<slug>/drafts/YYYY-MM-DD-email.md` (date in the run's `timezone`; create `drafts/` if missing; never repo root or `company/`) with the frontmatter below — `asset_referenced` and `cc` set at write time; `cc: []` on the no-meeting path. Then narrate it in chat (filename + body), stating it is a draft only.

```markdown
---
kind: email
slug: <slug>
namespace: <accounts|projects>
date: <YYYY-MM-DD in the run's timezone>
source_task: <the followup_email task id, e.g. t1>
status: draft
asset_referenced: none      # the chosen asset when MATCH-ASSET verified one; else none
cc: []                      # SCHEDULING-CONFIRM-approved internal attendees ({name, email}); [] on the no-meeting path
---

Subject: <concise, evidence-grounded subject>

Hi <stakeholder from context.md>,

<warm one-line opener that references the call/email>

- <2–4 bullet recap, grounded in the task evidence>

<questions: acknowledgements + commitments; an answer only where existing material already provides it>

<content: the one verified asset link + rationale, OR the planned new content named tentatively, OR omitted>

<one clear next step — when it is a meeting, only the SCHEDULING-CONFIRM-approved slots for the
confirmed attendees (who are also on the cc: line)>

<plain sign-off>
```

**6 — PROPOSE-CONTENT.** Runs only at the MATCH-ASSET `none` outcome; skipped whenever an asset was
referenced or planned content was named.

- Identify the content gap from the item's `stage` + stated pain (grounded in the `source_task` evidence / `open_questions[]`, or marked `inferred:` where not directly stated).
- Add one in-memory task in the canonical schema, typed as the specific discrete deliverable (`create_deck` or `create_one_pager`), `proposed_action: ideate_content`, naming angle + pain point.

```yaml
- id: c1
  type: create_one_pager
  title: "Create a FinServ security-review one-pager for technical-validation"
  rationale: "No existing asset covers the security/governance objection at this stage."
  evidence: "transcript: 'security won't approve a new data platform'"   # cite, OR inferred: <reasoning>
  proposed_action: ideate_content
```

- Emit it in-memory and narrate it. The task is define-only; nothing is created in this run (on adoption the rep promotes it into the plan). Make no Drive call, add no write capability, write no link into the draft, and leave `asset_referenced: none` / `status: draft` intact. Do not persist to `drafts/*-tasks.yaml` (`work-account` owns that). Hand back to the loop.

**7 — DRAFT VERDICT CAPTURE.** Driven by the EXECUTE TASKS beat's artifact-verdict gate
(`triage-and-execute.md` Step 4), at this task's own turn, where the draft and its verdict controls
are one surface; runs only if a draft was written and only when the rep actually reacts.

- Read the draft's `source_task` frontmatter as the `task_id` (fall back to the stable id `email` if absent).
- Normalize the reply to `accept | edit | reject` and capture any note verbatim.
- On `accept` or `reject`: call the shared `capture-feedback(namespace, slug, task_id, verdict, note)` procedure (authored in `work-account.md`) once to append one line to `state/feedback-log.jsonl`, and the loop ends. The draft file is not touched.
- On `edit`: route through APPLY-DRAFT-EDIT (Step 8) — the draft-file rewrite happens first; the one `edit` line is logged only after it succeeds.
- Confirm tersely; surface a write failure rather than pretend it logged. A re-reaction on a re-rendered draft appends a new line — append-only, never a rewrite of a logged line.

**8 — APPLY-DRAFT-EDIT (shared procedure).** Authored here once — this handler owns the draft
file, so it owns the rewrite — and reused by name (never re-authored) by `run-unbound`'s output
gate and by any later rep edit request on the draft. Applies **one** rep `edit` verdict to the
draft via `apply-draft-edit(namespace, slug, source_task, note)`, in this exact order:

- (a) tie the edit to the draft this run wrote for the item — the **latest-dated** `drafts/YYYY-MM-DD-email.md` (the same authority rule as work-account's APPLY-EDIT / SET-STATUS); ask if ambiguous; when no draft exists say so honestly and write nothing.
- (b) bound the edit to `to[]`, `subject`, and `body` — the declared field set. `filename`, the `status: draft` boundary, and every other frontmatter field are **out of scope**: an edit never sends, queues, or renames.
- (c) re-draft the affected content in `rep/voice.md` voice, honoring the same content contract DRAFT honored (the questions, the verified-never-invented asset, the next step and its meeting ask) — an edit **re-runs** the contract, it does not bypass it. Never fabricate to satisfy an instruction the evidence cannot ground; say so instead.
- (d) **rewrite the draft file FIRST**, every out-of-scope field byte-unchanged — if that write fails, report it and do **not** log the edit.
- (e) **only then** append exactly one `edit` line via `capture-feedback(namespace, slug, task_id, verdict="edit", note=<the rep's text verbatim>)`, where `task_id` is the draft's `source_task`.
- (f) re-present the revised draft via `render.email_draft` (its verdict footer comes with it) and confirm tersely; the rep's next verdict continues the loop.
- Its only writes are the one draft-file rewrite and the one log line — never an external action, never a send or a queue.

## Writes

- `accounts|projects/<slug>/drafts/YYYY-MM-DD-email.md` (`status: draft`) — the only file write; written complete by DRAFT (frontmatter incl. `asset_referenced` and the `cc` list, both set at write time; `cc: []` on the no-meeting path); create `drafts/` if missing; idempotent-by-date. Rewritten in place by APPLY-DRAFT-EDIT (Step 8), bounded to `to[]` / `subject` / `body` — the same file, never a second one.
- `state/feedback-log.jsonl` — one appended line per draft verdict, via the shared `capture-feedback`; on an edit, only after the draft-file rewrite succeeds.
- No external write; no email is sent or queued (`email.queue_draft` / `crm.*` bindings are intentionally absent). The only external access is read-only Drive and Calendar. The PROPOSE-CONTENT task is in-memory only.

## Invariants

- **Never fabricate.** No invented link, address, attendee, slot, date, commitment, metric, stakeholder, or answer. Where grounding is only `inferred:`, mark it and keep the claim tentative.
- **Local only.** The draft is a file; nothing is ever sent or queued; Drive and Calendar are read-only; the PROPOSE-CONTENT task never touches disk.
- **One email per item per run.** Additional `followup_email` tasks fold into the same draft, never a second file. Idempotent-by-date; no empty draft is ever written.
- **Read-only grounding.** Never re-rank, re-annotate, or re-decide the `work-account` output.
- **Meeting path only.** AVAILABILITY and SCHEDULING-CONFIRM run only when `next_step` is a meeting; the no-meeting path drafts single-pass with `cc: []` and no attendee prompt. SCHEDULING-CONFIRM is a hard pre-draft gate.
- **Silence is never a signal.** Neither the SCHEDULING-CONFIRM gate nor DRAFT VERDICT CAPTURE proceeds on silence — each writes nothing until the rep reacts.
- **An email-draft edit is applied, not merely recorded** — APPLY-DRAFT-EDIT (Step 8) rewrites the draft file, mirroring the ordering discipline `work-account`'s APPLY-EDIT applies to the plan file.
- **Bounded rewrite.** An edit touches `to[]`, `subject`, and `body` only. `status: draft` and `filename` are never in scope — nothing is ever sent, queued, or renamed, and the rewrite is never a partial application: on a write failure the file is left as it was and nothing is logged.
- **Write the file first, log only on success.** The draft file and the feedback log never disagree; one `edit` line per cycle, append-only, and a rep who edits twice gets two lines, never a rewritten one.
- **The edit loop is rep-bounded.** Every cycle requires a rep turn — there is no handler-side iteration and no cycle cap. Accept ends it; silence ends it with nothing written and the draft at its last applied state, narrated honestly as abandoned, never as accepted.
- **At most one asset**, Drive-verified; a stale, dead, unresolved, or low-confidence candidate is dropped to `asset_referenced: none` (also a signal to refresh `assets.md`). A verified asset and a PROPOSE-CONTENT proposal are mutually exclusive.
- **`transcript: missing`** — do not re-fetch or fabricate; draft from the remaining evidence + `context.md` and surface the gap; if nothing is groundable, write no file and say so.
- **Project item (no deal stage)** — treat every `assets.md` row as stage-eligible and match on pain point + project context; ground any proposal angle on project context; never invent a stage.
