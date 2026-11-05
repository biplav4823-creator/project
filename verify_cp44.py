"""CP-44 (Part A): typed, redacted errors and safe recovery decisions.

Offline. Every stateful test uses a temporary database. Integration tests use
the real ``Recovery`` (not a stub) so the runtime -> executor -> recovery
chain is exercised end to end.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from core.errors import (
    ErrorInfo,
    ExecutionNotStartedError,
    OUTCOME_FAILED,
    OUTCOME_NOT_STARTED,
    OUTCOME_UNKNOWN,
    ToolFailure,
    classify,
)
from core.executor import Executor
from core.recovery import Recovery, RecoveryDecision

SECRET = "SECRET-123-token"


class APITimeoutError(Exception):
    """Provider-style timeout that does not inherit from TimeoutError."""


class RateLimitError(Exception):
    pass


class AuthenticationError(Exception):
    pass


class ClassificationTests(unittest.TestCase):
    def test_classification_table(self):
        cases = [
            (ConnectionRefusedError(SECRET), "connection_refused", True, OUTCOME_UNKNOWN),
            (TimeoutError(SECRET), "timeout", True, OUTCOME_UNKNOWN),
            (APITimeoutError(SECRET), "timeout", True, OUTCOME_UNKNOWN),
            (ConnectionResetError(SECRET), "connection", True, OUTCOME_UNKNOWN),
            (RateLimitError(SECRET), "throttled", True, OUTCOME_UNKNOWN),
            (PermissionError(SECRET), "auth", False, OUTCOME_UNKNOWN),
            (AuthenticationError(SECRET), "auth", False, OUTCOME_UNKNOWN),
            (ValueError(SECRET), "invalid_input", False, OUTCOME_UNKNOWN),
            (RuntimeError(SECRET), "tool_error", False, OUTCOME_UNKNOWN),
            (ZeroDivisionError(SECRET), "tool_error", False, OUTCOME_UNKNOWN),
        ]
        for exc, code, retryable, outcome in cases:
            with self.subTest(exc=type(exc).__name__):
                info = classify(exc)
                self.assertEqual(info.code, code)
                self.assertEqual(info.retryable, retryable)
                self.assertEqual(info.outcome, outcome)
                self.assertNotIn(SECRET, info.message)
                self.assertIn(type(exc).__name__, info.message)

    def test_cause_is_not_followed(self):
        # A wrapper must not inherit the retryability of what it wraps
        # (e.g. "Verification failed due to verifier error" from TimeoutError).
        try:
            try:
                raise TimeoutError("inner")
            except TimeoutError as inner:
                raise RuntimeError("wrapper") from inner
        except RuntimeError as wrapped:
            info = classify(wrapped)

        self.assertEqual(info.code, "tool_error")
        self.assertFalse(info.retryable)

    def test_tool_failure_round_trip(self):
        info = classify(TimeoutError(SECRET))
        failure = ToolFailure(info, detail=SECRET)
        self.assertIsInstance(failure, RuntimeError)
        self.assertEqual(str(failure), info.message)
        self.assertIs(classify(failure), info)
        self.assertIsNone(failure.detail)  # raw detail is opt-in only

    def test_invalid_outcome_rejected(self):
        with self.assertRaises(ValueError):
            ErrorInfo("x", False, "maybe", "m")


class RecoveryDecisionTests(unittest.TestCase):
    def setUp(self):
        self.recovery = Recovery()

    def test_not_started_is_retried_even_if_not_idempotent(self):
        for flag in (None, False, True):
            with self.subTest(tool_idempotent=flag):
                decision = self.recovery.recover(
                    ExecutionNotStartedError(SECRET), tool_idempotent=flag
                )
                self.assertIsInstance(decision, RecoveryDecision)
                self.assertEqual(decision.action, "RETRY")
                self.assertTrue(decision.retryable)
                self.assertEqual(decision.retry_policy, {"max_attempts": 1})

    def test_connection_refused_is_unknown_and_requires_idempotency(self):
        held = self.recovery.recover(ConnectionRefusedError(SECRET))
        self.assertEqual(held.action, "ABORT")
        self.assertTrue(held.human_intervention_required)
        retried = self.recovery.recover(
            ConnectionRefusedError(SECRET), tool_idempotent=True
        )
        self.assertEqual(retried.action, "RETRY")

    def test_unknown_outcome_requires_idempotency_to_retry(self):
        retried = self.recovery.recover(TimeoutError(SECRET), tool_idempotent=True)
        self.assertEqual(retried.action, "RETRY")

        for flag in (None, False):
            with self.subTest(tool_idempotent=flag):
                held = self.recovery.recover(
                    TimeoutError(SECRET), tool_idempotent=flag
                )
                self.assertEqual(held.action, "ABORT")
                self.assertFalse(held.retryable)
                self.assertTrue(held.human_intervention_required)
                self.assertEqual(held.reason, "outcome_unknown")

    def test_non_retryable_aborts_without_human_flag(self):
        decision = self.recovery.recover(ValueError(SECRET))
        self.assertEqual(decision.action, "ABORT")
        self.assertEqual(decision.reason, "outcome_unknown")
        self.assertTrue(decision.human_intervention_required)

    def test_metadata_is_redacted_by_default(self):
        decision = self.recovery.recover(TimeoutError(SECRET))
        self.assertNotIn(SECRET, json.dumps(decision.metadata))
        self.assertEqual(decision.metadata["error_code"], "timeout")
        self.assertEqual(decision.metadata["outcome"], OUTCOME_UNKNOWN)

    def test_debug_mode_exposes_detail_only_when_enabled(self):
        previous = os.environ.get("JARVIS_DEBUG_ERRORS")
        os.environ["JARVIS_DEBUG_ERRORS"] = "1"
        try:
            decision = self.recovery.recover(TimeoutError(SECRET))
            self.assertIn(SECRET, decision.metadata["error_detail"])
        finally:
            if previous is None:
                os.environ.pop("JARVIS_DEBUG_ERRORS", None)
            else:
                os.environ["JARVIS_DEBUG_ERRORS"] = previous

    def test_recovery_accepts_tool_failure(self):
        failure = ToolFailure(classify(ExecutionNotStartedError(SECRET)))
        self.assertEqual(self.recovery.recover(failure).action, "RETRY")


class _Result:
    def __init__(self, status, result=None, error=None, error_info=None):
        self.status = status
        self.result = result
        self.error = error
        self.error_info = error_info


class _Runtime:
    def __init__(self, result):
        self._result = result

    def execute(self, name, arguments, **kwargs):
        return self._result


class ExecutorTests(unittest.TestCase):
    def test_success_returns_result(self):
        executor = Executor(_Runtime(_Result("succeeded", result="2")))
        self.assertEqual(executor.execute(None, "calculate", {}), "2")

    def test_failure_preserves_error_info(self):
        info = classify(TimeoutError(SECRET))
        executor = Executor(
            _Runtime(_Result("failed", error=info.message, error_info=info))
        )
        with self.assertRaises(ToolFailure) as caught:
            executor.execute(None, "calculate", {})
        self.assertIs(caught.exception.info, info)
        self.assertNotIn(SECRET, str(caught.exception))

    def test_policy_block_is_not_started_and_keeps_message(self):
        message = "Tool 'x' is critical risk and is blocked."
        executor = Executor(_Runtime(_Result("blocked", error=message)))
        with self.assertRaises(ToolFailure) as caught:
            executor.execute(None, "x", {})
        info = caught.exception.info
        self.assertEqual(info.code, "blocked")
        self.assertEqual(info.outcome, OUTCOME_NOT_STARTED)
        self.assertFalse(info.retryable)
        self.assertEqual(str(caught.exception), message)

    def test_bare_failed_status_is_unknown_outcome(self):
        executor = Executor(_Runtime(_Result("failed")))
        with self.assertRaises(ToolFailure) as caught:
            executor.execute(None, "x", {})
        self.assertEqual(caught.exception.info.outcome, OUTCOME_UNKNOWN)

    def test_legacy_path_without_runtime_propagates_raw_exception(self):
        class Registry:
            def execute(self, name, arguments):
                raise TimeoutError("raw")

        with self.assertRaises(TimeoutError):
            Executor().execute(Registry(), "x", {})


class AgentIntegrationTests(unittest.TestCase):
    """End-to-end tests through Agent, CapabilityTool, runtime and Recovery."""

    def make_agent(self, fn, name="calculate", idempotent=False):
        from core.agent import Agent
        from core.state_store import StateStore

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        agent = Agent()
        store = StateStore(str(Path(temporary.name) / "state.sqlite"))
        agent.orchestrator.state_store = store
        agent.register_tool(
            name, "cp44 test tool", fn, risk="low", idempotent=idempotent
        )
        return agent, store

    def dump(self, agent, store, job_id):
        events = agent.get_execution_history(job_id)
        return json.dumps(
            {"state": store.load(job_id), "events": events}, default=str
        )

    def event_types(self, agent, job_id):
        return [e["event_type"] for e in agent.get_execution_history(job_id)]

    def test_invalid_input_is_not_retried_and_secret_never_persisted(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            raise ValueError(SECRET)

        agent, store = self.make_agent(calculate)
        state = agent.run("calculate 1 + 1")

        self.assertEqual(state.status, "failed", state.status)
        self.assertEqual(calls["n"], 1)
        self.assertNotIn("recovery_retry", self.event_types(agent, state.job_id))
        self.assertEqual(store.load(state.job_id)["executions"][-1]["status"], "UNKNOWN")
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))

    def test_connection_refused_retries_once_for_idempotent_tool(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionRefusedError(SECRET)
            return "2"

        agent, store = self.make_agent(calculate, idempotent=True)
        state = agent.run("calculate 1 + 1")

        self.assertEqual(state.status, "completed", state.status)
        self.assertEqual(calls["n"], 2)
        self.assertIn("recovery_retry", self.event_types(agent, state.job_id))
        self.assertEqual(
            [item["status"] for item in store.load(state.job_id)["executions"]],
            ["UNKNOWN", "SUCCEEDED"],
        )
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))

    def test_timeout_on_non_idempotent_tool_is_unknown_and_blocks_resume(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            raise TimeoutError(SECRET)

        agent, store = self.make_agent(calculate)
        state = agent.run("calculate 1 + 1")

        self.assertEqual(state.status, "failed", state.status)
        self.assertEqual(calls["n"], 1)
        self.assertNotIn("recovery_retry", self.event_types(agent, state.job_id))
        self.assertEqual(store.load(state.job_id)["executions"][-1]["status"], "UNKNOWN")
        self.assertIn("execution_unknown", self.event_types(agent, state.job_id))
        with self.assertRaisesRegex(RuntimeError, "manual reconciliation"):
            agent.resume(state.job_id)
        self.assertEqual(calls["n"], 1)
        self.assertIn(
            "resume_blocked_uncertain_execution",
            self.event_types(agent, state.job_id),
        )
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))

    def test_timeout_on_idempotent_tool_retries_once_and_completes(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError(SECRET)
            return "2"

        agent, store = self.make_agent(calculate, idempotent=True)
        state = agent.run("calculate 1 + 1")

        self.assertEqual(state.status, "completed", state.status)
        self.assertEqual(calls["n"], 2)
        self.assertIn("recovery_retry", self.event_types(agent, state.job_id))
        self.assertEqual(
            [item["status"] for item in store.load(state.job_id)["executions"]],
            ["UNKNOWN", "SUCCEEDED"],
        )
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))

    def test_resume_blocks_persisted_running_execution(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            raise TimeoutError(SECRET)

        agent, store = self.make_agent(calculate)
        state = agent.run("calculate 1 + 1")
        persisted = store.load(state.job_id)
        persisted["executions"][-1]["status"] = "RUNNING"
        store.save(state.job_id, persisted)

        with self.assertRaisesRegex(RuntimeError, "manual reconciliation"):
            agent.resume(state.job_id)
        self.assertEqual(calls["n"], 1)
        self.assertIn(
            "resume_blocked_uncertain_execution",
            self.event_types(agent, state.job_id),
        )



    def reject_once_verifier(self):
        from core.verifier import Verifier

        class RejectOnce:
            def __init__(self):
                self.real = Verifier()
                self.calls = 0

            def verify(self, result, *args, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    return {
                        "verified": False,
                        "status": "failed",
                        "reason": "CP-44 intentional first-pass rejection",
                        "result": result,
                    }
                return self.real.verify(result, *args, **kwargs)

        return RejectOnce()

    def test_resume_reuses_succeeded_execution_without_rerunning_tool(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            return "2"

        agent, store = self.make_agent(calculate)
        agent.orchestrator.verifier = self.reject_once_verifier()
        state = agent.run("calculate 1 + 1")
        self.assertEqual(store.load(state.job_id)["status"], "failed")
        self.assertEqual(calls["n"], 1)

        agent.resume(state.job_id)

        self.assertEqual(calls["n"], 1)
        self.assertEqual(store.load(state.job_id)["status"], "completed")
        self.assertIn("execution_reused", self.event_types(agent, state.job_id))
        self.assertEqual(
            [e["status"] for e in store.load(state.job_id)["executions"]],
            ["SUCCEEDED", "SUCCEEDED"],
        )

    def test_later_success_supersedes_unknown_execution_on_resume(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TimeoutError(SECRET)
            return "2"

        agent, store = self.make_agent(calculate, idempotent=True)
        agent.orchestrator.verifier = self.reject_once_verifier()
        state = agent.run("calculate 1 + 1")
        self.assertEqual(store.load(state.job_id)["status"], "failed")
        self.assertEqual(calls["n"], 2)

        agent.resume(state.job_id)

        self.assertEqual(calls["n"], 2)
        self.assertEqual(store.load(state.job_id)["status"], "completed")
        self.assertEqual(
            [e["status"] for e in store.load(state.job_id)["executions"]],
            ["UNKNOWN", "SUCCEEDED", "SUCCEEDED"],
        )
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)