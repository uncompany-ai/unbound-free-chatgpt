---
name: setup-unbound
description: Onboarding orchestrator for Unbound. Builds the company context tree — company/process.md, company/messaging.md, company/assets.md — plus the rep-owned rep/voice.md, the initial state/run-state.yaml, and closes with a connect-tools readiness verdict. Detects its mode from the files alone (first-run on an empty tree, resume on a partial one, refresh/audit on a complete one); on a complete tree it takes a directed instruction as readily as a document. Invoked directly by a rep or facilitator ("set up Unbound", "onboard me", "configure my company context", "refresh my company context", "audit my setup", "add an asset", "change a stage", "update my messaging", "fix my process") — it never auto-runs, and run-unbound invokes the shared managed-context-apply resource directly, never this skill by name.
tier: all
---
# setup-unbound

Onboarding orchestrator — the second root orchestrator beside `run-unbound`, invoked directly by a
rep or facilitator; it never auto-runs, and `run-unbound` invokes the shared `managed-context-apply`
resource directly, never this skill by name. Its posture is
extract-then-confirm: provided sources and interview answers do the talking, every artifact is
previewed and accepted before it is written, and the files themselves are the only state.

## Reads

- `company/process.md`, `company/messaging.md`, `company/assets.md`, `rep/voice.md`, `state/run-state.yaml` — read-only inspection at entry, against the validity predicates in Procedure step 1.
- `resources/context/STAMP` and `resources/context/{process,messaging,assets}.md` — bundled-resource reads at Procedure step 0, performed by `managed-context-apply`; an absent `STAMP` is the unmanaged path. Neither is capability-mediated: no `runtime/tool-bindings.md` row, and nothing for `connect-tools` to report.
- `resources/qualification-frameworks.md` — a bundled-resource read at Procedure step 3's `process` pass, framed like the `resources/context/STAMP` read above.
- `accounts/*/context.md` YAML frontmatter — account-only, read-only input to the Procedure step-0 and step-7.5 orphan scans; the scalar `stage:` value and directory slug are the complete read surface.
- Logical capability `render.setup_progress(progress_view)` — the section-checklist surface; view shape and Markdown fallback live in `runtime/tool-bindings.md` under `## render.setup_progress`; surface resolution per `resources/tool-bindings.md`.
- Logical capability `render.source_intake(intake_view)` (Procedure step 2) — the source-catalog checklist surface; view shape and Markdown fallback live in `runtime/tool-bindings.md` under `## render.source_intake`; surface resolution per `resources/tool-bindings.md`.
- The source pool (Procedure step 2) — session working material, one keyed slot per catalog item, read via four logical paths: files shared in chat, `content.search`/`content.get`, `web.fetch`, and `email.list_sent_threads` for the rep's own outbound mail.
- Logical capability `email.list_sent_threads(ts, limit)` (Procedure steps 2 and 3) — the rep's own sent mail, read on their explicit go-ahead; optional-degraded per its binding row in `runtime/tool-bindings.md`.
- Logical capabilities `render.context_preview` and `review.collect` (Procedure steps 3–4) — the section-loop preview and verdict surfaces; view shapes, item grammar, and routing live in `runtime/tool-bindings.md`; surface resolution per `resources/tool-bindings.md`.
- Logical capability `render.connections(connections_view)` (Procedure step 5) — the closing verdict-banner surface; view shape and board text rules live in `runtime/tool-bindings.md` under `## render.connections`; surface resolution per `resources/tool-bindings.md`.
- `skills/standalone/connect-tools.md` — the readiness-gate step invoked at Procedure step 5, composed per its gate entry; its handed-back report is the step's input.
- `runtime/tool-bindings.md` itself is never read by this skill — capability derivation belongs to `connect-tools`.

## Procedure

**0 — Managed context apply (slot). Contract: invoke the shared apply resource in full.**

1. **Compare** — read `context_stamp` from `state/run-state.yaml`.
  - A `state/run-state.yaml` that fails to parse stops the session before this invocation — see Invariants (unparseable state).
2. **Invoke** `managed-context-apply` (`skills/pipeline/managed-context-apply.md`) in full — it is the sole owner of detect → compare → note → apply whole → stamp → report replaced edits → report stage-rename fallout → state the asset-link assumption; this step restates none of its clauses.
3. **Consume** the returned report unchanged.
  - `unmanaged` or `current` ⇒ no write occurred: continue to step 1.
  - `applied` ⇒ continue to step 1.
  - `failed` ⇒ the tree keeps its prior `context_stamp`; continue to step 1.
4. **Continue** into step 1, whose predicates now read the applied files.

**1 — Detect the mode (read-only; the files are the only state).**

Each section id carries a rep-facing title and a one-line why:

| `id` | Title | Why it matters to you |
| --- | --- | --- |
| `process` | Your sales stages | Tells Unbound where each deal stands and what has to happen to move it forward. |
| `messaging` | How you talk about your product | Gives every follow-up draft your proof points and your answers to the objections you keep hearing. |
| `assets` | Your collateral library | Lets Unbound attach the right deck or one-pager instead of guessing. |
| `voice` | How you sound | Keeps your follow-ups sounding like you wrote them, not like your company's brochure. |
| `state` | Your starting point | Sets how far back your first run looks, in your timezone, so nothing is missed or double-counted. |

