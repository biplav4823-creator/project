"""CP-46: operator reconciliation of uncertain executions. Offline."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from core.reconcile import ReconciliationError, blocked_executions, list_blocked, main, reconcile

SECRET = "SECRET-123-token"


class CP46ReconcileTests(unittest.TestCase):
    def make_agent(self, fn, name="calculate"):
        from core.agent import Agent
        from core.state_store import StateStore

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = str(Path(temporary.name) / "state.sqlite")

        agent = Agent()
        store = StateStore(self.db)
        agent.orchestrator.state_store = store
        agent.register_tool(name, "cp46 test tool", fn, risk="low")
        return agent, store

    def blocked_job(self, succeed_after=True):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError(SECRET)
            return "2"

        agent, store = self.make_agent(calculate)
        state = agent.run("calculate 1 + 1")
        self.assertEqual(store.load(state.job_id)["status"], "failed")
        self.assertEqual(calls["n"], 1)
        return agent, store, state.job_id, calls

    def event_types(self, store, job_id):
        return [e["event_type"] for e in store.get_events(job_id)]

    def test_blocked_job_is_listed(self):
        agent, store, job_id, _ = self.blocked_job()
        rows = list_blocked(store)
        self.assertEqual([r["job_id"] for r in rows], [job_id])
        self.assertEqual(rows[0]["blocked"][0]["status"], "UNKNOWN")
        with self.assertRaisesRegex(RuntimeError, "manual reconciliation"):
            agent.resume(job_id)

    def test_not_started_outcome_unblocks_and_reruns_step(self):
        agent, store, job_id, calls = self.blocked_job()
        reconcile(store, job_id, 1, "not_started", "confirmed no side effect", operator="tester")
        self.assertEqual(blocked_executions(store.load(job_id)), [])

        agent.resume(job_id)

        self.assertEqual(calls["n"], 2)
        self.assertEqual(store.load(job_id)["status"], "completed")
        self.assertIn("execution_reconciled", self.event_types(store, job_id))
        self.assertEqual(list_blocked(store), [])

    def test_succeeded_outcome_reuses_recorded_result_without_rerun(self):
        agent, store, job_id, calls = self.blocked_job()
        reconcile(store, job_id, 1, "succeeded", "verified in provider console", result="2", operator="tester")

        agent.resume(job_id)

        self.assertEqual(calls["n"], 1)
        self.assertEqual(store.load(job_id)["status"], "completed")
        self.assertIn("execution_reused", self.event_types(store, job_id))

    def test_validation_errors(self):
        agent, store, job_id, _ = self.blocked_job()
        with self.assertRaises(ReconciliationError):
            reconcile(store, job_id, 1, "not_started", "   ")
        with self.assertRaises(ReconciliationError):
            reconcile(store, job_id, 1, "maybe", "note")
        with self.assertRaises(ReconciliationError):
            reconcile(store, job_id, 1, "succeeded", "note")
        with self.assertRaises(ReconciliationError):
            reconcile(store, job_id, 99, "failed", "note")
        with self.assertRaises(ReconciliationError):
            reconcile(store, "no-such-job", 1, "failed", "note")
        self.assertEqual(len(list_blocked(store)), 1)

    def test_audit_event_never_contains_secret_or_result(self):
        agent, store, job_id, _ = self.blocked_job()
        reconcile(store, job_id, 1, "succeeded", "checked manually", result="RESULT-VALUE", operator="tester")
        events = json.dumps(store.get_events(job_id), default=str)
        self.assertNotIn(SECRET, events)
        self.assertNotIn("RESULT-VALUE", events)

    def test_cli_list_and_resolve(self):
        agent, store, job_id, _ = self.blocked_job()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["--db", self.db, "list"]), 0)
        self.assertIn(job_id, out.getvalue())

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--db", self.db, "resolve", job_id, "--step", "1",
                         "--outcome", "not_started", "--note", "cli test"])
        self.assertEqual(code, 0)
        self.assertEqual(list_blocked(store), [])

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main(["--db", self.db, "resolve", job_id, "--step", "1",
                         "--outcome", "failed", "--note", "again"])
        self.assertEqual(code, 1)


    def test_malformed_state_rows_are_skipped(self):
        import tempfile
        from core.state_store import StateStore

        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(str(Path(directory) / "state.sqlite"))
            store.save("bad-row", "just a string")
            store.save("ok-row", {"status": "completed", "goal": "g", "plan": []})
            self.assertEqual([j["job_id"] for j in store.list_jobs()], ["ok-row"])
            self.assertEqual(list_blocked(store), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)