
import sys

from core.agent import Agent
from core.main import create_agent
from core.schema import SchemaError, validate
from core.state import JobState


results = []


def check(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
        results.append(True)
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        results.append(False)


def result_value(state, step_id):
    for item in state.intermediate_results:
        if item.get("step") == step_id and "result" in item:
            value = item["result"]
            if isinstance(value, dict) and "result" in value:
                return value["result"]
            return value
    return None


def cp10_regression():
    agent = create_agent()

    state = agent.run("calculate 25 + 15")
    assert isinstance(state, JobState)
    assert state.status == "completed"
    assert result_value(state, 1) == "40"

    state = agent.run("find the determinant of matrix [[1,2],[3,4]]")
    assert state.status == "completed"
    assert result_value(state, 1) == "-2"

    state = agent.run("find the inverse of matrix [[1,2],[3,4]]")
    assert state.status == "completed"
    assert "Matrix([[-2, 1], [3/2, -1/2]])" == result_value(state, 1)

    state = agent.run("find the rank of matrix [[1,2],[3,4]]")
    assert state.status == "completed"
    assert result_value(state, 1) == "2"


def cp11_independent():
    agent = create_agent()
    state = agent.run("calculate 25 + 15 and then calculate 10 + 5")

    assert state.status == "completed"
    assert state.completed_steps == [1, 2]
    assert state.plan[0].depends_on == []
    assert state.plan[1].depends_on == [1]
    assert result_value(state, 1) == "40"
    assert result_value(state, 2) == "15"


def cp11_dependency():
    agent = create_agent()
    state = agent.run(
        "calculate 25 + 15 and then multiply the result by 2"
    )

    assert state.status == "completed", state
    assert state.completed_steps == [1, 2], state
    assert state.plan[1].depends_on == [1]
    assert result_value(state, 1) == "40"
    assert result_value(state, 2) == "80"


def reference_resolution():
    agent = create_agent()
    orch = agent.orchestrator

    previous = [
        {
            "step": 1,
            "result": {
                "verified": True,
                "result": "40",
            },
        }
    ]

    assert orch._resolve_references(
        "calculate $step1.result + 2",
        previous,
    ) == "calculate 40 + 2"

    assert orch._resolve_references(
        "calculate the previous result + 2",
        previous,
    ) == "calculate 40 + 2"

    assert orch._resolve_references(
        "calculate the result + 2",
        previous,
    ) == "calculate 40 + 2"


def discovery():
    agent = create_agent()

    cases = [
        ("calculate 25 + 15", "calculate"),
        ("find the determinant of matrix [[1,2],[3,4]]", "matrix_determinant"),
        ("find the inverse of matrix [[1,2],[3,4]]", "matrix_inverse"),
        ("find the rank of matrix [[1,2],[3,4]]", "matrix_rank"),
        ("multiply the result by 2", "calculate"),
    ]

    for query, expected in cases:
        matches = agent.capabilities.discover(query, limit=3)
        assert matches, (query, matches)
        assert matches[0].name == expected, (query, [m.name for m in matches])

    assert agent.capabilities.discover(
        "tell me a story about a dragon",
        limit=3,
    ) == []


def contracts():
    agent = create_agent()

    names = agent.capabilities.list()

    expected = {"calculate","definite_integral","derivative","expand","factor","integral","limit","matrix_determinant","matrix_inverse","matrix_rank","nth_derivative","numerical","run_python","series","simplify","solve_equation","solve_system"}; assert expected.issubset(set(names)), sorted(expected - set(names))

    for name in names:
        capability = agent.capabilities.get(name)

        assert capability.input_schema.get("type") == "object", name
        if name in expected: assert capability.output_schema.get("type") == "string", name


def schema_rejection():
    try:
        validate(
            {"x": 123},
            {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        )
        raise AssertionError("wrong property type accepted")
    except SchemaError:
        pass

    try:
        validate(
            {"x": "ok", "y": "bad"},
            {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
                "additionalProperties": False,
            },
        )
        raise AssertionError("unknown property accepted")
    except SchemaError:
        pass

    try:
        validate(
            {},
            {
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        )
        raise AssertionError("missing required property accepted")
    except SchemaError:
        pass

    agent = create_agent()

    try:
        agent.capabilities.get("calculate").validate_output(123)
        raise AssertionError("invalid output accepted")
    except SchemaError:
        pass


def main():
    print("=" * 60)
    print("CP-10 / CP-11 / CP-12 REAL VERIFICATION")
    print("=" * 60)

    check("CP-10 regression: four core mathematical operations", cp10_regression)
    check("CP-11: independent multi-step", cp11_independent)
    check("CP-11: dependency dataflow 40 -> 80", cp11_dependency)
    check("CP-11: reference resolution", reference_resolution)
    check("CP-11/CP-12: capability discovery", discovery)
    check("CP-12 capability contracts", contracts)
    check("CP-12: schema rejection", schema_rejection)

    print("=" * 60)

    total = len(results)
    passed = sum(results)

    print(f"RESULT: {passed}/{total} checks passed")
    print("=" * 60)

    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
