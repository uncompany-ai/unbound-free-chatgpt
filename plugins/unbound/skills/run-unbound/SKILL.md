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
- `resources/context/STAMP` — taken in Step 1's batch; an absent `STAMP` is the unmanaged path. Its `resources/context/{process,messaging,assets}.md` bodies stay lazy, read at Step 1.5 by `managed-context-apply` and only on a stamp mismatch. Neither is capability-mediated: no binding row, and nothing for `connect-tools` to report. The bundle ships this skill the shared apply resource and its bodies now too, so this loop can apply new context itself rather than only detecting it.
- The loop-phase files under `resources/` — each read at its beat's entry, never earlier but for the one batch the invariant names (see Invariants, phase loading). Their own Reads sections state what each beat touches on disk.
- `resources/helpers/prepare-slate.py` and `resources/pre-slate-fallback.md` — the bundled deterministic pre-slate helper and its version-matched prose fallback, probed once at the final pre-query beat below (ADR-1 amendment). Neither is capability-mediated: no binding row.
- In-memory outputs of every downstream skill it composes.

## Procedure

**Pre-slate contract — binding on every beat below.**

- **Silent until the slate.** Nothing rep-facing before it but six loud outputs: a Step 1 stop
  (including `prepare`/`materialize` refusals), the pre-query beat's no-reachable-helper line, a
  `discover-events` source-binding failure, a `classify-work` ambiguity ask, the empty-slate
  "nothing new since `<last_run>`" line, and Step 1.5's apply reports where they name something. No echo, framing, status, "Let me…", fixtures
  commentary, or play-by-play. Silence covers the happy path, never an error.
- **One render.** A non-empty slate is exactly one `render.slate`, the helper's fragment passed
  unchanged — never re-derived, hand-assembled, or echoed as lines.
- **Fallback is licensed, never assumed.** Plain lines only where the bindings fragment's surface
  line reads `unbound`, or a render call actually failed. Skipping the attempt licenses nothing.

**1 — Read state and set up the session (silent).**

**Open the pre-slate reads as one batch (parallel where supported)** before anything below, never one
at a time as each beat reaches them: `state/run-state.yaml`; the Step 1.5 apply resource
`resources/managed-context-apply.md`; `resources/context/STAMP`; the slot 1–3 bodies
`resources/1-discover-events.md`, `resources/2-classify-work.md` and `resources/3-build-slate.md`;
and `resources/bindings/pre-slate-discovery.md` and `resources/bindings/pre-slate-slate.md`. Where
these are registered as named skills rather than bundled beside this one, take each by name. Every
one is read on the happy path regardless and none decides whether another is opened, so the load
costs about one read rather than eight. The beat that owns each file uses what this batch returned
and does not re-open it. Two misses are ordinary and silent, not faults: an absent `STAMP` is the
unmanaged path (Step 1.5 owns that rule), and absent fragments leave capability resolution exactly
where a tree shipping no fragments already has it. Nothing else joins the batch — the
`resources/context/*.md` bodies load only on a stamp mismatch, `resources/pre-slate-fallback.md` only
on an unavailable helper, and every phase file at its own beat (see Invariants, phase loading).

1. Open `state/run-state.yaml` as-is and read `last_run`, `timezone`, and optional `scan_window`.
  - Do not recreate, reshape, or write the file.
  - If the file is missing, or is not valid YAML with both `last_run` and `timezone`, stop and
     tell the rep — never invent values or create the file.
  - Do not parse or validate `scan_window` here — the final pre-query beat's `prepare` call (or its
     fallback) is its sole validator, and it needs the sampled clock to do that validation, so no
     earlier step can duplicate it.

**1.5 — Managed context apply (slot).** Runs after Step 1's state read, before Step 2's discovery — see Invariants (managed context).

1. **Invoke** `managed-context-apply` (`resources/managed-context-apply.md`) in full — it is the sole owner of detect → compare → note → apply whole → stamp → report replaced edits → report stage-rename fallout → state the asset-link assumption; this beat restates none of its clauses and never enters `setup-unbound`'s steps 1–8.
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

