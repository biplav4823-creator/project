import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


class StateStore:
    def __init__(self, database_path="jarvis_state.db"):
        self.database_path = database_path
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_states (
                    job_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    step_id INTEGER,
                    timestamp TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_execution_events_job_id
                ON execution_events(job_id, event_id)
                """
            )

            connection.commit()

    def save(self, job_id: str, state: dict[str, Any]):
        state_json = json.dumps(state, default=str)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_states (job_id, state_json)
                VALUES (?, ?)
                ON CONFLICT(job_id)
                DO UPDATE SET state_json = excluded.state_json
                """,
                (job_id, state_json)
            )
            connection.commit()

    def load(self, job_id: str):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT state_json
                FROM job_states
                WHERE job_id = ?
                """,
                (job_id,)
            ).fetchone()

        if row is None:
            return None

        return json.loads(row[0])

    def delete(self, job_id: str):
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM job_states
                WHERE job_id = ?
                """,
                (job_id,)
            )
            connection.commit()

    def exists(self, job_id: str):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM job_states
                WHERE job_id = ?
                """,
                (job_id,)
            ).fetchone()

        return row is not None

    def record_event(
        self,
        job_id: str,
        event_type: str,
        step_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ):
        timestamp = datetime.now(timezone.utc).isoformat()
        payload_json = json.dumps(payload or {}, default=str)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO execution_events (
                    job_id,
                    event_type,
                    step_id,
                    timestamp,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    event_type,
                    step_id,
                    timestamp,
                    payload_json,
                )
            )
            connection.commit()
            return cursor.lastrowid

    def get_events(self, job_id: str):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    event_id,
                    job_id,
                    event_type,
                    step_id,
                    timestamp,
                    payload_json
                FROM execution_events
                WHERE job_id = ?
                ORDER BY event_id ASC
                """,
                (job_id,)
            ).fetchall()

        return [
            {
                "event_id": row[0],
                "job_id": row[1],
                "event_type": row[2],
                "step_id": row[3],
                "timestamp": row[4],
                "payload": json.loads(row[5]),
            }
            for row in rows
        ]
