from capabilities.capability import Capability
from core.approval import ApprovalGate
from core.interrupt import InterruptEngine


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    engine = InterruptEngine()
    gate = ApprovalGate()

    # 1. Low-risk capability passes without interrupt.
    low = Capability(
        name="low_test",
        description="low risk",
        risk="low",
    )
    result = engine.pre_execution(low, step_id=1, arguments={})
    check(result.action == "continue", "low-risk interrupt failed")

    decision = gate.evaluate(
        low,
        step_id=1,
        arguments={},
        interrupts=result.interrupts,
    )
    check(decision.action == "allow", "low-risk approval failed")

    # 2. Medium-risk capability requires approval.
    medium = Capability(
        name="medium_test",
        description="medium risk",
        risk="medium",
    )
    result = engine.pre_execution(medium, step_id=2, arguments={})
    check(result.action == "interrupt", "medium risk did not interrupt")
    check(
        any(i.name == "medium_risk" for i in result.interrupts),
        "medium_risk trigger missing",
    )

    decision = gate.evaluate(
        medium,
        step_id=2,
        arguments={},
        interrupts=result.interrupts,
    )
    check(
        decision.action == "approve",
        "medium risk did not require approval",
    )

    # 3. High-risk capability requires approval.
    high = Capability(
        name="high_test",
        description="high risk",
        risk="high",
    )
    result = engine.pre_execution(high, step_id=3, arguments={})
    check(result.action == "interrupt", "high risk did not interrupt")
    check(
        any(i.name == "high_risk" for i in result.interrupts),
        "high_risk trigger missing",
    )

    decision = gate.evaluate(
        high,
        step_id=3,
        arguments={},
        interrupts=result.interrupts,
    )
    check(
        decision.action == "approve",
        "high risk did not require approval",
    )

    # 4. External side-effect permission creates named interrupt.
    write = Capability(
        name="write_test",
        description="filesystem write",
        permissions=["filesystem_write"],
        risk="low",
    )
    result = engine.pre_execution(write, step_id=4, arguments={})
    check(
        any(i.name == "external_side_effect" for i in result.interrupts),
        "external_side_effect trigger missing",
    )

    decision = gate.evaluate(
        write,
        step_id=4,
        arguments={},
        interrupts=result.interrupts,
    )
    check(
        decision.action == "approve",
        "external side effect did not require approval",
    )

    # 5. Credential access creates named interrupt.
    credential = Capability(
        name="credential_test",
        description="credential access",
        permissions=["credential_access"],
        risk="low",
    )
    result = engine.pre_execution(
        credential,
        step_id=5,
        arguments={},
    )
    check(
        any(i.name == "credential_access" for i in result.interrupts),
        "credential_access trigger missing",
    )

    # 6. Explicit capability interrupt is preserved.
    explicit = Capability(
        name="explicit_test",
        description="explicit interrupt",
        risk="low",
    )
    explicit.interrupts = ["destructive_action"]

    result = engine.pre_execution(
        explicit,
        step_id=6,
        arguments={},
    )
    check(
        any(i.name == "destructive_action" for i in result.interrupts),
        "explicit interrupt trigger missing",
    )

    # 7. Auto-approval is explicit and opt-in.
    auto_gate = ApprovalGate(auto_approve=True)
    decision = auto_gate.evaluate(
        high,
        step_id=7,
        arguments={},
        interrupts=result.interrupts,
    )
    check(
        decision.action == "allow",
        "explicit auto-approval failed",
    )

    # 8. Post-execution hook currently preserves continuation.
    post = engine.post_execution(
        low,
        {"result": 40},
        step_id=8,
    )
    check(
        post.action == "continue",
        "post-execution continuation failed",
    )

    print("CP-14.3 INTERRUPT TESTS: 8/8 PASSED")


if __name__ == "__main__":
    main()
