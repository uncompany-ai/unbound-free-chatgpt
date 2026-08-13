---
name: qualification-frameworks
description: The canonical registry of qualification-framework declaration templates — one complete, paste-ready `## Qualification` section per framework (MEDDPICC, MEDDIC, BANT). Read by setup-unbound at authoring time, exclusively, and by nothing at run time. Natural-language Markdown, no code (ADR-1); no external writes.
tier: all
---

# qualification-frameworks

The canonical registry of **qualification-framework declaration templates** — the deterministic
source material `setup-unbound`'s `process` pass populates a company's `## Qualification` section
from, so that the field labels persisted into every account record are constants across installs
rather than a per-install freehand extraction.

**Read by `setup-unbound`'s `process` pass, exclusively, at setup (or resume/refresh) time.**
`work-account` Step 6.5 — the frozen consumer of the declaration — reads only
`company/process.md`; it never reads this file, and this file never restates Step 6.5's
well-formedness grammar (pointer below, not a copy).

**Adding a fourth framework** is a one-file edit: append a `##`-headed template block below,
shaped exactly as the three that follow — a `**Framework:**` line plus bold-term field bullets,
each with one `Evidence:` and one `Coach:` child. `setup-unbound` derives its named enum options
from this file's `##` headings rather than hard-coding them, so a new template needs no edit to
the setup skill.

## Authoring rules

Stated once here; every template below, and every future one, conforms.

- **Declaration shape.** A template body is a complete `## Qualification` section: one
  `**Framework:**` line, then one or more bold-term field bullets. Each field bullet carries
  exactly one non-empty `Evidence:` child and one non-empty `Coach:` child — the exact shape
  `work-account` Step 6.5 declares well-formed (anchor: "**`qualification`** — declaration-driven
  and conditional"). This file states the shape by pointer; Step 6.5 stays the sole authority on
  it.
- **Fields stay bullets, never headings.** Promoting a field to a heading would collide with the
  lowercase/kebab heading convention the canonical stage enum already owns in `process.md`.
- **Field text is the verbatim join key.** Every account record's stored `qualification.fields[]`
  entry matches a field's bold label by exact text. Renaming a label orphans every account record
  already carrying it — there is no migration, no shim, no backfill (ADR-5). `Evidence:` and
  `Coach:` wording carries no such constraint; it is coaching text, freely rewritten.
- **Placement in `process.md`.** A populated section lands after the stage material (and the
  Quick reference table, when present), before the freshness note.

## MEDDPICC

**Framework:** MEDDPICC

Each bold field label below is a verbatim join key. Keep qualification fields as bullets — never
promote one to a heading, because lowercase/kebab headings participate in the canonical stage
convention.

- **Metrics**
  - Evidence: the number the buyer says the install must move, in their words
  - Coach: ask "what number does this have to move for this to be a clear yes?"
- **Economic Buyer**
  - Evidence: the person who owns the budget is named and their view is known
  - Coach: ask the champion who signs, and what that person cares about
- **Decision Criteria**
  - Evidence: the buyer's written or stated criteria for choosing a solution are known
  - Coach: ask what a clear yes looks like on paper, and who wrote it
- **Decision Process**
  - Evidence: the evaluation steps, decision participants, and decision date are known
  - Coach: ask how the decision will be made, by whom, and on what date
- **Paper Process**
  - Evidence: the procurement, legal, security, and signature path is named with owners
  - Coach: ask what has to happen between a verbal yes and a signed agreement
- **Identify Pain**
  - Evidence: the buyer has stated the business pain, its consequence, and why it matters now
  - Coach: ask what breaks if nothing changes, and who feels that consequence most
- **Champion**
  - Evidence: an internal advocate is named, has influence, and is actively selling the change
  - Coach: ask who will carry this forward when we are not in the room
- **Competition**
  - Evidence: the alternatives, including no decision, and the buyer's view of them are known
  - Coach: ask what else they could choose and why they might choose it

## MEDDIC

**Framework:** MEDDIC

The same six shared fields as MEDDPICC, less Paper Process and Competition. Each field's
`Evidence:` and `Coach:` line is reused verbatim from the MEDDPICC template above — they are the
same field under either framework name, so the payload is duplicated here; the authoring rule
that governs both stays owned once, above.

- **Metrics**
  - Evidence: the number the buyer says the install must move, in their words
  - Coach: ask "what number does this have to move for this to be a clear yes?"
- **Economic Buyer**
  - Evidence: the person who owns the budget is named and their view is known
  - Coach: ask the champion who signs, and what that person cares about
- **Decision Criteria**
  - Evidence: the buyer's written or stated criteria for choosing a solution are known
  - Coach: ask what a clear yes looks like on paper, and who wrote it
- **Decision Process**
  - Evidence: the evaluation steps, decision participants, and decision date are known
  - Coach: ask how the decision will be made, by whom, and on what date
- **Identify Pain**
  - Evidence: the buyer has stated the business pain, its consequence, and why it matters now
  - Coach: ask what breaks if nothing changes, and who feels that consequence most
- **Champion**
  - Evidence: an internal advocate is named, has influence, and is actively selling the change
  - Coach: ask who will carry this forward when we are not in the room

## BANT

**Framework:** BANT

Four fields, newly authored in the same register as the templates above: `Evidence:` states the
observable fact that makes the field `captured`; `Coach:` is the one question a rep asks to get
it.

- **Budget**
  - Evidence: a budget figure or range for this purchase is named, or its funding source is known
  - Coach: ask what has been set aside for solving this, or where the money would come from
- **Authority**
  - Evidence: the person or group who can approve this purchase is named
  - Coach: ask who else needs to say yes before this moves forward
- **Need**
  - Evidence: a specific business problem this purchase would solve is stated
  - Coach: ask what problem this is meant to fix, and what happens if it stays unfixed
- **Timeline**
  - Evidence: a target decision or go-live date is stated
  - Coach: ask when they need this solved by, and what is driving that date
