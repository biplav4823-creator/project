from core.errors import (
    ErrorInfo,
    OUTCOME_NOT_STARTED,
    OUTCOME_UNKNOWN,
    ToolFailure,
)
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
                info = getattr(result, "error_info", None)
                if info is None:
                    # Policy decisions (blocked / unsupported / invalid) never
                    # reached the tool: outcome "not_started". A bare "failed"
                    # status without detail may have run: outcome "unknown".
                    info = ErrorInfo(
                        code=str(status),
                        retryable=False,
                        outcome=(
                            OUTCOME_UNKNOWN
                            if status == "failed"
                            else OUTCOME_NOT_STARTED
                        ),
                        message=(
                            getattr(result, "error", None)
                            or f"Tool '{tool_name}' did not succeed "
                            f"(status={status!r})."
                        ),
                    )
                raise ToolFailure(info)
            return result.result

        return tool_registry.execute(tool_name, arguments or {})