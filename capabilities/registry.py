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

    def discover(self, query, limit=5):
        """Return capabilities ranked by relevance to a natural-language query."""
        if not query:
            return []

        terms = set(str(query).lower().replace("_", " ").split())
        scored = []

        for capability in self._capabilities.values():
            name = str(capability.name).lower().replace("_", " ")
            description = str(capability.description).lower()
            haystack = f"{name} {description}"

            score = 0
            for term in terms:
                if term in name:
                    score += 4
                elif term in description:
                    score += 2
                elif term in haystack:
                    score += 1

            if score > 0:
                scored.append((score, capability))

        scored.sort(key=lambda item: (-item[0], item[1].name))
        return [capability for _, capability in scored[:max(1, int(limit))]]

    def execute(self, name: str, arguments=None):
        capability = self.get(name)
        return capability.execute(arguments)
