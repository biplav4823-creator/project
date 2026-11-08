"""CP-54: durable recurring-job scheduler (no daemon; caller drives `run_due`).

SQLite-backed. Clock is injected (epoch seconds) so behaviour is deterministic.
A job that fails 3 times consecutively is disabled (circuit breaker).
Missed intervals are not replayed: next_run = now + interval.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
MAX_CONSECUTIVE_FAILURES = 3
MIN_INTERVAL = 1


class Scheduler:
    def __init__(self, path: str = ":memory:", clock: Callable[[], float] = time.time):
        self._clock = clock
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                interval_seconds INTEGER NOT NULL,
                next_run REAL NOT NULL,
                last_run REAL,
                runs INTEGER NOT NULL DEFAULT 0,
                max_runs INTEGER,
                failures INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                payload TEXT NOT NULL DEFAULT '{}'
            )"""
        )
        self._db.commit()

    def add(
        self,
        name: str,
        interval_seconds: int,
        payload: Optional[Dict[str, Any]] = None,
        max_runs: Optional[int] = None,
        start_at: Optional[float] = None,
    ) -> int:
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise ValueError("invalid name")
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int) \
                or interval_seconds < MIN_INTERVAL:
            raise ValueError("interval_seconds must be an integer >= 1")
        if max_runs is not None and (isinstance(max_runs, bool)
                                     or not isinstance(max_runs, int) or max_runs < 1):
            raise ValueError("max_runs must be a positive integer")
        text = json.dumps(payload or {})
        if len(text) > 10000:
            raise ValueError("payload too large")
        first = self._clock() + interval_seconds if start_at is None else float(start_at)
        try:
            cur = self._db.execute(
                "INSERT INTO schedule(name, interval_seconds, next_run, max_runs, payload)"
                " VALUES (?,?,?,?,?)",
                (name, interval_seconds, first, max_runs, text),
            )
        except sqlite3.IntegrityError:
            raise ValueError("name already scheduled") from None
        self._db.commit()
        return int(cur.lastrowid)

    def due(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        now = self._clock() if now is None else now
        rows = self._db.execute(
            "SELECT * FROM schedule WHERE enabled = 1 AND next_run <= ? ORDER BY next_run, id",
            (now,),
        ).fetchall()
        return [self._row(r) for r in rows]

    def run_due(self, handler: Callable[[Dict[str, Any]], Any], now: Optional[float] = None):
        now = self._clock() if now is None else now
        summary = {"ran": 0, "failed": 0, "disabled": []}
        for job in self.due(now):
            try:
                handler(job)
                ok = True
            except Exception:
                ok = False
            runs = job["runs"] + 1
            failures = 0 if ok else job["failures"] + 1
            enabled = 1
            if not ok and failures >= MAX_CONSECUTIVE_FAILURES:
                enabled = 0
            if job["max_runs"] is not None and runs >= job["max_runs"]:
                enabled = 0
            if enabled == 0:
                summary["disabled"].append(job["name"])
            self._db.execute(
                "UPDATE schedule SET runs=?, failures=?, last_run=?, next_run=?, enabled=?"
                " WHERE id=?",
                (runs, failures, now, now + job["interval_seconds"], enabled, job["id"]),
            )
            summary["ran" if ok else "failed"] += 1
        self._db.commit()
        return summary

    def set_enabled(self, name: str, enabled: bool) -> None:
        cur = self._db.execute(
            "UPDATE schedule SET enabled=?, failures=0 WHERE name=?", (1 if enabled else 0, name)
        )
        self._db.commit()
        if cur.rowcount == 0:
            raise ValueError("unknown job")

    def remove(self, name: str) -> bool:
        cur = self._db.execute("DELETE FROM schedule WHERE name=?", (name,))
        self._db.commit()
        return cur.rowcount > 0

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM schedule WHERE name=?", (name,)).fetchone()
        return self._row(row) if row else None

    @staticmethod
    def _row(row: sqlite3.Row) -> Dict[str, Any]:
        data = dict(row)
        data["payload"] = json.loads(data["payload"])
        data["enabled"] = bool(data["enabled"])
        return data

    def close(self) -> None:
        self._db.close()