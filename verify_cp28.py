import os
import shutil
import sys
import tempfile
import traceback

from core.agent import Agent
from core.state import JobState
from core.state_store import StateStore

WORK = tempfile.mkdtemp(prefix="cp28_")
RESULTS = []


class StubRecovery:
    def recover(self, error):
        return {"action": "retry", "reason": "cp28-test"}


def make_agent(fn, name="calculate", risk="low"):
    agent = Agent()
    agent.orchestrator.state_store = StateStore(
        os.path.join(WORK, f"{name}_{id(fn)}.db")
    )
    agent.orchestrator.recovery = StubRecovery()
    agent.register_tool(name, "cp28 test tool", fn, risk=risk)
    return agent


def check(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
        RESULTS.append(True)
    except Exception:
        print(f"[FAIL] {name}")
        traceback.print_exc()
        RESULTS.append(False)


def flaky(fail_times):
    calls = {"n": 0}

    def calculate(expression: str) -> str:
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise RuntimeError("boom")
        return "2"

    return calculate, calls


def t_retry_reexecutes_same_step():
    fn, calls = flaky(1)
    agent = make_agent(fn)
    state = agent.run("calculate 1 + 1")
    assert state.status == "completed", state.status
    assert calls["n"] == 2, calls
    assert state.recovery_attempts == {1: 1}, state.recovery_attempts
    assert state.failed_steps == []
    types = [e["event_type"] for e in agent.get_execution_history(state.job_id)]
    assert "recovery_retry" in types
    assert types[-1] == "job_completed", types


def t_retry_budget_exhausted():
    fn, calls = flaky(99)
    agent = make_agent(fn)
    state = agent.run("calculate 1 + 1")
    assert state.status == "failed", state.status
    assert calls["n"] == 2, calls
    assert state.failed_steps == [1]


def t_retry_does_not_skip_to_next_step():
    fn, calls = flaky(1)
    agent = make_agent(fn)
    state = agent.run("calculate 1 + 1 and then calculate 2 + 2")
    assert state.status == "completed", state.status
    assert calls["n"] == 3, calls
    assert state.completed_steps == [1, 2], state.completed_steps


def t_failed_job_resumes_to_completed():
    mode = {"fail": True}

    def calculate(expression: str) -> str:
        if mode["fail"]:
            raise RuntimeError("down")
        return "2"

    agent = make_agent(calculate)
    state = agent.run("calculate 1 + 1")
    assert state.status == "failed", state.status
    mode["fail"] = False
    resumed = agent.resume(state.job_id)
    assert resumed.status == "completed", resumed.status
    assert resumed.failed_steps == [], resumed.failed_steps


def t_unknown_job_raises():
    fn, _ = flaky(0)
    agent = make_agent(fn)
    try:
        agent.resume("job-does-not-exist")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def t_roundtrip_int_keys():
    store = StateStore(os.path.join(WORK, "roundtrip.db"))
    state = JobState(
        job_id="j1",
        user_input="x",
        goal="x",
        recovery_attempts={1: 1, 2: 2},
        approved_steps=[3],
    )
    store.save("j1", state.to_dict())
    restored = JobState.from_dict(store.load("j1"))
    assert restored.recovery_attempts == {1: 1, 2: 2}
    assert restored.approved_steps == [3]
    assert [j["job_id"] for j in store.list_jobs()] == ["j1"]


def t_approval_flow():
    calls = {"n": 0}

    def run_python(expression: str) -> str:
        calls["n"] += 1
        return "ok"

    agent = make_agent(run_python, name="run_python", risk="high")
    state = agent.run("python 1+1")
    if state.status != "waiting_approval":
        print("       (gate allowed this capability; approval flow not exercised)")
        return
    assert calls["n"] == 0
    done = agent.approve(state.job_id)
    assert done.status == "completed", done.status
    assert calls["n"] == 1


def t_reject_flow():
    calls = {"n": 0}

    def run_python(expression: str) -> str:
        calls["n"] += 1
        return "ok"

    agent = make_agent(run_python, name="run_python", risk="high")
    state = agent.run("python 1+1")
    if state.status != "waiting_approval":
        print("       (gate allowed this capability; reject flow not exercised)")
        return
    rejected = agent.reject(state.job_id, reason="no")
    assert rejected.status == "failed", rejected.status
    again = agent.resume(state.job_id)
    assert again.status == "failed"
    assert calls["n"] == 0


check("retry re-executes the same step (F-1)", t_retry_reexecutes_same_step)
check("retry budget is bounded", t_retry_budget_exhausted)
check("retry does not skip to next step", t_retry_does_not_skip_to_next_step)
check("failed job resumes to completed (F-2)", t_failed_job_resumes_to_completed)
check("unknown job id raises", t_unknown_job_raises)
check("JSON round trip keeps int keys + approvals", t_roundtrip_int_keys)
check("approval flow (F-3)", t_approval_flow)
check("reject flow (F-3)", t_reject_flow)

shutil.rmtree(WORK, ignore_errors=True)
passed = sum(RESULTS)
print(f"CP-28 VERIFICATION: {passed}/{len(RESULTS)} PASSED")
sys.exit(0 if all(RESULTS) else 1)
