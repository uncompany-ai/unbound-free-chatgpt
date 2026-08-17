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
- The loop-phase files under `skills/loop/` — each read at its beat's entry, never earlier (see Invariants, phase loading). Their own Reads sections state what each beat touches on disk.
- `resources/helpers/prepare-slate.py` and `resources/pre-slate-fallback.md` — the bundled deterministic pre-slate helper and its version-matched prose fallback, probed once at the final pre-query beat below (ADR-1 amendment). Neither is capability-mediated: no `runtime/tool-bindings.md` row.
- In-memory outputs of every downstream skill it composes.

## Procedure

**1 — Read state and set up the session (silent — see Invariants, narration discipline).**

1. Open `state/run-state.yaml` as-is and read `last_run`, `timezone`, and optional `scan_window`.
  - Do not recreate, reshape, or write the file.
  - If the file is missing, or is not valid YAML with both `last_run` and `timezone`, stop and
     tell the rep — never invent values or create the file.
  - Do not parse or validate `scan_window` here — the final pre-query beat's `prepare` call (or its
     fallback) is its sole validator, and it needs the sampled clock to do that validation, so no
     earlier step can duplicate it.

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

**Final pre-query beat — helper probe and `prepare`.** After Step 1.5 has returned and immediately
before slot 1, sample the current instant exactly once as full ISO 8601 with offset in `timezone` —
the run's only clock read; no later step re-samples it. Take `resources/helpers/prepare-slate.py`
beside this skill's bundled resources, or `runtime/helpers/prepare-slate.py` in a corpus checkout,
and invoke its `prepare` command with `{ contract_version: 1, workspace_root: <working directory>,
sampled_at }` on stdin (protocol v1; full contract in `notes/tech-spec-deterministic-pre-slate.md`).
Read its stdout as JSON and branch on the result — never on the process exit code alone, since a
dead interpreter surface exits non-zero with no JSON at all:

- **`status: "ok"`** → the helper is available. Carry its six fields — `discovery_until`,
  `state_sha256`, `known_anchors`, `domain_routes`, `domain_collisions`, `context` — unchanged
  through slots 1-3 as the run's one immutable snapshot: `discover-events` passes it to `normalize`
  verbatim, `classify-work` reads `known_anchors` from it, `build-slate` passes its `state_sha256` to
  `materialize --apply`. No slot re-derives any of these.
- **`status: "unavailable"`** (missing PyYAML, or an unsupported `contract_version`) — an eligible
  fallback reason. Load `resources/pre-slate-fallback.md` in full and run its own `prepare` section
  over the same `sampled_at` instead; it returns the same window, known anchors, domain routing and
  display data by the identical rules (it carries no state-precondition hash of its own — its
  `materialize` section re-reads state directly within the same pass, so it needs none). Every
  downstream slot reads one carried "using the fallback" flag rather than re-probing.
- **No parseable JSON at all** — the script is missing at both paths, not executable, or the
  interpreter failed to launch — is the same eligible-fallback outcome as `unavailable`: the module's
  own doc comment is explicit that a dead interpreter surface never gets to emit its own diagnostic,
  so treat silence exactly like an explicit `unavailable`.
- **`status: "error"`** → a refusal: malformed state, a duplicate key, an unparseable `scan_window`,
  a `sampled_at` offset that does not represent `timezone`, or a resolved `discovery_until` not
  strictly after `last_run`. Stop before either source query and surface the exact diagnostic. Never
  fall back on a refusal — the fallback would reproduce the identical fault under prose reasoning,
  and reading it as unavailability would let a real defect hide behind a degraded-but-silent path.

| Slot | Skill | What it contributes |
| --- | --- | --- |
| 1 | `discover-events` | Find events in the discovery window by handing the raw source results and the `prepare` snapshot to `normalize` (or its fallback); retain ambiguity and fuzzy-match judgment. |
| 2 | `classify-work` | Route each event to its owning account or project, honoring upstream `suggested_slug` hints and the `prepare` snapshot's `known_anchors`; return each event's `display_name`. |
| 3 | `build-slate` | Hand classified events and the `prepare` snapshot to `materialize --apply` (or its fallback), which upserts `events` and derives the slate; render the returned `slate_view` unranked. |
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
below and stated in full in its phase file under `skills/loop/`:

- PLAN TRIAGE — one comparative verdict pass over the whole ranked plan, collected in a single
  batch, before anything is handled (Step 3.5 — `skills/loop/triage-and-execute.md`).
- EXECUTE TASKS — walk the accepted, executable tasks, sequentially in priority order, presenting
  and gating each one's drafted artifact at its own turn (Step 4 — the same
  `skills/loop/triage-and-execute.md`).
- NEXT STEPS — close-out: prescribed next step, outcome recap, open questions, then the CRM
  Updates sub-beat (Step 5 — `skills/loop/close-out.md`).

