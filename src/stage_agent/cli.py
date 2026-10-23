import argparse
from pathlib import Path
from .replay import run_replay

def main():
    parser = argparse.ArgumentParser(description="Replay the STAGE One User, One Agent assignment.")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("replay", help="Run a deterministic replay against a supplied data pack.")
    command.add_argument("--pack", type=Path, required=True)
    command.add_argument("--out", type=Path, default=Path("sample_run"))
    command.add_argument("--run-simulator", action="store_true",
                         help="Run simulator/simulate_outcomes.py using the documented --actions/--out interface.")
    args = parser.parse_args()
    report = run_replay(args.pack, args.out, run_simulator=args.run_simulator)
    print(f"Replay complete: {report['decision_count']} decisions, {report['action_count']} actions.")
    print(f"Latency p95={report['p95_ms']}ms; stale triggers={report['stale_trigger_count']}; faults={report['fault_count']}.")
    if not report["within_60_seconds"]:
        raise SystemExit("FAIL: one or more decisions exceeded 60 seconds.")
    if args.run_simulator and report["action_count"] and report.get("simulator_execution") == 0:
        raise SystemExit("FAIL: simulator did not produce a successful execution record.")

if __name__ == "__main__":
    main()
