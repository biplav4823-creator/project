from dataclasses import dataclass, field
from typing import Any, Callable


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
    executor: Callable[..., Any] | None = None

    def execute(self, arguments: dict[str, Any] | None = None):
        if self.executor is None:
            raise RuntimeError(
                f"Capability '{self.name}' has no executor."
            )

        return self.executor(arguments or {})
