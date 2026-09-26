from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Interrupt:
    name: str
    phase: str
    reason: str
    capability: str
    step_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalDecision:
    action: str
    capability: str
    reason: str
    interrupt: Interrupt | None = None


class ApprovalGate:
    """
    CP-14 human approval boundary.

    Approval is evaluated before execution for actions that require
    explicit human authorization.
    """

    APPROVAL_RISKS = {"medium", "high"}

    def __init__(self, auto_approve=False):
        self.auto_approve = bool(auto_approve)

    def evaluate(
        self,
        capability,
        step_id=None,
        arguments=None,
        interrupts=None,
    ):
        name = capability.name
        risk = capability.risk or "low"
        interrupts = interrupts or []

        requires_approval = (
            risk in self.APPROVAL_RISKS
            or bool(interrupts)
        )

        if not requires_approval:
            return ApprovalDecision(
                action="allow",
                capability=name,
                reason=(
                    f"Capability '{name}' does not require "
                    "human approval."
                ),
            )

        interrupt = interrupts[0] if interrupts else Interrupt(
            name=f"{risk}_risk",
            phase="pre_execution",
            reason=(
                f"Capability '{name}' is {risk} risk "
                "and requires human approval."
            ),
            capability=name,
            step_id=step_id,
            metadata={
                "risk": risk,
                "arguments": arguments or {},
            },
        )

        if self.auto_approve:
            return ApprovalDecision(
                action="allow",
                capability=name,
                reason="Approval automatically granted by policy.",
                interrupt=interrupt,
            )

        return ApprovalDecision(
            action="approve",
            capability=name,
            reason=interrupt.reason,
            interrupt=interrupt,
        )

    def check(
        self,
        capability,
        step_id=None,
        arguments=None,
        interrupts=None,
    ):
        decision = self.evaluate(
            capability,
            step_id=step_id,
            arguments=arguments,
            interrupts=interrupts,
        )

        return decision
