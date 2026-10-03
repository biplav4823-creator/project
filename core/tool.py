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

        self.spec = ToolSpec(
            name=name,
            version=version,
            description=description or str(getattr(capability, "description", "")),
            permissions=tuple(
                permissions if permissions else getattr(capability, "permissions", ())
            ),
            risk=risk if risk != "low" else str(getattr(capability, "risk", "low") or "low"),
            supports_dry_run=supports_dry_run or hasattr(capability, "dry_run"),
            supports_cancellation=supports_cancellation,
            idempotent=idempotent,
            requires_approval=requires_approval,
            dependencies=tuple(
                dependencies if dependencies else getattr(capability, "dependencies", ())
            ),
            metadata=dict(metadata or {}),
        )

    def execute(self, arguments=None):
        return self.capability.execute(arguments or {})

    def dry_run(self, arguments=None):
        if hasattr(self.capability, "dry_run"):
            return self.capability.dry_run(arguments or {})
        return super().dry_run(arguments or {})