**Final pre-query beat — helper probe and `prepare`.** After Step 1.5 has returned and immediately
before slot 1, sample the current instant exactly once as full ISO 8601 with offset in `timezone` —
the run's only clock read; no later step re-samples it. Resolve the helper **in the shell that can
write the workspace tree**, and run it — and every helper command after it — there:
`runtime/helpers/prepare-slate.py` in the tree, or `resources/helpers/prepare-slate.py` beside this
skill's bundled resources. Where that tree and the executing environment are separate filesystems —
the condition the bundled run order's slot 1 already names — a copy reachable only from the other
side is not a candidate at all, because it cannot land slot 3's `materialize --apply`; probing it
there returns an `ok` truthful about that shell and meaningless for the write, so it is never the
basis of the branch. No candidate on the writable side is the last outcome below. Otherwise invoke
`prepare` with `{ contract_version: 2, workspace_root: <working directory>, sampled_at }` on stdin
(protocol v2; `describe` prints the full stdin contract).

**Two commands, and neither is narrated.** The clock sample and the `prepare` invocation are the
whole of this beat. Never reach it through a run of small shell steps that list the tree, test the
helper path, echo the stdin payload, or re-read the snapshot afterwards — the helper already reports
every one of those outcomes in its own JSON, so each extra call costs a model round trip and buys
nothing. The pre-slate contract's silence rule covers this beat entire: nothing between the two
commands, and nothing between the second and the branch below.

Read its stdout as JSON and branch on the result — never on the process exit code alone, since a
dead interpreter surface exits non-zero with no JSON at all:

- **`status: "ok"`** → the helper is available and has written the run's snapshot. Carry its six
  returned fields — `snapshot_path`, `last_run`, `timezone`, `discovery_until`, `known_anchors`,
  `context` — unchanged through slots 1–3: slot 1 hands `snapshot_path` and `sampled_at` to
  `normalize`, slot 2 reads `known_anchors` and `context` in head, slot 3 hands the same pair to
  `materialize --apply --render`. Domain routing stays in the snapshot; no slot re-types or
  re-derives it.
- **`status: "unavailable"`** with `reason` `pyyaml_missing` or an unsupported `contract_version`
  — an eligible fallback reason. Load `resources/pre-slate-fallback.md` in full and run its `prepare` section
  over the same `sampled_at`; it returns the same window, known anchors, domain routing and
  display data by identical rules. Every
  downstream slot reads one carried "using the fallback" flag rather than re-probing.
- **No parseable JSON at all** — the script is missing at both paths, not executable, or the
  interpreter failed to launch — is the same eligible-fallback outcome as `unavailable`: a dead
  interpreter never emits its own diagnostic.
- **`status: "error"`** → a refusal: malformed state, a duplicate key, an unparseable `scan_window`,
  a `sampled_at` offset that does not represent `timezone`, or a resolved `discovery_until` not
  strictly after `last_run`. Stop before either source query and surface the exact diagnostic. Never
  fall back on a refusal — the fallback would reproduce the identical fault under prose reasoning,
  and reading it as unavailability would let a real defect hide behind a degraded-but-silent path.
- **`reason: "template_unreadable"`** — the pinned slate template is unreadable — stops by that
  same rule: the fallback renders no widget, and a resource this artifact ships is broken
  identically on every install. Its `message` names the template path.
- **No helper reachable from the write-capable shell** — settled at the resolution above, before
  `prepare` is invoked, so there is no status to read. Neither a broken shipped resource nor a
  declined attempt: the other side's copy was never a candidate here, so nothing was skipped. That
  is a real unavailability and it licenses the fallback on the same terms as `unavailable` — load
  `resources/pre-slate-fallback.md` in full and carry the same flag. Say which shell was probed and
  why the bundled copy was not a candidate: this degradation is named, never silent.

