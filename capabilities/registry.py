from .capability import Capability


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability):
        if capability.name in self._capabilities:
            raise ValueError(
                f"Capability '{capability.name}' is already registered."
            )

        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability:
        if name not in self._capabilities:
            raise KeyError(
                f"Capability '{name}' is not registered."
            )

        return self._capabilities[name]

    def has(self, name: str) -> bool:
        return name in self._capabilities

    def list(self) -> list[str]:
        return sorted(self._capabilities.keys())

    def execute(self, name: str, arguments=None):
        capability = self.get(name)
        return capability.execute(arguments)
