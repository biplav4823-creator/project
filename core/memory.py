"""CP-52: persistent memory with provenance (SQLite FTS5, offline).

Namespaced, size-capped, secret-redacted on write. Full-text search ranks with
bm25; if FTS5 is unavailable the store falls back to token-overlap scoring.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

NAMESPACE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
MAX_TEXT = 20000
_SECRET = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|bearer\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})",
    re.IGNORECASE,
)
_WORD = re.compile(r"\w+", re.UNICODE)


class MemoryStore:
    def __init__(self, path: str = ":memory:"):
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS mem (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                namespace TEXT NOT NULL,
                text TEXT NOT NULL,
                source TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                job_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS mem_ns ON mem(namespace);
            """
        )
        self._fts = self._init_fts()

    def _init_fts(self) -> bool:
        try:
            self._db.executescript(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts
                    USING fts5(text, content='mem', content_rowid='id');
                CREATE TRIGGER IF NOT EXISTS mem_ai AFTER INSERT ON mem BEGIN
                    INSERT INTO mem_fts(rowid, text) VALUES (new.id, new.text);
                END;
                CREATE TRIGGER IF NOT EXISTS mem_ad AFTER DELETE ON mem BEGIN
                    INSERT INTO mem_fts(mem_fts, rowid, text)
                        VALUES ('delete', old.id, old.text);
                END;
                """
            )
            return True
        except sqlite3.OperationalError:
            return False

    @staticmethod
    def _ns(namespace: str) -> str:
        if not isinstance(namespace, str) or not NAMESPACE_RE.match(namespace):
            raise ValueError("invalid namespace")
        return namespace

    def add(
        self,
        text: str,
        namespace: str = "default",
        source: str = "user",
        tags: Iterable[str] = (),
        job_id: Optional[str] = None,
    ) -> int:
        namespace = self._ns(namespace)
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text required")
        if len(text) > MAX_TEXT:
            raise ValueError("text too long")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source (provenance) required")
        clean = _SECRET.sub("[REDACTED]", text)
        cur = self._db.execute(
            "INSERT INTO mem(namespace,text,source,tags,job_id,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (
                namespace, clean, source.strip()[:200],
                json.dumps(sorted({str(t)[:50] for t in tags})),
                job_id, datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._db.commit()
        return int(cur.lastrowid)

    def search(self, query: str, namespace: str = "default", limit: int = 5) -> List[Dict[str, Any]]:
        namespace = self._ns(namespace)
        limit = max(1, min(int(limit), 50))
        words = [w.lower() for w in _WORD.findall(query or "")][:20]
        if not words:
            return []
        if self._fts:
            match = " OR ".join('"' + w.replace('"', "") + '"' for w in words)
            rows = self._db.execute(
                "SELECT m.*, bm25(mem_fts) AS rank FROM mem_fts "
                "JOIN mem m ON m.id = mem_fts.rowid "
                "WHERE mem_fts MATCH ? AND m.namespace = ? "
                "ORDER BY rank LIMIT ?",
                (match, namespace, limit),
            ).fetchall()
            return [self._row(r, score=-float(r["rank"])) for r in rows]
        rows = self._db.execute("SELECT * FROM mem WHERE namespace = ?", (namespace,)).fetchall()
        scored = []
        for r in rows:
            tokens = {w.lower() for w in _WORD.findall(r["text"])}
            score = sum(1 for w in words if w in tokens)
            if score:
                scored.append((score, r))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [self._row(r, score=float(s)) for s, r in scored[:limit]]

    @staticmethod
    def _row(row: sqlite3.Row, score: float) -> Dict[str, Any]:
        return {
            "id": row["id"], "namespace": row["namespace"], "text": row["text"],
            "source": row["source"], "tags": json.loads(row["tags"]),
            "job_id": row["job_id"], "created_at": row["created_at"],
            "score": round(score, 6),
        }

    def get(self, memory_id: int) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT * FROM mem WHERE id = ?", (int(memory_id),)).fetchone()
        return self._row(row, 0.0) if row else None

    def delete(self, memory_id: int) -> bool:
        cur = self._db.execute("DELETE FROM mem WHERE id = ?", (int(memory_id),))
        self._db.commit()
        return cur.rowcount > 0

    def forget_namespace(self, namespace: str) -> int:
        cur = self._db.execute("DELETE FROM mem WHERE namespace = ?", (self._ns(namespace),))
        self._db.commit()
        return cur.rowcount

    def count(self, namespace: Optional[str] = None) -> int:
        if namespace is None:
            return self._db.execute("SELECT COUNT(*) FROM mem").fetchone()[0]
        return self._db.execute(
            "SELECT COUNT(*) FROM mem WHERE namespace = ?", (self._ns(namespace),)
        ).fetchone()[0]

    def close(self) -> None:
        self._db.close()