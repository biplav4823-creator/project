from core.tool_runtime import ToolRuntime

class Executor:
    def __init__(self, runtime=None):
        self.runtime = runtime

    def execute(self, tool_registry, tool_name, arguments=None):
        if self.runtime is not None:
            result = self.runtime.execute(tool_name, arguments or {})
            if result.status == "failed":
                raise RuntimeError(result.error or f"Tool '{tool_name}' failed")
            return result.result

        return tool_registry.execute(tool_name, arguments or {})
