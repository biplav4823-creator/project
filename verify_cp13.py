from capabilities.capability import Capability
from core.guardrail import Guardrail
from core.main import create_agent


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    g = Guardrail()

    # 1. Low-risk capability allowed.
    safe = Capability(
        name="safe_test",
        description="safe",
        risk="low",
    )
    check(
        g.evaluate(safe).action == "allow",
        "low-risk capability was not allowed",
    )

    # 2. Missing permission denied.
    protected = Capability(
        name="protected_test",
        description="protected",
        permissions=["filesystem_write"],
        risk="low",
    )
    check(
        g.evaluate(protected).action == "deny",
        "missing permission was accepted",
    )

    # 3. Granted permission allowed.
    permitted = Guardrail(
        allowed_permissions=["filesystem_write"]
    )
    check(
        permitted.evaluate(protected).action == "allow",
        "granted permission was denied",
    )

    # 4. Sensitive permission denied.
    admin = Capability(
        name="admin_test",
        description="admin",
        permissions=["system_admin"],
        risk="low",
    )
    check(
        g.evaluate(admin).action == "deny",
        "blocked permission was accepted",
    )

    # 5. Medium risk denied until approval.
    medium = Capability(
        name="medium_test",
        description="medium",
        risk="medium",
    )
    check(
        g.evaluate(medium).action == "deny",
        "medium-risk capability was allowed",
    )

    # 6. High risk denied until approval.
    high = Capability(
        name="high_test",
        description="high",
        risk="high",
    )
    check(
        g.evaluate(high).action == "deny",
        "high-risk capability was allowed",
    )

    # 7. Critical risk blocked.
    critical = Capability(
        name="critical_test",
        description="critical",
        risk="critical",
    )
    check(
        g.evaluate(critical).action == "deny",
        "critical-risk capability was allowed",
    )

    # 8. run_python is forced to high risk.
    python_cap = Capability(
        name="run_python",
        description="python execution",
        risk="low",
    )
    check(
        g.evaluate(python_cap).action == "deny",
        "run_python was not protected",
    )

    # 9. CP-10 regression.
    agent = create_agent()
    result = agent.run("calculate 25 + 15")
    check(
        "40" in str(result),
        "CP-10 regression failed",
    )

    # 10. CP-11 dependency regression.
    result = agent.run(
        "calculate 25 + 15 and then multiply the result by 2"
    )
    check(
        "80" in str(result),
        "CP-11 dependency regression failed",
    )

    print("CP-13 verification: 10/10 checks passed")


if __name__ == "__main__":
    main()
