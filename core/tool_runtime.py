from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolExecutionResult:
    tool: str
    status: str
    result: Any = None
    error: str | None = None
    dry_run: bool = False


class ToolRuntime:
    """
    Canonical execution boundary for JARVIS tools.

    CP-31.2 is an adapter around the existing registry. It does not
    replace Executor or CapabilityRegistry yet.
    """

    def __init__(self, registry):
        self.registry = registry

    def has_tool(self, name: str) -> bool:
        return self.registry.has(name)

    def get_tool(self, name: str):
        return self.registry.get(name)

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        arguments = arguments or {}

        try:
            result = self.registry.execute(name, arguments)
            return ToolExecutionResult(
                tool=name,
                status="succeeded",
                result=result,
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool=name,
                status="failed",
                error=str(exc),
            )

    def dry_run(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        tool = self.registry.get(name)

        if not hasattr(tool, "dry_run"):
            return ToolExecutionResult(
                tool=name,
                status="unsupported",
                dry_run=True,
                error=f"Tool '{name}' does not support dry-run.",
            )

        try:
            result = tool.dry_run(arguments or {})
            return ToolExecutionResult(
                tool=name,
                status="succeeded",
                result=result,
                dry_run=True,
            )
        except NotImplementedError:
            return ToolExecutionResult(
                tool=name,
                status="unsupported",
                dry_run=True,
                error=f"Tool '{name}' does not support dry-run.",
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool=name,
                status="failed",
                error=str(exc),
                dry_run=True,
            )

    def health(self, name: str) -> dict[str, Any]:
        tool = self.registry.get(name)

        if hasattr(tool, "health"):
            return dict(tool.health())

        return {
            "name": name,
            "healthy": True,
        }

    def permissions(self, name: str) -> tuple[str, ...]:
        tool = self.registry.get(name)

        if hasattr(tool, "permissions"):
            return tuple(tool.permissions())

        return tuple(getattr(tool, "permissions", ()) or ())

    def risk(self, name: str) -> str:
        tool = self.registry.get(name)

        if hasattr(tool, "risk"):
            return str(tool.risk())

        return str(getattr(tool, "risk", "low") or "low")

    def idempotent(self, name: str) -> bool:
        tool = self.registry.get(name)

        if hasattr(tool, "idempotency"):
            return bool(tool.idempotency())

        return bool(getattr(tool, "idempotent", False))

    def requires_approval(self, name: str) -> bool:
        tool = self.registry.get(name)

        if hasattr(tool, "requires_approval"):
            return bool(tool.requires_approval())

        return False
