# Known Limitations

1. The official synthetic Data Pack and simulator were not supplied with the two reference documents used during initial implementation. Exact field names and replay behavior must be validated.
2. Goal eligibility currently handles only simple generic rule shapes. All goal-specific conditions from the actual goals configuration still need explicit mapping and tests.
3. Corrected goal rules during replay and outcome re-judgment are not implemented end to end.
4. The loader reads common replay files, but all actual control-event and injected-fault semantics require integration.
5. Push and WhatsApp publication are not connected to providers. The baseline should not be described as sending real messages.
6. Outcome attribution, intention-to-treat confidence intervals, pilot re-analysis, and goal-level impact require simulator results and are not yet complete.
7. SQLite provides local persistence, but cross-process publication claims require transactions/leases or a queue for production.
8. Latency reports measure local computation and do not prove publication or message delivery latency.
9. Confidence values are heuristic, not calibrated probabilities.
10. No positive uplift or unseen replay pass is claimed.
