from core.main import create_agent
from core.state import JobState, StepState


def check(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def test_registration():
    agent = create_agent()
    expected = {
        "job_inspect",
        "plan_validate",
        "dependency_inspect",
        "retry_policy",
        "execution_summary",
        "operational_diagnose",
    }
    assert expected.issubset(set(agent.capabilities.list()))


def test_job_inspect():
    agent = create_agent()
    state = JobState(
        job_id="cp18",
        user_input="test",
        goal="test",
        plan=[StepState(id=1, description="test")],
    )
    result = agent.tools.execute("job_inspect", {"state": state})
    assert result["job_id"] == "cp18"
    assert result["plan_steps"] == 1


def test_plan_validate():
    agent = create_agent()
    steps = [
        {"id": 1, "description": "first", "depends_on": []},
        {"id": 2, "description": "second", "depends_on": [1]},
    ]
    result = agent.tools.execute("plan_validate", {"steps": steps})
    assert result["valid"] is True
    assert result["step_count"] == 2


def test_dependency_inspect():
    agent = create_agent()
    steps = [
        {"id": 1, "depends_on": []},
        {"id": 2, "depends_on": [1]},
        {"id": 3, "depends_on": [2]},
    ]
    result = agent.tools.execute("dependency_inspect", {"steps": steps})
    assert result["roots"] == [1]
    assert result["leaves"] == [3]
    assert result["dependents"][1] == [2]


def test_retry_policy():
    agent = create_agent()
    result = agent.tools.execute(
        "retry_policy",
        {"attempts": 1, "max_attempts": 3, "error": "temporary"},
    )
    assert result["retry"] is True
    assert result["remaining"] == 2


def test_execution_summary():
    agent = create_agent()
    result = agent.tools.execute(
        "execution_summary",
        {
            "results": [
                {"step": 1, "result": 10},
                {"step": 2, "result": 20},
                {"step": 3, "error": "failure"},
            ]
        },
    )
    assert result["total"] == 3
    assert result["completed"] == 2
    assert result["failed"] == 1
    assert result["success_rate"] == 2 / 3


def test_operational_diagnose():
    agent = create_agent()
    state = JobState(
        job_id="cp18",
        user_input="test",
        goal="test",
        plan=[],
    )
    state.status = "failed"
    state.failed_steps = [1]
    result = agent.tools.execute("operational_diagnose", {"state": state})
    assert "job_failure" in result["issues"]
    assert "inspect_failed_step" in result["recommended_actions"]


def test_discovery():
    agent = create_agent()
    cases = [
        ("inspect job status", "job_inspect"),
        ("validate workflow plan", "plan_validate"),
        ("inspect dependency graph", "dependency_inspect"),
        ("retry policy", "retry_policy"),
        ("execution summary", "execution_summary"),
        ("diagnose job", "operational_diagnose"),
    ]
    for query, expected in cases:
        matches = agent.capabilities.discover(query, limit=3)
        assert matches, (query, matches)
        assert matches[0].name == expected, (
            query,
            [m.name for m in matches],
        )


def test_schemas():
    agent = create_agent()
    for name in [
        "job_inspect",
        "plan_validate",
        "dependency_inspect",
        "retry_policy",
        "execution_summary",
        "operational_diagnose",
    ]:
        capability = agent.capabilities.get(name)
        assert capability.input_schema.get("type") == "object"
        assert capability.output_schema.get("type") == "object"


def test_core_runtime():
    agent = create_agent()
    state = agent.run("calculate 25 + 15")
    assert state.status == "completed"


def main():
    tests = [
        ("registration", test_registration),
        ("job inspection", test_job_inspect),
        ("plan validation", test_plan_validate),
        ("dependency inspection", test_dependency_inspect),
        ("retry policy", test_retry_policy),
        ("execution summary", test_execution_summary),
        ("operational diagnosis", test_operational_diagnose),
        ("capability discovery", test_discovery),
        ("capability schemas", test_schemas),
        ("core runtime regression", test_core_runtime),
    ]
    passed = sum(check(name, fn) for name, fn in tests)
    print(f"CP-18 AGENTIC-OPS TESTS: {passed}/{len(tests)} PASSED")
    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
