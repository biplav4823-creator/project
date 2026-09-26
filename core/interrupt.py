from dataclasses import dataclass
from typing import Any

from core.approval import Interrupt


@dataclass(frozen=True)
class InterruptResult:
    action: str
    interrupts: list[Any]


class InterruptEngine:
    """
    CP-14 interrupt detection and control layer.

    Pre-execution interrupts stop execution and route through the
    Approval Gate. Post-execution hooks provide a future control point
    for retry, replan, and escalation decisions.
    """

    RISK_TRIGGERS = {
        "medium": "medium_risk",
        "high": "high_risk",
    }

    PERMISSION_TRIGGERS = {
        "filesystem_write": "external_side_effect",
        "network_access": "external_side_effect",
        "process_control": "process_control",
        "credential_access": "credential_access",
        "secret_access": "credential_access",
        "network_admin": "network_admin",
        "system_admin": "permission_required",
    }

    def pre_execution(
        self,
        capability,
        step_id=None,
        arguments=None,
    ):
        interrupts = []

        risk = capability.risk or "low"
        trigger = self.RISK_TRIGGERS.get(risk)

        if trigger:
            interrupts.append(
                self._interrupt(
                    trigger,
                    "pre_execution",
                    capability,
                    step_id,
                    arguments,
                    f"Capability '{capability.name}' has {risk} risk.",
                )
            )

        for permission in capability.permissions or []:
            trigger = self.PERMISSION_TRIGGERS.get(permission)

            if trigger and not any(
                item.name == trigger for item in interrupts
            ):
                interrupts.append(
                    self._interrupt(
                        trigger,
                        "pre_execution",
                        capability,
                        step_id,
                        arguments,
                        (
                            f"Capability '{capability.name}' requires "
                            f"permission '{permission}'."
                        ),
                    )
                )

        for name in getattr(capability, "interrupts", []) or []:
            if not any(item.name == name for item in interrupts):
                interrupts.append(
                    self._interrupt(
                        name,
                        "pre_execution",
                        capability,
                        step_id,
                        arguments,
                        (
                            f"Capability '{capability.name}' declares "
                            f"interrupt trigger '{name}'."
                        ),
                    )
                )

        return InterruptResult(
            action="interrupt" if interrupts else "continue",
            interrupts=interrupts,
        )

    def post_execution(
        self,
        capability,
        result,
        step_id=None,
    ):
        return InterruptResult(
            action="continue",
            interrupts=[],
        )

    @staticmethod
    def _interrupt(
        name,
        phase,
        capability,
        step_id,
        arguments,
        reason,
    ):
        return Interrupt(
            name=name,
            phase=phase,
            reason=reason,
            capability=capability.name,
            step_id=step_id,
            metadata={
                "arguments": arguments or {},
                "risk": capability.risk or "low",
            },
        )
