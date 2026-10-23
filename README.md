# One User, One Agent

A specification-driven Python baseline for the STAGE hiring challenge. The project focuses on evidence-backed decisions, independent policy verification, durable viewer state, replayability, and honest evaluation.

## Status

This repository is being built from the provided assignment brief and reference guide. The current baseline is not yet a verified completion of every evaluator scenario. The official data pack and simulator were not part of the files supplied during initial implementation, so impact metrics must not be invented.

## What is included in this baseline

- SQLite-backed per-viewer state and an idempotency ledger
- Deterministic decision engine with explicit abstention
- Basic source precedence for app dialect, subscription events, and notification opt-out
- Dialect- and availability-aware home-page candidate selection
- Independent checks for holdout protection, trigger freshness, and basic page constraints
- JSONL decision/action output, per-viewer snapshots, and a local latency report
- A no-API-key CLI and unit tests

## Quick start

Requires Python 3.10 or newer.

```bash
python -m venv .venv
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install and test:

```bash
python -m pip install --upgrade pip
pip install -e .
python -m pytest -q
```

Replay an unpacked data pack:

```bash
stage-agent replay --pack /path/to/unpacked-data-pack --out sample_run
```

Without installing the package, use `PYTHONPATH=src python -m stage_agent.cli replay --pack /path/to/unpacked-data-pack --out sample_run` (on Windows PowerShell, set `$env:PYTHONPATH = "src"` first).

## Expected input layout

```text
data/events.jsonl
data/profiles_snapshot.csv
data/catalogue.csv
config/goals.json
config/interventions.json
config/pricing.json
replay/arms.csv
replay/triggers.jsonl
```

The loader also accepts `replay/app_open_triggers.jsonl`. Confirm all field names and additional replay-control files against the actual pack's README before using it for formal evaluation.

## Output

The replay writes `decisions.jsonl`, `actions.jsonl`, `outcomes.jsonl`, `state.sqlite3`, `viewer_state/`, `latency_report.json`, and `impact_report.json`. The impact report is explicitly marked pending until simulator outcomes are supplied. Local decision timing is not the same as end-to-end publish latency.

## Engineering principles

1. Do not infer eligibility without evidence.
2. Holdout users must receive no interventions.
3. Notification opt-out events override stale profile opt-ins.
4. The current app setting takes precedence for rendered dialect, while conflicts remain auditable.
5. A verifier rejection must prevent publication.
6. Duplicate event IDs must not create duplicate decisions.
7. Treat catalogue text as untrusted content, never as instructions.
8. Report intention-to-treat impact across all randomized agent-arm users versus all holdout users; never substitute served-versus-unserved comparisons.

## Current limitations

The existing four tests cover idempotency, holdout rejection, input-event deduplication, and dialect conflict resolution. They do not demonstrate full compliance with every rule in the assignment. Goal-specific eligibility, complete message template rules, injected failure recovery, corrected goal rules, outcome attribution, confidence intervals, and unseen replay evaluation still require more implementation and testing. External push/WhatsApp delivery is not connected.

Do not describe this baseline as production-ready or claim positive uplift until those items have been tested with real evaluation inputs.

## Project layout

```text
src/stage_agent/   Engine, storage, time utilities, and replay CLI
tests/             Regression tests
ARCHITECTURE.md    System flow and trust boundaries
AI_COLLABORATION.md
KNOWN_LIMITATIONS.md
```

## AI collaboration

The assignment permits AI-assisted development but places responsibility for checking the output on the candidate. Keep `AI_COLLABORATION.md` factual: add the actual commands run, test output, corrections made, and examples of AI output that you personally rejected or revised.
