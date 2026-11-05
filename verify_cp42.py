import unittest
from types import SimpleNamespace

from core.approval import ApprovalGate
from core.executor import Executor
from core.tool import CapabilityTool, Tool, ToolSpec
from core.tool_runtime import ToolExecutionResult, ToolRuntime


class Registry:
    def __init__(self, *tools):
        self.tools = {tool.spec.name: tool for tool in tools}

    def has(self, name):
        return name in self.tools

    def get_tool(self, name):
        return self.tools[name]

    def get(self, name):
        return self.tools[name]


class StubTool(Tool):
    def __init__(
        self, name="stub", risk="low", permissions=(),
        timeout_seconds=None, requires_approval=False
    ):
        self.spec = ToolSpec(
            name=name,
            risk=risk,
            permissions=tuple(permissions),
            timeout_seconds=timeout_seconds,
            requires_approval=requires_approval,
        )
        self.calls = 0

    def execute(self, arguments=None):
        self.calls += 1
        return {"ok": True, "arguments": arguments or {}}


class TimeoutAwareTool(StubTool):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.timeout_calls = []

    def execute_with_timeout(self, arguments=None, *, timeout_seconds):
        self.timeout_calls.append(timeout_seconds)
        self.calls += 1
        return {"timeout": timeout_seconds, "arguments": arguments or {}}


class CP42ToolRuntimeTests(unittest.TestCase):
    def runtime(self, tool):
        return ToolRuntime(Registry(tool))

    def test_low_risk_tool_executes(self):
        tool = StubTool()
        result = self.runtime(tool).execute("stub")
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(tool.calls, 1)

    def test_medium_and_high_risk_require_approval(self):
        for risk in ("medium", "high"):
            with self.subTest(risk=risk):
                tool = StubTool(risk=risk)
                result = self.runtime(tool).execute("stub")
                self.assertEqual(result.status, "approval_required")
                self.assertEqual(tool.calls, 0)

    def test_critical_risk_is_blocked(self):
        tool = StubTool(risk="critical")
        result = self.runtime(tool).execute("stub", approved=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(tool.calls, 0)

    def test_unknown_risk_fails_closed(self):
        tool = StubTool(risk="unclassified")
        result = self.runtime(tool).execute("stub", approved=True)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(tool.calls, 0)

    def test_missing_permission_grant_blocks_execution(self):
        tool = StubTool(permissions=("filesystem_read",))
        result = self.runtime(tool).execute("stub")
        self.assertEqual(result.status, "blocked")
        self.assertIn("filesystem_read", result.error)
        self.assertEqual(tool.calls, 0)

    def test_forbidden_permission_blocks_even_when_granted(self):
        tool = StubTool(permissions=("credential_access",))
        result = self.runtime(tool).execute(
            "stub", allowed_permissions=("credential_access",)
        )
        self.assertEqual(result.status, "blocked")
        self.assertEqual(tool.calls, 0)

    def test_run_python_is_never_treated_as_low_risk(self):
        tool = StubTool(name="run_python", risk="low")
        result = self.runtime(tool).execute("run_python")
        self.assertEqual(result.status, "approval_required")
        self.assertEqual(self.runtime(tool).risk("run_python"), "high")
        self.assertEqual(tool.calls, 0)

    def test_timeout_hook_is_used_when_timeout_is_configured(self):
        tool = TimeoutAwareTool(timeout_seconds=2.5)
        result = self.runtime(tool).execute("stub")
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(tool.timeout_calls, [2.5])
        self.assertEqual(tool.calls, 1)

    def test_missing_timeout_hook_fails_closed_without_execution(self):
        tool = StubTool(timeout_seconds=1.0)
        result = self.runtime(tool).execute("stub")
        self.assertEqual(result.status, "unsupported")
        self.assertEqual(tool.calls, 0)

    def test_executor_raises_for_non_success_status(self):
        class Runtime:
            def execute(self, name, arguments=None, **kwargs):
                return ToolExecutionResult(
                    name, "unsupported", error="timeout hook unavailable"
                )

        executor = Executor(runtime=Runtime())
        with self.assertRaisesRegex(RuntimeError, "timeout hook unavailable"):
            executor.execute(None, "stub", {})

    def test_capability_adapter_derives_approval_and_timeout_metadata(self):
        class Capability:
            name = "medium_capability"
            risk = "medium"
            permissions = ()

            def execute(self, arguments=None):
                return "ok"

        tool = CapabilityTool(Capability(), timeout_seconds=3.0)
        self.assertEqual(tool.spec.risk, "medium")
        self.assertTrue(tool.spec.requires_approval)
        self.assertEqual(tool.spec.timeout_seconds, 3.0)

    def test_explicit_approval_policy_reaches_approval_gate(self):
        capability = SimpleNamespace(name="special_tool", risk="low")
        decision = ApprovalGate(auto_approve=False).evaluate(
            capability, requires_approval=True
        )
        self.assertEqual(decision.action, "approve")


if __name__ == "__main__":
    unittest.main(verbosity=2)
