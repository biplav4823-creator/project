from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ToolSpec:
    """
    Canonical metadata contract for every executable JARVIS tool.

    This is metadata only. Execution remains owned by the existing
    Executor/registry path until the runtime migration is completed.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    permissions: tuple[str, ...] = ()
    risk: str = "low"
    timeout_seconds: float | None = None
    supports_dry_run: bool = False
    supports_cancellation: bool = False
    idempotent: bool = False
    requires_approval: bool = False
    dependencies: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool:
    """
    Canonical executable tool contract.

    Concrete tools implement execute(). Optional lifecycle hooks allow
    future browser/API/MCP/system integrations without changing the
    Orchestrator contract.
    """

    spec: ToolSpec

    def execute(self, arguments: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError

    def dry_run(self, arguments: dict[str, Any] | None = None) -> Any:
        if not self.spec.supports_dry_run:
            raise NotImplementedError(
                f"Tool '{self.spec.name}' does not support dry-run."
            )
        raise NotImplementedError

    def cancel(self, execution_id: str) -> bool:
        if not self.spec.supports_cancellation:
            return False
        return False

    def health(self) -> dict[str, Any]:
        return {
            "name": self.spec.name,
            "version": self.spec.version,
            "healthy": True,
        }

    def permissions(self) -> tuple[str, ...]:
        return self.spec.permissions

    def risk(self) -> str:
        return self.spec.risk

    def dependencies(self) -> tuple[str, ...]:
        return self.spec.dependencies

    def idempotency(self) -> bool:
        return self.spec.idempotent

    def requires_approval(self) -> bool:
        return self.spec.requires_approval

class CapabilityTool(Tool):
    """Adapter exposing an existing capability through the canonical Tool contract."""

    def __init__(
        self,
        capability,
        *,
        version="1.0.0",
        description="",
        permissions=(),
        risk="low",
        timeout_seconds=None,
        supports_dry_run=False,
        supports_cancellation=False,
        idempotent=False,
        requires_approval=False,
        dependencies=(),
        metadata=None,
    ):
        self.capability = capability

        name = getattr(capability, "name", None)
        if not name:
            raise ValueError("Capability must define a non-empty name")

        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        capability_risk = str(getattr(capability, "risk", "low") or "low").lower()
        requested_risk = str(risk or "low").lower()

        # Adapter metadata may raise risk but must never lower it.
        if capability_risk not in risk_order:
            effective_risk = capability_risk
        elif requested_risk not in risk_order:
            effective_risk = requested_risk
        else:
            effective_risk = max(
                (capability_risk, requested_risk),
                key=risk_order.__getitem__,
            )

        if (
            name == "run_python"
            and effective_risk in risk_order
            and risk_order[effective_risk] < risk_order["high"]
        ):
            effective_risk = "high"

        capability_approval = getattr(capability, "requires_approval", False)
        if callable(capability_approval):
            capability_approval = capability_approval()

        approval_required = (
            bool(requires_approval)
            or bool(capability_approval)
            or effective_risk in {"medium", "high"}
        )

        self.spec = ToolSpec(
            name=name,
            version=version,
            description=description or str(getattr(capability, "description", "")),
            permissions=tuple(
                permissions if permissions else getattr(capability, "permissions", ())
            ),
            risk=effective_risk,
            timeout_seconds=timeout_seconds,
            supports_dry_run=supports_dry_run or hasattr(capability, "dry_run"),
            supports_cancellation=supports_cancellation,
            idempotent=idempotent,
            requires_approval=approval_required,
            dependencies=tuple(
                dependencies if dependencies else getattr(capability, "dependencies", ())
            ),
            metadata=dict(metadata or {}),
        )

    def execute(self, arguments=None):
        return self.capability.execute(arguments or {})

    def execute_with_timeout(self, arguments=None, *, timeout_seconds):
        hook = getattr(self.capability, "execute_with_timeout", None)
        if not callable(hook):
            raise NotImplementedError(
                f"Capability '{self.spec.name}' has no timeout-aware execution hook."
            )
        return hook(arguments or {}, timeout_seconds=timeout_seconds)

    def dry_run(self, arguments=None):
        if hasattr(self.capability, "dry_run"):
            return self.capability.dry_run(arguments or {})
        return super().dry_run(arguments or {})
