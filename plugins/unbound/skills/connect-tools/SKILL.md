---
name: connect-tools
description: Dual-entry environment readiness check that binds the rep's tools for them. Derives the required capability set from the bundled bindings reference's own binding tables, creates the working tree's runtime/tool-bindings.md from that reference when it is absent, enumerates the live runtime's tool inventory, binds every capability it can resolve without asking, and for every gap tells the rep exactly which connector to add and what it gives them back. Invoked standalone by the rep ("check my connections", "connect my tools", "am I ready to run", after adding or removing a connector or switching runtimes) and by setup-unbound at its readiness gate — NOT part of the run-unbound loop.
tier: all
---
# connect-tools

Environment readiness check with two entries: the rep invokes it standalone ("connect my tools",
"check my connections", after any connector or runtime change), or `setup-unbound` invokes it at its
readiness gate. It derives the required capability set from the bundled bindings reference, seeds
the working tree's `runtime/tool-bindings.md` from that reference when it is absent, enumerates the
live tool inventory, **binds every capability it can resolve on its own**, and reports each
remaining gap with its run-time cost and the concrete way to close it.

**It does not interview the rep.** The rep asked for their tools to be connected; deciding which
concrete tool serves `transcript.get` is this skill's job, not theirs. Every binding it can
determine, it makes and narrates. It stops to ask on exactly one thing — Step 2.5's authoritative-CRM
choice, where two or more equally valid answers exist, nothing has already answered it centrally, and
guessing would write to the wrong organization. All environment access is read-only, no external
write of any kind is made here, and it never auto-runs inside the `run-unbound` loop.

## Reads

- The bundled bindings reference — `resources/tool-bindings.md` beside this skill's bundled resources when it exists, otherwise `runtime/tool-bindings.md` in a corpus checkout. Read-only, and three things at once: the requirements source (its binding tables), the schema-of-record every core update refreshes, and the file Procedure step 0 seeds from.
- `runtime/tool-bindings.md` in the working tree — the current binding state those requirements are matched against, and the one file this skill maintains; Procedure step 0 creates it from the reference when it is absent.
- The bundled **runtime half** — `resources/helpers/` and `resources/templates/` beside this skill's bundled resources, with `resources/RUNTIME-STAMP` naming their bytes. Read-only, and the source step 0.5 installs into the working tree's `runtime/`; in a corpus checkout source and destination are the same paths, so the install is a no-op by construction as the seed above is.
- The runtime's live tool inventory — inspected read-only in-session; concrete tool names enter the conversation only from here.
- Optional CRM binding profiles — `resources/binding-profiles/crm/` beside bundled resources when it exists, otherwise `runtime/binding-profiles/crm/` in a corpus checkout; inactive recipes opened only after step 2 observes their provider.
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

**0.5 — Install the runtime half (slot).** Contract: the idiom above applied to a **set** rather than
a file — the bundled helper and template directories named in Reads, copied to `runtime/helpers/`
and `resources/templates/`, with `runtime/RUNTIME-STAMP` **derived from the landed bytes**, never
copied from the bundle's, and a disagreement between them stopped on. This install is what puts a
helper on the side of the tree the pre-slate beat can write from; `run-unbound` states that rule and
it is not restated here.

The four branches above carry over unchanged in meaning and are not restated. Four things are
specific to a set:

- **Install the set or install nothing.** The helper resolves its template as a sibling of its own
  directory, with no probe and no fallback, so a tree holding the helper without its templates is
  broken in a way nothing notices until a beat reaches a template. Absent ⇒ copy the helper **and**
  every template, byte for byte, then write the stamp; any part failing ⇒ stop and name what failed,
  leaving no partial set behind.
- **Present but incomplete** — the helper without its templates, or a template missing — ⇒ **stop**
  and name the missing files. This is the present-but-unparseable branch reached by another route:
  never a partial repair, never a silent completion.