1. State what setup builds: the three `company/*` files (`process.md`, `messaging.md`, `assets.md`), the rep-owned `rep/voice.md`, the initial `state/run-state.yaml`, and the closing readiness verdict.
2. Render the section checklist via the logical `render.setup_progress` capability — section ids `process | messaging | assets | voice | state`, in that fixed order; in first-run mode all five are pending.
  - Each row carries its `title` and `why` from the table above.
  - Fallback: the plain-Markdown section-status list, identical content; resolution rule per `resources/tool-bindings.md`.
3. Evaluate each artifact against its validity predicate — valid-present or not. A predicate reads an absent *directory* identically to an absent *file* — the artifact is simply not valid-present; no error is surfaced, and step 1 stays a pure read:
  - `company/process.md` — exists, non-empty, carries the authoritative-enum header prose, and defines ≥ 1 stage as a heading whose token is lowercase/kebab, each with a definition and entry/exit criteria; and, when a `## Qualification` section is present, it is well-formed as `work-account` Step 6.5 declares — exactly one non-empty `**Framework:**` line and ≥ 1 bold-term field bullet, each with exactly one non-empty `Evidence:` child and one non-empty `Coach:` child; an absent section is valid.
  - `company/messaging.md` — exists, non-empty, and carries the full downstream section contract: positioning (what/who/value proposition), differentiation pillars, proof points, objection handling. Voice and tone are **not** part of this contract — they are the `voice` section's, in `rep/voice.md`. A surplus voice/tone block does not invalidate the file; the `voice` section's migration rule (step 3) removes it.
  - `company/assets.md` — exists with the fixed six-column header `| Asset | Vertical | Use case | Stage | Pain point | Link |`, every Stage cell in the process enum or `any`, and a freshness note with a named owner; zero data rows is valid.
  - `rep/voice.md` — exists, non-empty, and carries a voice/tone section: how the rep sounds, stated as rules a draft can be written against.
  - `state/run-state.yaml` — parses to a mapping with `last_run` (ISO 8601 with offset), `timezone` (IANA), and `events` (a list, empty on a fresh seed); keys beyond those three (for example `scan_window`) are permitted.
4. Decide the mode from those five results alone:
  - All five absent or template-empty ⇒ **first-run**. "Template-empty" = file absent, zero-length, or a `.gitkeep`-only directory — the working directory empty, or any namespace directory absent, reads the same way. A truly empty folder is the canonical first-run.
  - Some valid-present, some not ⇒ **resume**, continuing from the first invalid or absent artifact in the fixed section order.
  - All five valid-present ⇒ **refresh/audit**.
  - A present `state/run-state.yaml` that does not parse at all is not a resume target — see Invariants (unparseable state).
5. Announce the detected mode to the user.
6. Re-render progress to match: first-run ⇒ all sections pending; resume ⇒ completed sections done, the continuation target active; refresh/audit ⇒ the audit framing (the `proposed-changes(n)` status variant, shape unchanged).
7. In refresh/audit mode, continue past the announcement into one of two branches, decided on the opening utterance alone:
  - **A directed instruction enters the directed branch (step 8). The utterance names what to change and carries the change itself; it is not asking to be shown one.** Worked: "rename discovery to qualify" — names a `process` stage and its replacement, and offers no source.
  - **Anything else enters the refresh branch (step 7), exactly as before.** The utterance offers a source, or asks to be shown the diff, and names no change of its own. Worked: "refresh my context — here's our new deck" — offers a source, names no target; "audit my setup" — asks for the diff, names neither target nor change.
  - **Tie-break — a mixed utterance carries both** ("here's the new deck, and also rename discovery to qualify"): step 8 runs first for the directed half, then the flow falls through to step 7.2 re-intake for the document half. Both halves are proposed; neither is dropped.
  - **Mode detection wins over the instruction.** The directed branch is reachable only from a refresh/audit decision — all five artifacts valid-present (step 1.4). An instruction whose target section is not valid-present is a resume by that same decision, never a directed change. There is nothing to amend in a file that does not yet exist in schema-valid shape, so the session announces resume and continues at that artifact (step 6).

**1.5 — Prepare the working tree (slot).** Contract: the first write in the flow — idempotent, directory-only, content-free.

1. In first-run and resume modes, before the first section write, create each of `company/`, `rep/`, `state/`, `accounts/`, `projects/` where absent — an existing directory is left untouched, and a directory is only ever created, never removed, emptied, or renamed.
2. `accounts/` and `projects/` are created empty — directories only. Setup writes no file into either, ever; their content (`context.md`, drafts, task lists) stays bootstrap-context/run-loop owned — see Writes.
3. In refresh/audit mode this slot is a no-op by construction: all five artifacts are valid-present, so every directory already exists.
4. Creation is silent — no narration, no progress event.

**2 — Source intake & pooling.** Contract: eight asks, one item at a time, into one keyed source pool carried into every section that follows.

| `id` | What we ask for | Why it matters to you | Grounds |
| --- | --- | --- | --- |
| `sales-process` | Your sales process or playbook | Sets the stages every deal moves through, so Unbound knows what has to happen next. | `process` |
| `pitch-deck` | Your pitch deck | The fastest way to teach Unbound what you sell, who you sell it to, and what you prove. | `messaging`, `assets` |
| `positioning` | Your positioning or ICP doc | Tells Unbound who a good fit looks like, so follow-ups speak to the right buyer. | `messaging` |
| `brand` | Your brand guidelines | Keeps every draft inside the words your company uses and outside the ones it doesn't. | `messaging`, `voice` |
| `messaging-guide` | Your messaging guide | Gives Unbound your answers to the objections you keep hearing. | `messaging` |
| `website` | Your company website | A public, always-current source for how you describe yourselves and what you publish. | `messaging`, `assets` |
| `asset-list` | Your asset list or collateral folder | Lets Unbound attach the right deck or one-pager instead of guessing. | `assets` |
| `own-writing` | Your own writing — sent emails or anything that sounds like you | Keeps your follow-ups sounding like you wrote them. | `voice` |

