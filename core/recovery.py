from dataclasses import dataclass, field
from typing import Any

from core.errors import (
    OUTCOME_NOT_STARTED,
    classify,
    debug_errors_enabled,
)


@dataclass(frozen=True)
class RecoveryDecision:
    action: str
    reason: str
    retryable: bool = False
    retry_policy: dict[str, Any] = field(default_factory=dict)
    alternative_capability: str | None = None
    replan_required: bool = False
    rollback_required: bool = False
    human_intervention_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class Recovery:
    """Return a structured recovery decision without executing the retry.

    Rule: retry only when the failed attempt provably did not run, or when the
    caller states the tool is idempotent. A retryable error whose outcome is
    unknown on a non-idempotent (or unspecified) tool is never retried
    automatically; it is escalated to a human.
    """

    # Retained for backward compatibility; classification now lives in
    # core.errors.classify and this tuple is no longer consulted.
    RETRYABLE_ERRORS = (
        TimeoutError,
        ConnectionError,
    )

    MAX_ATTEMPTS = 1

    def recover(self, error, tool_idempotent=None):
        info = classify(error)

        metadata = {
            "error_type": info.error_type or type(error).__name__,
            "error_code": info.code,
            "error": info.message,
            "outcome": info.outcome,
        }
        if debug_errors_enabled():
            metadata["error_detail"] = str(error)

        if info.retryable:
            if info.outcome == OUTCOME_NOT_STARTED or tool_idempotent is True:
                return RecoveryDecision(
                    action="RETRY",
                    retryable=True,
                    reason="transient_error",
                    retry_policy={"max_attempts": self.MAX_ATTEMPTS},
                    metadata=metadata,
                )

            return RecoveryDecision(
                action="ABORT",
                retryable=False,
                reason="outcome_unknown",
                human_intervention_required=True,
                metadata=metadata,
            )

        return RecoveryDecision(
            action="ABORT",
            retryable=False,
            reason="non_retryable_error",
            metadata=metadata,
        )