- **Present with a stamp differing from the bundle's** ⇒ **report the drift at step 6, naming both
  stamps, and overwrite nothing.** A core release ships new template bytes and a rep may have edited
  one on purpose; nothing here tells those apart, so the refresh is the rep's explicit act.
- **Present with a matching stamp** ⇒ silent no-op, no narration and no re-copy.

Narrate an install once, plainly, in the register the seed above uses — it is the rep's only cue
that files they now own exist in their tree.

**1 — Derive.** Read the binding tables of the reference resolved in step 0; their
logical-capability column is the requirements list — no second list exists anywhere. The working
tree's `runtime/tool-bindings.md` supplies the current binding state those requirements are matched
against, never the requirements themselves.

- Carry each capability's criticality from the reference's own framing, never from a restated row inventory: optional-degraded rows degrade as they state, provider rows degrade to `missing`, render rows degrade to their documented fallbacks, and rows carrying no degradation note are hard-required.
- Carry the scope cell too. A write-scoped row is bound on the same terms as a read row — the
  reference declares no eligibility grade above bound — but its **consequence text differs**: what a
  bound write row enables is live external writes at close-out, each still requiring the rep's
  in-session approval of the exact payload. Say that plainly wherever the row is reported.
- A capability the reference carries with no row in the working-tree file is an ordinary missing row: it enters step 3 like any other and step 4 binds it. That is how a capability a core update adds reaches a file seeded from an earlier reference — the rep's own row edits untouched beside it.
- A row in the working-tree file naming a capability the reference no longer carries is surfaced plainly and left in place. Removing a row the rep may have added on purpose is the one edit this skill does not make on its own; it is reported, and the rep removes it if they want it gone.
- A present but unparseable working-tree file, or neither file reachable, stops the check at step 0 — an absent file does not: step 0 seeds it. See Invariants.

**2 — Enumerate.** Inspect the runtime's actual tool inventory as a read-only pass over what the
live session exposes. Concrete names arrive from the environment into the conversation, and reach
`runtime/tool-bindings.md` only through step 4.

**2.5 — Profile (optional).** Complete step 2 over the full live inventory before listing or
reading any provider profile. Resolve the optional profile directory named in Reads. If the whole
resource is absent, continue ordinary discovery without a readiness gap. After enumeration, list
filenames only; for each observed CRM provider, open only its corresponding candidate. Never use a
profile or filename as connector-presence evidence.

- A profile is current only when its provider and runtime match the observation and every surface
  it marks required is present with a compatible documented call shape, including identity and
  primary read. Missing expected or stale ⇒ report the reason concisely, ignore that recipe,
  continue ordinary discovery, and change no row. Optional correlation or cleanup drift
  is reported and that path omitted without invalidating a current primary path.
- For each current candidate, run only the read-only call in its `Organization check`, with the
  exact documented shape. **One organization on one provider ⇒ take it and say which**: name the
  organization, ID, environment type, domain and authenticated account in the narration, and carry
  on — a single unambiguous answer is not a question. **Two or more organizations, or two or more
  CRM providers ⇒ ask, and ask once**: display every candidate's identity fields together and have
  the rep name the one authoritative CRM. Where no authority has been declared centrally, this is
  the only question this skill asks, and it exists because a wrong guess here writes a rep's
  pipeline into someone else's system. A decline leaves both CRM rows unbound and reported as gaps.


**3 — Match.** Classify every derived capability against its binding cell in the working-tree file
and the enumerated inventory: *resolved* (the bound tool is present), *resolvable* (a suitable tool
exists but the binding row is absent or stale), or *unresolved* (nothing suitable — the capability
degrades per its criticality).

- Exactly one matching tool ⇒ resolvable, and the match is the answer.
- Two or more matching tools ⇒ still resolvable, and this skill picks: score each candidate against
  the row's documented call shape in the reference — required parameters present, return shape
  compatible, addressed by the identifier the capability carries rather than by search — and take
  the best fit. Record which one was chosen and what made it the best fit; step 6 reports both. A
  genuine tie on call-shape fit resolves to the tool whose provider already serves another bound
  row, so a deployment converges on one provider rather than a patchwork.
