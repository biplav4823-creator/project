"""CP-58a: secret broker. Secrets come from the environment, are never stored,
logged, or returned in reprs; `scrub` removes any known secret value from text.
(Named vault.py to avoid shadowing the standard-library `secrets` module.)
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Mapping, Optional

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
MIN_SECRET_LEN = 6


class SecretUnavailable(KeyError):
    pass


class SecretBroker:
    def __init__(self, env: Optional[Mapping[str, str]] = None):
        self._env = env if env is not None else os.environ
        self._map: Dict[str, str] = {}
        self.audit: List[Dict[str, Any]] = []

    def register(self, name: str, env_var: str) -> None:
        if not NAME_RE.match(name or "") or not ENV_RE.match(env_var or ""):
            raise ValueError("invalid secret name or environment variable")
        self._map[name] = env_var

    def get(self, name: str, purpose: str) -> str:
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("purpose required")
        env_var = self._map.get(name)
        value = self._env.get(env_var, "") if env_var else ""
        outcome = "ok" if value else "unavailable"
        self.audit.append({"name": name, "purpose": purpose[:100], "outcome": outcome})
        if not value:
            raise SecretUnavailable(name)
        return value

    def available(self, name: str) -> bool:
        env_var = self._map.get(name)
        return bool(env_var and self._env.get(env_var))

    def scrub(self, text: Any) -> str:
        out = str(text)
        for name, env_var in sorted(self._map.items(),
                                    key=lambda kv: -len(self._env.get(kv[1], "") or "")):
            value = self._env.get(env_var, "")
            if value and len(value) >= MIN_SECRET_LEN:
                out = out.replace(value, f"[REDACTED:{name}]")
        return out

    def __repr__(self) -> str:
        return f"SecretBroker(registered={sorted(self._map)})"