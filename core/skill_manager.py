from .skill import Skill


class SkillManager:
    """Canonical registry and lifecycle boundary for JARVIS skills."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        if not isinstance(skill, Skill):
            raise TypeError("SkillManager accepts Skill instances only.")

        name = skill.spec.name
        if not name:
            raise ValueError("Skill must define a non-empty name.")

        if name in self._skills:
            raise ValueError(f"Skill '{name}' is already registered.")

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