- An incumbent tool still present in the live inventory stays bound: a working row that resolves is
  never re-pointed at an alternative just because one exists. Re-pointing happens only when the
  incumbent is absent from the inventory.
- Nothing suitable ⇒ unresolved, and it goes to step 5 for guidance rather than a silent gap.

**4 — Bind.** Apply the row edit for every *resolvable* row directly to the working-tree
`runtime/tool-bindings.md` — no verdict, no proposal, no confirmation step, for read rows and write
rows alike.

- Narrate every edit at the time it is made, one line each, in the same plain register step 0 uses
  for its seed: the capability, the concrete tool now bound, and — where step 3 chose between
  candidates — why that one. This narration and step 6's report are the rep's whole record of
  decisions they did not personally make, so neither is ever skipped or summarized into a count.
- Each edit touches exactly one row, or the render surface's one declared line, and leaves every other byte unchanged.
- A row edit that cannot be written — unwritable file, a runtime whose bindings ship read-only
  inside the built artifact — is not a failure of the check: report the capability as observed,
  state that the binding could not be persisted here and why, and continue. Never claim a row was
  bound when it was not.

**5 — Guide.** For every *unresolved* capability, assemble the `connect` block the reference's
`## render.connections` declares — `what`, `where`, `unlocks` — so the rep can close the gap without
asking a follow-up question.

- `what` names the connector in the words the rep will see in their own settings UI, never a raw
  tool identifier. `where` is the concrete place they go on **this** runtime to add it. `unlocks` is
  what they get back, stated as behavior they will notice — not the capability's internal name.
- One `connect` block per unresolved capability, and where several gaps close with the same
  connector, say so on each rather than merging them into a single instruction the rep has to
  decompose.
- Where no connector exists for a capability on this runtime, emit no `connect` block and say so in
  the `consequence` instead. Guidance that cannot be followed is worse than an honest gap.
- Guidance is never a prompt. Nothing here waits on the rep, and the report is complete whether or
  not they act on it.

**6 — Report.** Assemble `connections_view`: one entry per derived capability plus the
ready-or-exceptions `verdict`, matching the shape declared in `runtime/tool-bindings.md` under
`## render.connections`.

- Each entry carries `capability`, `status` (`connected | missing | degraded`), `tool` only when bound from the live environment, a `consequence` line on every `missing` or `degraded` row, and the `connect` block step 5 assembled where one exists.
- Every row bound this run carries its own entry — `status: connected`, its concrete `tool`, and a
  `consequence` line naming what it now does. Named individually, one line per row: never an "N rows
  bound" summary, and never folded into another row's line.
- A bound write row reports `connected` with its consequence stating what that enables — live
  external writes at close-out, each still requiring in-session approval of the exact payload. An
  unbound one reports `missing` with its documented fallback as the consequence.
- Carry step 0.5's outcome as one runtime-half line: installed this run, incomplete, or **drifted**
  with both stamps named and nothing overwritten. A matching set contributes no line — the no-op is
  silent here too.
- Render via the logical `render.connections` capability whenever the reference's bound-render-surface line names a tool; an unresolved surface reports `degraded` with its consequence.
- Otherwise emit the plain-Markdown capability table plus verdict line — identical content, never an assumed rich UI.
- Write each `consequence` in the honest-degradation voice, derived from the reference's own degradation notes — for example: no transcript source ⇒ calls worked `transcript: missing`; no email source ⇒ discovery is calendar-only; no `web.fetch` ⇒ website intake unavailable; no widget tool ⇒ plain-chat surfaces; no CRM write connected ⇒ CRM updates are simulated / drafted locally; no CRM read connected ⇒ qualification is evaluated from the run's own evidence and the account's stored context alone, so anything only the CRM already knows still gets asked; no CRM lookup connected ⇒ an account with no CRM record of its own is never offered one to map to, so its CRM updates stay simulated; no task manager connected ⇒ task plans stay local-only and statuses reconcile nowhere.
- Close per entry point: standalone ⇒ end with this report as the session summary; gate entry ⇒ hand the identical report back to the invoking `setup-unbound` — behavior identical, framing only.

