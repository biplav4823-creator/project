import unittest

from capabilities.capability import Capability
from core.approval import ApprovalGate
from core.guardrail import Guardrail
from core.interrupt import InterruptEngine
from core.skill import Skill, SkillSpec
from core.skill_manager import SkillManager
from core.skill_policy import build_effective_contract


def capability(name="demo", risk="low", permissions=None):
    return Capability(
        name=name,
        description="CP-33 verification",
        permissions=list(permissions or []),
        risk=risk,
    )


def make_skill(name="test-skill", risk="low", permissions=None, capabilities=()):
    instance = Skill()
    instance.spec = SkillSpec(
        name=name,
        risk=risk,
        permissions=tuple(permissions or ()),
        capabilities=tuple(capabilities),
    )
    return instance


class SkillPolicyTests(unittest.TestCase):
    def test_permission_merge_and_deduplication(self):
        result = build_effective_contract(
            capability(permissions=["filesystem_read", "network_access"]),
            make_skill(permissions=["network_access", "filesystem_write"]),
        )
        self.assertEqual(
            result.permissions,
            ["filesystem_read", "filesystem_write", "network_access"],
        )

    def test_skill_escalates_risk(self):
        self.assertEqual(
            build_effective_contract(capability(), make_skill(risk="high")).risk,
            "high",
        )

    def test_skill_cannot_lower_risk(self):
        self.assertEqual(
            build_effective_contract(
                capability(risk="high"), make_skill(risk="low")
            ).risk,
            "high",
        )

    def test_run_python_is_high_risk(self):
        self.assertEqual(
            build_effective_contract(
                capability(name="run_python"), make_skill()
            ).risk,
            "high",
        )

    def test_critical_risk_is_preserved(self):
        self.assertEqual(
            build_effective_contract(
                capability(risk="critical"), make_skill()
            ).risk,
            "critical",
        )

    def test_critical_run_python_risk_is_not_lowered(self):
        self.assertEqual(
            build_effective_contract(
                capability(name="run_python", risk="critical"),
                make_skill(),
            ).risk,
            "critical",
        )

    def test_unknown_capability_risk_fails_closed(self):
        with self.assertRaises(ValueError):
            build_effective_contract(capability(risk="unknown"))

    def test_unknown_skill_risk_fails_closed(self):
        with self.assertRaises(ValueError):
            build_effective_contract(
                capability(), make_skill(risk="unknown")
            )

    def test_empty_skill_permissions_preserve_capability_permissions(self):
        result = build_effective_contract(
            capability(permissions=["filesystem_read"]), make_skill()
        )
        self.assertEqual(result.permissions, ["filesystem_read"])

    def test_skill_permission_addition_does_not_mutate_original(self):
        original = capability(permissions=["filesystem_read"])
        result = build_effective_contract(
            original, make_skill(permissions=["network_access"])
        )
        self.assertEqual(
            result.permissions, ["filesystem_read", "network_access"]
        )
        self.assertEqual(original.permissions, ["filesystem_read"])

    def test_original_capability_is_unchanged(self):
        original = capability(permissions=["filesystem_read"])
        build_effective_contract(
            original,
            make_skill(risk="high", permissions=["network_access"]),
        )
        self.assertEqual(original.risk, "low")
        self.assertEqual(original.permissions, ["filesystem_read"])


class RealSkillContractTests(unittest.TestCase):
    def test_skill_manager_registers_and_resolves_real_skill(self):
        registry = type(
            "Registry", (),
            {"has": lambda self, name: name == "demo"},
        )()
        manager = SkillManager(registry)
        actual_skill = make_skill(capabilities=("demo",))
        manager.register(actual_skill)

        self.assertTrue(manager.has("test-skill"))
        self.assertIs(manager.get("test-skill"), actual_skill)
        self.assertEqual(
            manager.get_capability_names("test-skill"), ("demo",)
        )

    def test_skill_manager_rejects_missing_capability(self):
        registry = type("Registry", (), {"has": lambda self, name: False})()
        manager = SkillManager(registry)
        with self.assertRaises(ValueError):
            manager.register(make_skill(capabilities=("missing",)))

    def test_real_skill_policy_escalates_capability(self):
        actual_skill = make_skill(
            risk="high", permissions=["network_access"]
        )
        result = build_effective_contract(capability(), actual_skill)
        self.assertEqual(result.risk, "high")
        self.assertIn("network_access", result.permissions)


class GovernanceTests(unittest.TestCase):
    def test_skill_permission_reaches_guardrail(self):
        effective = build_effective_contract(
            capability(), make_skill(permissions=["system_admin"])
        )
        with self.assertRaises(PermissionError):
            Guardrail().check(effective, {})

    def test_escalated_risk_reaches_interrupt_engine(self):
        effective = build_effective_contract(
            capability(), make_skill(risk="high")
        )
        result = InterruptEngine().pre_execution(
            effective, step_id=1, arguments={}
        )
        self.assertTrue(result.interrupts)

    def test_escalated_risk_requires_approval(self):
        effective = build_effective_contract(
            capability(), make_skill(risk="high")
        )
        decision = ApprovalGate().evaluate(
            effective, step_id=1, arguments={}, interrupts=[]
        )
        self.assertNotEqual(decision.action, "allow")


if __name__ == "__main__":
    unittest.main(verbosity=2)
