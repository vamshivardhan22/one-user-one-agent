from stage_agent.goal_rules import evaluate_eligibility

def test_required_and_excluded_events_are_explicit():
    facts={"subscription":{"value":"free"},"dialect":{"value":"d1"}}
    goal={"eligibility":{"requires_event":"signup_completed","excludes_event":"purchase"}}
    assert evaluate_eligibility(goal,facts,[{"event_name":"signup_completed"}])[0]
    assert not evaluate_eligibility(goal,facts,[{"event_name":"signup_completed"},{"event_name":"purchase"}])[0]

def test_unknown_rule_fields_fail_closed():
    assert not evaluate_eligibility({"eligibility":{"magic_condition":"yes"}},{},[])[0]

def test_missing_rule_does_not_assume_eligible():
    assert not evaluate_eligibility({"id":"goal_without_rule"},{},[])[0]
