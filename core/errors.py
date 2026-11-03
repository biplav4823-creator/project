"""Typed, redacted error model shared by the tool runtime, executor and recovery.

Design rules (CP-44):
* Classification happens once, at the runtime boundary, on the exception that
  the tool actually raised. ``__cause__`` / ``__context__`` are deliberately
  NOT followed: a wrapper such as "Verification failed due to verifier error"
  must not inherit the retryability of the exception it wraps.
* ``ErrorInfo.message`` is safe to persist and log. It never contains
  ``str(exc)``; only a fixed label plus the exception class name.
* ``outcome`` records what is known about side effects:
    not_started - the call provably did not run (safe to retry)
    unknown     - the call may or may not have run (retry only if idempotent)
    failed      - the call ran and failed deterministically
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass

OUTCOME_NOT_STARTED = "not_started"
OUTCOME_UNKNOWN = "unknown"
OUTCOME_FAILED = "failed"
VALID_OUTCOMES = frozenset(
    {OUTCOME_NOT_STARTED, OUTCOME_UNKNOWN, OUTCOME_FAILED}
)


def debug_errors_enabled() -> bool:
    """Raw exception detail is opt-in and local only."""
    return os.environ.get("JARVIS_DEBUG_ERRORS", "").strip() == "1"


@dataclass(frozen=True)
class ErrorInfo:
    code: str
    retryable: bool
    outcome: str
    message: str
    error_type: str = ""

    def __post_init__(self):
        if self.outcome not in VALID_OUTCOMES:
            raise ValueError(f"Invalid error outcome: {self.outcome!r}")

    def to_dict(self) -> dict:
        return asdict(self)


class ToolFailure(RuntimeError):
    """A tool invocation failure that carries its classified ``ErrorInfo``.

    Subclasses ``RuntimeError`` so existing ``except Exception`` handling in
    the orchestrator keeps working. ``str(failure)`` is the safe message.
    """

    def __init__(self, info: ErrorInfo, detail: str | None = None):
        super().__init__(info.message)
        self.info = info
        self.detail = detail if debug_errors_enabled() else None


def _class_names(exc: BaseException) -> list[str]:
    return [
        cls.__name__.lower()
        for cls in type(exc).__mro__
        if cls not in (object, BaseException, Exception)
    ]


def _info(code, retryable, outcome, label, exc) -> ErrorInfo:
    name = type(exc).__name__
    return ErrorInfo(code, retryable, outcome, f"{label} ({name}).", name)


def classify(exc: BaseException) -> ErrorInfo:
    """Map any exception to a stable, redacted ``ErrorInfo``."""
    if isinstance(exc, ToolFailure):
        return exc.info

    names = _class_names(exc)

    def has(*fragments: str) -> bool:
        return any(f in n for n in names for f in fragments)

    if isinstance(exc, ConnectionRefusedError):
        return _info(
            "connection_refused", True, OUTCOME_NOT_STARTED,
            "Connection refused", exc,
        )
    if isinstance(exc, TimeoutError) or has("timeout", "timedout"):
        return _info(
            "timeout", True, OUTCOME_UNKNOWN, "Tool call timed out", exc
        )
    if isinstance(exc, ConnectionError) or has("connection"):
        return _info(
            "connection", True, OUTCOME_UNKNOWN, "Connection failed", exc
        )
    if has("ratelimit", "throttl", "toomanyrequests"):
        return _info(
            "throttled", True, OUTCOME_NOT_STARTED, "Rate limited", exc
        )
    if isinstance(exc, PermissionError) or has(
        "auth", "permission", "forbidden"
    ):
        return _info(
            "auth", False, OUTCOME_FAILED, "Authorization failed", exc
        )
    if isinstance(exc, (ValueError, TypeError, KeyError)) or has(
        "validation"
    ):
        return _info(
            "invalid_input", False, OUTCOME_FAILED,
            "Tool rejected its input", exc,
        )
    return _info("tool_error", False, OUTCOME_UNKNOWN, "Tool failed", exc)