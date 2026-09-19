class Executor:
    def execute(self, tool_registry, tool_name, arguments=None):
        return tool_registry.execute(tool_name, arguments or {})
