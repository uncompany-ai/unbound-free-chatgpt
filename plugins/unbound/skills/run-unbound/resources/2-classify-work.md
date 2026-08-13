---
name: classify-work
description: Routes each discovered event (call or email) to its owning account (opportunity) or project (non-opportunity) namespace and assigns a stable kebab-case slug, reusing existing slugs and honoring a confident upstream suggested_slug hint when present. Invoked internally by run-unbound after discover-events.
tier: all
---
# classify-work

Classification step of an Unbound run (composition slot 2). Given the source-discriminated
`discovered_events` working set from `discover-events`, route each event to
`accounts` (opportunity) or `projects` (non-opportunity), assign a deterministic kebab-case slug
(reusing existing slugs on re-encounter; honoring `suggested_slug` from `discover-events` as a
confident slug-reuse hint when present), and return the augmented set. Routing happens on event
metadata: no evidence has been retrieved at this point in the run. This skill only classifies
and assigns a slug — it does not discover events, fetch evidence, create context.md, upsert
the queue, or advance `last_run`.

## Reads

- In-memory `discovered_events` from `discover-events` — source-discriminated working set. Each item carries `{ event_id, source: "call"|"email", external_ref, occurred_at, title, participants, ambiguous, suggested_slug?, call_type? (call-only), latest_message_body? (email-only) }`. Accept as-is; do not reshape or re-fetch; carry `event_id` and `external_ref` verbatim.
- `accounts/` and `projects/` directory listings — existing slug directories: the first anchor of the stability check.
- `state/run-state.yaml` — the distinct `(namespace, slug)` pairs already recorded across `events`: the second anchor of the stability check, and the one that still holds for an item discovered in an earlier run but never selected. Read-only; this skill writes nothing back.

## Procedure

**1 — Iterate per discovered event.** Every input event must appear in the output with
`namespace` and `slug` — never drop an event. Preserve all upstream fields (including `source`
and `suggested_slug` when present); only add `namespace` and `slug`. If the input is empty,
return an empty set cleanly.

**2 — Decide namespace: `accounts` XOR `projects`.** Each event routes to exactly one:

- `accounts` — opportunity work: external prospect/customer conversation (discovery, demo,
  evaluation, proposal, negotiation) — or unanswered inbound email from a prospect/customer.
- `projects` — non-opportunity work: internal initiative, cross-account program, operational effort.

Base the decision on available signal: title + participants + source-specific signal (`call_type`
for calls, sender domain + subject line for emails) + pasted info, plus — for emails only —
`latest_message_body`, which `discover-events` already carries inline at no fetch cost. **Calls
route on metadata**: no transcript exists at this point in the run, because evidence recovery
happens after selection. A call with metadata alone is still classifiable from remaining signal —
that has always been true of a call whose transcript could not be found, and it is now simply the
ordinary case rather than the exception. Never fabricate call content to fill the gap; where the
remaining signal genuinely does not settle `accounts` vs `projects`, Step 4's rep ask is the
answer. The `source` field is **additional signal** for namespace
choice (e.g., an inbound business email from a prospect domain weakly suggests `accounts`); it is
**not** a bias toward `accounts` over `projects` or vice versa — an internal-coordination email
between teammates classifies to `projects` exactly as an internal coordination call would.

**3 — Derive a deterministic, stable kebab-case slug.** Honor `suggested_slug` first when present.

A slug is "known" in a namespace when **either** anchor holds: a `<namespace>/<slug>/` directory
exists, **or** the run-state `events` list already carries that `(namespace, slug)` pair. Two
anchors, not one, because the directory is created by `bootstrap-context`, which runs only on the
selected item — so an item discovered in an earlier run and never selected has no directory while
its events have been durable in `events` since the run that found them. Consulting both is what
keeps its slug stable; consulting only the first would re-mint one.

1. **Suggested-slug fast path (preferred).** If the upstream event carries `suggested_slug`
   (attached by `discover-events` on a confident prospect/customer match — email-only today, but
   the rule is source-agnostic), **verify the slug is known in the chosen namespace** by either
   anchor. On verified hit → reuse the slug verbatim and skip to
   Step 4. On miss (neither anchor holds in the chosen namespace) → discard the hint silently and
   fall through to step 3.2; **never silently mint a near-duplicate of an existing slug just
   because the hint missed**.
2. Identify the entity name from available signal (when no `suggested_slug` or it was discarded);
   never invent one.
3. Check both anchors under the chosen namespace before minting — if the entity matches an
   already-known slug (allowing obvious name variants), reuse it verbatim. Never mint a
   near-duplicate.
4. Mint only when genuinely new: lowercase → strip legal suffixes (inc, llc, ltd, corp, etc.) →
   remove punctuation → collapse whitespace to hyphens → trim leading/trailing hyphens.

The slug is the coverage upsert key in `build-slate` — an inconsistent slug for the same entity
would fragment its context. `suggested_slug` is a **hint** only; this skill remains the
slug-decision authority and must never auto-confirm a slug it could not verify.

**4 — Ambiguous signal: ask the rep.** When the account-vs-project signal is insufficient, or a
name might match an existing slug but you are not confident, ask the rep to disambiguate. Never
default silently; the event stays in the working set while awaiting the answer. Unknown-sender
emails with no `suggested_slug` and no confident inference follow this exact rule — the rep
decides whether to attach to an existing slug, mint a new one, or skip — mirroring the existing
ambiguous-call disambiguation prose.

**5 — Return the augmented set.** `{ ...discovered_event, namespace: accounts|projects, slug }`.
The set is in-memory only, not persisted to its own file.

## Writes

None. This skill performs no write of any kind. Re-running leaves the working tree unchanged.

## Failure rules

- Insufficient account-vs-project signal → ask the rep; never default silently.
- No call content (none is retrieved before selection) → classify from the remaining metadata signal; never fabricate call content; never drop the event.
- Near-duplicate entity name → ask the rep rather than minting a second slug. Fragmentation is the dangerous failure.
- No determinable entity name → surface to the rep; never invent a placeholder slug.
- Never anchor slug stability on the directory alone — an item discovered but never selected has no directory yet, and re-minting its slug is exactly the fragmentation this check exists to prevent. Both anchors, every time.
- `suggested_slug` present but unverifiable in the chosen namespace → discard the hint and proceed via the normal slug-derivation path; never auto-confirm an unverifiable hint.
- `source` field is additional signal only — never use it as a bias toward `accounts` or `projects` independent of the underlying content signal.
