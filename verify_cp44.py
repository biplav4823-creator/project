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
            (ConnectionRefusedError(SECRET), "connection_refused", True, OUTCOME_NOT_STARTED),
            (TimeoutError(SECRET), "timeout", True, OUTCOME_UNKNOWN),
            (APITimeoutError(SECRET), "timeout", True, OUTCOME_UNKNOWN),
            (ConnectionResetError(SECRET), "connection", True, OUTCOME_UNKNOWN),
            (RateLimitError(SECRET), "throttled", True, OUTCOME_NOT_STARTED),
            (PermissionError(SECRET), "auth", False, OUTCOME_FAILED),
            (AuthenticationError(SECRET), "auth", False, OUTCOME_FAILED),
            (ValueError(SECRET), "invalid_input", False, OUTCOME_FAILED),
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
                    ConnectionRefusedError(SECRET), tool_idempotent=flag
                )
                self.assertIsInstance(decision, RecoveryDecision)
                self.assertEqual(decision.action, "RETRY")
                self.assertTrue(decision.retryable)
                self.assertEqual(decision.retry_policy, {"max_attempts": 1})

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
        self.assertEqual(decision.reason, "non_retryable_error")
        self.assertFalse(decision.human_intervention_required)

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
        failure = ToolFailure(classify(ConnectionRefusedError(SECRET)))
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
    """End to end through Agent with the REAL Recovery."""

    def make_agent(self, fn, name="calculate"):
        from core.agent import Agent
        from core.state_store import StateStore

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        agent = Agent()
        store = StateStore(str(Path(temporary.name) / "state.sqlite"))
        agent.orchestrator.state_store = store
        agent.register_tool(name, "cp44 test tool", fn, risk="low")
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
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))

    def test_connection_refused_is_retried_once_then_completes(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionRefusedError(SECRET)
            return "2"

        agent, store = self.make_agent(calculate)
        state = agent.run("calculate 1 + 1")

        self.assertEqual(state.status, "completed", state.status)
        self.assertEqual(calls["n"], 2)
        self.assertIn("recovery_retry", self.event_types(agent, state.job_id))
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))

    def test_timeout_on_non_idempotent_tool_is_not_auto_retried(self):
        calls = {"n": 0}

        def calculate(expression: str) -> str:
            calls["n"] += 1
            raise TimeoutError(SECRET)

        agent, store = self.make_agent(calculate)
        state = agent.run("calculate 1 + 1")

        self.assertEqual(state.status, "failed", state.status)
        self.assertEqual(calls["n"], 1)
        self.assertNotIn("recovery_retry", self.event_types(agent, state.job_id))
        self.assertNotIn(SECRET, self.dump(agent, store, state.job_id))


if __name__ == "__main__":
    unittest.main(verbosity=2)