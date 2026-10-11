import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from core.approval import ApprovalGate
from core.guardrail import Guardrail
from core.interrupt import InterruptEngine
from core.main import create_agent
from core.state_store import StateStore


class RecordingGuardrail(Guardrail):
    def __init__(self):
        super().__init__(allow_medium=True, allow_high=True)
        self.seen = []

    def check(self, capability, arguments=None):
        self.seen.append((
            capability.name,
            capability.risk,
            tuple(capability.permissions or ()),
        ))
        return super().check(capability, arguments)


class RecordingInterruptEngine(InterruptEngine):
    def __init__(self):
        self.seen = []

    def pre_execution(self, capability, step_id=None, arguments=None):
        self.seen.append((capability.name, capability.risk))
        return super().pre_execution(capability, step_id, arguments)


class RecordingApprovalGate(ApprovalGate):
    def __init__(self):
        super().__init__()
        self.seen = []

    def evaluate(self, capability, step_id=None, arguments=None, interrupts=None):
        self.seen.append((capability.name, capability.risk))
        return super().evaluate(capability, step_id, arguments, interrupts)


class MismatchedSkillPlanner:
    def __init__(self, planner):
        self.planner = planner
        self.skill_manager = planner.skill_manager

    def plan(self, user_input):
        plan = self.planner.plan(user_input)
        plan["steps"][0]["skill"] = "data_science"
        return plan


class CP34SkillBoundaryTests(unittest.TestCase):
    def make_agent(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        agent = create_agent()
        store = StateStore(str(Path(temporary.name) / "state.sqlite"))
        agent.orchestrator.state_store = store
        return agent, store

    def only_job(self, store):
        jobs = store.list_jobs()
        self.assertEqual(len(jobs), 1)
        return jobs[0]

    def test_planned_skill_policy_reaches_all_governance_gates(self):
        agent, store = self.make_agent()

        skill = agent.skill_manager.get("mathematics")
        skill.spec = replace(skill.spec, risk="high")

        guardrail = RecordingGuardrail()
        interrupts = RecordingInterruptEngine()
        approval = RecordingApprovalGate()

        agent.orchestrator.guardrail = guardrail
        agent.orchestrator.interrupt_engine = interrupts
        agent.orchestrator.approval_gate = approval

        agent.run("calculate derivative of x^2")

        job = self.only_job(store)
        self.assertEqual(job["status"], "waiting_approval")
        self.assertEqual(job["goal"], "calculate derivative of x^2")

        state = store.load(job["job_id"])
        self.assertEqual(state["plan"][0]["skill"], "mathematics")

        self.assertEqual(guardrail.seen, [("derivative", "high", ())])
        self.assertEqual(interrupts.seen, [("derivative", "high")])
        self.assertEqual(approval.seen, [("derivative", "high")])

        event_types = [
            event["event_type"] for event in store.get_events(job["job_id"])
        ]
        self.assertIn("approval_requested", event_types)
        self.assertNotIn("execution_started", event_types)

    def test_skill_cannot_execute_an_undeclared_capability(self):
        agent, store = self.make_agent()
        agent.orchestrator.planner = MismatchedSkillPlanner(
            agent.orchestrator.planner
        )

        guardrail = RecordingGuardrail()
        agent.orchestrator.guardrail = guardrail

        agent.run("calculate derivative of x^2")

        job = self.only_job(store)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(guardrail.seen, [])

        events = store.get_events(job["job_id"])
        event_types = [event["event_type"] for event in events]

        self.assertNotIn("guardrail_checked", event_types)
        self.assertNotIn("execution_started", event_types)

        errors = [
            event["payload"].get("error", "")
            for event in events
            if event["event_type"] == "recovery_attempted"
        ]
        self.assertTrue(
            any("does not declare capability 'derivative'" in error
                for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
