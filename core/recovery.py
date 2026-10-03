from dataclasses import dataclass, field
from typing import Any


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
    """Return a structured recovery decision without executing the retry."""

    RETRYABLE_ERRORS = (
        TimeoutError,
        ConnectionError,
    )

    def recover(self, error):
        error_type = type(error).__name__
        message = str(error)

        if isinstance(error, self.RETRYABLE_ERRORS):
            return RecoveryDecision(
                action="RETRY",
                retryable=True,
                reason="transient_error",
                retry_policy={"max_attempts": 1},
                metadata={"error_type": error_type, "error": message},
            )

        return RecoveryDecision(
            action="ABORT",
            retryable=False,
            reason="non_retryable_error",
            metadata={"error_type": error_type, "error": message},
        )
