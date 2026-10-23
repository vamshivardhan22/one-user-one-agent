import tempfile
from pathlib import Path
from stage_agent.engine import AgentEngine, deduplicate_events
from stage_agent.state import StateStore

def setup_engine(pack):
    temp = tempfile.TemporaryDirectory()
    store = StateStore(Path(temp.name) / "state.sqlite3")
    return temp, store, AgentEngine(pack, store)

def test_duplicate_trigger_is_idempotent():
    pack = {"events": [], "profiles": [], "catalogue": [], "goals": [], "interventions": {}, "arms": {}}
    temp, store, engine = setup_engine(pack)
    trigger = {"event_id":"e1","viewer_id":"u1","event_name":"app_open","received_at":"2026-10-23T12:00:00Z","occurred_at":"2026-10-23T11:59:59Z","app_dialect":"d1"}
    first = engine.decide(trigger)
    assert engine.decide(trigger) == first
    store.close()
    temp.cleanup()

def test_holdout_fails_closed():
    pack = {"events": [], "profiles": [], "catalogue": [
        {"title_id":"t1","content_slug":"s1","dialect":"d1","title":"A"},
        {"title_id":"t2","content_slug":"s2","dialect":"d1","title":"B"},
        {"title_id":"t3","content_slug":"s3","dialect":"d1","title":"C"}],
        "goals":[{"id":"g1","success_event":"episode_completed","window_days":3}],
        "interventions": {}, "arms":{"u1":"holdout"}}
    temp, store, engine = setup_engine(pack)
    result = engine.decide({"event_id":"e1","viewer_id":"u1","event_name":"app_open","received_at":"2026-10-23T12:00:00Z","occurred_at":"2026-10-23T11:59:59Z","app_dialect":"d1"})
    assert result["action"] == "NO_ACTION"
    assert any(row.get("check") == "holdout" for row in result["checks"]["failed"])
    store.close()
    temp.cleanup()

def test_event_deduplication():
    rows = [{"event_id":"x","value":1},{"event_id":"x","value":2},{"event_id":"y","value":3}]
    assert deduplicate_events(rows) == [{"event_id":"x","value":1},{"event_id":"y","value":3}]

def test_dialect_conflict_prefers_app_setting():
    pack = {"events": [], "profiles":[{"viewer_id":"u1","preferred_dialect":"d2"}], "catalogue": [], "goals": [], "interventions": {}, "arms": {}}
    temp, store, engine = setup_engine(pack)
    facts, conflicts, _ = engine.resolve_facts("u1", {"viewer_id":"u1","app_dialect":"d1","received_at":"2026-10-23T12:00:00Z"})
    assert facts["dialect"]["value"] == "d1"
    assert conflicts
    store.close()
    temp.cleanup()
