"""CP-47: evaluation harness. Offline; isolated temporary databases."""
import json
import unittest

from core.evals import (
    EvalTask,
    ToolSpec,
    Trial,
    builtin_tasks,
    run_suite,
)


class FakeState:
    def __init__(self, status):
        self.status = status


class FakeAgent:
    """Runs the first registered tool and reports a configured status."""

    def __init__(self, status="completed"):
        self.status = status
        self.tools = {}

    def register_tool(self, name, description, fn, risk="low", idempotent=False):
        self.tools[name] = fn

    def run(self, goal):
        for fn in self.tools.values():
            fn("x")
        return FakeState(self.status)


def fake_factory(status="completed"):
    return lambda db_path: FakeAgent(status)


def make_task(task_id, check, status="completed", max_calls=None, fn=None):
    def prepare():
        return Trial(
            tools=[ToolSpec("t", "d", fn or (lambda x: "ok"))],
            check=check,
        )

    return EvalTask(task_id, "goal", prepare, expect_status=status,
                    max_calls=max_calls)


class HarnessLogicTests(unittest.TestCase):
    def test_passing_task_has_pass_hat_k_one(self):
        task = make_task("p", lambda s, t: t.outputs == ["ok"])
        report = run_suite([task], k=3, agent_factory=fake_factory())
        self.assertEqual(report["summary"]["pass_hat_k"], 1.0)
        self.assertEqual(report["summary"]["pass_at_1"], 1.0)
        self.assertEqual(report["summary"]["false_success_rate"], 0.0)

    def test_completed_with_wrong_end_state_is_false_success(self):
        task = make_task("fs", lambda s, t: False)
        report = run_suite([task], k=2, agent_factory=fake_factory())
        self.assertEqual(report["summary"]["false_success_rate"], 1.0)
        self.assertEqual(report["summary"]["pass_hat_k"], 0.0)
        self.assertEqual(report["tasks"][0]["reasons"], ["end_state_mismatch"])

    def test_flaky_task_fails_pass_hat_k_but_keeps_pass_at_1(self):
        counter = {"n": 0}

        def prepare():
            counter["n"] += 1
            good = counter["n"] != 2
            return Trial(
                tools=[ToolSpec("t", "d", lambda x: "ok")],
                check=lambda s, t, good=good: good,
            )

        task = EvalTask("flaky", "goal", prepare)
        report = run_suite([task], k=3, agent_factory=fake_factory())
        self.assertFalse(report["tasks"][0]["pass_hat_k"])
        self.assertAlmostEqual(report["summary"]["pass_at_1"], 0.6667, places=3)

    def test_call_budget_is_enforced(self):
        def prepare():
            return Trial(
                tools=[ToolSpec("a", "d", lambda x: "ok"),
                       ToolSpec("b", "d", lambda x: "ok")],
                check=lambda s, t: True,
            )

        task = EvalTask("budget", "goal", prepare, max_calls=1)
        report = run_suite([task], k=1, agent_factory=fake_factory())
        self.assertEqual(report["tasks"][0]["reasons"], ["too_many_calls"])

    def test_unexpected_status_fails(self):
        task = make_task("st", lambda s, t: True, status="failed")
        report = run_suite([task], k=1, agent_factory=fake_factory("completed"))
        self.assertEqual(report["tasks"][0]["reasons"], ["unexpected_status"])

    def test_exception_is_recorded_without_leaking_text(self):
        def boom(x):
            raise RuntimeError("SECRET-123")

        task = make_task("boom", lambda s, t: True, fn=boom)
        report = run_suite([task], k=1, agent_factory=fake_factory())
        text = json.dumps(report)
        self.assertNotIn("SECRET-123", text)
        self.assertEqual(report["tasks"][0]["reasons"], ["exception"])

    def test_invalid_k_is_rejected(self):
        with self.assertRaises(ValueError):
            run_suite([], k=0)

    def test_report_is_json_serializable(self):
        task = make_task("j", lambda s, t: True)
        json.dumps(run_suite([task], k=1, agent_factory=fake_factory()))


class RealAgentSuiteTests(unittest.TestCase):
    def test_builtin_suite_is_reliable_on_the_real_agent(self):
        report = run_suite(builtin_tasks(), k=2)
        failing = [t for t in report["tasks"] if not t["pass_hat_k"]]
        self.assertEqual(failing, [], failing)
        self.assertEqual(report["summary"]["false_success_rate"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)