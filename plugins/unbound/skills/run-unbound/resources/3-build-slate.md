---
name: build-slate
description: Invokes the bundled helper's materialize --apply --render (or its fallback) to upsert each discovered call and email as a durable event record in run-state.yaml and derive the annotated, unranked slate — one card per account, grouping that account's pending events — rendered in the same call. Invoked internally by run-unbound before selection.
tier: all
---
# build-slate

Presentation + persistence step of an Unbound run (composition slot 3). Given the classified
source-discriminated `discovered_events` working set, hand it to the helper's
`materialize --apply --render` command (or its fallback) to upsert each event as its own durable
record into `events` in `state/run-state.yaml` keyed by `event_id`, derive `slate_view` and render
the annotated, unranked slate in the same call. This skill only invokes materialization and
presents the result — it does
not decide evidence status, group events, derive labels, select, single-thread, or advance
`last_run`; every one of those is `materialize`'s contract, printed by the helper's `describe` and
stated in prose by `pre-slate-fallback.md`.

## Reads

- In-memory classified events from `classify-work` — source-discriminated, each carrying `{ event_id, source: "call"|"email", namespace, slug, external_ref, occurred_at, title, display_name, call_type? (call-only), suggested_slug?, ambiguous, ... }`. Accept as-is; use `event_id`/`external_ref`/`namespace`/`slug`/`display_name` verbatim.
- The `prepare` result from run-unbound's final pre-query beat — `snapshot_path` and `sampled_at`, handed to `materialize` untouched — required, passed by the orchestrator; do not re-derive either, and do not read `state/run-state.yaml` or any `context.md` directly. The write precondition and the per-slug context sit in the snapshot, which `materialize` reads for itself.
- `resources/helpers/prepare-slate.py`'s `materialize --apply --render` command, or `resources/pre-slate-fallback.md`'s `materialize` section — whichever run-unbound already resolved.
- The same helper's `reslate` command, or the same fallback file's `reslate` section — read only at REDRAW, and resolved the same way: whichever run-unbound's final pre-query beat already settled, in the shell that beat named. That beat's resolution binds every helper command after it, this one included; it is not re-probed here.
- Logical capability `render.slate(slate_view)`, resolved from the working tree's bindings authority where the tree carries one, and from `resources/bindings/pre-slate-slate.md` where it does not — the authority's `## Resolution precedence` section owns that rule. Never a concrete tool name.

## Procedure

**1 — Materialize and render, in one call.** Construct `classified_events` from `classify-work`'s
output — `event_id, source, external_ref, occurred_at, namespace, slug, display_name`, plus the one
source-specific display annotation (`call_type` for a call, or the email's `title` carried across as
`subject`), plus `origin` where the event carries one — how it was found, passed through untouched
and omitted entirely where upstream set none; no other field crosses into this payload. Invoke `materialize --apply --render` — the
bundled helper's command, or `pre-slate-fallback.md`'s `materialize` section, matching whichever
run-unbound already resolved — with `workspace_root`, `snapshot_path`, `sampled_at`, that array, and
the run's `surface`. It matches by `event_id`, preserves prior status verbatim on rediscovery,
deletes nothing, derives `slate_view` fresh, atomically replaces only the top-level `events` value
in `state/run-state.yaml` — this skill touches no other byte of that file — and returns the
rendered `fragment` from the same pass.

