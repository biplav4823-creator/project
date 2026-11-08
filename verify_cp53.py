"""CP-53: owner profile and policy decisions."""
import os
import tempfile
import unittest

from core.owner import OwnerPolicy, OwnerProfile


def policy(**over):
    base = {"budget_cap_usd": 10, "approval_at_or_above": "high"}
    base.update(over)
    return OwnerPolicy(OwnerProfile.from_dict(base))


class ProfileTests(unittest.TestCase):
    def test_roundtrip(self):
        p = OwnerProfile.from_dict({"budget_cap_usd": 5, "quiet_hours": [22, 6],
                                    "blocked_actions": ["wipe"]})
        self.assertEqual(OwnerProfile.from_dict(p.to_dict()), p)

    def test_validation(self):
        for bad in ({"budget_cap_usd": -1}, {"budget_cap_usd": True},
                    {"approval_at_or_above": "x"}, {"quiet_hours": [1]},
                    {"quiet_hours": [1, 30]}, {"interrupt_on": ["nope"]},
                    {"extra": 1}, "str"):
            with self.assertRaises(ValueError, msg=str(bad)):
                OwnerProfile.from_dict(bad)

    def test_load_from_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "o.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"budget_cap_usd": 3}')
            self.assertEqual(OwnerProfile.load(path).budget_cap_usd, 3.0)


class DecisionTests(unittest.TestCase):
    def test_low_risk_allowed(self):
        d = policy().decide({"name": "calc", "risk": "low"})
        self.assertEqual((d.allow, d.requires_approval, d.reason), (True, False, "allowed"))

    def test_risk_bar_requires_approval(self):
        d = policy().decide({"name": "x", "risk": "high"})
        self.assertTrue(d.allow and d.requires_approval)

    def test_missing_risk_fails_closed_to_approval(self):
        self.assertTrue(policy().decide({"name": "x"}).requires_approval)

    def test_blocked_action_denied(self):
        d = policy(blocked_actions=["wipe"]).decide({"name": "wipe", "risk": "low"})
        self.assertEqual((d.allow, d.reason), (False, "blocked_action"))

    def test_budget_is_cumulative(self):
        p = policy()
        self.assertTrue(p.decide({"name": "a", "risk": "low", "cost_usd": 4}, spent_usd=5).allow)
        d = p.decide({"name": "a", "risk": "low", "cost_usd": 6}, spent_usd=5)
        self.assertEqual(d.reason, "over_budget")

    def test_zero_budget_blocks_any_spend(self):
        d = policy(budget_cap_usd=0).decide({"name": "a", "risk": "low", "cost_usd": 0.01})
        self.assertFalse(d.allow)

    def test_invalid_cost_and_risk(self):
        self.assertEqual(policy().decide({"name": "a", "risk": "low", "cost_usd": "5"}).reason, "invalid_cost")
        self.assertEqual(policy().decide({"name": "a", "risk": "weird"}).reason, "unknown_risk")

    def test_path_scoping_blocks_traversal(self):
        with tempfile.TemporaryDirectory() as root:
            p = policy(allowed_dirs=[root])
            inside = os.path.join(root, "a.txt")
            self.assertTrue(p.decide({"name": "r", "risk": "low", "path": inside}).allow)
            escape = os.path.join(root, "..", "etc", "passwd")
            self.assertEqual(p.decide({"name": "r", "risk": "low", "path": escape}).reason,
                             "path_outside_allowed")

    def test_path_with_no_allowed_dirs_is_denied(self):
        self.assertFalse(policy().decide({"name": "r", "risk": "low", "path": "/x"}).allow)

    def test_quiet_hours_wraparound(self):
        p = policy(quiet_hours=[22, 6])
        self.assertTrue(p.decide({"name": "a", "risk": "low"}, hour=23).requires_approval)
        self.assertTrue(p.decide({"name": "a", "risk": "low"}, hour=3).requires_approval)
        self.assertFalse(p.decide({"name": "a", "risk": "low"}, hour=12).requires_approval)

    def test_interrupt_triggers(self):
        p = policy(interrupt_on=["spend_over_budget"])
        self.assertTrue(p.should_interrupt("spend_over_budget"))
        self.assertFalse(p.should_interrupt("external_message"))


if __name__ == "__main__":
    unittest.main(verbosity=2)