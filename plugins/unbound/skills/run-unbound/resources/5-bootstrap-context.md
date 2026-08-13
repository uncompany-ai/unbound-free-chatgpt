---
name: bootstrap-context
description: Creates accounts|projects/<slug>/context.md on first encounter using the canonical schema, grounded strictly in the evidence recovered for the selected item — the call transcript when one is present, the email body when the item is email-grounded (no call yet). Invoked internally by run-unbound after evidence recovery, for the selected item only.
tier: all
---
# bootstrap-context

Context-creation step of an Unbound run (composition slot 5, post-selection). Given the selected
item's `{ namespace, slug, evidence[] }`, check whether `accounts|projects/<slug>/context.md`
already exists and, only if it does not, create it using the canonical frontmatter schema
grounded in the evidence `fetch-transcript` just recovered — the call transcript when one is
present, the email body when the item is email-grounded and no call yet exists for this slug. It
runs **once per run, for the one selected item**: an item the rep did not pick is never
bootstrapped, which is why `classify-work` no longer relies on a directory existing to keep that
item's slug stable. On a re-encountered slug (file exists), this is a no-op — no duplicate, no
enrichment. This skill only creates a new context.md on first encounter; enrichment is
`work-account`'s job.

## Reads

- `accounts/<slug>/context.md` or `projects/<slug>/context.md` — existence check only.
- `company/process.md` — canonical stage enum for account `stage` validation.
- In-memory `selected_item.evidence[]` — the grounding artifacts recovered for this slug, each `{ event_id, source, external_ref, occurred_at, kind: "transcript"|"email_body", content, evidence_status, ...source-specific }`. `content` is the verbatim grounding payload and is present only on an entry marked `present`. The entry shape is `fetch-transcript`'s; accept it as-is and never re-fetch.
- The selected item's event metadata carried on those entries (title, `participants`, `call_type`/`subject`) plus any pasted info — the fallback signal when no entry carries `content`.

## Procedure

**1 — Existence check.** If `<namespace>/<slug>/context.md` already exists, this is a no-op:
leave the file unchanged, do not append or enrich, and move on. Create only when the file is absent.

**2 — Create context.md with the canonical schema.** Create `<namespace>/<slug>/context.md`
(create the slug directory if needed) with this exact structure. The parent namespace
directory (`accounts/` or `projects/`) is guaranteed by `setup-unbound`'s scaffolding, but on
a bare run without prior setup it is likewise created if absent — never an error:

```markdown
---
type: <account|project>        # mirrors namespace
slug: <slug>                   # exactly as supplied by classify-work
name: <entity name>            # from available signal, never invented
domains: []                    # accounts only; OPTIONAL — list of email-domain strings (rep-editable). Used by discover-events for deterministic prospect/customer matching of inbound email senders. Left empty at bootstrap; rep adds entries when they want a sender domain to deterministically route to this slug. discover-events reads it; bootstrap-context and work-account do not write to it.
crm_ref: <crm record ref>      # accounts only; OPTIONAL — opaque CRM record reference, inert data (rep-editable). Names the one CRM record this account maps to, so a CRM read is keyed deterministically instead of matched by name or domain. OMITTED ENTIRELY at bootstrap — the rep adds the key if and when they want that mapping. work-account reads it; bootstrap-context and work-account do not write to it. Absent (the normal case) is valid and simply means no CRM read is attempted.
stage: <enum or NEEDS-REP-INPUT>  # accounts only; omit for projects
stakeholders:
  - { name: <name>, role: <role>, champion: <true|false> }
last_next_step: ""
open_questions: []
competitive_threats: []        # accounts only; omit for projects
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>          # same as created at bootstrap
---

## Summary
<one paragraph grounded strictly in transcript/pasted info>

## Activity Log
```

