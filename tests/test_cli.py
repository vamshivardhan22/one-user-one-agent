import json
from pathlib import Path
from stage_agent.replay import run_replay

def test_empty_pack_produces_auditable_reports(tmp_path: Path):
    pack = tmp_path / "pack"
    (pack / "data").mkdir(parents=True)
    (pack / "config").mkdir()
    (pack / "replay").mkdir()
    (pack / "data" / "events.jsonl").write_text("", encoding="utf-8")
    (pack / "data" / "profiles_snapshot.csv").write_text("viewer_id\n", encoding="utf-8")
    (pack / "data" / "catalogue.csv").write_text("title_id,content_slug,dialect,title\n", encoding="utf-8")
    (pack / "config" / "goals.json").write_text("[]", encoding="utf-8")
    (pack / "config" / "interventions.json").write_text("{}", encoding="utf-8")
    (pack / "config" / "pricing.json").write_text("{}", encoding="utf-8")
    (pack / "replay" / "arms.csv").write_text("viewer_id,arm\n", encoding="utf-8")
    (pack / "replay" / "triggers.jsonl").write_text("", encoding="utf-8")
    out = tmp_path / "out"
    report = run_replay(pack, out)
    assert report["decision_count"] == 0
    assert (out / "decisions.jsonl").exists()
    assert (out / "latency_report.json").exists()
    impact = json.loads((out / "impact_report.json").read_text(encoding="utf-8"))
    assert impact["status"] == "NOT_COMPUTED"