1. **Open the checklist** — render every catalog item `pending` via the logical `render.source_intake` capability; view shape and Markdown fallback live in `runtime/tool-bindings.md` under `## render.source_intake`; surface resolution per `resources/tool-bindings.md`.
2. **Ask one item at a time** — work the catalog in table order, stating that item's ask and its why, then naming which read-only paths can carry it. No single ask names two items.
  - The four paths: files shared directly in chat; Drive documents via `content.search`/`content.get`; website pages via `web.fetch`; the rep's own recent sent mail via `email.list_sent_threads`, offered once at `own-writing`. The Drive and sent-mail reads happen only on the user's explicit go-ahead, named for what they read before asking; declining costs nothing but that path.
  - `have it` — the artifact arrives now, by any of those paths, and is pooled under this item's `id`.
  - `interview me` — no document, and ask me: the mark is recorded, and step 3.3 honours it.
  - `skip` — no document and no questions: the mark is recorded, and step 3.3 honours it.
3. **Record the answer** — re-render `render.source_intake` with that item's status now `provided | interview | skipped`, the mark step 3.3 reads. An ambiguous answer is asked once more, never inferred.
4. **Pool what arrived** — gather everything provided into the single source pool: session-held working material, one keyed slot per catalog item, never written to the repo, and no file write anywhere in this step (see Writes). Later sections re-read the pool — a source is never re-fetched, and a source already given is never re-asked. The pool carries the credential-hygiene standing rule — see Invariants (credential hygiene).
5. **Name any unavailable path** — an unavailable intake capability disables only its own path, never the outcome. `web.fetch` unavailable ⇒ `website` is named unavailable and setup proceeds on the remaining sources. `content.search`/`content.get` unavailable ⇒ Drive intake is named unavailable, and chat files and the interview still stand. `email.list_sent_threads` unavailable, or its go-ahead declined ⇒ the sent-mail path is named unavailable and `voice` is built from the samples the rep provides plus its own interview — never a blocked section.
6. **Recap the pool** — close the step with an honest recap, named per source. A source that failed to fetch or read is named plainly in that recap, and setup continues on the rest.
7. **Treat "I have nothing" as a first-class path** — every item still unanswered takes the `interview me` mark, and the flow proceeds to the guided interview in the section loop with no retry pressure and no error framing.
8. **Narrow on the managed path** — where step 0 applied the three `company/*` files, the catalog presents `own-writing` alone; the other seven ground only sections the rep no longer authors — see Invariants (managed ownership).

**3 — Section loop over `process`, `messaging`, `assets`, `voice` (slot).** Contract: one extract-then-confirm pass per section, in that order.

One generic pass, applied per section. The loop visits every section not yet valid-present — all of them on first-run, from the step-6 entry point on resume — and never reopens a completed one:

