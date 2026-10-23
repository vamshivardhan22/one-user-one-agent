"""Deterministic replay fault matching and safe fallback helpers."""
from __future__ import annotations

def fault_for_trigger(faults, trigger):
    event_id = str(trigger.get("event_id", trigger.get("id", "")))
    viewer_id = str(trigger.get("viewer_id", trigger.get("user_id", "")))
    for fault in faults:
        target_event = fault.get("event_id", fault.get("trigger_event_id"))
        target_viewer = fault.get("viewer_id", fault.get("user_id"))
        if target_event is not None and str(target_event) == event_id:
            return fault
        if target_viewer is not None and str(target_viewer) == viewer_id and target_event is None:
            return fault
    return None

def fault_kind(fault):
    if not fault:
        return None
    return str(fault.get("fault_type", fault.get("type", fault.get("fault", "unknown")))).lower()

def apply_fault_policy(engine, trigger, fault):
    """Route injected model faults to the deterministic safe path.

    This implementation intentionally does not fabricate a model response.
    A malformed/timed-out model is represented in the decision audit and the
    deterministic planner is used with model_calls bounded to zero.
    """
    if not fault:
        return engine.decide(trigger)
    kind = fault_kind(fault)
    if any(token in kind for token in ("timeout", "malformed", "invalid_json", "provider_down", "model_error")):
        decision = engine.decide(trigger)
        decision["fallback_used"] = True
        decision["fault_injected"] = {"type": kind, "handled_by": "deterministic_safe_path"}
        decision["assumptions"].append("Injected model fault was handled without trusting model output.")
        if decision["action"] != "NO_ACTION":
            # Without evidence that a model-derived plan was needed, preserve
            # deterministic actions; all still pass through independent checks.
            decision["checks"]["passed"].append("fault_fallback")
        else:
            decision["no_action_reason"] = decision.get("no_action_reason") or "Safe fallback abstained during injected fault."
        return decision
    if any(token in kind for token in ("store_down", "database_down", "state_store_error")):
        # State cannot be trusted, so no intervention is safe.
        return {
            "decision_id": "D-FAULT-" + str(trigger.get("event_id", trigger.get("id", "unknown"))),
            "viewer_id": str(trigger.get("viewer_id", trigger.get("user_id", "UNKNOWN"))),
            "trigger": {"event_id": trigger.get("event_id", trigger.get("id")), "received_at": trigger.get("received_at")},
            "goal": None, "action": "NO_ACTION", "action_payload": None,
            "no_action_reason": "State store unavailable; fail-closed fallback.",
            "confidence": 0.0, "confidence_reason": "State unavailable; no decision confidence is claimed.",
            "evidence": [], "assumptions": ["State store unavailable during injected fault."],
            "checks": {"passed": [], "failed": [{"check":"state_store","reason":"Injected store failure; action blocked."}]},
            "decided_in_ms": 0.0, "model_calls": 0, "tool_calls": 0,
            "fallback_used": True, "status": "ABSTAINED", "rule_version": "1.0.0",
            "fault_injected": {"type": kind, "handled_by": "fail_closed"}
        }
    return engine.decide(trigger)
