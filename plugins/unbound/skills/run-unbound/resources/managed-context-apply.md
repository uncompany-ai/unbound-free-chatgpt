---
name: managed-context-apply
description: Managed-context apply procedure — detects the bundled company-context STAMP, compares it against the working tree's context_stamp, and on a mismatch applies every bundled company/* body whole (process.md, messaging.md, assets.md, and bindings.md where the pack carries it), stamps state/run-state.yaml, and reports what changed. Invoked internally by run-unbound (Step 1.5) and by setup-unbound (Procedure step 0) — not a public entry point, and never invoked directly by a rep.
tier: all
---
# managed-context-apply

Shared apply step (not a composition slot, not a public entry point) both root skills bundle and
invoke in full. Given the caller has already opened `state/run-state.yaml`, detect a bundled
`resources/context/STAMP`, compare it against the tree's `context_stamp`, and on a mismatch apply
every bundled `company/*` body whole, stamp the tree, and report what changed. This is
the sole owner of that procedure — no caller restates any of its clauses, and no second copy of it
exists anywhere in the corpus.

## Reads

- `resources/context/STAMP` and `resources/context/{process,messaging,assets,bindings}.md` — bundled-resource reads at step 1; an absent `STAMP` is the unmanaged path, and an absent `bindings.md` is a complete bundle, not a partial one. Neither is capability-mediated: no `runtime/tool-bindings.md` row, and nothing for `connect-tools` to report.
- `context_stamp` in the caller's already-open `state/run-state.yaml` — never reopened here.
- `accounts/*/context.md` YAML frontmatter — read-only input to step 6's stage-rename scan; the scalar `stage:` value and directory slug are the complete read surface.

## Procedure

**1 — Detect.** Read `resources/context/STAMP` from the bundle.

- Absent, empty, or unreadable ⇒ **unmanaged**: return `{ applied: false, unmanaged: true }` — the caller ends this beat in silence, and nothing below runs.
- Present ⇒ take the body set as found: the three named files, plus `bindings.md` where the bundle carries it. Arity is read, never assumed — a bundle without it is whole, not partial.

**2 — Compare.** Read `context_stamp` from the caller's already-open `state/run-state.yaml`.

- Equal to `STAMP` ⇒ the tree is current: return `{ applied: false, current: true }` — no write, no output.
- Different, absent, or the whole file absent ⇒ apply, from the next step.

**3 — Note what will be replaced.** Compare each bundled body against its on-disk `company/` counterpart.

- Record every path whose bytes differ; no hash is stored, since both sides are in hand at this moment.

**4 — Apply.** Write each bundled body whole to its `company/` path — `process.md`, `messaging.md`, `assets.md`, and `bindings.md` where step 1 found one — creating `company/` if absent.

- Every present body, or none — see Writes. Atomicity is the rule; arity is not. A failure part-way leaves the tree at its prior `context_stamp`; return `{ applied: false, failed: true, reason }` — the caller keeps the prior stamp and continues its run (see Invariants — apply failure).
- A bundle carrying no `bindings.md` **removes** `company/bindings.md` where the tree holds one, in the same all-or-none write. Dropping it from the pack is how a deployment returns to unmanaged writes; a stale copy would keep every rep under a rule their pack no longer states. The other three cannot be omitted, so they are never removed.
- No `render.context_preview` call and no `review.collect` item — the rep holds no verdict here.
- A bundled body that fails `setup-unbound`'s step-1 validity predicate surfaces there as an artifact exception whose unlock is a corrected pack, never a rep interview.

**5 — Stamp.** Write `context_stamp` (the bundle's `STAMP`) and `context_applied_at` (ISO 8601 with offset) into `state/run-state.yaml`, touching no other key — see Writes.

**6 — Report the replaced edits.** Name each path recorded at step 3, one line each, stating that the rep's own changes to it did not survive. A removed `company/bindings.md` is named the same way, as withdrawn rather than replaced.

**7 — Report the stage-rename fallout.** Where the applied `process.md` changed the stage enum, read each `accounts/*/context.md` frontmatter.

- Name every account whose scalar `stage:` matches no token in the new enum, or state that none do.
- The scan reports and never gates: the apply has already happened, and it repairs nothing — `accounts/` stays under the Writes never-list.
- A candidate that cannot be read or parsed is named as unread, never counted clean.
- **Sibling scan.** Where an applied `bindings.md` carries `## Value Rules`, name every token in its `stage` keys but not the applied enum, and every enum token with no key — or state that they agree. The first translates nothing; the second is a stage that reaches the write path unmapped. Reports and gates nothing, as above; unparseable reads as unread, never as agreeing.

**8 — State the asset-link assumption.** One line: the links in `company/assets.md` are the team's files, and any the rep cannot open are skipped from drafts.

**9 — Return.** Hand back `{ applied: true, replaced_paths[], bindings_applied, stage_rename_report, value_map_report, asset_link_note }` to the caller. `bindings_applied` is true only where step 4 wrote `company/bindings.md` — false where the bundle carried none, removal included. This step performs no persist call itself — see Invariants (caller owns persist).

## Writes

- `company/process.md`, `company/messaging.md`, `company/assets.md` — this step is their sole writer on the managed path; written whole at step 4.
- `company/bindings.md` — this step is its sole writer anywhere, on any path; written whole at step 4 where the bundle carries it, removed there where the bundle does not. No other skill creates, edits or deletes it, and no rep verdict reaches it.
- `context_stamp` and `context_applied_at` in `state/run-state.yaml` — written at step 5, and never any other key (`last_run`, `timezone`, `scan_window`, `events`, `work` untouched).
- Never written here: `rep/voice.md`, `accounts/`, `projects/`, and any partial subset of the bundle's bodies — every present body lands or none does.

## Invariants

- Applied, never negotiated: this step takes no verdict, renders no widget, and makes no `review.collect` call — the caller's own entry surface is unchanged by this step's outcome.
- Unreadable or absent `STAMP` reads as unmanaged, never a parse error surfaced to the rep.
- **Apply failure is fail-open.** A step-4 failure leaves `context_stamp` at its prior value so the next invocation retries; it never blocks the caller's own run, and the caller reports it honestly rather than treating it as a hard stop.
- **Caller saves its own state.** This step makes no external call itself — the caller saves its own state afterward, the normal way, once, on a successful apply. This is an internal control signal, not a Handler Contract change.
- Sole-writer rules travel with this step wherever it is bundled: `rep/voice.md`, `accounts/`, `projects/` never appear in its Writes, in either caller.
