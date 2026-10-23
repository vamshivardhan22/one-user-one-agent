from pathlib import Path
from .io import read_json, read_jsonl, read_csv, write_json, write_jsonl
from .engine import AgentEngine, deduplicate_events
from .state import StateStore
from .timeutil import parse_time
import json

def load_pack(root: Path):
    data, config, replay = root / "data", root / "config", root / "replay"
    events = read_jsonl(data / "events.jsonl")
    profiles = read_csv(data / "profiles_snapshot.csv")
    catalogue = read_csv(data / "catalogue.csv")
    goals_raw = read_json(config / "goals.json", [])
    interventions = read_json(config / "interventions.json", {})
    pricing = read_json(config / "pricing.json", {})
    arms_rows = read_csv(replay / "arms.csv")
    arms = {str(row.get("viewer_id", row.get("user_id"))): str(row.get("arm", "")).lower()
            for row in arms_rows if row.get("viewer_id", row.get("user_id"))}
    triggers = read_jsonl(replay / "triggers.jsonl") or read_jsonl(replay / "app_open_triggers.jsonl")
    live_events = read_jsonl(replay / "live_events.jsonl")
    faults = read_jsonl(replay / "model_faults.jsonl")
    return {"events": deduplicate_events(events), "profiles": profiles, "catalogue": catalogue,
            "goals": goals_raw if isinstance(goals_raw, list) else goals_raw.get("goals", []),
            "interventions": interventions if isinstance(interventions, dict) else {},
            "pricing": pricing, "arms": arms, "triggers": triggers, "live_events": live_events, "faults": faults}

def percentile(values, quantile):
    if not values:
        return 0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * quantile))], 3)

def run_replay(root: Path, output: Path):
    pack = load_pack(root)
    output.mkdir(parents=True, exist_ok=True)
    store = StateStore(output / "state.sqlite3")
    try:
        engine = AgentEngine(pack, store)
        zero = parse_time("1970-01-01T00:00:00Z")
        triggers = sorted(pack["triggers"], key=lambda row: parse_time(row.get("deliver_at") or row.get("received_at")) or zero)
        decisions, actions = [], []
        for trigger in triggers:
            decision = engine.decide(trigger)
            decisions.append(decision)
            if decision["action"] != "NO_ACTION":
                actions.append({"event_id": decision["trigger"]["event_id"], "viewer_id": decision["viewer_id"],
                                "action": decision["action"], "payload": decision["action_payload"], "status": decision["status"]})
        write_jsonl(output / "decisions.jsonl", decisions)
        write_jsonl(output / "actions.jsonl", actions)
        write_jsonl(output / "outcomes.jsonl", [])
        for row in store.db.execute("SELECT viewer_id,state_json FROM viewers").fetchall():
            write_json(output / "viewer_state" / f"{row['viewer_id']}.json", json.loads(row["state_json"]))
        durations = [row["decided_in_ms"] for row in decisions]
        report = {"trigger_count": len(triggers), "decision_count": len(decisions), "action_count": len(actions),
                  "p50_ms": percentile(durations, .50), "p95_ms": percentile(durations, .95),
                  "max_ms": max(durations, default=0), "within_60_seconds": all(value <= 60000 for value in durations),
                  "note": "Local compute timing only; external publication and official simulator timings are not included."}
        write_json(output / "latency_report.json", report)
        write_json(output / "impact_report.json", {"status": "NOT_COMPUTED",
            "reason": "Run the provided simulator and measure outcomes before claiming impact.",
            "comparison": "Intention-to-treat: all agent-arm viewers versus all holdout-arm viewers."})
        return report
    finally:
        store.close()
