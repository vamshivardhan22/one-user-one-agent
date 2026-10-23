"""Goal outcome attribution and randomized-arm impact analysis.

This module is deliberately schema-tolerant because replay packs may encode
outcome names and timestamps under slightly different field names. It never
infers success from an action being served; only observed outcome events count.
"""
from __future__ import annotations
import math
from collections import defaultdict
from datetime import timedelta
from .timeutil import parse_time, iso

def _first(row, *keys, default=None):
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    return default

def _event_name(row):
    return str(_first(row, "event_name", "event_type", "name", "type", default="")).strip().lower()

def _viewer(row):
    value = _first(row, "viewer_id", "user_id", "viewer", default=None)
    return str(value) if value is not None else None

def _event_time(row):
    # Server receive time is authoritative; phone event time is only fallback.
    return parse_time(_first(row, "received_at", "deliver_at", "published_at", "occurred_at", "sent_at", "timestamp"))

def _goal_id(goal):
    value = _first(goal, "id", "goal_id", "key", default="unknown_goal")
    return str(value)

def judge_goals(decisions, events, arms, goals, replay_end=None):
    """Judge each assigned goal as succeeded, failed, or inconclusive.

    Success is attributable only if the configured success event occurs from
    the decision/goal start through its deadline. A missing signal or an
    unelapsed window is inconclusive rather than a fabricated failure.
    """
    by_viewer = defaultdict(list)
    for event in events:
        viewer = _viewer(event)
        if viewer:
            by_viewer[viewer].append(event)
    definitions = {_goal_id(goal): goal for goal in goals}
    judgments = []
    end_time = parse_time(replay_end)
    for decision in decisions:
        viewer = str(decision.get("viewer_id", ""))
        goal = decision.get("goal")
        if not isinstance(goal, dict):
            continue
        gid = str(_first(goal, "id", "goal_id", default="unknown_goal"))
        definition = definitions.get(gid, {})
        signal = _first(goal, "success_signal", default=None) or _first(definition, "success_event", "success_signal", "success_event_name")
        start = parse_time(_first(goal, "started_at", "start_at")) or parse_time(decision.get("trigger", {}).get("received_at"))
        deadline = parse_time(goal.get("deadline"))
        if not signal or not start or not deadline:
            status, matched = "inconclusive", None
            reason = "Missing measurable success signal, start time, or deadline."
        else:
            matched = None
            for event in by_viewer.get(viewer, []):
                timestamp = _event_time(event)
                if _event_name(event) == str(signal).lower() and timestamp and start <= timestamp <= deadline:
                    matched = event
                    break
            if matched:
                status, reason = "succeeded", "Configured success event occurred inside the goal window."
            elif end_time and end_time >= deadline:
                status, reason = "failed", "Goal window elapsed without the configured success event."
            else:
                status, reason = "inconclusive", "Goal window has not elapsed; outcome is not yet knowable."
        judgments.append({
            "viewer_id": viewer, "decision_id": decision.get("decision_id"),
            "goal_id": gid, "success_signal": signal, "started_at": iso(start),
            "deadline": iso(deadline), "status": status,
            "matched_event_id": _first(matched, "event_id", "id") if matched else None,
            "reason": reason, "arm": str(arms.get(viewer, "unknown")).lower()
        })
    return judgments

def _wilson(successes, total, z=1.959963984540054):
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    margin = z * math.sqrt((p*(1-p) + z*z/(4*total))/total) / denom
    return [max(0.0, center-margin), min(1.0, center+margin)]

def _rate(rows):
    known = [r for r in rows if r.get("status") in {"succeeded", "failed"}]
    success = sum(r["status"] == "succeeded" for r in known)
    total = len(known)
    return {"successes": success, "known_outcomes": total, "inconclusive": len(rows)-total,
            "rate": success/total if total else None, "ci95_wilson": _wilson(success,total)}

def intention_to_treat(judgments, arms):
    """Compare all randomized arm users, not served vs unserved.

    Each viewer contributes at most one binary goal outcome per goal ID: any
    success in the observation window counts as success; unresolved goals stay
    inconclusive and are excluded from the known-outcome rate but reported.
    """
    viewer_goal = {}
    for row in judgments:
        key = (str(row.get("viewer_id")), str(row.get("goal_id")))
        prior = viewer_goal.get(key)
        if prior is None or (prior.get("status") != "succeeded" and row.get("status") == "succeeded"):
            viewer_goal[key] = row
    all_goal_ids = sorted({key[1] for key in viewer_goal})
    reports = {}
    for gid in all_goal_ids:
        rows = [row for (viewer,g),row in viewer_goal.items() if g == gid]
        agent_ids = {str(v) for v,a in arms.items() if str(a).lower() in {"agent","treatment","test"}}
        holdout_ids = {str(v) for v,a in arms.items() if str(a).lower() in {"holdout","control"}}
        agent_rows = [row for row in rows if row["viewer_id"] in agent_ids]
        holdout_rows = [row for row in rows if row["viewer_id"] in holdout_ids]
        agent, holdout = _rate(agent_rows), _rate(holdout_rows)
        diff = agent["rate"] - holdout["rate"] if agent["rate"] is not None and holdout["rate"] is not None else None
        reports[gid] = {"agent":agent,"holdout":holdout,"risk_difference":diff,
                        "interpretation":"Intention-to-treat; arm membership comes from randomized assignment, not whether an action was served."}
    return {"method":"intention_to_treat", "goals":reports,
            "warning":"A simple difference is descriptive; use a bootstrap or a two-proportion interval for a formal risk-difference confidence interval."}

def analyze_pilot(rows):
    """Calculate randomized-arm conversion when pilot rows include arm and outcome.

    Returns an explicit unavailable status if the required randomized columns
    are absent. Does not use the biased served-versus-unserved comparison.
    """
    arm_key = next((key for key in ("arm","randomized_arm","experiment_arm") if rows and key in rows[0]), None)
    outcome_key = next((key for key in ("converted","success","goal_succeeded","outcome") if rows and key in rows[0]), None)
    if not rows or not arm_key or not outcome_key:
        return {"status":"NOT_COMPUTED","reason":"Pilot file does not expose recognizable randomized-arm and binary-outcome columns; inspect the schema and map explicitly."}
    groups = {"agent":[],"holdout":[]}
    for row in rows:
        arm = str(row.get(arm_key,"")).lower()
        if arm in {"agent","treatment","test"}: group="agent"
        elif arm in {"holdout","control"}: group="holdout"
        else: continue
        raw = str(row.get(outcome_key,"")).lower()
        value = raw in {"1","true","yes","success","succeeded","converted"}
        groups[group].append(value)
    def stats(values):
        successes=sum(values); n=len(values)
        return {"successes":successes,"total":n,"rate":successes/n if n else None,"ci95_wilson":_wilson(successes,n)}
    a,h=stats(groups["agent"]),stats(groups["holdout"])
    return {"status":"COMPUTED" if a["total"] and h["total"] else "NOT_COMPUTED",
            "method":"randomized-arm comparison", "agent":a,"holdout":h,
            "risk_difference":a["rate"]-h["rate"] if a["rate"] is not None and h["rate"] is not None else None,
            "note":"No served-versus-unserved estimate is produced."}