**3 — Stage rules.** Accounts: set `stage` to a `company/process.md` enum token only on explicit
evidence in the grounding source (the `content` of a `present` evidence entry, whichever kind);
flag `NEEDS-REP-INPUT` when not confidently inferrable — never guess. Projects: omit
`stage` and `competitive_threats` entirely. `domains:` is rep-authored, not bootstrapped: leave
it as the empty list `[]` on accounts (omit entirely for projects). Never auto-populate
`domains:` from the call transcript or from the email sender's domain — the rep curates which
sender domains deterministically route to a given slug. `crm_ref:` follows that same rule one step
further: omit the key entirely at bootstrap, on accounts and projects alike, and never auto-populate
it from a transcript, an email, an account name, or a domain — the rep authors the CRM mapping or
there is none, and there being none is the ordinary case.

**4 — Ground everything; surface gaps.** Every populated field traces to the grounding source (the
`content` of a `present` evidence entry, plus pasted info in either
case). Never fabricate facts, stakeholders, roles, or summary details. When a field cannot be
grounded, leave it empty/flagged and tell the rep. `stakeholders` includes only people evidenced
in the source — on an email-grounded bootstrap the entry's `participants[]` (sender + named
recipients) may be extracted as stakeholders when their role/relationship is evidenced in the
email body or pasted info; never invent a role or champion-flag. `## Activity Log` is left empty
(heading only).

Grounding source, decided across the item's evidence entries rather than one upstream event —
an item can arrive with several, and they are read together:

- **Any `present` entry of `kind: "transcript"`** → ground `## Summary` strictly in that entry's
  `content` + pasted info (existing behavior; unchanged). More than one → read them all, most
  recent `occurred_at` first.
- **No present transcript, but a `present` entry of `kind: "email_body"`** (no call yet exists for
  this slug — confirmed by the file-absent existence check in Step 1) → ground `## Summary` in that
  entry's `content` + its subject + pasted info, AND
  note in `## Summary`: *"no call yet — grounded in email correspondence"* (or substantively
  equivalent prose) so the rep can see at a glance that the bootstrap was email-grounded. The
  stage default (NEEDS-REP-INPUT unless email-body evidence explicitly maps to a
  `company/process.md` enum token) is unchanged.
- **No entry carries `content` at all** — every entry came back `missing` — → ground in the
  entries' titles, `participants`, and pasted info, and note in `## Summary` that no evidence was
  retrievable. Create the file anyway: a thin honest context is what the rep can correct, and
  refusing to create one would leave the selected item with no context at all. Never fabricate a
  summary to fill the gap, and never guess a stage.

**5 — Augment and return.** Carry the selected item forward with
`context_ref: <namespace>/<slug>/context.md` — the path is deterministic, so it is returned on both
branches: the file this step created, and the one Step 1 found already there. Preserve all upstream
fields.

## Writes

- `accounts/<slug>/context.md` or `projects/<slug>/context.md` — created only on first encounter (file absent). No other file.

## Failure rules

- Never fabricate facts, stakeholders, roles, stages, or summary unsupported by the grounding source (a `present` evidence entry's `content`); surface missing info as gaps.
- Never create a duplicate context.md on re-encounter; never enrich/append at bootstrap.
- Never write any file other than the one context.md; never touch run-state/events/last_run.
- Never guess/default a stage; never pre-fill open_questions/competitive_threats/last_next_step with guesses. Email-grounded bootstrap follows the same stage rule — set `stage` only on explicit email-body evidence mapping to a `company/process.md` enum token; otherwise flag `NEEDS-REP-INPUT`.
- Never auto-populate `domains:` or `crm_ref:` — both are rep-authored. Bootstrap leaves `domains:` empty on accounts and omits it entirely on projects; it omits `crm_ref:` entirely on both, and an absent `crm_ref:` is valid — it simply means no CRM read is attempted.
- Never assume a call exists for an email-grounded item. When the existence check (Step 1) confirms no `context.md` exists, the email body IS the grounding source — note that explicitly in `## Summary`; never fabricate a transcript that wasn't there.
- Never read a `missing` entry's `content` — there is none. An item whose evidence all came back `missing` still gets its context.md, grounded in metadata with the gap stated; refusing to create one, or filling it with invented detail, are both worse than a thin honest file.
- Never bootstrap an item the rep did not select — this step runs once per run, on the one selected item.
