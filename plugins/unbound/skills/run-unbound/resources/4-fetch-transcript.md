---
name: fetch-transcript
description: Recovers the evidence for the one selected item — a transcript for each pending call, the thread body for each pending email — by re-fetching each event's stored external_ref, and returns them as evidence[] entries marked present or missing (a first-class state). Invoked internally by run-unbound after selection.
tier: all
---
# fetch-transcript

Evidence-recovery step of an Unbound run (composition slot 4, post-selection). Given the selected
item's `(namespace, slug)`, collect that item's durable `processing_status: pending` event records
from `state/run-state.yaml` and recover each one's evidence from its stored `external_ref` —
`source: "call"` via the logical `transcript.get(call_ref)` capability, `source: "email"` via
`email.get_thread(thread_ref)`. Union the results into `evidence[]`, one entry per event, each
marked `evidence_status: present` or `missing` (a first-class state), and return them with the same
events' ids. Nothing is fetched before selection: the slate is built from event metadata alone, and
this is the run's only evidence retrieval. This skill only recovers evidence and returns — it does
not discover events, classify, upsert the event records, create context.md, or advance `last_run`.

## Reads

- `state/run-state.yaml` — every event record whose `processing_status` is `pending` and whose `(namespace, slug)` matches the selected item; the schema doc-comment in that file is authoritative. This is the **durable** event list, not this run's discovery bag, which is what makes recovery independent of the discovery window: an event sitting behind `last_run` and therefore never re-discovered is recovered here exactly like one found minutes ago. Read-only — this skill writes nothing back to it.
- Logical capability `transcript.get(call_ref) -> { text, provider } | { missing: true }` — read scope only; the binding fans out across all configured transcript providers and returns the best confident match (or `missing` when none is confident). The skill never names a concrete provider. Only invoked for `source: "call"` events.
- Logical capability `email.get_thread(thread_ref) -> thread | missing` — read scope only; get-by-ref, no window and no search, so a stored ref is the whole query. A ref that no longer resolves (thread deleted, moved out of the account, or otherwise purged) returns `missing` — never a nearest-match thread. Only invoked for `source: "email"` events.

## Procedure

**1 — Collect the selected item's pending events; branch on `source`.** Read the durable event
records and keep every one whose `processing_status` is `pending` and whose `(namespace, slug)`
matches the selection — **however many runs ago it was discovered**. Every collected event must
appear in the output with an `evidence_status` — never drop an event. If the item has no pending
events, return an empty set cleanly.

- `source: "call"` → proceed to Step 2 (correlate via `transcript.get`).
- `source: "email"` → proceed to Step 3 (resolve the thread via `email.get_thread`).

Carry each event's `event_id`, `external_ref`, and `occurred_at` verbatim from the record onto its
entry. Never re-classify or re-discover here; re-fetching by stored ref **is** the recovery
mechanism, not a re-discovery.

**Issue the collected events' fetches concurrently, at most four in flight (parallel where
supported).** The events are mutually independent — no event's fetch takes any input from another
event's result — so Steps 2 and 3 apply per event rather than one event after another, and the
step costs about its slowest single fetch instead of the sum of them. The bound is a fixed **four**
because an item left unworked for weeks accumulates pending events without limit, and a call
event's fetch is *itself* a fan-out across providers at the binding layer, so an unbounded set of
events in flight would multiply out at both levels at once. Four is generous against any realistic
pending set for one item and still cannot burst its sources. This governs **when** fetches are
issued, never **how** any result is handled: every event's outcome is still resolved by Steps 2–4
exactly as written, and one event's failure is its own (Step 4).

**Fetch each `event_id` at most once per cycle.** Keep an in-memory map from `event_id` to the
result its fetch returned, and serve any later request for that same `event_id` in this cycle from
the map instead of re-issuing the fetch. `event_id` is `"<source>:<external_ref>"`, minted once by
`discover-events` and carried verbatim under an explicit never-rewrite rule, so it is immutable for
the life of its source object and therefore sound as the key. This is the **only** reuse rule in
the recovery path — a selection re-entered or retried within the same cycle re-reads the map rather
than the sources, and no second fast path exists or is to be added. The map is per-run and
in-memory: nothing is persisted, it never outlives the cycle, and a later run re-fetches from its
stored refs exactly as if the map had never existed.

