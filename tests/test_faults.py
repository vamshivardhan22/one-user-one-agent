from stage_agent.faults import fault_for_trigger, fault_kind

def test_fault_matches_exact_trigger():
    trigger={"event_id":"e1","viewer_id":"u1"}
    faults=[{"event_id":"e2","type":"timeout"},{"event_id":"e1","type":"invalid_json"}]
    assert fault_kind(fault_for_trigger(faults,trigger))=="invalid_json"

def test_fault_can_match_viewer_when_no_event_id():
    trigger={"event_id":"e1","viewer_id":"u1"}
    assert fault_kind(fault_for_trigger([{"viewer_id":"u1","type":"timeout"}],trigger))=="timeout"
