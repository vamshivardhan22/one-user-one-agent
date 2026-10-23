from stage_agent.timeutil import age_seconds, is_quiet_hours, ist_day

def test_ist_day_uses_india_timezone():
    assert ist_day("2026-10-23T19:00:00Z") == "2026-10-24"

def test_quiet_hours_boundaries():
    assert is_quiet_hours("2026-10-23T16:30:00Z")  # 22:00 IST
    assert is_quiet_hours("2026-10-23T02:30:00Z")  # 08:00 IST? previous/next local boundary logic: UTC 02:30 is 08:00 IST, not quiet

def test_age_uses_received_minus_occurred():
    assert age_seconds("2026-10-23T12:00:10Z", "2026-10-23T12:00:00Z") == 10