| Slot | Skill | What it contributes |
| --- | --- | --- |
| 1 | `discover-events` | Find events in the discovery window by handing the raw source results and the snapshot path to `normalize` (or its fallback); retain ambiguity and fuzzy-match judgment. |
| 2 | `classify-work` | Route each event to its owning account or project, honoring upstream `suggested_slug` hints and the `prepare` result's `known_anchors`; return each event's `display_name`. |
| 3 | `build-slate` | Hand classified events and the snapshot path to `materialize --apply --render` (or its fallback), which upserts `events` and derives the slate with its fragment; present it unranked. |
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

After slot 6 hands back its plan, three loop beats close the run, each routed by its own step
below and stated in full in its phase file under `resources/`:

- PLAN TRIAGE — one comparative verdict pass over the whole ranked plan, collected in a single
  batch, shaping the list before anything is handled (Step 3.5 —
  `resources/triage-and-execute.md`).
- EXECUTE TASKS — walk the accepted executable tasks sequentially in priority order, gating each
  at its own turn before dispatch and again on the artifact it drafts (Step 4 — the same
  `resources/triage-and-execute.md`).
- NEXT STEPS — close-out: prescribed next step, outcome recap, open questions, then the CRM
  Updates sub-beat (Step 5 — `resources/close-out.md`).

**The resume fork.** Immediately after selection, Step 3.2 detects an open work record and, when
one is present, reshapes this composition — superseding slots 4 and 6 — via
`resources/select-and-resume.md`; see Step 3.2.

Side entry (not part of this loop): `collect-tasks` is rep-invoked and pure-read; the
orchestrator never invokes it.

**3 — Selection (rep picks one).**

- Present the unranked slate and let the rep choose one item; do not auto-rank or auto-select.
- If ambiguous, ask — proceed only once exactly one item is identified.
- Items whose evidence is `missing` remain selectable, as are email-grounded items (see
  Invariants).
- **This step is re-entered**, from Step 5's loop-back, once an item's cycle closes. A second pick
  runs this step and everything after it unchanged, resume fork included; slots 1–3 do not run
  again and `run-unbound` is not re-invoked.
- Selecting does not mark anything `processed` — that is `work-account`'s job, and it flips only
  the contributing `event_ids[]`, at the cycle's close-out rather than anywhere earlier. Unselected
  items keep every pending event they had and reappear next run.

**3.2 — RESUME (detect, then route).** Runs on the one selected item after selection, before PLAN
TRIAGE. Look up `work[]` in `state/run-state.yaml` for the selected `(namespace, slug)`:

- **No record → the normal path**: state nothing, and beyond the batch below run nothing else in
  this step — the composition continues to slots 4, 5 and 6 exactly as written. That is the
  ordinary case, not a failure: an absent record simply means nothing is in flight for this item,
  which is also what a hand-deleted record honestly means. The resume file is never opened on this
  path.

  **Open this path's reads as one batch (parallel where supported)**, before slot 4 and never one
  at a time as each beat reaches them: `resources/4-fetch-transcript.md`,
  `resources/6-work-account.md`, `resources/task-registry.md` and
  `resources/triage-and-execute.md`. Where these are registered as named skills rather than bundled
  beside this one, take each by name. Every one is read on this path regardless — slot 4 and slot 6
  both run, and Step 3.5 reads the registry to resolve each retained task's `mode` — and none
  decides whether another is opened, so the load costs about one read rather than four. The beat
  that owns each file uses what this batch returned and does not re-open it. Nothing else joins it:
  `resources/5-bootstrap-context.md` opens only on a first encounter, `select-and-resume` only on
  the branch below, and `close-out` at its own beat.
- **Record present → the resume path**: read `select-and-resume`
  (`resources/select-and-resume.md`) in full and follow it before anything else happens on this
  item. It owns verify → rehydrate → jump → restart and **writes nothing at all**; it **supersedes
  slots 4 and 6** — evidence re-fetched bounded to the record's `event_ids[]`, the plan read off
  disk, `work-account` not re-run, no second dated tasks file — and it enters PLAN TRIAGE, EXECUTE
  TASKS or NEXT STEPS at whichever beat the record's `phase` names.

