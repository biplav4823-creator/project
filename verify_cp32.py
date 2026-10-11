from core.main import create_agent


def main():
    agent = create_agent()

    expected = {
        "analyze a dataset": "dataset_profile",
        "analyze dataset": "dataset_profile",
        "analyze the dataset": "dataset_profile",
        "analyze this dataset": "dataset_profile",
        "analyze data": "dataset_profile",
        "profile dataset": "dataset_profile",
        "calculate derivative of x^2": "derivative",
    }

    failures = []
    for query, expected_capability in expected.items():
        actual = [
            capability.name
            for capability in agent.capabilities.discover(query, limit=5)
        ]
        if expected_capability in actual:
            print(f"[PASS] {query!r} -> {expected_capability}")
        else:
            failures.append((query, expected_capability, actual))
            print(
                f"[FAIL] {query!r}: expected {expected_capability!r}, "
                f"got {actual!r}"
            )

    if failures:
        raise SystemExit(f"CP-32 DISCOVERY VERIFICATION: {len(failures)} failure(s)")

    print(f"CP-32 DISCOVERY VERIFICATION: {len(expected)}/{len(expected)} PASSED")

    # Verify the real skill registry and planner integration.
    skill_manager = agent.skill_manager
    skill_names = skill_manager.list()

    required_skills = {
        "mathematics",
        "data_science",
        "data_engineering",
        "generative_ai",
        "agentic_operations",
        "python_execution",
    }

    missing = required_skills - set(skill_names)
    assert not missing, f"Missing registered skills: {sorted(missing)}"
    print(f"[PASS] Required skills registered: {len(required_skills)}")

    cases = [
        ("analyze a dataset", "dataset_profile", "data_science"),
        ("calculate derivative of x^2", "derivative", "mathematics"),
    ]

    for query, expected_capability, expected_skill in cases:
        plan = agent.planner.plan(query)
        assert plan["steps"], f"Planner returned no steps for {query!r}"

        step = plan["steps"][0]
        assert step["capability"] == expected_capability, (
            f"{query!r}: expected capability {expected_capability!r}, "
            f"got {step['capability']!r}"
        )
        assert step["skill"] == expected_skill, (
            f"{query!r}: expected skill {expected_skill!r}, "
            f"got {step['skill']!r}"
        )
        print(
            f"[PASS] Planner: {query!r} -> "
            f"{step['capability']} -> {step['skill']}"
        )

    print("CP-32 SKILL INTEGRATION VERIFICATION: 3/3 PASSED")


if __name__ == "__main__":
    main()
