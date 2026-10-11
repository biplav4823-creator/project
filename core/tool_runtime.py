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
    """Governed execution boundary for canonical JARVIS tools."""

    RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    BLOCKED_PERMISSIONS = frozenset({
        "system_admin",
        "process_control",
        "network_admin",
        "credential_access",
        "secret_access",
    })

    def __init__(self, registry):
        self.registry = registry

    def has_tool(self, name: str) -> bool:
        return self.registry.has(name)

    def get_tool(self, name: str):
        if hasattr(self.registry, "get_tool"):
            return self.registry.get_tool(name)
        return self.registry.get(name)

    @staticmethod
    def _member(tool, method_name, attribute_name, default=None):
        value = getattr(tool, method_name, None)
        if callable(value):
            return value()
        if value is not None:
            return value
        value = getattr(tool, attribute_name, default)
        return value() if callable(value) else value

    def _effective_risk(self, name, tool, effective_risk=None):
        raw = self._member(tool, "risk", "risk", "low")
        risks = [str(raw or "low").strip().lower()]
        if effective_risk is not None:
            risks.append(str(effective_risk or "low").strip().lower())

        unknown = next((risk for risk in risks if risk not in self.RISK_ORDER), None)
        if unknown is not None:
            return unknown

        risk = max(risks, key=self.RISK_ORDER.__getitem__)
        if name == "run_python" and self.RISK_ORDER[risk] < self.RISK_ORDER["high"]:
            risk = "high"
        return risk

    def permissions(self, name):
        tool = self.get_tool(name)
        value = self._member(tool, "permissions", "permissions", ())
        if isinstance(value, str):
            return (value,)
        return tuple(value or ())

    def risk(self, name):
        tool = self.get_tool(name)
        return self._effective_risk(name, tool)

    def idempotent(self, name):
        tool = self.get_tool(name)
        return bool(
            self._member(tool, "idempotency", "idempotent", False)
        )

    def requires_approval(self, name):
        tool = self.get_tool(name)
        risk = self._effective_risk(name, tool)
        explicit = self._member(
            tool, "requires_approval", "requires_approval", False
        )
        return bool(explicit) or risk in {"medium", "high"}

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        approved: bool = False,
        allowed_permissions=(),
        effective_risk=None,
    ):
        try:
            tool = self.get_tool(name)
            risk = self._effective_risk(name, tool, effective_risk)

            if risk not in self.RISK_ORDER:
                return ToolExecutionResult(
                    name, "blocked",
                    error=f"Unknown risk level {risk!r}; execution is denied.",
                )

            if risk == "critical":
                return ToolExecutionResult(
                    name, "blocked",
                    error=f"Tool '{name}' is critical risk and is blocked.",
                )

            required = set(self.permissions(name))
            blocked = required & self.BLOCKED_PERMISSIONS
            if blocked:
                return ToolExecutionResult(
                    name, "blocked",
                    error=f"Tool '{name}' requires blocked permission(s): {sorted(blocked)}.",
                )

            granted = set(allowed_permissions or ())
            missing = required - granted
            if missing:
                return ToolExecutionResult(
                    name, "blocked",
                    error=f"Permission grant missing for: {sorted(missing)}.",
                )

            explicit_approval = self._member(
                tool, "requires_approval", "requires_approval", False
            )
            if (
                risk in {"medium", "high"} or bool(explicit_approval)
            ) and not approved:
                return ToolExecutionResult(
                    name, "approval_required",
                    error=f"Tool '{name}' requires approval before execution.",
                )

            spec = getattr(tool, "spec", None)
            timeout = getattr(spec, "timeout_seconds", None)
            if timeout is None:
                timeout = getattr(tool, "timeout_seconds", None)

            if timeout is not None:
                import math
                try:
                    timeout_value = float(timeout)
                except (TypeError, ValueError):
                    return ToolExecutionResult(
                        name, "blocked", error="Invalid timeout contract."
                    )
                if not math.isfinite(timeout_value) or timeout_value <= 0:
                    return ToolExecutionResult(
                        name, "blocked", error="Timeout must be a positive finite number."
                    )

                hook = getattr(tool, "execute_with_timeout", None)
                if not callable(hook):
                    return ToolExecutionResult(
                        name, "unsupported",
                        error=(
                            f"Tool '{name}' declares a timeout but has no "
                            "timeout-aware execution hook; normal execution was not called."
                        ),
                    )
                result = hook(arguments or {}, timeout_seconds=timeout_value)
            else:
                result = tool.execute(arguments or {})

            return ToolExecutionResult(name, "succeeded", result=result)

        except Exception as exc:
            return ToolExecutionResult(name, "failed", error=str(exc))

    def dry_run(self, name, arguments=None):
        tool = self.get_tool(name)
        if not hasattr(tool, "dry_run"):
            return ToolExecutionResult(
                name, "unsupported", dry_run=True,
                error=f"Tool '{name}' does not support dry-run.",
            )
        try:
            return ToolExecutionResult(
                name, "succeeded", result=tool.dry_run(arguments or {}), dry_run=True
            )
        except NotImplementedError:
            return ToolExecutionResult(
                name, "unsupported", dry_run=True,
                error=f"Tool '{name}' does not support dry-run.",
            )
        except Exception as exc:
            return ToolExecutionResult(name, "failed", error=str(exc), dry_run=True)

    def health(self, name):
        tool = self.get_tool(name)
        return dict(tool.health()) if hasattr(tool, "health") else {
            "name": name, "healthy": True
        }
