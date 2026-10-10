"""SQLite audit, bounded memory and transactional lifetime API budget."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY, created TEXT NOT NULL, status TEXT NOT NULL,
            result TEXT);
        CREATE TABLE IF NOT EXISTS events (
            sequence INTEGER PRIMARY KEY, run_id TEXT NOT NULL,
            created TEXT NOT NULL, role TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS costs (
            id TEXT PRIMARY KEY, run_id TEXT NOT NULL, role TEXT NOT NULL,
            created TEXT NOT NULL, model TEXT NOT NULL, charged TEXT NOT NULL,
            status TEXT NOT NULL, usage TEXT, response_id TEXT);
        """)
        if "mode" not in {r[1] for r in self.db.execute("PRAGMA table_info(runs)")}:
            with self.db:
                self.db.execute("ALTER TABLE runs ADD COLUMN mode TEXT NOT NULL DEFAULT 'ai'")

    def close(self):
        self.db.close()

    def start(self, mode="ai"):
        run = str(uuid.uuid4())
        with self.db:
            self.db.execute("INSERT INTO runs(id,created,status,result,mode) VALUES (?, ?, 'running', NULL, ?)",
                            (run, now(), mode))
        return run

    def event(self, run, role, payload):
        with self.db:
            self.db.execute("INSERT INTO events(run_id,created,role,payload) VALUES(?,?,?,?)",
                            (run, now(), role, json.dumps(payload, allow_nan=False)))

    def finish(self, run, status, result):
        with self.db:
            self.db.execute("UPDATE runs SET status=?,result=? WHERE id=?",
                            (status, json.dumps(result, allow_nan=False), run))

    def memory(self):
        rows = self.db.execute("SELECT id,result FROM runs WHERE status='completed' AND mode='ai' "
                               "ORDER BY created DESC LIMIT 3").fetchall()
        return [{"run_id": r[0], "result": json.loads(r[1])} for r in rows]

    def reserve(self, run, role, model, amount, budget):
        ticket = str(uuid.uuid4())
        self.db.execute("BEGIN IMMEDIATE")
        try:
            total = sum((Decimal(r[0]) for r in self.db.execute("SELECT charged FROM costs")), Decimal(0))
            if total + amount > budget:
                raise ValueError("Lifetime API budget exhausted")
            self.db.execute("INSERT INTO costs VALUES(?,?,?,?,?,?, 'reserved',NULL,NULL)",
                            (ticket, run, role, now(), model, str(amount)))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return ticket

    def settle(self, ticket, amount, usage, response_id):
        with self.db:
            self.db.execute("UPDATE costs SET charged=?,status='reported',usage=?,response_id=? WHERE id=?",
                            (str(amount), json.dumps(usage), response_id, ticket))

    def costs(self):
        rows = self.db.execute("SELECT charged,status FROM costs").fetchall()
        return {"estimated_or_reserved_usd": str(sum((Decimal(r[0]) for r in rows), Decimal(0))),
                "calls": len(rows), "unsettled_calls": sum(r[1] == "reserved" for r in rows)}
