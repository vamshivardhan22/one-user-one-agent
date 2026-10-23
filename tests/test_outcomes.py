from stage_agent.outcomes import judge_goals, intention_to_treat, analyze_pilot

def test_goal_success_only_counts_inside_deadline():
    decisions=[{"decision_id":"d1","viewer_id":"u1","trigger":{"received_at":"2026-01-01T00:00:00Z"},
                "goal":{"id":"g1","deadline":"2026-01-04T00:00:00Z","success_signal":"episode_completed"}}]
    events=[{"event_id":"e1","viewer_id":"u1","event_name":"episode_completed","received_at":"2026-01-03T00:00:00Z"}]
    result=judge_goals(decisions,events,{"u1":"agent"},[{"id":"g1","success_event":"episode_completed"}],"2026-01-05T00:00:00Z")
    assert result[0]["status"]=="succeeded"

def test_goal_failure_requires_elapsed_window():
    decisions=[{"decision_id":"d1","viewer_id":"u1","trigger":{"received_at":"2026-01-01T00:00:00Z"},
                "goal":{"id":"g1","deadline":"2026-01-04T00:00:00Z","success_signal":"episode_completed"}}]
    result=judge_goals(decisions,[],{"u1":"agent"},[{"id":"g1","success_event":"episode_completed"}],"2026-01-02T00:00:00Z")
    assert result[0]["status"]=="inconclusive"

def test_itt_uses_arm_not_served_flag():
    judgments=[
      {"viewer_id":"a1","goal_id":"g1","status":"succeeded"},
      {"viewer_id":"a2","goal_id":"g1","status":"failed"},
      {"viewer_id":"h1","goal_id":"g1","status":"failed"},
      {"viewer_id":"h2","goal_id":"g1","status":"failed"}]
    result=intention_to_treat(judgments,{"a1":"agent","a2":"agent","h1":"holdout","h2":"holdout"})
    assert result["goals"]["g1"]["agent"]["rate"]==0.5
    assert result["goals"]["g1"]["holdout"]["rate"]==0.0

def test_pilot_missing_columns_is_honest():
    assert analyze_pilot([{"served":True,"converted":True}])["status"]=="NOT_COMPUTED"
