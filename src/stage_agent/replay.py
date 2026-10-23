from pathlib import Path
import json
import subprocess
import sys
from .io import read_json, read_jsonl, read_csv, write_json, write_jsonl
from .engine import AgentEngine, deduplicate_events
from .faults import fault_for_trigger, apply_fault_policy
from .outcomes import judge_goals, intention_to_treat, analyze_pilot
from .state import StateStore
from .timeutil import parse_time, iso

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
    control_events = read_jsonl(replay / "control_events.jsonl")
    faults = read_jsonl(replay / "model_faults.jsonl")
    pilot_rows = read_csv(root / "pilot" / "pilot_results.csv")
    return {"events": deduplicate_events(events), "profiles": profiles, "catalogue": catalogue,
            "goals": goals_raw if isinstance(goals_raw, list) else goals_raw.get("goals", []),
            "interventions": interventions if isinstance(interventions, dict) else {},
            "pricing": pricing, "arms": arms, "triggers": triggers, "live_events": live_events,
            "control_events": control_events, "faults": faults, "pilot_rows": pilot_rows}

def percentile(values, quantile):
    if not values:
        return 0
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int((len(ordered) - 1) * quantile))], 3)

def _time(row):
    return parse_time(row.get("deliver_at") or row.get("received_at") or row.get("effective_at") or row.get("timestamp"))

def _event_name(row):
    return str(row.get("event_name", row.get("event_type", row.get("type", row.get("name", ""))))).lower()

def _apply_control(engine, control, pack, audit):
    """Apply explicit, targeted control events without rebuilding all viewers."""
    kind = _event_name(control)
    target_goal = control.get("goal_id", control.get("target_goal_id"))
    if "goal" in kind and ("correct" in kind or "rule" in kind or "update" in kind):
        new_rule = control.get("goal_rule", control.get("rule", control.get("updated_goal")))
        if isinstance(new_rule, dict) and target_goal:
            replaced = False
            for index, goal in enumerate(pack["goals"]):
                if str(goal.get("id", goal.get("goal_id", goal.get("key")))) == str(target_goal):
                    pack["goals"][index] = {**goal, **new_rule}
                    replaced = True
            audit.append({"control_event_id":control.get("event_id"),"type":kind,
                          "target_goal_id":str(target_goal),"applied":replaced,
                          "rule_version":control.get("rule_version", control.get("version")),
                          "note":"Updated the in-memory rule for subsequent decisions; prior decisions remain immutable."})
        else:
            audit.append({"control_event_id":control.get("event_id"),"type":kind,"applied":False,
                          "reason":"Goal rule update lacked a target goal ID or rule payload."})
    elif "withdraw" in kind or "availability" in kind:
        title_id = control.get("title_id", control.get("target_title_id"))
        if title_id is not None:
            changed = 0
            for title in pack["catalogue"]:
                if str(title.get("title_id", title.get("id"))) == str(title_id):
                    title["available_until"] = control.get("received_at", control.get("effective_at", control.get("timestamp")))
                    changed += 1
            audit.append({"control_event_id":control.get("event_id"),"type":kind,"title_id":str(title_id),
                          "catalogue_rows_updated":changed,"applied":changed > 0})
        else:
            audit.append({"control_event_id":control.get("event_id"),"type":kind,"applied":False,
                          "reason":"Withdrawal event had no title ID."})
    else:
        audit.append({"control_event_id":control.get("event_id"),"type":kind,"applied":False,
                      "reason":"Unknown control event; preserved in audit without guessing its meaning."})

