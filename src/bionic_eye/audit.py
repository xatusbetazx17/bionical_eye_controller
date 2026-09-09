"""Bounded local diagnostic history, without image or microphone contents."""

import json
import sqlite3
import threading


class AuditLog:
    def __init__(self, path=":memory:"):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, "
                         "time TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')), "
                         "operation TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL)")
        self._db.commit()

    def record(self, operation, outcome, detail=None):
        with self._lock, self._db:
            self._db.execute("INSERT INTO events(operation,outcome,detail) VALUES(?,?,?)",
                             (operation, outcome, json.dumps(detail or {}, allow_nan=False)))
            self._db.execute("DELETE FROM events WHERE id NOT IN "
                             "(SELECT id FROM events ORDER BY id DESC LIMIT 1000)")

    def recent(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("History limit must be between 1 and 1000.")
        with self._lock:
            rows = self._db.execute("SELECT time,operation,outcome,detail FROM events "
                                    "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(time=t, operation=o, outcome=s, detail=json.loads(d)) for t, o, s, d in rows]

    def close(self):
        with self._lock:
            self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
