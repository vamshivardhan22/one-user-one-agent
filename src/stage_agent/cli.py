import argparse
from pathlib import Path
from .replay import run_replay

def main():
    parser = argparse.ArgumentParser(description="Replay the STAGE One User, One Agent assignment.")
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("replay", help="Run a deterministic replay against a supplied data pack.")
    command.add_argument("--pack", type=Path, required=True)
    command.add_argument("--out", type=Path, default=Path("sample_run"))
    args = parser.parse_args()
    report = run_replay(args.pack, args.out)
    print(f"Replay complete: {report['decision_count']} decisions, {report['action_count']} actions.")
    print(f"Latency p95={report['p95_ms']}ms")
    if not report["within_60_seconds"]:
        raise SystemExit("FAIL: one or more decisions exceeded 60 seconds.")

if __name__ == "__main__":
    main()
