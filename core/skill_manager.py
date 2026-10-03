from .skill import Skill


class SkillManager:
    """Canonical registry and lifecycle boundary for JARVIS skills."""

    def __init__(self, capability_registry=None):
        self._skills: dict[str, Skill] = {}
        self._capability_registry = capability_registry

    def register(self, skill: Skill):
        if not isinstance(skill, Skill):
            raise TypeError("SkillManager accepts Skill instances only.")

        name = skill.spec.name
        if not name:
            raise ValueError("Skill must define a non-empty name.")

        if name in self._skills:
            raise ValueError(f"Skill '{name}' is already registered.")

        if self._capability_registry is not None:
            missing = [
                capability
                for capability in skill.capabilities()
                if not self._capability_registry.has(capability)
            ]
            if missing:
                raise ValueError(
                    f"Skill '{name}' references unregistered capabilities: "
                    + ", ".join(missing)
                )

        self._skills[name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' is not registered.")
        return self._skills[name]

    def has(self, name: str) -> bool:
        return name in self._skills

    def list(self) -> list[str]:
        return sorted(self._skills.keys())

    def unregister(self, name: str):
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' is not registered.")
        del self._skills[name]

    def get_capability_names(self, name: str) -> tuple[str, ...]:
        return self.get(name).capabilities()

    def discover_capabilities(self, name: str):
        """Return registered Capability objects exposed by a Skill."""
        skill = self.get(name)

        if self._capability_registry is None:
            return []

        return [
            self._capability_registry.get(capability_name)
            for capability_name in skill.capabilities()
        ]

    def get_tools(self, name: str):
        """Return canonical Tool adapters exposed by a Skill."""
        skill = self.get(name)

        if self._capability_registry is None:
            return []

        return [
            self._capability_registry.get_tool(capability_name)
            for capability_name in skill.capabilities()
        ]
