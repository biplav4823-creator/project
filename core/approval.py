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
        requires_approval=False,
    ):
        name = capability.name
        risk = capability.risk or "low"
        interrupts = interrupts or []

        contract_requirement = getattr(capability, "requires_approval", False)
        if callable(contract_requirement):
            contract_requirement = contract_requirement()

        approval_required = (
            risk in self.APPROVAL_RISKS
            or bool(interrupts)
            or bool(requires_approval)
            or bool(contract_requirement)
        )

        if not approval_required:
            return ApprovalDecision(
                action="allow",
                capability=name,
                reason=(
                    f"Capability '{name}' does not require "
                    "human approval."
                ),
            )

        interrupt = interrupts[0] if interrupts else Interrupt(
            name=(
                f"{risk}_risk"
                if risk in self.APPROVAL_RISKS
                else "explicit_approval_required"
            ),
            phase="pre_execution",
            reason=(
                f"Capability '{name}' is {risk} risk and requires human approval."
                if risk in self.APPROVAL_RISKS
                else f"Capability '{name}' requires human approval by tool policy."
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
