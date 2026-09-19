from dataclasses import dataclass
from typing import Callable, Any


@dataclass
class Tool:
    name: str
    description: str
    function: Callable[..., Any]


class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def list_tools(self):
        return list(self._tools.values())

    def execute(self, name: str, arguments=None):
        tool = self.get(name)

        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        arguments = arguments or {}

        return tool.function(**arguments)
