# One User, One Agent

This is my solution for the STAGE **One User, One Agent** assignment.

The idea is simple: every user should have one agent that understands what is known about them, chooses one useful goal, and decides whether to take an action or do nothing. The agent must follow the app's rules and use real data. It should not guess when the information is missing or unclear.

I focused on making the decisions safe, easy to check, and repeatable. Doing nothing is also a valid decision when there is not enough evidence or an action would break a rule.

## What the project does

- Reads user events, profile information, catalogue data, and replay inputs from the assignment data pack.
- Keeps user state and decision records in SQLite.
- Tracks where user facts came from and makes conflicting information visible.
- Checks whether a goal is eligible before selecting it. A goal without a measurable success event should not be selected.
- Plans home-page content using catalogue information, including dialect and availability checks.
- Checks actions against safety rules before allowing them.
- Keeps holdout users free from agent interventions.
- Handles duplicate or stale triggers without blindly repeating an action.
- Replays events and records decisions, actions, and audit information.
- Judges goal outcomes as succeeded, failed, or inconclusive when the required evidence is available.
- Includes reporting code for comparing the randomized agent and holdout groups.
- Runs automated tests through GitHub Actions.

## How to set it up

You need Python 3.10 or newer.

Create and activate a virtual environment:

```bash
python -m venv .venv
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project and test tools:

```bash
python -m pip install --upgrade pip
pip install -e .
pip install pytest
```

Run the tests:

```bash
python -m pytest -q
```

## Running a replay

First, download and extract the official **One User, One Agent – Data Pack**. Then run:

```bash
stage-agent replay --pack /path/to/unpacked-data-pack --out sample_run
```

Replace the example path with the location where you extracted the pack. Check the pack's README and the simulator instructions before running the simulator.

## Data the assignment provides

The replay expects the official pack to contain files such as:

```text
data/
  events.jsonl
  profiles_snapshot.csv
  catalogue.csv
  episodes.csv
config/
  goals.json
  interventions.json
  pricing.json
  messaging_policy.md
pilot/
replay/
  triggers.jsonl
  live_events.jsonl
  control_events.jsonl
  model_faults.jsonl
  arms.csv
simulator/
  simulate_outcomes.py
```

The exact files and formats in the official pack are important. The project should use those real definitions rather than making up missing rules or data. The simulator itself is supplied by the assignment pack, not by this repository.

## Output files

A replay writes reports and records to the output folder, including:

- `decisions.jsonl` — what the agent decided, including when it chose not to act.
- `actions.jsonl` — actions that passed the checks.
- `outcomes.jsonl` — goal results when they can be judged from the available evidence.
- `replay_audit.jsonl` — audit details about replay events and controls.
- `state.sqlite3` and `viewer_state/` — saved user state.
- `latency_report.json` — timing and replay information.
- `impact_report.json` — impact analysis status and results, when the data supports them.

## How impact should be measured

The assignment includes a randomized agent group and holdout group in `replay/arms.csv`. The comparison should use the assigned groups, including users who did not receive an action. Comparing only users who were contacted with everyone else can give a misleading result, because those users may already have been more active.

The outcome report should use the success rules and time windows from the actual goal definitions. If the available data is not enough to calculate a result, the project should say that the result could not be calculated instead of inventing an uplift number.

## What is verified and what still needs the official pack

The automated tests check parts of the code, and GitHub Actions runs those tests when changes are pushed. A passing test run is useful, but it does not by itself prove that the full assignment works with the evaluator's data.

The official data pack is needed to verify all 12 goal definitions, the real injected faults, the simulator interface, and the pilot results. Until those files are run, those parts should be treated as **not yet verified**. Unclear goal rules and goals without measurable success events should be handled according to the real configuration, not guessed.

## Main project files

- `src/stage_agent/engine.py` — makes decisions and checks proposed actions.
- `src/stage_agent/replay.py` — replays the input events and writes reports.
- `src/stage_agent/goal_rules.py` — checks goal eligibility.
- `src/stage_agent/faults.py` — handles injected model faults.
- `src/stage_agent/outcomes.py` — judges outcomes and prepares impact reports.
- `src/stage_agent/state.py` — stores state in SQLite.
- `tests/` — automated tests.
- `ARCHITECTURE.md` — explains the design.
- `KNOWN_LIMITATIONS.md` — lists the current limitations.
- `AI_COLLABORATION.md` — records how AI tools were used.

## Final note

I want this project to make decisions that can be explained and checked, not just produce actions. I will only report results that can be supported by the actual data and replay. Before submission, the full official pack needs to be run, the generated files checked, and any remaining failures documented honestly.
