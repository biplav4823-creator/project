from dataclasses import dataclass, field
from typing import Any, Callable

from core.schema import validate


@dataclass
class Capability:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    permissions: list[str] = field(default_factory=list)
    cost: float = 0.0
    latency: float = 0.0
    risk: str = "low"
    interrupts: list[str] = field(default_factory=list)
    executor: Callable[..., Any] | None = None

    def validate_input(self, arguments: dict[str, Any] | None = None):
        arguments = arguments or {}
        return validate(arguments, self.input_schema, f"Capability '{self.name}' input")

    def validate_output(self, result: Any):
        return validate(result, self.output_schema, f"Capability '{self.name}' output")

    def execute(self, arguments: dict[str, Any] | None = None):
        if self.executor is None:
            raise RuntimeError(f"Capability '{self.name}' has no executor.")

        arguments = arguments or {}
        self.validate_input(arguments)
        result = self.executor(arguments)
        self.validate_output(result)
        return result
