"""CP-56: content-addressed artifact store with provenance and integrity checks."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

ID_RE = re.compile(r"^[0-9a-f]{64}$")
KIND_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,31}$")
MAX_BYTES = 50 * 1024 * 1024


class ArtifactError(ValueError):
    pass


class ArtifactStore:
    def __init__(self, root: str):
        self._root = os.path.abspath(root)
        os.makedirs(os.path.join(self._root, "blobs"), exist_ok=True)
        os.makedirs(os.path.join(self._root, "meta"), exist_ok=True)

    # ------------------------------------------------------------- paths
    def _blob(self, aid: str) -> str:
        return os.path.join(self._root, "blobs", aid[:2], aid)

    def _meta(self, aid: str) -> str:
        return os.path.join(self._root, "meta", aid + ".json")

    @staticmethod
    def _check_id(aid: Any) -> str:
        if not isinstance(aid, str) or not ID_RE.match(aid):
            raise ArtifactError("invalid artifact id")
        return aid

    def _atomic_write(self, path: str, data: bytes) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # --------------------------------------------------------------- api
    def put(
        self,
        data: bytes,
        kind: str,
        producer: Optional[Dict[str, Any]] = None,
        parents: Iterable[str] = (),
    ) -> str:
        if not isinstance(data, (bytes, bytearray)):
            raise ArtifactError("data must be bytes")
        if len(data) > MAX_BYTES:
            raise ArtifactError("artifact too large")
        if not isinstance(kind, str) or not KIND_RE.match(kind):
            raise ArtifactError("invalid kind")
        parent_ids = sorted({self._check_id(p) for p in parents})
        for pid in parent_ids:
            if not os.path.exists(self._meta(pid)):
                raise ArtifactError("unknown parent artifact")
        aid = hashlib.sha256(bytes(data)).hexdigest()
        if not os.path.exists(self._blob(aid)):
            self._atomic_write(self._blob(aid), bytes(data))
        entry = {
            "producer": producer or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = self._meta(aid)
        if os.path.exists(meta_path):
            meta = self._read_meta(aid)
            meta["produced_by"].append(entry)
            meta["parents"] = sorted(set(meta["parents"]) | set(parent_ids))
        else:
            meta = {"id": aid, "kind": kind, "size": len(data),
                    "parents": parent_ids, "produced_by": [entry]}
        self._atomic_write(meta_path, json.dumps(meta, sort_keys=True).encode("utf-8"))
        return aid

    def _read_meta(self, aid: str) -> Dict[str, Any]:
        try:
            with open(self._meta(aid), "r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            raise ArtifactError("unknown artifact") from None

    def info(self, aid: str) -> Dict[str, Any]:
        return self._read_meta(self._check_id(aid))

    def get(self, aid: str) -> bytes:
        aid = self._check_id(aid)
        self._read_meta(aid)
        with open(self._blob(aid), "rb") as handle:
            data = handle.read()
        if hashlib.sha256(data).hexdigest() != aid:
            raise ArtifactError("integrity check failed")
        return data

    def verify(self, aid: str) -> bool:
        try:
            self.get(aid)
            return True
        except (ArtifactError, OSError):
            return False

    def lineage(self, aid: str) -> List[str]:
        """All ancestors (transitive), nearest first, without duplicates."""
        seen: List[str] = []
        queue = list(self.info(aid)["parents"])
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.append(current)
            queue.extend(self.info(current)["parents"])
        return seen

    def list(self, kind: Optional[str] = None) -> List[str]:
        ids = sorted(f[:-5] for f in os.listdir(os.path.join(self._root, "meta"))
                     if f.endswith(".json"))
        if kind is None:
            return ids
        return [i for i in ids if self._read_meta(i)["kind"] == kind]