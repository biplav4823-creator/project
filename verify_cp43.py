import tempfile
import unittest
from pathlib import Path

from core.main import create_agent
from core.state_store import StateStore


class RejectingVerifier:
    def verify(self, result):
        return {
            "verified": False,
            "status": "failed",
            "reason": "CP-43 intentional test rejection",
            "result": result,
        }


class CP43ExecutionVerificationTests(unittest.TestCase):
    def make_agent(self, verifier=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        agent = create_agent()
        store = StateStore(str(Path(temporary.name) / "state.sqlite"))
        agent.orchestrator.state_store = store

        if verifier is not None:
            agent.orchestrator.verifier = verifier

        return agent, store

    def one_job(self, store):
        jobs = store.list_jobs()
        self.assertEqual(len(jobs), 1)
        return jobs[0]

    def test_execution_success_is_separate_from_verification(self):
        agent, store = self.make_agent()
        agent.run("calculate derivative of x^2")

        job = self.one_job(store)
        self.assertEqual(job["status"], "completed")

        state = store.load(job["job_id"])
        self.assertTrue(state["executions"])
        self.assertEqual(state["executions"][-1]["status"], "SUCCEEDED")

        event_types = [
            event["event_type"] for event in store.get_events(job["job_id"])
        ]
        self.assertIn("verification_completed", event_types)
        self.assertIn("execution_completed", event_types)
        self.assertLess(
            event_types.index("execution_completed"),
            event_types.index("verification_completed"),
        )

    def test_verification_failure_preserves_invocation_success(self):
        agent, store = self.make_agent(RejectingVerifier())
        agent.run("calculate derivative of x^2")

        job = self.one_job(store)
        self.assertEqual(job["status"], "failed")

        state = store.load(job["job_id"])
        self.assertTrue(state["executions"])
        self.assertEqual(
            state["executions"][-1]["status"],
            "SUCCEEDED",
            state["executions"],
        )

        events = store.get_events(job["job_id"])
        event_types = [event["event_type"] for event in events]
        self.assertIn("verification_failed", event_types)
        self.assertIn("execution_completed", event_types)
        self.assertNotIn("execution_failed", event_types)
        self.assertNotIn("verification_completed", event_types)
        self.assertNotIn("recovery_retry", event_types)


    def test_verifier_timeout_does_not_retry_completed_invocation(self):
        class TimeoutVerifier:
            def verify(self, result):
                raise TimeoutError("simulated verifier timeout")

        agent, store = self.make_agent(TimeoutVerifier())
        agent.run("calculate derivative of x^2")

        job = self.one_job(store)
        self.assertEqual(job["status"], "failed")

        events = store.get_events(job["job_id"])
        event_types = [event["event_type"] for event in events]
        self.assertIn("execution_completed", event_types)
        self.assertIn("verification_failed", event_types)
        self.assertNotIn("execution_failed", event_types)
        self.assertNotIn("recovery_retry", event_types)

        state = store.load(job["job_id"])
        self.assertEqual(
            sum(e == "execution_completed" for e in event_types),
            len(state["executions"]),
            state["executions"],
        )

if __name__ == "__main__":
    unittest.main(verbosity=2)
