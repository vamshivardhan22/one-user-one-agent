# One User, One Agent

A deterministic, auditable agent framework for the STAGE take-home assignment. The design is evidence-first: each viewer has one goal owner, every proposed intervention is independently checked, and uncertain or unsafe cases abstain instead of inventing facts.

## What is implemented

- SQLite persistence for per-viewer state, decisions, action idempotency, and outcome records.
- Deterministic source resolution with provenance and visible dialect conflicts.
- Conservative goal selection: goals without a measurable success signal are not selected.
- Home-page planning from catalogue records, with dialect, availability, row-size, row-type and content_slug checks.
- Holdout protection, stale-trigger abstention, duplicate-trigger idempotency, quiet-hours helpers and messaging policy checks.
- Replay ordering for triggers, live events, and control events; targeted goal-rule updates and title withdrawals are recorded in the replay audit.
- Injected model faults are matched by trigger/viewer and handled with deterministic fallback; simulated state-store failures fail closed.
- Goal outcome judging distinguishes succeeded, failed and inconclusive, and uses configured success signals inside goal windows.
- Randomized-arm intention-to-treat reporting with per-goal rates and Wilson intervals; pilot re-analysis refuses to fabricate estimates when the expected randomized-arm schema is absent.
- GitHub Actions runs the automated test suite on pushes and pull requests.

## Quick start

Requires Python 3.10+.

    python -m venv .venv

macOS/Linux: `source .venv/bin/activate`

Windows PowerShell: `.\.venv\Scripts\Activate.ps1`

Install and test:

    python -m pip install --upgrade pip
    pip install -e .
    pip install pytest
    python -m pytest -q

Replay:

    stage-agent replay --pack /path/to/unpacked-data-pack --out sample_run

## Expected data pack

The loader expects the assignment's documented layout:

    data/events.jsonl
    data/profiles_snapshot.csv
    data/catalogue.csv
    data/episodes.csv
    config/goals.json
    config/interventions.json
    config/pricing.json
    config/messaging_policy.md
    pilot/
    replay/triggers.jsonl
    replay/live_events.jsonl
    replay/control_events.jsonl
    replay/model_faults.jsonl
    replay/arms.csv
    simulator/simulate_outcomes.py

The replay loader reads common input files and tolerates absent optional files. It does not invent a missing pack or assume unknown schema fields are valid. Verify the pack README and simulator's actual CLI before running the simulator. The simulator is not included in this repository.

## Replay outputs

- decisions.jsonl: decision records and explicit abstentions
- actions.jsonl: actions that passed the verifier
- outcomes.jsonl: goal-level succeeded/failed/inconclusive judgments
- replay_audit.jsonl: control-event and duplicate-live-event handling
- state.sqlite3 and viewer_state/: durable state and readable snapshots
- latency_report.json: local decision compute timing, stale triggers, and fault/control counts
- impact_report.json: per-goal intention-to-treat analysis and pilot re-analysis status

## Policy rules enforced in the baseline

- Holdout viewers receive no interventions.
- A stale/offline-buffered trigger is not treated as a live session.
- App dialect wins for the current render; disagreements remain visible.
- Catalogue items must match dialect and availability at decision time.
- Pages use allowed row types, 3–10 titles per row, no more than six rows, and unique content slugs.
- Push and WhatsApp verification checks consent, quiet hours, combined daily cap, approved WhatsApp template and push copy constraints.
- An opt-out event overrides a stale profile opt-in.
- Catalogue descriptions and other user-supplied text are data, never instructions.
- An unavailable state store leads to abstention rather than an unverified action.
- Missing outcome evidence is not reported as zero uplift.

## Impact methodology

Use the randomized assignment in replay/arms.csv. Compare all assigned agent-arm viewers against all holdout viewers, not users who were served versus those who were not. The latter comparison is biased because being served is not random. Goal outcomes are attributed only when the configured success event occurs between goal start and deadline. Wilson intervals are reported for each arm's rate.

A formal risk-difference confidence interval and the pilot's exact re-analysis require the actual pilot/outcome schemas and data. If the available columns cannot establish randomized assignment and binary outcome, the report explicitly returns NOT_COMPUTED.

## Current verification boundary

The CI suite covers unit-level behavior and an empty-pack replay contract. It does not prove that the complete unseen evaluation passes. The actual Data Pack, its 12 goal definitions, the simulator implementation, and pilot tables were not present in the material available for this repository work. Therefore exact goal-specific interpretations, actual injected fault formats, simulator compatibility, and real impact figures cannot be truthfully marked verified until the official files are run.

The two unclear goals and the unmeasurable goal must be resolved from the actual config/goals.json, not guessed. The same applies to the three approved WhatsApp templates and simulator arguments.

## Project files

- src/stage_agent/engine.py — decision engine and independent verifier
- src/stage_agent/replay.py — replay, live/control event ordering and reports
- src/stage_agent/faults.py — deterministic injected-fault handling
- src/stage_agent/outcomes.py — goal judging, randomized-arm reporting and pilot schema checks
- src/stage_agent/state.py — SQLite state
- tests/ — regression tests
- ARCHITECTURE.md, KNOWN_LIMITATIONS.md, AI_COLLABORATION.md — design, scope and verification notes

## Submission discipline

Run the actual pack from a clean environment, inspect every failed test, and archive the generated reports. Do not claim positive uplift, successful delivery, production readiness, or a full unseen replay pass unless the evidence exists. Complete AI_COLLABORATION.md with real examples from your own review rather than invented anecdotes.