1. **Gather** — re-read the step-2 session pool; its no-re-fetch, no-re-ask contract (step 2) governs every section's read.
2. **Extract** — draft the section from the pool with a provenance label on every block: `Evidence · <source> <locator>` (for example `Evidence · deck p.4`, `Evidence · website /pricing`, `Evidence · playbook §3`) or `Answer · rep`. A block with no source becomes a gap marker (the write step's blockquote form) or a targeted question — never a plausible invention.
3. **Gap interview** — ask only for what extraction couldn't cover: one focused question at a time, bounded to the gap, never a form-dump; each answer folds into the draft as an `Answer · rep` block. A pooled source contradicting the user's direct answer resolves in the answer's favor, noted in the preview. Extraction and interview alike sit under the credential-hygiene standing rule — see Invariants.
  - **The step-2 marks decide what is asked.** `interview` ⇒ the parts that item grounds are asked here, as promised at intake. `skipped` ⇒ nothing is asked, and any part it leaves ungrounded persists as the write step's gap blockquote. A part already grounded by a different provided item is never asked regardless of any mark — coverage wins over intent.
4. **Preview** — render the draft via the logical `render.context_preview` capability: the artifact shaped like itself, gaps and provenance visible; view shape and Markdown fallback live in `runtime/tool-bindings.md` under `## render.context_preview`; surface resolution per `resources/tool-bindings.md`.
  - The call carries the section's `title` and `why` from the step-1 table.
5. **Verdict** — collect exactly one `review.collect` item of kind `context_section`, its `task_id` carrying the section id; item grammar and verdict routing live in `runtime/tool-bindings.md` under `## review.collect`. Accept ⇒ this skill performs the section's file write (next step); edit ⇒ the note is applied to the draft and re-previewed; reject ⇒ the section is re-extracted or re-interviewed afresh. No `state/feedback-log.jsonl` line, ever.
6. **Write whole** — on accept, write the section's file complete, in a single write, creating the file's parent directory if absent (see Writes). Provenance labels are a preview-only overlay, never written into `company/*`; an unresolved gap persists into the file only as the exact blockquote `> **Gap:** <what's missing>. Fill via a setup-unbound refresh.` The written file passes its step-1 validity predicate and `runtime/lint.sh` at the moment of writing — a post-write failure is surfaced as a bug, never shrugged off.
7. **Progress** — re-render via `render.setup_progress` with the section marked done.

Per-section specifics — each accepted file's self-documenting schema prose is adapted from the hand-authored original, never copied verbatim:

- **`process → company/process.md. Extract the stage ladder — stage names, a definition, and entry/exit criteria per stage; playbook, process doc, and deck are the usual carriers. The draft previews as a pipeline.`** The accepted file lands in its step-1 predicate shape, and its tokens stay stable — renaming one silently orphans every account already tagged with it. The pass always asks which qualification framework the team runs, every time this section is authored. Pooled evidence naming one pre-selects the ask's default as an `Evidence · <source> <locator>` suggestion. Only the rep's answer decides; an ambiguous answer is asked once more per the step-2.3 idiom, never inferred. The answer enum is exactly `MEDDPICC | MEDDIC | BANT | Custom | None`, its named options derived from `resources/qualification-frameworks.md`'s own `##` headings rather than hard-coded. A named framework populates the section deterministically from that file's matching template — field labels, Evidence, and Coach lines byte-identical, provenance `Evidence · qualification-frameworks.md <framework>`. Exactly one bounded customize offer follows: reword an Evidence or Coach line, or add or remove a field. Each edit folds in as `Answer · rep`, a label edit preceded by the registry's join-key warning. A decline leaves the template as-is. **`Custom builds the section through this same gap-interview grammar, one field at a time, the rep's own framework name on the **Framework:** line, never the token Custom. The draft is validated against the registry's declaration shape before preview; a defect is named and re-asked, never written invalid. None writes no ## Qualification section — that absence in the accepted file is the whole durable record, no marker key and no sidecar state. The section, present or absent, rides this same single verdict, never a second review.collect item. A bundle missing resources/qualification-frameworks.md degrades the named-framework path to the Custom interview, the absence surfaced plainly, never a fabricated template.`**
- **`messaging → company/messaging.md. Extract the four contract parts from their usual pooled carriers — positioning (what/who/value proposition) chiefly from the ICP or positioning doc, deck, and website; differentiation pillars from the deck and website; proof points from case-study or results material in the deck or on the site; objection handling from the playbook or messaging guide — pairings are guidance, not a closed rule. Voice and tone are not extracted here — they are the voice section's. The draft previews as a positioning-block card. The accepted file lands in its step-1 predicate shape.`** Its schema prose names its downstream readers `work-account` and `draft-followup` and its source-of-truth stance. **`An ungrounded part persists via the write step's gap blockquote — for example > **Gap:** no proof points found in provided sources. Fill via a setup-unbound refresh.`**
- **`assets → company/assets.md.`** Build the asset index — one row per asset across the six columns of its step-1 predicate — chiefly from a pooled asset list when one was given, plus collateral named in the deck, on the website, or by the user in the gap interview. A `Stage` cell draws from the `process.md` enum — authored in this session's `process` pass, or standing valid on disk on a resume — or `any`, permitted only in this file. A missing freshness-note owner is a targeted gap question, never an invented name. A `Link` cell has exactly two admissible origins: pasted verbatim by the user, or verified resolvable during the session via the logical `content.get` capability — a per-link resolvability read on the already-pooled path, distinct from a source re-fetch. A link that fails verification, or a claimed asset with no link and no user-provided location, stays out of the table and is surfaced plainly in the preview — never construct, guess, or repair a URL. Zero data rows is a valid accepted outcome. The draft previews as the asset-table card — the actual table shape. The accepted file lands in its step-1 predicate shape. Its schema prose names its downstream reader `draft-followup`, the first-pass asset matcher, and restates the stage-token stability warning against the user's own enum — an orphan stage value silently breaks matching.
- **`voice → rep/voice.md. Extract how the rep sounds — tone, register, the constructions they use and the ones they refuse. Its usual pooled carriers are the messaging guide and the rep's own writing — samples shared in chat, and sent mail on the go-ahead; pairings are guidance, not a closed rule. The draft previews as a positioning-block card. The accepted file lands in its step-1 predicate shape. Its schema prose names its downstream readers work-account and draft-followup, and states that the file is the rep's own. An ungrounded part persists via the write step's gap blockquote.`**
  - **The sent-mail read.** On the step-2 go-ahead, call `email.list_sent_threads` **once**, bounded by the capability's own `limit`. Read the messages for how they are written — sentence length, greeting and sign-off habits, hedges, the constructions that recur and the ones that never appear. Never for what they are about. Each distilled rule carries the step-3.2 provenance form as `Evidence · sent email <yyyy-mm-dd>`. Unavailable or declined ⇒ the step-2.5 degradation line governs. Never re-offered here — step 2's no-re-ask contract.
  - **What lands in the file is rules, never correspondence. Every sample and sent-message read here sits under the credential-hygiene standing rule (see Invariants). An illustrative snippet is the rep's own phrasing with every identifying detail removed.**
  - **Ask for more samples when coverage is thin, before the gap interview runs.** Coverage is thin when fewer than three rep-authored samples reached this section, or when none of them is a prospect-facing email. Below that bar, ask exactly once: name what is thin, and invite two or three more samples. A decline is first-class and carries no retry pressure — the section proceeds on what it has, and an ungrounded rule persists as the write step's gap blockquote.
  - **Migration from a five-part `company/messaging.md`.** A tree whose `messaging.md` still carries a voice/tone block and has no valid-present `rep/voice.md` is a step-1 resume continuing at `voice`. On entering the section, seed the `rep/voice.md` draft from that block rather than interviewing cold. The pooled sources still apply on top of the seed; the gap interview asks only for what neither covers.
  - Both artifacts preview together and land under **one** verdict — the extracted `rep/voice.md`, and `company/messaging.md` with the block removed.
  - Accept writes both. Reject leaves **both** files untouched, so the next invocation resumes here identically. Edit folds the note into the draft and re-previews both, still under one verdict.
  - Idempotent by construction: once `rep/voice.md` is valid-present, step 1 never routes here again. A `messaging.md` with no voice/tone block seeds nothing — the section interviews from the pool like any other.

**4 — State initialization (`state`) (slot).** Contract: one lightweight checkpoint — two rep-answered facts, one preview, one verdict, one whole write. Deliberately not a section-loop pass: no pool read, no provenance overlay, no gap markers — both values are rep answers by construction.

1. **Confirm the timezone** — propose an IANA zone when session evidence offers one; the user's confirmation is the contract. Record the confirmed IANA zone name, never a bare UTC offset.
2. **Resolve the baseline** — ask how far back the first run should look, one focused question; the answer resolves to a full ISO-8601 `last_run` by date math done in prose in the confirmed zone — no code, no scripts.
  - The recorded offset is the confirmed zone's offset at the resolved date — a baseline across a DST boundary carries that date's offset, not today's.
  - Present both resolved facts back to the user before any verdict.
3. **Preview** — render the seed shaped like itself via `render.context_preview` (section id `state`): the three-key YAML block exactly as it will be written, comment prose visible.
  - The call carries `state`'s `title` and `why` from the step-1 table.
4. **Verdict** — collect exactly one `review.collect` item of kind `context_section`, `task_id` = `state`; routing and the no-log-line rule are the step-3 verdict rules, consumed unchanged. On the checkpoint: accept ⇒ write (next step); edit ⇒ the corrected value(s) fold in and the seed re-previews; reject ⇒ the checkpoint re-confirms from the top, both facts re-asked.
5. **Write whole, once** — on accept, write `state/run-state.yaml` under the step-3 write-whole rule (complete, single write, creating the file's parent directory if absent, predicate and `runtime/lint.sh` clean at the moment of writing): exactly the three required keys — `last_run` (full ISO 8601 with offset), `timezone` (IANA zone name), `events: []` — with `scan_window` omitted as the documented default.
  - Carry the hand-authored original's self-documenting comment block in adapted, schema-only form: the three required keys, the optional `scan_window` key with its when-absent default (`now`, unbounded), the event record shape as run-loop-owned, and the hand-edit-must-stay-valid rule.
  - Never carry that file's event records, dates, or any company-specific value into a fresh seed — setup seeds `events: []` and never writes an event record; the write boundary and `last_run` ownership live in Writes. An empty `events` list is a clean empty slate, not an error.
6. **Progress** — re-render via `render.setup_progress` with `state` marked done.

**5 — Readiness gate & verdict (slot).** Contract: invoke `connect-tools` at its gate entry, then close the session on its report.

1. **Invoke** — call `connect-tools` at its gate entry exactly as `run-unbound` invokes pipeline steps: defined input, this invocation context; defined output, the binding/degradation report that skill assembles in the `connections_view` shape (`runtime/tool-bindings.md`, `## render.connections`). Never proceed to a verdict without the report.
2. **Receive, never re-derive** — the report is consumed as handed back: this step performs no capability derivation and no tool-inventory enumeration (see Reads — capability derivation belongs to `connect-tools`). Any `binding_change` proposal during the gate runs under `connect-tools`' own grammar and sole write authority; this step collects no `review.collect` item and writes nothing. On a first run in a working tree that has no `runtime/tool-bindings.md`, that same gate call may seed the file from its bundled reference — `connect-tools`' Procedure step 0, its write under the same sole authority; this skill neither performs it, gates it, nor reports it as its own.
3. **Re-check the artifacts** — re-evaluate the five step-1 validity predicates read-only against the files on disk, never assumed from session memory; the same predicates, consumed from step 1 — a resume entry or a mid-session hand-edit is exactly what this re-check catches.
4. **Compose the verdict** — READY TO RUN ⇔ all five predicates hold ∧ every hard-required capability in the report is resolved; otherwise READY EXCEPT X, each X exactly one unresolved hard-required capability or one invalid or absent artifact, carrying its concrete run-time consequence and what unlocks it.
  - A capability exception carries the report's own consequence and unlock content, in its honest-degradation voice; an artifact exception's unlock is the resume path — re-invoke `setup-unbound`, which continues at that artifact per step 1.
  - Optional-degraded capabilities degrade as their binding rows document: they surface as `degraded` board rows with consequences, never as exceptions, and never block READY TO RUN. Which capabilities are hard-required is the report's own classification, carried from the bindings file's framing — never enumerated here.
5. **Render and close** — render the closing banner via the logical `render.connections` capability: the handed-back report's rows unchanged, the composed verdict in the declared `verdict` slot, artifact exceptions folded into its `exceptions[]` what/unlocks shape. Fallback: the plain-Markdown capability table plus verdict line, identical content; resolution rule per `resources/tool-bindings.md`. Close the session on the verdict plus one invitation to start the first `run-unbound` — on READY EXCEPT, conditioned honestly on what to unlock first. The session never closes without the readiness verdict.
6. **Falsifiability** — READY TO RUN claims `runtime/lint.sh` exits 0 on this tree; a ready verdict followed by a lint failure is a bug to surface, never a shrug.

**6 — Resume continuation (slot).** Contract: on a step-1 resume decision, the flow enters at the first invalid or absent section in the fixed order and runs the remaining slots from there.

1. **Enter** — the step-1 resume decision routes here: its predicates locate the entry point, the first invalid or absent artifact in the fixed section order.
  - The step-1 progress re-render shows completed sections done, the continuation target active; the files alone carry the interruption.
2. **Continue** — from the entry point, run the remaining flow exactly as first-run would:
  - Source intake (step 2) re-runs scoped to what the remaining sections need — the session-held pool did not survive the interruption, so it is re-gathered only as needed.
  - The user is told which sections are already done; sources are requested only for what remains — a source that only fed completed sections is never re-requested. The within-session no-re-fetch, no-re-ask contract (step 2) then governs as usual.
  - The section loop (step 3) visits only sections not yet valid-present, per its own rule; the state checkpoint (step 4) runs only if `state/run-state.yaml` is invalid or absent; the gate (step 5) always runs before close.
3. **Never re-ask** — a completed section is never re-asked, re-confirmed, or re-verdicted.
  - An explicit ask to redo one is not a resume: it routes through the refresh grammar — the refresh branch (step 7).
  - A re-invocation that finds all five artifacts valid is refresh/audit by the step-1 decision — this step never runs there.
4. **Constructional guarantee** — a session killed at any instant leaves each artifact either untouched or complete-and-valid: no partially written file is possible, and no repair path is needed.
  - The basis is the write protocol alone: every write is whole-file-after-accept, in dependency order — the step-3.6 write-whole rule and the step-4.5 state write — and the write of file N is never gated on file N+1.
  - A mid-section interruption loses only that section's un-accepted draft, never an accepted artifact.

**7 — Refresh & audit (slot).** Contract: the diff-and-propose form of steps 2–4 — audit the existing artifacts against a fresh source pool, present the per-section proposed changes, and apply only what the user accepts. Every consumed rule is a pointer to a carried step, and every write is accept-gated (see Writes).

1. **Enter** — the step-1 refresh/audit decision routes here: all five artifacts valid-present (step 1.4), the mode announced (step 1.5), progress already re-rendered in the audit framing (step 1.6).
2. **Re-intake** — offer to re-read the prior source types or take new ones, under the step-2 contract consumed whole.
  - Consumed unchanged from step 2: the eight-item catalog and its three-answer grammar, the four read-only paths, and the pool-once, no-re-fetch/no-re-ask, degradation, and credential-hygiene rules.
  - "Nothing new" is a first-class answer — the step-2.7 "I have nothing" rule, consumed here for declining re-intake.
  - An empty pool leaves nothing to diff: the audit completes with every section stated unchanged, and the session closes cleanly with zero writes.
3. **Diff per section** — for `process`, `messaging`, `assets`, `voice` in that fixed order, extract candidates from the pool under the step-3 extract rules and per-section specifics, provenance labels included.
  - Diff the extracted candidates against the section's existing file and collect the proposed changes — the diff replaces the gap interview as what happens next.
  - A proposed change is one coherent block-level unit, named per artifact: a stage (heading, definition, entry/exit criteria) or, in the `## Qualification` section, the `**Framework:**` declaration or one field bullet (label, Evidence, Coach), in `process`; a contract part, or a block within one, in `messaging`; a table row in `assets`; a tone rule, or a block within one, in `voice`.
  - A change is never a whole-file replacement and never sub-word noise.
  - A standing gap blockquote (the step-3.6 form) that new evidence can cover becomes an ordinary fill-a-gap proposal — the blockquote's own documented promise coming due.
  - The `state` section is deliberately not audited — it reopens only on the user's explicit ask.
  - On the managed path the three `company/*` sections are outside this diff — see Invariants (managed ownership).
  - A corrupt `state/run-state.yaml` stays stop-and-surface — see Invariants (unparseable state).
4. **Audit view** — once all three sections are diffed, render once via `render.setup_progress`, mode `refresh`: each section carries its `proposed-changes(n)` status and a `coverage_note` freshness signal (for example "3 proposals from new positioning doc", "unchanged") — the declared view shape, unchanged.
  - Every row carries its `title` and `why` from the step-1 table.
  - A section with zero proposed changes is stated as unchanged and skipped in everything that follows.
  - Fallback: the plain-Markdown section-status list, identical content; resolution rule per `resources/tool-bindings.md`.
5. **Proposal loop — for each section the audit view left with proposed-changes(n), n > 0, work its proposals one at a time, in file order, top to bottom.** Two callers reach this loop and everything after it: step 7's per-section diff, and step 8's directed drafts, whose step-8.2 target sets stand in for the audit view's list.
  - One proposed change is one card: current text → proposed text → motivating source, the source in the step-3.2 provenance label form (`Evidence · <source> <locator>`).
  - Before a `process` proposal that renames or removes an existing canonical stage token can expose a verdict, enumerate every `accounts/*/context.md` candidate.
  - The scan reads no `projects/` path.
  - Parse only each candidate's YAML frontmatter.
  - Compare its scalar `stage:` value exactly with the affected old token.
  - Derive each affected account slug from the candidate's directory.
  - If any candidate cannot be read or its frontmatter cannot be parsed, name every such path and keep the card un-verdictable. Never present a partial count as complete.
  - After a complete scan, enrich the same card's `drafted_content` with the exact affected-account count and every affected slug, or the exact text `no accounts affected`.
  - When the count is nonzero, state plainly that those accounts' `stage:` values will no longer match any canonical enum token if the proposal is accepted.
  - A `process` proposal that only adds a new stage follows the ordinary proposal path with no orphan-scan block.
  - The same enumerate-parse-compare-enrich sequence above — every consequence included, unchanged — applies before a `process` proposal that renames or removes a declared qualification field can expose a verdict, candidates compared against `qualification.fields[]` entries' `field` values instead of `stage:`.
  - The card renders via `render.context_preview` — the declared `preview_view` shape, unchanged. Fallback: the plain-Markdown card, identical content; resolution rule per `resources/tool-bindings.md`.
    - The card carries its section's `title` and `why` from the step-1 table.
  - The verdict is exactly one `review.collect` item of kind `context_section`, its `task_id` carrying the section id — one item per call, never batched.
  - Accept ⇒ the change is applied to the session-held working copy of the section, never directly to disk.
    - For a scanned `process` proposal, only that working copy changes; `accounts/` remains under the Writes never-list.
  - Reject ⇒ the existing text stands.
  - Edit ⇒ the note folds into the proposal and the card re-presents.
    - If the edit changes the affected old token, discard the stale scan result.
    - Repeat the scan-and-enrichment branch before re-presenting the card or exposing a verdict.
  - Routing is the step-3.5 verdict rule, consumed unchanged, its no-log clause included — this skill performs the eventual write.
6. **Write-back** — after all of a section's proposals are verdicted, apply only the accepted diffs to the section's content — never a wholesale rewrite.
  - Every un-proposed block — hand-edited or unchanged — and every rejected-proposal block is byte-identical in the result.
  - Until that moment the on-disk file is untouched: accepted changes accumulate only in the session-held working copy, so a session killed mid-loop loses un-verdicted proposals, never an on-disk artifact — the step-6.4 constructional guarantee, extended unchanged to refresh.
  - The write is the step-3.6 write-whole rule, consumed unchanged: the file written whole, once, schema-valid — predicate and `runtime/lint.sh` clean at the moment of writing, provenance preview-only.
  - A section with every proposal rejected is not rewritten; a session with zero accepts performs zero writes.
  - A section file found unparseable or predicate-invalid mid-refresh — a mid-session hand-edit is what this catches — stays stop-and-surface: see Invariants (unparseable state).
  - Re-render progress via `render.setup_progress` after each section's write.
7. **Close** — after the last section's verdicts, re-render the audit view once more and close the session on it: each worked section's applied/rejected outcome rides its `coverage_note` (for example "2 applied, 1 rejected"), zero-proposal sections still "unchanged".
  - The step-5 readiness gate is not mandatory on refresh: the tree was valid at entry, and every write preserved validity by construction — predicate plus lint at write time.
  - The close carries one reminder: `connect-tools` runs standalone if connectors changed.
  - An audit-only session — zero accepts — closes with zero writes and no gate; an all-unchanged audit never reaches the loop at all: it states the result and closes cleanly.

**8 — Directed change (slot).** Contract: the instruction-driven form of step 7 — scope the user's own words to block-level targets, draft them, then run step 7's orphan scan, proposal loop, write-back and close unchanged. Step 7's back half serves both callers (step 7.5); every consumed rule here is a pointer to a carried step, and every write is accept-gated (see Writes).

1. **Enter** — the step-1.7 directed-instruction routing lands here: all five artifacts valid-present (step 1.4), the mode announced (step 1.5), progress already re-rendered in the audit framing (step 1.6). No source pool is gathered on this path — the instruction is the grounding, so step 2's intake does not run and step 7.2's re-intake is reached only by the mixed-utterance fall-through below.
2. **Scope** — map the instruction onto `(section, block)` targets, where a block is the same unit step 7.3 declares: a stage in `process`; a contract part, or a block within one, in `messaging`; a table row in `assets`; a tone rule, or a block within one, in `voice`. The resulting per-section target sets are what the step-7.5 loop walks.
  - An instruction naming no locatable block asks exactly one bounded clarifying question — never a guess, never a form-dump.
  - An instruction spanning sections splits into per-section target sets, worked in the fixed `process → messaging → assets → voice` order.
  - An instruction that is a question rather than a change is answered read-only from the files on disk: zero proposals, zero cards, zero verdicts, zero writes.
  - This slot's section enum is `process | messaging | assets | voice`. An instruction naming `state` is outside it and routes to the step-4 checkpoint on the user's explicit re-ask — the step-7.3 rule that `state` reopens only on that ask, consumed unchanged.
  - On the managed path that enum narrows to `voice` — see Invariants (managed ownership).
3. **Draft** — one coherent block-level unit per proposal, provenance `Answer · rep`: the step-3.2 label, consumed unchanged, because the user's own words are the source.
  - Each draft's content is governed by its section's own extract rules, consumed from the step-3 per-section specifics unchanged — the asset `Link` cell's two admissible origins and its never-construct-guess-or-repair rule included, of which this slot adds no second copy.
  - The per-link resolvability read that rule already provides for — the logical `content.get` capability — is this slot's only external read: no `content.search`, no `web.fetch`, no source pool, and no re-fetch of anything.
4. **Hand off to the proposal loop — the drafted proposals enter step 7.5 unchanged.** What they meet there is carried, never restated: the orphan-scan block before any `process` rename or removal can expose a verdict, one card per change, exactly one `context_section` `review.collect` item per card, and the accept/edit/reject routing with its no-log clause.
5. **Close through write-back** — step 7.6 applies only the accepted diffs, whole file, once, leaving every un-proposed, hand-edited and rejected block byte-identical, and step 7.7 re-renders the audit view on each worked section's applied/rejected outcome. Both are consumed as carried: a directed session with zero accepts performs zero writes and closes on that outcome, and one killed mid-loop loses un-verdicted proposals, never an on-disk artifact.
6. **Mixed utterance** — handled per the step-1.7 tie-break: this slot runs first, then the flow falls through to step 7.2 re-intake for the document half.

## Writes

- The empty directories `company/`, `rep/`, `state/`, `accounts/`, `projects/` — created where absent by step 1.5 (and, per file write, by the write clause's own parent-dir-if-absent rule); directory creation only, idempotent, never a removal or a mutation of anything existing.
- `company/process.md`, `company/messaging.md`, `company/assets.md` — this skill is their sole writer; each file is written whole, once, behind the accept verdict on its `context_section` item.
  - On the managed path, step 0 instead writes all three whole from the bundled bodies.
- `rep/voice.md` — this skill is its **sole** writer; no other path in this corpus writes it. It is written whole, once, behind the accept verdict on its own `context_section` item (`task_id: voice`).
  - On the step-3 `voice` migration, that one accept verdict also rewrites `company/messaging.md` with its voice/tone block removed — two whole-file writes behind one verdict, or neither.
- `state/run-state.yaml` — setup-time initialization only, behind its accept verdict; advancing `last_run` afterward stays with the run loop.
  - Step 0's apply writes `context_stamp` and `context_applied_at` alone, and never `last_run`, `timezone`, `scan_window`, `events`, or `work`.
- Never written by a managed apply: `rep/voice.md`, `accounts/`, `projects/`, and any partial subset of the three managed files.
- Never written by this skill: the **content** of `accounts/` and `projects/` — step 1.5 creates those two empty *directories*, but every file under them (`context.md`, drafts, task lists) stays bootstrap-context/run-loop owned — `state/feedback-log.jsonl` (no line, ever — that log stays the run loop's prioritization instrument), `runtime/tool-bindings.md` (sole writer: `connect-tools`, including the first-run seed its step-5 gate invocation may perform), and anything external.
- With steps 0–8 in this file, steps 1 and 2 remain pure reads, and the first write in the flow is step 0's managed apply on the managed path or step 1.5's empty-directory creation otherwise. Steps 5 and 6 add no write of their own. Steps 7 and 8 write only through the accept-gated whole-file writes above, and never `state/run-state.yaml` — its section reopens only on the explicit ask step 7.3 names.

## Invariants

- Unparseable state stops the session: a present `state/run-state.yaml` that fails to parse is named to the user and left untouched — never silently recreated, repaired, or overwritten. Any other malformed-but-present artifact is likewise named at detection, never silently repaired. Scaffolding never runs over an existing file: step 1.5 and the parent-dir clauses create directories only, so this stop-and-surface rule is unreachable by them.
- Scaffolding is idempotent and interruption-safe: creating a directory where absent mutates nothing existing, re-running or resuming repeats it harmlessly, and an empty directory is never a partial artifact — present-or-absent are both valid states. The step-6.4 constructional guarantee — every artifact untouched or complete-and-valid at any kill point — is preserved unchanged, with no repair path introduced.
- The step-1 title/why table is the sole owner of the five rep-facing section titles and why-lines: a render call passes those values verbatim, and no second copy of either string exists anywhere in the corpus.
- The step-2 catalog table is the sole owner of the eight rep-facing source asks and why-lines, on the same terms: a render call and every consuming skill pass those values verbatim, and no second copy of either string exists anywhere in the corpus.
- Slot boundaries: every declared slot in this file carries its body. Never improvise an interview, an extraction, a scan, or a write beyond the declared flow.
- Credential hygiene: credentials, API keys, tokens, and personal contact data — including, where the pooled source is the rep's own mail, a recipient's name, address, employer, and the deal they are in — found in any pooled source are ignored for distillation — never written into `company/*`, `rep/*`, or `state/*`, never quoted back beyond what naming the exclusion requires; the rule binds every read of the pool, not intake alone.
- Managed ownership: when the bundle carries resources/context/STAMP, company/process.md, company/messaging.md and company/assets.md belong to the pack's author and are stored in the rep's folder, not authored by them. Step 0 applies them (see Writes), and the rep-driven paths narrow to `voice` — the step-3 loop by its own not-yet-valid-present rule, the step-7.3 diff and the step-8.2 directed enum by exclusion, and the step-2.8 catalog narrowing by its own clause. A rep can still type into a managed file; what is guaranteed is that the edit does not survive the next apply, never that editing is prevented.
- Never write without an accept verdict on the covering `context_section` item; silence is never a verdict. The step-0 managed apply is the one exception.
- Never fabricate content for any artifact — a gap is surfaced, never filled in.
- A render capability whose interactive surface is unconfirmed resolves to its documented plain-Markdown fallback — never an assumed rich UI.

---

## Bundled resources (Cowork)

> This is the **bundled** Cowork build of setup-unbound. The readiness-gate slot (Procedure
> step 5) resolves `connect-tools` from `resources/connect-tools.md` in this same skill
> folder — do not expect a separate connect-tools install. Procedure step 0 resolves the shared
> managed-context apply procedure from `resources/managed-context-apply.md` in this same skill
> folder — do not expect a separate skill install; it is the sole writer of `company/*`,
> `context_stamp` and `context_applied_at` on the managed path. The logical capability map ships
> as `resources/tool-bindings.md`, and the pinned widget layouts ship under
> `resources/templates/`. Resolve capabilities from those bundled copies — do not expect a
> `runtime/` tree. All data and write paths (`company/*`, `state/run-state.yaml`) remain
> relative to the working directory Cowork is operating in (the `unbound/` tree). On a first run
> the readiness gate's `connect-tools` step may create `runtime/tool-bindings.md` in that same
> working directory — connect-tools' write under its own sole authority, never this skill's.