**The resume fork.** Immediately after selection, Step 3.2 detects an open work record and, when
one is present, reshapes this composition — superseding slots 4 and 6 — via
`skills/loop/select-and-resume.md`; see Step 3.2.

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

**3.2 — RESUME (detect, then route).** Runs on the one selected item after selection, before PLAN
TRIAGE. Look up `work[]` in `state/run-state.yaml` for the selected `(namespace, slug)`:

- **No record → the normal path**: state nothing and run nothing else in this step — the
  composition continues to slots 4, 5 and 6 exactly as written. That is the ordinary case, not a
  failure: an absent record simply means nothing is in flight for this item, which is also what a
  hand-deleted record honestly means. The resume file is never opened on this path.
- **Record present → the resume path**: read `select-and-resume`
  (`skills/loop/select-and-resume.md`) in full and follow it before anything else happens on this
  item. It owns verify → rehydrate → jump → restart and **writes nothing at all**; it **supersedes
  slots 4 and 6** — evidence re-fetched bounded to the record's `event_ids[]`, the plan read off
  disk, `work-account` not re-run, no second dated tasks file — and it enters PLAN TRIAGE, EXECUTE
  TASKS or NEXT STEPS at whichever beat the record's `phase` names.

**3.5 — PLAN TRIAGE (one comparative gate on the whole plan).** Runs on the one selected item
after `work-account` hands back its plan, before EXECUTE TASKS — and a `planned` resume enters
here. Read `triage-and-execute` (`skills/loop/triage-and-execute.md`) in full before collecting
any verdict: it states the beat's single batch `review.collect` pass, the per-verdict fan-out, the
edit re-confirmation rule, and the `advance-phase(…, triaged)` transition that admits Step 4.

**4 — EXECUTE TASKS (accepted only, sequential, type-dispatched).** Runs on the one selected item
after the Step 3.5 triage, before NEXT STEPS — and a `triaged` resume enters here. Stated in full
in the same `skills/loop/triage-and-execute.md`, read before anything is handled: the accepted-only
walk and its order, the `handled_on` skip, registry dispatch, the single `followup_email`
invocation, `mark-handled`, the artifact-verdict gate at each handler's own turn — present, then
collect accept/reject/edit, per `task-registry.md` Part B's Output-edit obligation — and the
closing `advance-phase(…, executed)` — including with an empty accepted set.

**5 — NEXT STEPS (close-out).** Runs on the one selected item, after the task-execution loop,
before session end — and an `executed` resume enters here. Read `close-out`
(`skills/loop/close-out.md`) in full before rendering any close-out beat: it states the headline
`next_step`, the outcome recap, the open-questions + qualification checkpoint, the CRM Updates
sub-beat `write-crm` completes, and the cycle's terminal `advance-phase(…, closed)` — the one beat
at which this item's events flip.

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

- **Phase files load at their beats, never before.** Steps 3.2 (resume path), 3.5, 4 and 5 are
  stated in full in `skills/loop/select-and-resume.md`, `skills/loop/triage-and-execute.md` and
  `skills/loop/close-out.md`. Do not open a phase file before its beat is reached, and do not
  enter a beat before reading its file in full this session — the step stubs above are entry
  conditions and routing, never the procedure, and nothing here licenses running a beat from its
  stub alone. A file already read this session is not re-read at a later beat it also owns.
