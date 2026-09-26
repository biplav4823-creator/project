from core.main import create_agent


def check(condition, message):
    if not condition:
        raise AssertionError(message)


agent = create_agent()

names = agent.capabilities.list()

expected = {
    "data_statistics",
    "data_correlation",
    "linear_regression",
    "dataset_profile",
}

check(expected.issubset(set(names)), "CP-15 capabilities not registered")

stats = agent.tools.execute(
    "data_statistics",
    {"values": [1, 2, 3, 4, 5]},
)
check(stats["count"] == 5, "statistics count failed")
check(stats["mean"] == 3.0, "statistics mean failed")
check(stats["median"] == 3.0, "statistics median failed")
check(stats["minimum"] == 1.0, "statistics minimum failed")
check(stats["maximum"] == 5.0, "statistics maximum failed")

correlation = agent.tools.execute(
    "data_correlation",
    {"x": [1, 2, 3], "y": [2, 4, 6]},
)
check(abs(correlation - 1.0) < 1e-12, "correlation failed")

regression = agent.tools.execute(
    "linear_regression",
    {"x": [1, 2, 3], "y": [2, 4, 6]},
)
check(abs(regression["slope"] - 2.0) < 1e-12, "regression slope failed")
check(abs(regression["intercept"]) < 1e-12, "regression intercept failed")
check(abs(regression["r_squared"] - 1.0) < 1e-12, "regression R2 failed")

profile = agent.tools.execute(
    "dataset_profile",
    {
        "rows": [
            {"age": 20, "name": "A"},
            {"age": 30, "name": "B"},
            {"age": None, "name": "A"},
        ]
    },
)
check(profile["row_count"] == 3, "profile row count failed")
check(profile["column_count"] == 2, "profile column count failed")
check(profile["columns"]["age"]["null_count"] == 1, "profile null count failed")
check(profile["columns"]["age"]["mean"] == 25.0, "profile numeric mean failed")
check(profile["columns"]["name"]["unique_count"] == 2, "profile unique count failed")

discovered = agent.discover_capabilities(
    "calculate descriptive statistics for this data",
    limit=5,
)
check(
    any(c.name == "data_statistics" for c in discovered),
    "data_statistics discovery failed",
)

discovered = agent.discover_capabilities(
    "find the Pearson correlation between x and y",
    limit=5,
)
check(
    any(c.name == "data_correlation" for c in discovered),
    "data_correlation discovery failed",
)

# Verify schema enforcement.
try:
    agent.capabilities.get("data_statistics").validate_input(
        {"values": ["bad"]}
    )
    raise AssertionError("schema rejection failed")
except Exception:
    pass

# Verify complete runtime path through Agent -> Planner -> Orchestrator.
result = agent.run("calculate 25 + 15")
check(result.status == "completed", "core runtime regression failed")
check(
    result.intermediate_results[0]["result"]["result"] == "40",
    "core calculation regression failed",
)

print("CP-15 DATA SCIENCE TESTS: 10/10 PASSED")
print("DATA SCIENCE CAPABILITIES:", [
    name for name in names
    if name in expected
])
