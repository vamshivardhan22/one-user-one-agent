# Architecture

## Decision lifecycle

1. Load source events and snapshots.
2. Deduplicate source events by event ID.
3. Process replay triggers by server delivery/receipt time.
4. Resolve the viewer's facts and retain conflict details.
5. Select a goal only when a measurable signal exists and eligibility can be supported.
6. Propose an intervention or explicit abstention.
7. Run an independent verifier; a rejected proposal is converted to `NO_ACTION`.
8. Persist decision, viewer state, and action ledger.
9. Export a replay report that distinguishes local compute timing from end-to-end delivery latency.

## State and ownership

`StateStore` uses SQLite to persist per-viewer state, processed trigger decisions, action idempotency, and outcome records. A trigger event ID is the idempotency key in the baseline. A production multi-worker deployment should add transactional claiming/locking before any external action is published.

## Fact precedence

- Current app setting wins for the dialect rendered on the active visit; profile disagreement remains visible.
- A known purchase event overrides a stale profile subscription snapshot.
- A notification opt-out event overrides a profile opt-in.
- Server `received_at` / delivery time is the trusted ordering basis; client timestamps may be wrong.
- Duplicate profile rows use the latest parseable snapshot timestamp, then a stable tie-break.

These are the current baseline rules. Each fact and goal rule must be checked against the supplied configuration before a full assessment claim is made.

## Safety boundary

Catalogue descriptions, titles, campaign parameters, and viewer text are data, not instructions. Never let them override policy. Model outputs are proposals rather than evidence or policy approval.

## Availability and latency

The CLI reports local decision computation time only. It is not a proof of delivery confirmation within 60 seconds. A real deployment should measure trigger arrival, queue time, decision, verification, publication, and delivery confirmation separately.

## Measurement

Use intention-to-treat: all randomized agent-arm viewers compared with all randomized holdout viewers, whether or not an action was served. A served-versus-unserved comparison is biased by selection into service. Report uncertainty and explain limitations.