**3.5 — PLAN TRIAGE (one comparative gate on the whole plan).** Runs on the one selected item
after `work-account` hands back its plan, before EXECUTE TASKS — and a `planned` resume enters
here. Read `triage-and-execute` (`resources/triage-and-execute.md`) in full before collecting
any verdict: it states the beat's single batch `review.collect` pass, the per-verdict fan-out, the
edit re-confirmation rule, and the `advance-phase(…, triaged)` transition that admits Step 4.

**4 — EXECUTE TASKS (accepted executable tasks only, sequential, gated at each turn).** Runs on the
one selected item after the Step 3.5 triage, before NEXT STEPS — and a `triaged` resume enters here.
Stated in full in the same `resources/triage-and-execute.md`, read before handling: the walk's
two-part filter and its order, the `handled_on` skip, the **4a per-task gate that decides execution
before any handler is invoked**, registry dispatch, the single `followup_email` invocation,
`mark-handled`, the artifact-verdict gate at each handler's own turn — present, then collect
accept/reject/edit, per `task-registry.md` Part B's Output-edit obligation — and the closing
`advance-phase(…, executed)` — including with an empty walk set.

**5 — NEXT STEPS (close-out).** Runs on the one selected item, after the task-execution loop,
before session end — and an `executed` resume enters here. Read `close-out`
(`resources/close-out.md`) in full before rendering any close-out beat: it states the headline
`next_step`, the outcome recap, the open-questions + qualification checkpoint, the CRM Updates
sub-beat `write-crm` completes, and the cycle's terminal `advance-phase(…, closed)` — the one beat
at which this item's events flip — and the loop-back that follows it, returning control to Step 3
over a slate `build-slate`'s REDRAW entry redrew. The procedure for both stays in those two files.

**6 — Advance `last_run` at session end.**

- Advance exactly once, at session end — never mid-run. The precondition: the slate was fully
  presented and selection resolved, where "resolved" means the rep selected an item, the rep
  explicitly declined or deferred every item, or the slate was empty (nothing to select). All
  three paths advance. A session that looped back resolves on its **last** slate, not its first,
  and still advances exactly once however many accounts the rep worked.
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

- **Phase files load at their beats, never before.** Steps 3.2 (resume path), 3.5, 4 and 5 are
  stated in full in `resources/select-and-resume.md`, `resources/triage-and-execute.md` and
  `resources/close-out.md`. Do not open a phase file before its beat is reached, and do not
  enter a beat before reading its file in full this session — the step stubs above are entry
  conditions and routing, never the procedure, and nothing here licenses running a beat from its
  stub alone. A file already read this session is not re-read at a later beat it also owns. The one
  exception is `triage-and-execute.md`, taken in Step 3.2's no-record batch because that path always
  reaches Step 3.5 — read in full there, which is what admits the beat.
- **Managed context is applied, never negotiated.** Step 1.5 takes no verdict, renders no widget, makes no `review.collect` call, and offers the rep no way to decline — the ownership rule that licenses this is `setup-unbound`'s to state. It is never a reason a rep cannot work: an unreadable `STAMP` is read as unmanaged rather than surfaced as a parse error, and an apply that fails part-way leaves `context_stamp` at its prior value for the next run to retry — Step 1.5's continue clause carries the run past both.
- Drafts and plans only, and **nothing leaves the machine that the rep did not approve in this
  session**: no email is ever sent or queued, and the loop itself performs no external action. The
  Step 5 CRM close-out is one place an external write can occur, owned by `write-crm` and gated on
  its own explicit per-payload approval — the orchestrator never sends anything, and never carries
  an approval forward from an earlier beat, item, or run.
- Never name a concrete UI mechanism (ADR-6): call the logical `review.collect` / `render.*`
  capabilities; the runtime resolves them (interactive or in-chat fallback).
- Approval gates execution at the task's own turn: the Step 3.5 submission shapes the list —
  `accept` admits an executable task to the walk and starts nothing — and the 4a gate is the bar.
  Only its explicit `execute` (or execute-after-edit) runs a handler; on `defer`, `cancel` or
  silence at either gate nothing is executed, the outcome narrated rather than silently skipped. A
  deferred, define-only or unverdicted task stays in the plan; a rejected or cancelled one is
  dropped.
