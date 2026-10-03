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
    """Canonical execution boundary for JARVIS tools."""
    def __init__(self, registry):
        self.registry = registry

    def has_tool(self, name: str) -> bool:
        return self.registry.has(name)

    def get_tool(self, name: str):
        return self.registry.get(name)

    def execute(self, name: str, arguments: dict[str, Any] | None = None):
        try:
            result = self.registry.execute(name, arguments or {})
            return ToolExecutionResult(name, "succeeded", result=result)
        except Exception as exc:
            return ToolExecutionResult(name, "failed", error=str(exc))

    def dry_run(self, name, arguments=None):
        tool = self.registry.get(name)
        if not hasattr(tool, "dry_run"):
            return ToolExecutionResult(name, "unsupported", dry_run=True,
                                        error=f"Tool '{name}' does not support dry-run.")
        try:
            return ToolExecutionResult(
                name, "succeeded", result=tool.dry_run(arguments or {}), dry_run=True
            )
        except NotImplementedError:
            return ToolExecutionResult(
                name, "unsupported", dry_run=True,
                error=f"Tool '{name}' does not support dry-run."
            )
        except Exception as exc:
            return ToolExecutionResult(name, "failed", error=str(exc), dry_run=True)

    def health(self, name):
        tool = self.registry.get(name)
        return dict(tool.health()) if hasattr(tool, "health") else {"name": name, "healthy": True}

    def permissions(self, name):
        tool = self.registry.get(name)
        return tuple(tool.permissions()) if hasattr(tool, "permissions") else tuple(getattr(tool, "permissions", ()) or ())

    def risk(self, name):
        tool = self.registry.get(name)
        return str(tool.risk()) if hasattr(tool, "risk") else str(getattr(tool, "risk", "low") or "low")

    def idempotent(self, name):
        tool = self.registry.get(name)
        return bool(tool.idempotency()) if hasattr(tool, "idempotency") else bool(getattr(tool, "idempotent", False))

    def requires_approval(self, name):
        tool = self.registry.get(name)
        return bool(tool.requires_approval()) if hasattr(tool, "requires_approval") else False