- **Success** → take the returned `slate_view` and `fragment` as-is; proceed to Step 2.
- **`stale_state`** (helper path only — the file changed since `prepare`'s hash was taken) → stop
  and surface; never retry with a fresh `prepare`, never fall back — this is a genuine state race to
  report, not an availability problem.
- **`invalid_classified_event`** (a missing `display_name`, a duplicate `event_id`, a malformed
  field) → stop and surface; this is a defect in this run's own classified batch, never a reason to
  fall back.
- **`template_unreadable`** → stop and surface; the template is read before the upsert, so nothing
  was written.
- **A write or replace failure** → stop and surface; the original file is untouched on every
  pre-replace failure, and an uncertain replace outcome stops rather than guesses that it landed.

**2 — Present.** On a confirmed interactive surface, hand Step 1's `fragment` to
`render.slate` **unchanged** — never a concrete tool name (ADR-6), never re-derived,
re-sorted, re-labeled or filtered, and never hand-assembled. It is the pinned slate card grid the
template defines; non-UI or unknown-capability runtimes ignore it and read each
group's `plain_line` verbatim. Same words on both surfaces (ADR-1). An **empty `slate_view` renders nothing** — no widget
and no lines, and the call returns no fragment (the run-level "nothing new since `<last_run>`" line
is `run-unbound`'s). Selection stays rep-owned on both surfaces — never auto-rank, auto-select, or
label a "top pick."

**3 — Hand off.** Stop after presenting.

**REDRAW — second entry.** Invoked by name from `close-out`'s last beat, once an item's cycle has
closed, so the rep can pick the next account without re-entering `run-unbound`. It is this file's
entry rather than that one's because the pass-the-fragment-unchanged rule above is stated here, and
stating it twice is how the two slates would drift apart.

1. Invoke `reslate` with `workspace_root`, the run's fixed `sampled_at`, the run's `surface`, and
   the display names `classify-work` resolved. It re-derives the slate from current state and
   returns `slate_view` and `fragment` in one call. It writes nothing at all: no event, no
   snapshot, not one byte of `state/run-state.yaml`. Nothing is re-discovered, no clock is
   re-sampled, and `last_run` is untouched.
2. Present exactly as Step 2 presents — the same `render.slate` pass-through, the same unchanged
   fragment, the same `plain_line` reading on non-UI surfaces. None of that is restated here.
3. **Non-empty** → hand control back to the rep's selection beat. The account just closed has no
   card, because its events are no longer `pending` — derived, never filtered. **Empty** → render
   nothing, exactly as Step 2 says, and hand back; the line that states nothing is left is
   `close-out`'s to say.
4. A refusal or an unreadable template stops the run and is surfaced, by Step 1's rules unchanged.

## Writes

- `state/run-state.yaml` — `events` upsert only, performed by `materialize --apply` (or its
  fallback's `materialize` section) on this skill's invocation; this skill never mutates the file
  directly, and neither path advances `last_run`, marks an event processed, deletes one, or touches
  a `context.md`.
- **REDRAW writes nothing.** Its whole path is read-only: `reslate` takes no snapshot, compares no
  hash, and leaves `state/run-state.yaml` byte-identical. The only write anywhere near the loop-back
  is the `advance-phase` that already landed before `close-out` invoked it.
- `state/.prepare-snapshot.json` — written by `prepare`, not here; declared because this beat is its
  last reader. Derived, disposable, rebuilt every run: never edited, never a source of truth. On
  remote Cowork it lives in the container's staged tree and never syncs back to the device.

## Failure rules

- Every `materialize` refusal in Step 1 stops the run — never read one as unavailability, and never
  fall back on one; the identical fault reproduces under the fallback's prose.
- Never modify, re-rank, re-sort, re-label, or filter `slate_view` before rendering — pass through
  exactly what `materialize` returned, and the fragment exactly as that same call returned it.
- Never call `render` separately after `materialize --apply --render` — one call produces both; the
  standalone command survives for the fallback alone.
- Never auto-rank, auto-select, or label a "top pick" — the rep decides; present a complete,
  unranked view so the rep can trust nothing slipped.
- Never put a field beyond Step 1's list into `classified_events` — extra fields do not belong in
  the persisted record, `title` crosses only as `subject`, and `origin` crosses under its own name
  or not at all. Never synthesize one for an event that arrived without it.
- An empty `slate_view` renders nothing on its own — no widget, no lines, no placeholder card.
