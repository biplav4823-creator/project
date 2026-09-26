from core.main import create_agent
from core.state import JobState


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
        "csv_parse",
        "csv_serialize",
        "schema_inspect",
        "data_validate",
        "data_transform",
        "data_aggregate",
    }
    names = set(agent.capabilities.list())
    assert expected.issubset(names), sorted(expected - names)
    assert len(names) >= 27, sorted(names)


def test_csv():
    agent = create_agent()
    rows = agent.tools.execute(
        "csv_parse",
        {"text": "name,age\nAlice,20\nBob,30\n"},
    )
    assert rows == [
        {"name": "Alice", "age": "20"},
        {"name": "Bob", "age": "30"},
    ]

    csv_text = agent.tools.execute(
        "csv_serialize",
        {"rows": [{"name": "Alice", "age": "20"}, {"name": "Bob", "age": "30"}]},
    )
    assert csv_text == "name,age\nAlice,20\nBob,30\n"


def test_schema():
    agent = create_agent()
    rows = [
        {"name": "Alice", "age": 20},
        {"name": "Bob", "age": 30},
        {"name": "Cara", "age": None},
    ]
    result = agent.tools.execute("schema_inspect", {"rows": rows})
    assert result["row_count"] == 3
    assert result["column_count"] == 2
    assert result["columns"]["age"]["type"] == "number"
    assert result["columns"]["age"]["null_count"] == 1


def test_validation():
    agent = create_agent()
    rows = [
        {"name": "Alice", "age": 20},
        {"name": "Bob", "age": "bad"},
    ]
    result = agent.tools.execute(
        "data_validate",
        {
            "rows": rows,
            "schema": {
                "name": {"type": "string", "required": True},
                "age": {"type": "number", "required": True},
            },
        },
    )
    assert result["valid"] is False
    assert result["error_count"] == 1
    assert result["errors"][0]["row"] == 1


def test_transform():
    agent = create_agent()
    rows = [
        {"name": "Alice", "city": "Kathmandu", "age": 20},
        {"name": "Bob", "city": "Pokhara", "age": 25},
        {"name": "Cara", "city": "Kathmandu", "age": None},
    ]
    result = agent.tools.execute(
        "data_transform",
        {
            "rows": rows,
            "operations": [
                {"action": "filter_equals", "column": "city", "value": "Kathmandu"},
                {"action": "drop_nulls", "columns": ["age"]},
                {"action": "rename", "mapping": {"name": "person"}},
                {"action": "select", "columns": ["person", "age"]},
            ],
        },
    )
    assert result == [{"person": "Alice", "age": 20}]


def test_aggregate():
    agent = create_agent()
    rows = [
        {"city": "Kathmandu", "sales": 10},
        {"city": "Kathmandu", "sales": 20},
        {"city": "Pokhara", "sales": 30},
    ]
    result = agent.tools.execute(
        "data_aggregate",
        {
            "rows": rows,
            "group_by": ["city"],
            "aggregations": {
                "count": {"column": "sales", "operation": "count"},
                "total": {"column": "sales", "operation": "sum"},
                "average": {"column": "sales", "operation": "mean"},
            },
        },
    )
    result = sorted(result, key=lambda item: item["city"])
    assert result == [
        {"city": "Kathmandu", "count": 2, "total": 30, "average": 15},
        {"city": "Pokhara", "count": 1, "total": 30, "average": 30},
    ]


def test_discovery():
    agent = create_agent()
    cases = [
        ("parse csv data", "csv_parse"),
        ("serialize records to csv", "csv_serialize"),
        ("inspect dataset schema", "schema_inspect"),
        ("validate data against schema", "data_validate"),
        ("transform records", "data_transform"),
        ("aggregate data", "data_aggregate"),
    ]
    for query, expected in cases:
        matches = agent.capabilities.discover(query, limit=3)
        assert matches, (query, matches)
        assert matches[0].name == expected, (query, [m.name for m in matches])


def test_schemas():
    agent = create_agent()
    for name in [
        "csv_parse",
        "csv_serialize",
        "schema_inspect",
        "data_validate",
        "data_transform",
        "data_aggregate",
    ]:
        capability = agent.capabilities.get(name)
        assert capability.input_schema.get("type") == "object", name
        assert capability.output_schema, name


def test_runtime_regression():
    agent = create_agent()
    state = agent.run("calculate 25 + 15")
    assert isinstance(state, JobState)
    assert state.status == "completed"


def main():
    tests = [
        ("registration", test_registration),
        ("CSV parsing/serialization", test_csv),
        ("schema inspection", test_schema),
        ("data validation", test_validation),
        ("data transformation", test_transform),
        ("data aggregation", test_aggregate),
        ("capability discovery", test_discovery),
        ("capability schemas", test_schemas),
        ("core runtime regression", test_runtime_regression),
    ]

    passed = sum(check(name, fn) for name, fn in tests)
    print(f"CP-16 DATA ENGINEERING TESTS: {passed}/{len(tests)} PASSED")

    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