## Writes

- `runtime/tool-bindings.md` in the working tree, and nothing else — this skill is its sole writer, in exactly two forms: step 0's whole-file create-if-absent seed, written only when the file is absent, and step 4's single-row binding edits, leaving every unaffected row byte-unchanged. The seed never overwrites, merges into, or repairs an existing file — a file that is present is present, whatever its contents.
- `runtime/helpers/`, `resources/templates/` and `runtime/RUNTIME-STAMP` in the working tree — this skill is their sole writer too, in exactly one form: step 0.5's whole-set create-if-absent install. No per-file edit, no refresh path.
- No `company/*`, `state/*`, `accounts/`, or `projects/` file is ever touched, and no external write of any kind is ever made.

## Invariants

- A present but unparseable `runtime/tool-bindings.md` ⇒ name the problem and stop, leaving the file byte-untouched — never repaired, and never overwritten by a seed. An *absent* file is explicitly not this case: step 0 seeds it and the check proceeds. With neither the reference nor a working-tree file reachable ⇒ name both probed paths and stop; never reconstruct requirements from memory.
- Never install the runtime half partially, and never overwrite one. The helper and every template arrive together or none does; an incomplete set is named and stopped on, never completed; a differing stamp is reported with both values and left alone, because refreshing it is the rep's act.
- Never re-seed: the seed runs against an absent file only. A file that exists is never refreshed from the reference, diffed against it, or replaced by it — its contents are the rep's, and only a step-4 row edit changes them.
- Never bind silently. Binding without a verdict is the design; binding without a **record** is not.
  Every edit is narrated when made and named individually in step 6, and a row this skill could not
  bind is never reported as bound.
- Never remove a row on the rep's behalf. A row naming a capability the reference no longer carries
  is reported and left alone — it is the one thing in this file the rep may have put there on purpose.
- Never ask a question step 2.5 does not authorize. One or zero candidates is an answer, not a
  prompt, and so is a centrally declared authority; the authoritative-CRM choice among genuine
  alternatives nothing has already settled is the only interruption here.
- Never append to `feedback-log.jsonl` — that log stays the run loop's prioritization instrument.
- Never name a concrete tool from this file's prose — concrete names enter only per step 2's direction of flow.
- Never a silent gap: every unresolved capability is reported with its concrete run-time consequence, and with the way to close it wherever one exists.
- Never make an external write to prove a binding. Binding is decided from the read-only inventory
  pass and the reference's documented call shapes — never from a trial write, a double-apply, or a
  cleanup experiment against a real system.

---

## Bundled resources (Cowork)

> This is the **standalone** Cowork build of connect-tools. The logical capability map
> (`render.connections`, `review.collect`, and friends) ships in this same skill folder as
> `resources/tool-bindings.md`, and the pinned widget layouts ship under
> `resources/templates/`. Resolve capabilities from those bundled copies — do not expect a
> `runtime/` tree.
>
> `resources/tool-bindings.md` is the bundled bindings reference the Procedure names, and it is
> three things at once: the requirements source, the schema-of-record every core update refreshes,
> and the file Procedure step 0 seeds from. On a first run in a working directory that has no
> `runtime/tool-bindings.md`, this skill creates one there as a byte-copy of that reference. From
> then on it is the rep's file: no later core update touches it, and every change to it is exactly
> one accepted row edit. All data and write paths remain relative to the working directory Cowork
> is operating in (the `unbound/` tree).
