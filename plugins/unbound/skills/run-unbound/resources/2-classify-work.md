---
name: classify-work
description: Routes each discovered event (call or email) to its owning account (opportunity) or project (non-opportunity) namespace, assigns a stable kebab-case slug, reusing existing slugs and honoring a confident upstream suggested_slug hint when present, and resolves each event's required in-memory display name. Invoked internally by run-unbound after discover-events.
tier: all
---
# classify-work

Classification step of an Unbound run (composition slot 2). Given the source-discriminated
`discovered_events` working set from `discover-events`, route each event to
`accounts` (opportunity) or `projects` (non-opportunity), assign a deterministic kebab-case slug
(reusing existing slugs on re-encounter; honoring `suggested_slug` from `discover-events` as a
confident slug-reuse hint when present) against the `prepare` snapshot's `known_anchors`, resolve a
required `display_name`, and return the augmented set. Routing happens on event metadata: no
evidence has been retrieved at this point in the run. This skill only classifies, assigns a slug and
resolves a display name — it does not discover events, fetch evidence, create context.md, upsert
the queue, or advance `last_run`.

## Reads

- In-memory `discovered_events` from `discover-events` — source-discriminated working set. Each item carries `{ event_id, source: "call"|"email", external_ref, occurred_at, title, participants, ambiguous, suggested_slug?, call_type? (call-only), latest_message_body? (email-only) }`. Accept as-is; do not reshape or re-fetch; carry `event_id` and `external_ref` verbatim.
- The `prepare` snapshot from run-unbound's final pre-query beat — `known_anchors` (the stability check below) and `context` (the known-name lookup for `display_name`) — required, passed by the orchestrator; do not re-derive either by listing `accounts/`/`projects/` or re-reading `state/run-state.yaml` directly. `known_anchors` is already the union both a directory and a durable-but-unselected event pair would otherwise require checking separately — that union is exactly what keeps a discovered-but-never-selected item's slug stable, since `bootstrap-context` (which creates the directory) runs only on the selected item.

## Procedure

**1 — Iterate per discovered event.** Every input event must appear in the output with
`namespace`, `slug` and `display_name` — never drop an event. Preserve all upstream fields
(including `source` and `suggested_slug` when present); only add the three. If the input is empty,
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

**3 — Derive a deterministic, stable kebab-case slug and `display_name`.** Neither is ever blank.

1. **Resolve a working name** from available signal (title, participants, sender, subject) — never
   invent one when the signal genuinely does not support it; fall through to Step 4's rep ask
   instead. This is both the minting input below and the `display_name` fallback.
2. **Suggested-slug fast path (preferred).** If the event carries `suggested_slug` (attached by
   `discover-events` on a confident domain or fuzzy match — email-only today, but the rule is
   source-agnostic), **verify it is a member of `known_anchors` under the chosen namespace**.
   Verified → reuse the slug verbatim and skip to sub-step 4. Miss (not a member) → discard the hint
   silently and fall through to sub-step 3; **never silently mint a near-duplicate of an existing
   slug just because the hint missed**.
3. Not reused via the fast path: check `known_anchors` under the chosen namespace for a slug whose
   known name matches the resolved working name (allowing obvious variants) → reuse it verbatim.
   Never mint a near-duplicate.
4. Mint only when genuinely new (no `known_anchors` member matched): lowercase → strip legal
   suffixes (inc, llc, ltd, corp, etc.) → remove punctuation → collapse whitespace to hyphens → trim
   leading/trailing hyphens.
5. **`display_name`**: the slug's current `name` from the `prepare` snapshot's `context` when
   known — an established account or project keeps its own name even when this one event's signal
   reads slightly differently — otherwise sub-step 1's resolved working name. Never persisted: it
   lives only in memory for this run, and `build-slate`'s `materialize --apply` call is its one
   consumer.

The slug is the coverage upsert key in `materialize` — an inconsistent slug for the same entity
would fragment its context. `suggested_slug` is a **hint** only; this skill remains the
slug-decision authority and must never auto-confirm a slug it could not verify against
`known_anchors`.

**4 — Ambiguous signal: ask the rep.** When the account-vs-project signal is insufficient, a
working name cannot be resolved, or a name might match an existing slug but you are not confident,
ask the rep to disambiguate. Never default silently; the event stays in the working set while
awaiting the answer. Unknown-sender emails with no `suggested_slug` and no confident inference
follow this exact rule — the rep decides whether to attach to an existing slug, mint a new one, or
skip — mirroring the existing ambiguous-call disambiguation prose.

**5 — Return the augmented set.** `{ ...discovered_event, namespace: accounts|projects, slug,
display_name }`. The set is in-memory only, not persisted to its own file.

## Writes

None. This skill performs no write of any kind. Re-running leaves the working tree unchanged.

## Failure rules

- Insufficient account-vs-project signal → ask the rep; never default silently.
- No call content (none is retrieved before selection) → classify from the remaining metadata signal; never fabricate call content; never drop the event.
- No resolvable working name → surface to the rep; never invent a placeholder name, slug, or `display_name`.
- Near-duplicate entity name → ask the rep rather than minting a second slug. Fragmentation is the dangerous failure.
- Never anchor slug stability on a directory listing alone — `known_anchors` is already the union that keeps a discovered-but-never-selected item's slug stable; consult it whole, never a subset.
- `suggested_slug` present but not a `known_anchors` member in the chosen namespace → discard the hint and proceed via the normal slug-derivation path; never auto-confirm an unverifiable hint.
- `source` field is additional signal only — never use it as a bias toward `accounts` or `projects` independent of the underlying content signal.
- Every returned event carries `display_name` — a missing one blocks `materialize` outright; never leave it blank and never invent one the resolved signal or `context` does not support.
