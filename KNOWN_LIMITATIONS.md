# Known Limitations and Verification Status

## Implemented in this repository

- SQLite state and trigger idempotency.
- Basic fact provenance and app-dialect precedence.
- Conservative generic goal selection requiring a measurable success signal.
- Home-page candidate planning and an independent verifier.
- Stale-trigger abstention, replay timeline ordering, control-event audit, and generic injected-fault matching.
- Goal outcome classification and per-goal randomized-arm intention-to-treat rates with Wilson intervals.
- CI test workflow.

## Not yet verifiable from available materials

The assignment guide describes the data pack and simulator, but those actual files were not available in the repository conversation. Without them, these items cannot honestly be declared complete:

1. Exact eligibility and success logic for all 12 goals, including the two ambiguous rules and one unmeasurable goal.
2. Exact field names and payload semantics for every control event and injected model fault.
3. Whether the provided simulator accepts the replay adapter's expected inputs and which command-line arguments it supports.
4. Exact pilot report re-analysis and the difference from the biased served-versus-unserved headline.
5. End-to-end outcomes, goal-level uplift, and a valid confidence interval for the risk difference using the actual randomized cohort.
6. Provider delivery receipts and real end-to-end latency. The current latency report measures local computation, not confirmed delivery.
7. Multi-process action claiming/locking for a production distributed deployment.
8. The three actual approved WhatsApp template IDs and complete intervention schema.

## Safe reporting rules

- Missing outcome data is not a zero-success result.
- Missing or unsupported goal conditions must not be guessed.
- Synthetic test fixtures are not official replay evidence.
- Never upload personal pack data to third-party services.
- Never claim full assignment completion based only on unit tests.