**2 — Correlate `call_ref` to transcript (call events only).** Pass the call event's
`external_ref` to `transcript.get(call_ref)` and let the binding resolve the correlation.

- Confident match → mark `evidence_status: present`, carry the returned transcript text as
  `content` and the returned `provider` verbatim (do not summarize, truncate, paraphrase, edit, or
  normalize).
- Fuzzy/uncertain match → mark `evidence_status: missing` and surface for the rep. A mis-attributed
  transcript is worse than a surfaced gap.

**3 — Resolve `thread_ref` to the thread body (email events only).** Pass the email event's
`external_ref` to `email.get_thread(thread_ref)`.

- Thread returned → mark `evidence_status: present` and carry its latest external message body as
  `content` verbatim, on the same no-reformatting terms as a transcript.
- `missing` (the ref no longer resolves) → mark `evidence_status: missing`; never substitute a
  nearest-match thread and never fabricate a body. An email whose thread was purged degrades
  honestly like any other missing source.

**4 — Handle missing evidence (either source).** When no transcript exists, the correlation is
uncertain, a stored ref no longer resolves, or a single fetch fails transiently:

- Mark `evidence_status: missing` — a first-class state.
- Carry no `content` — never fabricate.
- Keep the event on the path and let the others resolve — never abort the run for one failure.
- Surface all `evidence_status: missing` cases to the rep. The event stays selectable and is never
  dropped.

**5 — Build and return the recovered set.** One `evidence[]` entry per collected event:

```
# call, present:  { event_id, source: "call", external_ref, occurred_at, kind: "transcript",
#                   content, provider, evidence_status: present, call_type?, title?, participants? }
# call, missing:  { event_id, source: "call", external_ref, occurred_at, kind: "transcript",
#                   evidence_status: missing, call_type?, title?, participants? }
# email, present: { event_id, source: "email", external_ref, occurred_at, kind: "email_body",
#                   content, evidence_status: present, subject?, participants? }
# email, missing: { event_id, source: "email", external_ref, occurred_at, kind: "email_body",
#                   evidence_status: missing, subject?, participants? }
```

Return `{ evidence[], event_ids[] }`, where `event_ids[]` is exactly the collected events' ids —
the same set and nothing wider, so the cycle that records them and the close-out that flips them
name the identical events. The set is in-memory only, not persisted to its own file.

**`evidence_status` on an entry is `present` or `missing` only.** `unknown` is a *run-state* value
— it is what `build-slate` writes on a call it has not fetched — and it never appears on an
`evidence[]` entry: by the time an entry exists the fetch has happened, so the answer is known.
Never copy a record's `unknown` onto an entry, and never write a resolved status back to the
record; the recovered status stays in memory for this cycle.

## Writes

None. This skill performs no write of any kind — in particular it never writes the recovered
`evidence_status` back to `state/run-state.yaml`. Re-running leaves the working tree unchanged.

## Failure rules

- Never fabricate transcript text or an email body; a missing evidence entry carries no `content`.
- Never abort the run on a single fetch failure; mark that event missing and continue with the rest.
- Never silently drop a pending event (call or email); every collected event stays on the path with its status marked, and an entry marked `missing` never blocks selection or synthesis.
- Never return a nearest-match transcript or thread for a ref that no longer resolves — a purged source is `missing`, which is an honest answer, and a mis-attributed one is not.
- Never write `evidence_status: unknown` onto an `evidence[]` entry, and never persist a recovered status back to the event record — the run-state value is `build-slate`'s to write, once, at upsert.
- Never let concurrency reach a failure outcome — the fan-out and its bound govern only when fetches are issued; a failed or unmatched fetch is still resolved per event by the rules above, and no event's failure cancels, aborts, or alters another's.
- Never fetch one `event_id` twice in a cycle, and never persist the cycle's map or carry it into a later run — it is in-memory for this cycle alone, and it is the recovery path's only reuse mechanism.
- Never widen `event_ids[]` past the events actually collected for this `(namespace, slug)`.
- Never scope the collection to this run's discovery window — the pending records are the input, and an event behind `last_run` is recovered on exactly the same terms as one discovered minutes ago.
