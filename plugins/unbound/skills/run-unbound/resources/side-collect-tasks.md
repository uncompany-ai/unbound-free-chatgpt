---
name: collect-tasks
description: Cross-item task roundup. A standalone, rep-invocable skill that scans every account/project for its persisted task-list draft, takes the latest-dated tasks.yaml per item as the source of truth, filters tasks by a requested status (not-done | done | deferred), and presents a read-only roundup grouped by item. Invoked directly by the rep ("show all not-done tasks", "what's still open across everything", "show deferred tasks") — NOT part of the single-item run loop.
tier: all
---
# collect-tasks

Standalone, rep-invoked cross-item task roundup. Scans every account and project for its persisted
task-list draft, takes the latest-dated `*-tasks.yaml` per item, filters by a requested status,
groups results by item, and renders via the logical `render.tasks` capability. This skill is pure
read — it writes nothing. It is not a slot in the `run-unbound` composition; the rep invokes it
directly for a cross-item view.

## Reads

- `accounts/*/drafts/*-tasks.yaml` and `projects/*/drafts/*-tasks.yaml` — glob all items; per item select the latest-dated file by `YYYY-MM-DD` filename (descending), lexicographic tie-break on same date. This is the same authority rule SET-STATUS uses.
- `state/run-state.yaml` — optional, read-only (timezone/date context for display).
- Logical capability `render.tasks(task_view)` — interactive task-plan cards (status pill + `namespace/slug` group headers on the roundup) or Markdown checklist; never a concrete tool name.

## Procedure

**1 — Accept a status filter.** Map the rep's phrasing to the closed enum
`{ not-done | done | deferred }`:

- "open", "still open", "not done", "to do", "outstanding" → `not-done`
- "done", "completed", "finished" → `done`
- "deferred", "snoozed", "on hold" → `deferred`

If unmappable, name the valid enum and ask. Do not invent an "all" mode.

**2 — Scan and resolve.** Glob every `accounts/<slug>/drafts/*-tasks.yaml` and
`projects/<slug>/drafts/*-tasks.yaml`. Per item, select the latest-dated file as the single source
of truth. Items with no task file contribute nothing (correctly invisible, not an error).

**3 — Filter by status.** From each authoritative file, keep only tasks whose declared `status`
equals the requested filter. Reflect the declared value — never re-classify or mutate status.

**4 — Present grouped by item.** Group matching tasks by `namespace/slug`. Show each task with
`id`, `title`, `priority`, `type`, `status`, and `evidence`, ordered by priority within each
group. Render via the logical `render.tasks` capability: interactive task-plan cards on UI-capable
runtimes (P# badge, type tag, title, evidence line, plus a **status pill** and cards grouped under
`namespace/slug` headers) — no checkbox, no buttons (the roundup is read-only) — Markdown checklist
(`- [ ]` / `- [x]`) otherwise. Display labels are presentation-only: `not-done` → "open",
`done` → "done" (checked in the Markdown fallback), `deferred` → "deferred"; the persisted enum is
unchanged. Task status changes stay explicit chat asks via SET-STATUS (`work-account`), never a card
affordance.

**5 — Handle degraded inputs honestly.**

- Zero matches → honest "no tasks match" message; never fabricate.
- Empty or missing task file per item → invisible (no error) or surfaced honestly, then continue.
- Unparseable YAML → surface and continue with remaining items; never guess.

## Writes

None. This skill writes nothing — no file created or mutated, no external action, no
`feedback-log.jsonl` touch. The repo is byte-stable before and after every invocation. The
checkbox write-back is the explicit SET-STATUS action in `work-account`, not part of this skill.

## Failure rules

- Zero matches → honest message; never fabricate tasks to fill the roundup.
- Unparseable YAML → surface honestly and continue; never guess or abort.
- Never re-classify, recompute, or mutate task status — reflect what is persisted.
- Never read or render `dropped`/`open_questions`/`next_step` (per-item synthesis artifacts, not the cross-item view).