- **Narration discipline — the discovery half runs silent.** Step 1 and composition slots 1–3
  (`discover-events` → `classify-work` → `build-slate`) emit **no** rep-facing narration: no
  state-validity line, no `last_run` echo,
  no framing sentence, no per-step status, no "Let me…" preambles, no demo/fixtures commentary,
  no tool-by-tool play-by-play. The first rep-facing output of a normal run is the slate. Exactly five pre-slate
  outputs stay loud: Step 1 stop conditions (now including the final pre-query beat's `prepare`
  refusal and, at slot 3, `materialize`'s), a `discover-events` source-binding failure, an
  ambiguous-classification ask in `classify-work`, the empty-slate "nothing new since
  `<last_run>`" line, and Step 1.5's two apply reports where they name something. Silence covers the happy path only — it never suppresses an error.
- **Managed context is applied, never negotiated.** Step 1.5 takes no verdict, renders no widget, makes no `review.collect` call, and offers the rep no way to decline — the ownership rule that licenses this is `setup-unbound`'s to state. It is never a reason a rep cannot work: an unreadable `STAMP` is read as unmanaged rather than surfaced as a parse error, and an apply that fails part-way leaves `context_stamp` at its prior value for the next run to retry — Step 1.5's continue clause carries the run past both.
- Drafts and plans only, and **nothing leaves the machine that the rep did not approve in this
  session**: no email is ever sent or queued, and the loop itself performs no external action. The
  Step 5 CRM close-out is one place an external write can occur, owned by `write-crm` and gated on
  its own explicit per-payload approval — the orchestrator never sends anything, and never carries
  an approval forward from an earlier beat, item, or run.
- Never name a concrete UI mechanism (ADR-6): call the logical `review.collect` / `render.*`
  capabilities; the runtime resolves them (interactive or in-chat fallback).
- Approval gates execution: the Step 3.5 triage submission is the bar — a task executes only on
  its explicit accept (or accept-after-edit) in that submission; on reject or silence nothing is
  executed — the outcome is narrated, never silently skipped, and the task stays documented in
  the plan.
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
> never before; never enter a beat without having read its file this session. The rows below only
> route to them — this map and the orchestrator's step stubs are entry conditions, never the
> procedure. `select-and-resume` opens on the resume path alone (an open work record found at
> Step 3.2); the no-record path never opens it.

| # | Phase | Procedure to follow | Notes |
|---|-------|---------------------|-------|
| 1 | Set up (silent) | *(this SKILL.md, Steps 1 and 1.5)* | Hydrate the working tree, then read `state/run-state.yaml` and resolve the optional `scan_window` (absent/`now` ⇒ unbounded to now; `<n>h`/`<n>d` ⇒ window capped at now; unparseable ⇒ STOP, surface, never guess) **silently** — no `last_run` echo, no framing sentence, no status line. The discovery half runs silent through slot 3; the window appears to the rep only with the slate (row 4), not before it. If run state is missing/invalid, STOP and surface — do not invent it. **Then Step 1.5's managed-context beat:** invoke `resources/managed-context-apply.md` directly and in full; no `resources/context/STAMP` in this bundle ⇒ the beat ends in silence and nothing below changes; a `STAMP` differing from run-state's `context_stamp` ⇒ the resource applies the team's context and this skill persists on success. It never blocks, never asks, and speaks only to name a replaced local edit or a stage rename's orphaned accounts. |
| 2 | Discover events | `resources/1-discover-events.md` | Resolve logical capabilities via `resources/tool-bindings.md`. |
| 3 | Classify work | `resources/2-classify-work.md` | Route to `accounts/` or `projects/`; assign/reuse slug. Routes on event metadata — no evidence has been fetched yet. |
| 4 | Build slate | `resources/3-build-slate.md` | Upsert the `events`; present the annotated slate via the logical `render.slate` capability (interactive card grid on rich-UI runtimes, plain annotated lines otherwise — resolved in `resources/tool-bindings.md`). A newly-discovered call is `evidence_status: unknown` and its card carries no recording clause. |
| 5 | Select | *(this SKILL.md, Step 3)* | Rep picks exactly one item; defer the rest (single-threading). **Then Step 3.2 detects a resume:** an item carrying an open work record routes through `resources/select-and-resume.md` — which supersedes rows 6 and 8 and jumps to the recorded beat — before anything else happens on it; no record ⇒ continue to row 6. **Nothing has been retrieved up to this point** — rows 2-4 issue no transcript or thread fetch at all. |
| 6 | Recover evidence | `resources/4-fetch-transcript.md` | The run's only evidence retrieval, for the selected item alone. Resolve `transcript.get` and `email.get_thread` via `resources/tool-bindings.md` (native Granola MCP connector for transcripts, read-only). Input is the item's durable `pending` events, so an event behind `last_run` recovers exactly like one found minutes ago. `missing` is first-class. |
| 7 | Bootstrap context | `resources/5-bootstrap-context.md` | Create `context.md` only if absent, grounded in the evidence just recovered. Selected item only. |
| 8 | Work the item | `resources/6-work-account.md` | REFERENCE → SYNTHESIZE (→ prioritize/etc. per that skill). |
| 9 | Plan triage, then execute tasks | `resources/triage-and-execute.md` | Open at PLAN TRIAGE entry — before any verdict is collected (a `planned` or `triaged` resume enters here too) — and follow it in full: one batch triage gate over the whole plan first (the accept is execution's only gate; triage card stack on rich-UI runtimes, in-chat prompt otherwise — resolved in `resources/tool-bindings.md`), then the sequential walk of accepted tasks. `followup_email` executes via `resources/7-draft-followup.md` at its turn; every other type resolves per `resources/task-registry.md`. Verdicts drive `feedback-log.jsonl` appends (via resources 6/7). |
| 10 | NEXT STEPS | `resources/close-out.md` | Open at close-out entry — before any close-out beat renders (an `executed` resume enters here) — and follow it in full: headline `next_step`, terse outcome recap, the combined email-draft render/verdict gate via the logical `render.email_draft` (preview and verdict on one surface; an edit is applied via `resources/7-draft-followup.md`'s `apply-draft-edit` before it is logged), the open-questions checkpoint, then the CRM sub-beat — open `resources/8-write-crm.md` and hand it the in-memory `crm_update` object; that file's own procedure is authoritative (nothing written externally on its simulate path). All resolved in `resources/tool-bindings.md`; verdicts drive `feedback-log.jsonl` appends (via resources 6/7). |
| 11 | Close | *(this SKILL.md, Step 6)* | Advance `last_run` in `state/run-state.yaml` — the only end-of-session write. |
