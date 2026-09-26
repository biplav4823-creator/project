import json
import sqlite3
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
            connection.commit()

    def save(self, job_id: str, state: dict[str, Any]):
        state_json = json.dumps(state)

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
