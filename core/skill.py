from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillSpec:
    """Canonical metadata contract for a JARVIS skill."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    capabilities: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    risk: str = "low"
    dependencies: tuple[str, ...] = ()
    provenance: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class Skill:
    """Canonical skill contract.

    A Skill groups related capabilities/tools under one governed identity.
    Execution remains owned by the existing capability/tool runtime.
    """

    spec: SkillSpec

    def capabilities(self) -> tuple[str, ...]:
        return self.spec.capabilities

    def permissions(self) -> tuple[str, ...]:
        return self.spec.permissions

    def risk(self) -> str:
        return self.spec.risk

    def dependencies(self) -> tuple[str, ...]:
        return self.spec.dependencies

    def provenance(self) -> dict[str, Any]:
        return dict(self.spec.provenance)
