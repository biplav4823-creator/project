from dataclasses import dataclass


@dataclass(frozen=True)
class GuardrailDecision:
    action: str
    capability: str
    reason: str


class Guardrail:
    """
    Capability execution policy.

    CP-13 provides permission/risk enforcement.
    CP-14 will add explicit human approval interrupts.
    """

    BLOCKED_PERMISSIONS = {
        "system_admin",
        "process_control",
        "network_admin",
        "credential_access",
        "secret_access",
    }

    def __init__(
        self,
        allowed_permissions=None,
        allow_medium=False,
        allow_high=False,
    ):
        self.allowed_permissions = set(allowed_permissions or [])
        self.allow_medium = bool(allow_medium)
        self.allow_high = bool(allow_high)

    def evaluate(self, capability, arguments=None):
        name = capability.name
        risk = capability.risk or "low"

        # run_python is never treated as ordinary low-risk execution.
        if name == "run_python":
            risk = "high"

        if risk == "critical":
            return GuardrailDecision(
                "deny",
                name,
                f"Capability '{name}' has critical risk and is blocked.",
            )

        required = set(capability.permissions or [])

        blocked = required & self.BLOCKED_PERMISSIONS
        if blocked:
            return GuardrailDecision(
                "deny",
                name,
                f"Capability '{name}' requires blocked permission(s): "
                f"{sorted(blocked)}.",
            )

        missing = required - self.allowed_permissions
        if missing:
            return GuardrailDecision(
                "deny",
                name,
                f"Capability '{name}' requires permission(s) not granted: "
                f"{sorted(missing)}.",
            )

        if risk == "high" and not self.allow_high:
            return GuardrailDecision(
                "deny",
                name,
                f"Capability '{name}' is high risk. "
                f"Approval Gate is implemented in CP-14.",
            )

        if risk == "medium" and not self.allow_medium:
            return GuardrailDecision(
                "deny",
                name,
                f"Capability '{name}' is medium risk. "
                f"Approval Gate is implemented in CP-14.",
            )

        return GuardrailDecision(
            "allow",
            name,
            f"Capability '{name}' passed guardrail policy.",
        )

    def check(self, capability, arguments=None):
        decision = self.evaluate(capability, arguments)

        if decision.action != "allow":
            raise PermissionError(decision.reason)

        return decision
