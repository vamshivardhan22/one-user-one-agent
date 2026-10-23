from __future__ import annotations
import json
import sqlite3
from pathlib import Path

class StateStore:
    """Durable viewer state with idempotency ledgers."""
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS viewers(viewer_id TEXT PRIMARY KEY, state_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS processed(event_id TEXT PRIMARY KEY, decision_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS actions(idempotency_key TEXT PRIMARY KEY, viewer_id TEXT, channel TEXT, action_json TEXT, ist_day TEXT);
        CREATE TABLE IF NOT EXISTS outcomes(outcome_id TEXT PRIMARY KEY, viewer_id TEXT, outcome_json TEXT NOT NULL);
        """)
        self.db.commit()

    def get_viewer(self, viewer_id: str) -> dict:
        row = self.db.execute("SELECT state_json FROM viewers WHERE viewer_id=?", (viewer_id,)).fetchone()
        return json.loads(row["state_json"]) if row else {"viewer_id": viewer_id, "facts": {}, "active_goal": None, "history": []}

    def save_viewer(self, viewer_id: str, state: dict):
        with self.db:
            self.db.execute(
                "INSERT INTO viewers(viewer_id,state_json) VALUES(?,?) "
                "ON CONFLICT(viewer_id) DO UPDATE SET state_json=excluded.state_json",
                (viewer_id, json.dumps(state, ensure_ascii=False, default=str)))

    def get_decision(self, event_id: str):
        row = self.db.execute("SELECT decision_json FROM processed WHERE event_id=?", (event_id,)).fetchone()
        return json.loads(row["decision_json"]) if row else None

    def save_decision(self, event_id: str, decision: dict):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO processed(event_id,decision_json) VALUES(?,?)",
                            (event_id, json.dumps(decision, ensure_ascii=False, default=str)))

    def prior_message_today(self, viewer_id: str, day: str) -> bool:
        row = self.db.execute("SELECT 1 FROM actions WHERE viewer_id=? AND ist_day=? AND channel IN ('PUSH','WHATSAPP') LIMIT 1",
                              (viewer_id, day)).fetchone()
        return row is not None

    def save_action(self, key: str, viewer_id: str, channel: str, action: dict, day: str):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO actions(idempotency_key,viewer_id,channel,action_json,ist_day) VALUES(?,?,?,?,?)",
                            (key, viewer_id, channel, json.dumps(action, ensure_ascii=False, default=str), day))

    def save_outcome(self, outcome_id: str, viewer_id: str, outcome: dict):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO outcomes(outcome_id,viewer_id,outcome_json) VALUES(?,?,?)",
                            (outcome_id, viewer_id, json.dumps(outcome, ensure_ascii=False, default=str)))

    def close(self):
        self.db.close()