- Neither PLAN TRIAGE, the task-execution loop, nor NEXT STEPS re-ranks, re-suppresses
  `tasks`/`dropped`, sets task status, or re-runs synthesis; their only writes are the per-verdict
  `feedback-log.jsonl` appends — including the artifact-verdict line the task-execution loop's
  present-and-collect beat captures at each handler's own turn — the `apply-edit`/promotion
  plan-file rewrites, and the `advance-phase`/`mark-handled` cycle writes (all via `work-account`'s
  shared procedures), plus the email draft `draft-followup` owns — written by its DRAFT phase and
  rewritten in place by its `apply-draft-edit` — and the account-only qualification updates
  `work-account`'s CAPTURE-QUALIFICATION owns. The Step 5 checkpoint remains a write-free collector:
  open answers persist nowhere, and qualification persistence routes only through that named
  authority. No new writer exists at any gate.
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
- **A session ends four ways, and none of them is a second run.** The rep declines to pick from a
  redrawn slate; the redrawn slate is empty; a close-out holds a cycle open instead of closing it;
  or the run stops on a surfaced fault. The first three reach Step 6 and advance once. The fourth
  ends where it stopped, advancing only if Step 6's precondition was already met. However many
  accounts a session works, there is one clock sample, one `prepare`, one pass of slots 1–3, and
  one advance.
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
- `capture-feedback` is referenced by name (authored in work-account), never re-authored here. So
  are `advance-phase`, `mark-handled`, `capture-qualification`, and the Step 6.5 CRM evaluation
  close-out derives at NEXT STEPS: this skill names the beat each one attaches to and restates no
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
>
> **Loop phases (Steps 3.2, 3.5–4, 5 — internal):** `resources/select-and-resume.md`,
> `resources/triage-and-execute.md` and `resources/close-out.md` are the run loop's own beat
> procedures, bundled unnumbered like the shared apply resource. Open each at its beat's entry and
> never before — the one exception is `resources/triage-and-execute.md`, taken in row 5's no-record
> batch because that path always reaches PLAN TRIAGE, and read in full there. Never enter a beat
> without having read its file this session. The rows below only
> route to them — this map and the orchestrator's step stubs are entry conditions, never the
> procedure. `select-and-resume` opens on the resume path alone (an open work record found at
> Step 3.2); the no-record path never opens it.

