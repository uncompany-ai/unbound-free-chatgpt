---
name: connect-tools
description: Dual-entry environment readiness check. Derives the required capability set from the bundled bindings reference's own binding tables, creates the working tree's runtime/tool-bindings.md from that reference when it is absent, enumerates the live runtime's tool inventory, matches the two, proposes binding-row updates one at a time, and reports every gap with its concrete run-time cost. Invoked standalone by the rep ("check my connections", "am I ready to run", after adding or removing a connector or switching runtimes) and by setup-unbound at its readiness gate — NOT part of the run-unbound loop.
tier: all
---
# connect-tools

Environment readiness check with two entries: the rep invokes it standalone ("check my
connections", after any connector or runtime change), or `setup-unbound` invokes it at its
readiness gate. It derives the required capability set from the bundled bindings reference, seeds
the working tree's `runtime/tool-bindings.md` from that reference when it is absent, enumerates the
live tool inventory, matches the two, proposes binding-row updates one at a time, and reports every
gap with its run-time cost. All environment access is read-only, and it never auto-runs inside the
`run-unbound` loop.

## Reads

- The bundled bindings reference — `resources/tool-bindings.md` beside this skill's bundled resources when it exists, otherwise `runtime/tool-bindings.md` in a corpus checkout. Read-only, and three things at once: the requirements source (its binding tables, including the declared future write gate), the schema-of-record every core update refreshes, and the file Procedure step 0 seeds from.
- `runtime/tool-bindings.md` in the working tree — the current binding state those requirements are matched against, and the one file this skill maintains; Procedure step 0 creates it from the reference when it is absent.
- The runtime's live tool inventory — inspected read-only in-session; concrete tool names enter the conversation only from here.
- Logical capability `review.collect(checkpoint_view)`, items of kind `binding_change` — the propose surface; item grammar and verdict routing live in `runtime/tool-bindings.md` under `## review.collect`.
- Logical capability `render.connections(connections_view)` — the report surface; view shape and board text rules live in `runtime/tool-bindings.md` under `## render.connections`.

## Procedure

**0 — Ensure (slot).** Contract: the file this skill maintains exists before anything derives
against it — create-if-absent, byte-copy only, never a repair. This is the create-if-absent idiom
`setup-unbound` step 1.5 already carries for the namespace directories, generalized once more to
one file.

- Resolve the reference first: `resources/tool-bindings.md` beside this skill's bundled resources when it exists, otherwise `runtime/tool-bindings.md` in a corpus checkout. In a corpus checkout the reference and the working-tree file are the same path — the seed is a no-op by construction and step 1 derives exactly as it does with a single file.
- Absent working-tree `runtime/tool-bindings.md`, reference reachable ⇒ **seed it**: copy the reference byte for byte to `runtime/tool-bindings.md`, creating its parent directory if absent. Narrate the create plainly — it is the rep's only cue that a file they now own and may edit exists. Then proceed to step 1.
- Present and parseable ⇒ **no-op**: the file is left byte-unchanged and is never re-seeded, refreshed, diffed against the reference, or repaired. The no-op is silent — no narration, no per-run line reporting that the file was already there, the same silence step 1.5's scaffolding keeps. Then proceed to step 1.
- Present and unparseable ⇒ **stop**: name the file and the problem, and leave it byte-untouched. A seed is **never** written over an existing file — a corrupt file is surfaced, never silently replaced. Zero-length counts here, not as absent: empty is unparseable. See Invariants.
- Neither the reference nor a working-tree file reachable ⇒ **stop**, naming **both** probed paths; requirements are never reconstructed from memory. See Invariants.
- Reference unreachable but the working-tree file present and parseable ⇒ proceed on that file alone, stating plainly that the reference could not be read, so derivation runs against the file's own tables.
- A seed that cannot be written — a read-only or unwritable working directory ⇒ name the failure and the path, and stop; never continue as if seeded.

**1 — Derive.** Read the binding tables of the reference resolved in step 0; their
logical-capability column is the requirements list — no second list exists anywhere. The working
tree's `runtime/tool-bindings.md` supplies the current binding state those requirements are matched
against, never the requirements themselves.

- Carry each capability's criticality from the reference's own framing, never from a restated row inventory: optional-degraded rows degrade as they state, provider rows degrade to `missing`, render rows degrade to their documented fallbacks, a declared-but-unbound future gate resolves to its documented fallback until bound — reported `missing`/`degraded` with that fallback as its consequence — and rows carrying no degradation note are hard-required.
- Carry the scope cell too. For every declared write-scoped row, also carry the reference-owned
  production-eligibility requirements and evidence state. A live inventory match proves only that a
  tool is present; it never proves the durable same-operation guarantees or normalized outcome the
  reference requires. Presence and production eligibility remain separate facts through every later
  step.
- A capability the reference carries with no row in the working-tree file is an ordinary missing row: it enters step 3 like any other and step 4 proposes it. That is how a capability a core update adds reaches a file seeded from an earlier reference — the rep's own row edits untouched beside it.
- A row in the working-tree file naming a capability the reference no longer carries is surfaced plainly, never silently dropped; removing it is a step-4 proposal like any other, never an unannounced edit.
- A present but unparseable working-tree file, or neither file reachable, stops the check at step 0 — an absent file does not: step 0 seeds it. See Invariants.

**2 — Enumerate.** Inspect the runtime's actual tool inventory as a read-only pass over what the
live session exposes. Concrete names arrive from the environment into the conversation, and reach
`runtime/tool-bindings.md` only through accepted proposals.

**3 — Match.** Classify every derived capability against its binding cell in the working-tree file
and the enumerated inventory: *resolved* (the bound tool is present), *resolvable* (a suitable tool
exists but the binding row is absent or stale), or *unresolved* (nothing suitable — the capability
degrades per its criticality).

- For a declared write-scoped row, `resolved` additionally requires the working-tree row to carry
  verified evidence satisfying every production-eligibility requirement owned by the reference.
  A matching live tool with missing, incomplete, or merely asserted evidence is
  *present-but-ineligible*: retain the concrete inventory match, classify the capability status as
  `degraded`, and select its documented non-production fallback. Never infer evidence from a tool's
  name, presence, documentation summary, or a successful one-off call.
- A *resolvable* row is further classified **unambiguous** when all three hold: (1) its Scope cell
  is `read`, or the row is a render/capture surface — stated positively, so any scope value not in
  that set requires a verdict; (2) exactly one tool in step 2's live inventory matches the
  capability; (3) the tool currently named in the working-tree row is absent from that inventory. A
  capability the reference carries with no row in the working-tree file and exactly one matching
  tool is unambiguous too — condition 3 holds vacuously, since a row with no bound tool has no
  present incumbent to be absent or present.
- Kept on the verdict path, always: any declared write-scoped row — excluded by condition 1, never
  by a `scope != write` test, so an unrecognized future scope value requires a verdict rather than
  auto-binding; a declared-but-unbound future gate (a design state, not a stale binding); two or
  more candidate tools; a working-tree row naming a capability the reference no longer carries (a
  removal proposal — the rep may have added it on purpose); and any row whose incumbent tool is
  present in the live inventory.

**4 — Propose.** For each resolvable row classified **unambiguous** in step 3, apply the row edit
directly — no `review.collect` item, no verdict. For every other resolvable or stale row, present
one `review.collect` item of kind `binding_change` — one item per call, never batched — naming the
capability, the concrete tool found, and the exact row edit to the working-tree file.

- An auto-bound row still writes exactly the row edit step 3 identified — same file, same edit
  shape a verdict would have produced — and it is never silent: narrate the edit at the time, in
  the same plain register step 0 uses for its seed, since it is the rep's only other cue that a
  file they own has changed. Step 5 then names the row individually, with its concrete tool and the
  fact that it was bound without a verdict — auto-binding removes the prompt, never the record.
- accept ⇒ apply exactly that one row edit; edit ⇒ fold the note into the proposal and re-present; reject ⇒ drop the proposal.
- A proposal for a declared write-scoped row states two outcomes separately: the candidate tool is
  present, and whether the row has verified production-eligibility evidence. Accepting a mapping-only
  proposal may record the concrete tool but leaves the row degraded; it must not describe the row as
  connected for production writes. Evidence is proposed only when the required observations are
  actually available and cited — never manufactured to make the proposal pass.
- The write boundary around every verdict is in Invariants.

**5 — Report.** Assemble `connections_view`: one entry per derived capability plus the
ready-or-exceptions `verdict`, matching the shape declared in `runtime/tool-bindings.md` under
`## render.connections`.

- Each entry carries `capability`, `status` (`connected | missing | degraded`), `tool` only when bound from the live environment, and a `consequence` line on every `missing` or `degraded` row.
- Every row auto-bound this run (step 4's no-verdict path) carries its own entry too — `status:
  connected`, its concrete `tool`, and a `consequence` line stating plainly that it was bound
  without a verdict this run. Named individually, one line per row, using the existing
  `consequence` text rather than a new field: never a "N rows auto-bound" summary, and never folded
  into another row's line. It is the rep's per-row record for a decision they did not personally
  make.
- For a declared write-scoped row, report inventory presence independently: a present candidate may
  carry `tool` while its status remains `degraded`. Its consequence says production writes are
  disabled and names the documented fallback. Use `connected` only when positive binding and every
  reference-owned production-eligibility requirement are both verified.
- Render via the logical `render.connections` capability only on positive confirmation that the widget tool is present in the runtime's tool list.
- Otherwise emit the plain-Markdown capability table plus verdict line — identical content, never an assumed rich UI.
- Write each `consequence` in the honest-degradation voice, derived from the reference's own degradation notes — for example: no transcript source ⇒ calls worked `transcript: missing`; no email source ⇒ discovery is calendar-only; no `web.fetch` ⇒ website intake unavailable; no widget tool ⇒ plain-chat surfaces; no CRM write connected ⇒ CRM updates are simulated / drafted locally; no CRM read connected ⇒ qualification is evaluated from the run's own evidence and the account's stored context alone, so anything only the CRM already knows still gets asked.
- Close per entry point: standalone ⇒ end with this report as the session summary; gate entry ⇒ hand the identical report back to the invoking `setup-unbound` — behavior identical, framing only.

## Writes

- `runtime/tool-bindings.md` in the working tree, and nothing else — this skill is its sole writer, in exactly two forms: step 0's whole-file create-if-absent seed, written only when the file is absent, and step 4's single accepted row edit, leaving every unaffected row byte-unchanged. The seed never overwrites, merges into, or repairs an existing file — a file that is present is present, whatever its contents.
- No `company/*`, `state/*`, `accounts/`, or `projects/` file is ever touched, and no external write of any kind is ever made.

## Invariants

- A present but unparseable `runtime/tool-bindings.md` ⇒ name the problem and stop, leaving the file byte-untouched — never repaired, and never overwritten by a seed. An *absent* file is explicitly not this case: step 0 seeds it and the check proceeds. With neither the reference nor a working-tree file reachable ⇒ name both probed paths and stop; never reconstruct requirements from memory.
- Never re-seed: the seed runs against an absent file only. A file that exists is never refreshed from the reference, diffed against it, or replaced by it — its contents are the rep's, and only an accepted row edit changes them.
- Never write without an accept verdict on the one `binding_change` item covering that row — with
  two stated exemptions, each reasoned and each stating where the rule resumes. Step 0's seed: it
  authors nothing — a byte-copy of a file already installed on this machine invents no content, so
  there is nothing for a rep to review; the rule resumes in full the moment the file exists, every
  later change to it one accepted row edit. Step 3's unambiguous auto-bind: the edit carries no
  decision — one candidate tool, the incumbent provably absent, read-scope or a render surface
  only; the rule resumes for every row that fails any of the three conditions, which still gets its
  own accept/edit/reject verdict.
- Never append to `feedback-log.jsonl` — that log stays the run loop's prioritization instrument.
- Never name a concrete tool from this file's prose — concrete names enter only per step 2's direction of flow.
- Never a silent gap: every unresolved capability is reported with its concrete run-time consequence.
- Never promote write presence into write eligibility: a declared write-scoped row lacking any
  required evidence remains degraded after matching and after an accepted mapping proposal.