def run_replay(root: Path, output: Path, run_simulator: bool = False):
    pack = load_pack(root)
    output.mkdir(parents=True, exist_ok=True)
    store = StateStore(output / "state.sqlite3")
    audit = []
    try:
        engine = AgentEngine(pack, store)
        zero = parse_time("1970-01-01T00:00:00Z")
        timeline = []
        for row in pack["triggers"]:
            timeline.append((_time(row) or zero, 2, row))
        for row in pack["live_events"]:
            timeline.append((_time(row) or zero, 1, row))
        for row in pack["control_events"]:
            timeline.append((_time(row) or zero, 0, row))
        timeline.sort(key=lambda item: (item[0], item[1]))
        decisions, actions = [], []
        for timestamp, kind, row in timeline:
            if kind == 0:
                _apply_control(engine, row, pack, audit)
                continue
            if kind == 1:
                event_id = row.get("event_id", row.get("id"))
                if event_id and any(str(e.get("event_id",e.get("id"))) == str(event_id) for e in pack["events"]):
                    audit.append({"event_id":event_id,"type":"duplicate_live_event","action":"deduplicated"})
                    continue
                pack["events"].append(row)
                continue
            # Stale offline-buffered app opens are explicitly abstained from.
            occurred = parse_time(row.get("occurred_at", row.get("sent_at")))
            received = parse_time(row.get("received_at", row.get("deliver_at")))
            age = (received - occurred).total_seconds() if received and occurred else None
            if age is not None and age > engine.max_trigger_age_s:
                decision = {"decision_id":"D-STALE-"+str(row.get("event_id",row.get("id","unknown"))),
                    "viewer_id":str(row.get("viewer_id",row.get("user_id","UNKNOWN"))),
                    "trigger":{"event_id":row.get("event_id",row.get("id")),"received_at":iso(received),"event_age_s":age},
                    "goal":None,"action":"NO_ACTION","action_payload":None,
                    "no_action_reason":"Stale/offline-buffered trigger exceeded the live-session freshness limit.",
                    "confidence":0.0,"confidence_reason":"Stale trigger; no intervention proposed.",
                    "evidence":[],"assumptions":["received_at is trusted; phone clock is not."],
                    "checks":{"passed":[],"failed":[{"check":"trigger_freshness","reason":f"Trigger age {int(age)}s exceeds {engine.max_trigger_age_s}s."}]},
                    "decided_in_ms":0.0,"model_calls":0,"tool_calls":0,"fallback_used":False,
                    "status":"ABSTAINED","rule_version":"1.0.0"}
            else:
                decision = apply_fault_policy(engine,row,fault_for_trigger(pack["faults"],row))
            decisions.append(decision)
            if decision["action"] != "NO_ACTION":
                actions.append({"event_id":decision.get("trigger",{}).get("event_id"),
                    "viewer_id":decision["viewer_id"],"action":decision["action"],
                    "payload":decision.get("action_payload"),"status":decision["status"],
                    "deliver_at":iso(timestamp),"published_at":iso(timestamp)})
        write_jsonl(output / "decisions.jsonl", decisions)
        write_jsonl(output / "actions.jsonl", actions)
        write_jsonl(output / "replay_audit.jsonl", audit)
        # Optional simulator execution is opt-in because its argument contract
        # belongs to the supplied simulator. We use the documented default CLI.
        simulator_script = root / "simulator" / "simulate_outcomes.py"
        if run_simulator and simulator_script.exists():
            completed = subprocess.run([sys.executable,str(simulator_script),"--actions",str(output/"actions.jsonl"),
                "--out",str(output)],capture_output=True,text=True,timeout=300)
            write_json(output / "simulator_execution.json",{"returncode":completed.returncode,
                "stdout":completed.stdout[-4000:],"stderr":completed.stderr[-4000:]})
        outcome_path = output / "outcome_events.jsonl"
        outcome_events = read_jsonl(outcome_path) if outcome_path.exists() else []
        # If the simulator's report names a different output path, the adapter
        # is explicit rather than treating empty output as zero success.
        replay_end = max((iso(item[0]) for item in timeline), default=None)
        judgments = judge_goals(decisions, pack["events"] + pack["live_events"] + outcome_events,
                                pack["arms"], pack["goals"], replay_end)
        write_jsonl(output / "outcomes.jsonl", judgments)
        impact = intention_to_treat(judgments,pack["arms"])
        pilot = analyze_pilot(pack["pilot_rows"])
        write_json(output / "impact_report.json",{"status":"COMPUTED" if impact["goals"] else "NOT_COMPUTED",
            "intention_to_treat":impact,"pilot_reanalysis":pilot,
            "caveat":"Impact is meaningful only if the simulator was actually run and produced outcome_events.jsonl. Empty/missing simulator outcomes are not evidence of zero uplift."})
        for row in store.db.execute("SELECT viewer_id,state_json FROM viewers").fetchall():
            safe_name = "".join(ch for ch in str(row["viewer_id"]) if ch.isalnum() or ch in "-_")
            if safe_name:
                write_json(output / "viewer_state" / f"{safe_name}.json",json.loads(row["state_json"]))
        durations=[row.get("decided_in_ms",0) for row in decisions]
        report={"trigger_count":len(pack["triggers"]),"decision_count":len(decisions),
            "action_count":len(actions),"p50_ms":percentile(durations,.50),"p95_ms":percentile(durations,.95),
            "max_ms":max(durations,default=0),"within_60_seconds":all(value<=60000 for value in durations),
            "stale_trigger_count":sum(row.get("no_action_reason","").startswith("Stale/") for row in decisions),
            "fault_count":sum("fault_injected" in row for row in decisions),
            "control_events_seen":len(pack["control_events"]),"control_events_applied":sum(bool(row.get("applied")) for row in audit),
            "note":"Local compute timing only; published_at is a replay timestamp estimate, not a provider delivery receipt."}
        write_json(output / "latency_report.json",report)
        return report
    finally:
        store.close()
