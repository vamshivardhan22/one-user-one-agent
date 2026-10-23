"""Declarative, fail-closed goal eligibility helpers."""
from __future__ import annotations

def first(row, *keys, default=None):
    for key in keys:
        if isinstance(row, dict) and row.get(key) not in (None, ""):
            return row[key]
    return default

def event_name(event):
    return str(first(event, "event_name", "event_type", "name", default="")).lower()

def evaluate_eligibility(goal, facts, events):
    """Evaluate supported explicit rule fields; unknown rule shapes fail closed.

    Supported fields: requires_event/requires_events, excludes_event/excludes_events,
    subscription_status, dialect, notifications_opt_in, whatsapp_opt_in,
    and eligible (boolean). A missing eligibility rule is not treated as proof.
    """
    rule = first(goal, "eligibility", "eligibility_rule", "eligibility_conditions", default=None)
    if rule is None:
        # Some packs use a direct boolean rather than a nested rule.
        direct = first(goal, "eligible", default=None)
        if direct is True:
            return True, ["Explicit eligible=true on goal definition."]
        return False, ["No supported explicit eligibility rule; abstain rather than infer."]
    if isinstance(rule, bool):
        return (rule, ["Boolean eligibility rule evaluated."])
    if not isinstance(rule, dict):
        return False, ["Unsupported eligibility rule type; fail closed."]
    names = {event_name(event) for event in events}
    reasons = []
    required = first(rule, "requires_events", "required_events", default=[])
    if isinstance(required, str): required = [required]
    one_required = first(rule, "requires_event", "event", default=None)
    if one_required: required = list(required or []) + [one_required]
    for name in required or []:
        if str(name).lower() not in names:
            return False, [f"Required event absent: {name}"]
    excluded = first(rule, "excludes_events", "forbidden_events", default=[])
    if isinstance(excluded, str): excluded = [excluded]
    one_excluded = first(rule, "excludes_event", "forbidden_event", default=None)
    if one_excluded: excluded = list(excluded or []) + [one_excluded]
    for name in excluded or []:
        if str(name).lower() in names:
            return False, [f"Disqualifying event present: {name}"]
    subscription = first(rule, "subscription_status", "subscription", default=None)
    if subscription is not None and str(facts.get("subscription", {}).get("value", "unknown")).lower() != str(subscription).lower():
        return False, ["Subscription status does not satisfy the goal rule."]
    dialect = first(rule, "dialect", "required_dialect", default=None)
    if dialect is not None and str(facts.get("dialect", {}).get("value", "")).lower() != str(dialect).lower():
        return False, ["Dialect does not satisfy the goal rule."]
    for key in ("notifications_opt_in", "whatsapp_opt_in"):
        if key in rule and bool(facts.get(key, {}).get("value")) is not bool(rule[key]):
            return False, [f"{key} does not satisfy the goal rule."]
    if "eligible" in rule and rule["eligible"] is not True:
        return False, ["Goal eligibility is explicitly false or unresolved."]
    known = {"requires_events","required_events","requires_event","event","excludes_events","forbidden_events",
             "excludes_event","forbidden_event","subscription_status","subscription","dialect","required_dialect",
             "notifications_opt_in","whatsapp_opt_in","eligible"}
    unknown = set(rule) - known
    if unknown:
        return False, [f"Unsupported eligibility fields: {', '.join(sorted(unknown))}"]
    return True, ["All supported explicit eligibility conditions passed."]
