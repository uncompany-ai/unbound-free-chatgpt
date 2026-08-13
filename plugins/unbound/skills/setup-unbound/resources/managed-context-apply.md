---
name: managed-context-apply
description: Managed-context apply procedure — detects the bundled company-context STAMP, compares it against the working tree's context_stamp, and on a mismatch applies company/process.md, company/messaging.md and company/assets.md whole from the bundle, stamps state/run-state.yaml, and reports what changed. Invoked internally by run-unbound (Step 1.5) and by setup-unbound (Procedure step 0) — not a public entry point, and never invoked directly by a rep.
tier: all
---
# managed-context-apply

Shared apply step (not a composition slot, not a public entry point) both root skills bundle and
invoke in full. Given the caller has already opened `state/run-state.yaml`, detect a bundled
`resources/context/STAMP`, compare it against the tree's `context_stamp`, and on a mismatch apply
the three `company/*` files whole from the bundle, stamp the tree, and report what changed. This is
the sole owner of that procedure — no caller restates any of its clauses, and no second copy of it
exists anywhere in the corpus.

## Reads

- `resources/context/STAMP` and `resources/context/{process,messaging,assets}.md` — bundled-resource reads at step 1; an absent `STAMP` is the unmanaged path. Neither is capability-mediated: no `runtime/tool-bindings.md` row, and nothing for `connect-tools` to report.
- `context_stamp` in the caller's already-open `state/run-state.yaml` — never reopened here.
- `accounts/*/context.md` YAML frontmatter — read-only input to step 6's stage-rename scan; the scalar `stage:` value and directory slug are the complete read surface.

## Procedure

**1 — Detect.** Read `resources/context/STAMP` from the bundle.

- Absent, empty, or unreadable ⇒ **unmanaged**: return `{ applied: false, unmanaged: true }` — the caller ends this beat in silence, and nothing below runs.

**2 — Compare.** Read `context_stamp` from the caller's already-open `state/run-state.yaml`.

- Equal to `STAMP` ⇒ the tree is current: return `{ applied: false, current: true }` — no write, no output.
- Different, absent, or the whole file absent ⇒ apply, from the next step.

**3 — Note what will be replaced.** Compare each managed file's on-disk bytes against its bundled body.

- Record every path whose bytes differ; no hash is stored, since both sides are in hand at this moment.

**4 — Apply.** Write `company/process.md`, `company/messaging.md` and `company/assets.md` whole from the bundled bodies, creating `company/` if absent.

- All three or none — see Writes. A failure part-way leaves the tree at its prior `context_stamp`; return `{ applied: false, failed: true, reason }` — the caller keeps the prior stamp and continues its run (see Invariants — apply failure).
- No `render.context_preview` call and no `review.collect` item — the rep holds no verdict here.
- A bundled body that fails `setup-unbound`'s step-1 validity predicate surfaces there as an artifact exception whose unlock is a corrected pack, never a rep interview.

**5 — Stamp.** Write `context_stamp` (the bundle's `STAMP`) and `context_applied_at` (ISO 8601 with offset) into `state/run-state.yaml`, touching no other key — see Writes.

**6 — Report the replaced edits.** Name each path recorded at step 3, one line each, stating that the rep's own changes to it did not survive.

**7 — Report the stage-rename fallout.** Where the applied `process.md` changed the stage enum, read each `accounts/*/context.md` frontmatter.

- Name every account whose scalar `stage:` matches no token in the new enum, or state that none do.
- The scan reports and never gates: the apply has already happened, and it repairs nothing — `accounts/` stays under the Writes never-list.
- A candidate that cannot be read or parsed is named as unread, never counted clean.

**8 — State the asset-link assumption.** One line: the links in `company/assets.md` are the team's files, and any the rep cannot open are skipped from drafts.

**9 — Return.** Hand back `{ applied: true, replaced_paths[], stage_rename_report, asset_link_note }` to the caller. This step performs no persist call itself — see Invariants (caller owns persist).

## Writes

- `company/process.md`, `company/messaging.md`, `company/assets.md` — this step is their sole writer on the managed path; written whole, all three or none, at step 4.
- `context_stamp` and `context_applied_at` in `state/run-state.yaml` — written at step 5, and never any other key (`last_run`, `timezone`, `scan_window`, `events`, `work` untouched).
- Never written here: `rep/voice.md`, `accounts/`, `projects/`, and any partial subset of the three managed files — all three land or none do.

## Invariants

- Applied, never negotiated: this step takes no verdict, renders no widget, and makes no `review.collect` call — the caller's own entry surface is unchanged by this step's outcome.
- Unreadable or absent `STAMP` reads as unmanaged, never a parse error surfaced to the rep.
- **Apply failure is fail-open.** A step-4 failure leaves `context_stamp` at its prior value so the next invocation retries; it never blocks the caller's own run, and the caller reports it honestly rather than treating it as a hard stop.
- **Caller saves its own state.** This step makes no external call itself — the caller saves its own state afterward, the normal way, once, on a successful apply. This is an internal control signal, not a Handler Contract change.
- Sole-writer rules travel with this step wherever it is bundled: `rep/voice.md`, `accounts/`, `projects/` never appear in its Writes, in either caller.
