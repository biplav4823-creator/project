from copy import copy

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def build_effective_contract(capability, skill=None):
    """Return a policy copy combining capability and skill restrictions."""
    effective = copy(capability)
    capability_risk = capability.risk or "low"

    if capability_risk not in RISK_ORDER:
        raise ValueError(f"Unknown capability risk level: {capability_risk!r}")

    if capability.name == "run_python":
        capability_risk = "high"

    permissions = set(capability.permissions or [])
    effective_risk = capability_risk

    if skill is not None:
        skill_risk = skill.risk() or "low"
        if skill_risk not in RISK_ORDER:
            raise ValueError(f"Unknown skill risk level: {skill_risk!r}")

        permissions.update(skill.permissions() or [])
        if RISK_ORDER[skill_risk] > RISK_ORDER[effective_risk]:
            effective_risk = skill_risk

    effective.permissions = sorted(permissions)
    effective.risk = effective_risk
    return effective