| # | Phase | Procedure to follow | Notes |
|---|-------|---------------------|-------|
| 1 | Set up (silent) | *(this SKILL.md, Steps 1 and 1.5)* | Stage the workspace tree in a single call before the first read — never lazily, as reads demand it. Where that tree and the executing environment are separate filesystems, the tree is also authoritative for writes: apply each write to it directly, by path — never stage a file, mutate the staged copy and hand-carry the result back, and never inline a file's bytes into a command. **Then batch the pre-slate reads:** open `state/run-state.yaml`, `resources/managed-context-apply.md`, `resources/context/STAMP`, `resources/1-discover-events.md`, `resources/2-classify-work.md`, `resources/3-build-slate.md`, `resources/bindings/pre-slate-discovery.md` and `resources/bindings/pre-slate-slate.md` in ONE parallel call — every one is read on the happy path regardless and none decides whether another is opened, so no row below re-opens one it already has, and a missing `STAMP` or fragment is ordinary and silent rather than an error. Then read `state/run-state.yaml` and resolve the optional `scan_window` (absent/`now` ⇒ unbounded to now; `<n>h`/`<n>d` ⇒ window capped at now; unparseable ⇒ STOP, surface, never guess) **silently** — no `last_run` echo, no framing sentence, no status line. The discovery half runs silent through slot 3; the window appears to the rep only with the slate (row 4), not before it. If run state is missing/invalid, STOP and surface — do not invent it. **Then Step 1.5's managed-context beat:** invoke `resources/managed-context-apply.md` directly and in full; no `resources/context/STAMP` in this bundle ⇒ the beat ends in silence and nothing below changes; a `STAMP` differing from run-state's `context_stamp` ⇒ the resource applies the team's context and this skill persists on success. It never blocks, never asks, and speaks only to name a replaced local edit or a stage rename's orphaned accounts. |
| 2 | Discover events | `resources/1-discover-events.md` | Resolve logical capabilities via `resources/tool-bindings.md`. |
| 3 | Classify work | `resources/2-classify-work.md` | Route to `accounts/` or `projects/`; assign/reuse slug. Routes on event metadata — no evidence has been fetched yet. |
| 4 | Build slate | `resources/3-build-slate.md` | Upsert the `events`; present the annotated slate via the logical `render.slate` capability (interactive card grid on rich-UI runtimes, plain annotated lines otherwise — resolved in `resources/tool-bindings.md`). A newly-discovered call is `evidence_status: unknown` and its card carries no recording clause. |
| 5 | Select | *(this SKILL.md, Step 3)* | Rep picks exactly one item; defer the rest (single-threading). **Then Step 3.2 detects a resume:** an item carrying an open work record routes through `resources/select-and-resume.md` — which supersedes rows 6 and 8 and jumps to the recorded beat — before anything else happens on it; no record ⇒ continue to row 6. **No record ⇒ batch this path's reads:** open `resources/4-fetch-transcript.md`, `resources/6-work-account.md`, `resources/task-registry.md` and `resources/triage-and-execute.md` in ONE parallel call before row 6 — every one is read on this path regardless (rows 6, 8 and 9 all run, and row 9 reads the registry for each task's `mode`) and none decides whether another is opened, so no row below re-opens one it already has. Nothing else joins it: row 7's `resources/5-bootstrap-context.md` is first-encounter-only, `resources/select-and-resume.md` belongs to the resume branch, and `resources/close-out.md` opens at row 10. **Nothing has been retrieved up to this point** — rows 2-4 issue no transcript or thread fetch at all. |
| 6 | Recover evidence | `resources/4-fetch-transcript.md` | The run's only evidence retrieval, for the selected item alone. Resolve `transcript.get` and `email.get_thread` via `resources/tool-bindings.md` (native Granola MCP connector for transcripts, read-only). Input is the item's durable `pending` events, so an event behind `last_run` recovers exactly like one found minutes ago. `missing` is first-class. |
| 7 | Bootstrap context | `resources/5-bootstrap-context.md` | Create `context.md` only if absent, grounded in the evidence just recovered. Selected item only. |
| 8 | Work the item | `resources/6-work-account.md` | REFERENCE → SYNTHESIZE (→ prioritize/etc. per that skill). |
| 9 | Plan triage, then execute tasks | `resources/triage-and-execute.md` | Open at PLAN TRIAGE entry — before any verdict is collected (a `planned` or `triaged` resume enters here too) — and follow it in full: one batch triage gate over the whole plan first (the accept is execution's only gate; triage card stack on rich-UI runtimes, in-chat prompt otherwise — resolved in `resources/tool-bindings.md`), then the sequential walk of accepted tasks. `followup_email` executes via `resources/7-draft-followup.md` at its turn, and its artifact's combined render/verdict gate runs there too — the logical `render.email_draft` (preview and verdict on one surface; an edit is applied via `apply-draft-edit` before it is logged), at the task's own turn, never deferred to NEXT STEPS; every other type resolves per `resources/task-registry.md`. Verdicts drive `feedback-log.jsonl` appends (via resources 6/7). |
| 10 | NEXT STEPS | `resources/close-out.md` | Open at close-out entry — before any close-out beat renders (an `executed` resume enters here) — and follow it in full: headline `next_step`, terse outcome recap citing each walked task's already-captured verdict (no artifact verdict is collected or re-collected here — that gate ran at row 9), the open-questions checkpoint, then the CRM sub-beat — the close-out file derives the in-memory `crm_update` object (its own invocation of `resources/6-work-account.md`'s Step 6.5, after triage) and opens `resources/8-write-crm.md` with it; that file's own procedure is authoritative (nothing written externally on its simulate path). All resolved in `resources/tool-bindings.md`. |
| 11 | Close | *(this SKILL.md, Step 6)* | Advance `last_run` in `state/run-state.yaml` — the only end-of-session write. |
