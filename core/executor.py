from core.tool_runtime import ToolRuntime


class Executor:
    def __init__(self, runtime=None):
        self.runtime = runtime

    def execute(
        self,
        tool_registry,
        tool_name,
        arguments=None,
        *,
        approved=False,
        allowed_permissions=(),
        effective_risk=None,
    ):
        if self.runtime is not None:
            result = self.runtime.execute(
                tool_name,
                arguments or {},
                approved=approved,
                allowed_permissions=allowed_permissions,
                effective_risk=effective_risk,
            )
            if getattr(result, "status", None) != "succeeded":
                status = getattr(result, "status", "invalid")
                error = getattr(result, "error", None)
                raise RuntimeError(
                    error or f"Tool '{tool_name}' did not succeed (status={status!r})."
                )
            return result.result

        return tool_registry.execute(tool_name, arguments or {})
