from typing import Any


def job_inspect(state):
    if state is None:
        raise ValueError("state is required.")
    if isinstance(state, dict):
        get = state.get
    else:
        get = lambda key, default=None: getattr(state, key, default)
    plan = get("plan", []) or []
    return {
        "job_id": get("job_id"),
        "goal": get("goal"),
        "status": get("status"),
        "current_step": get("current_step"),
        "completed_steps": list(get("completed_steps", []) or []),
        "failed_steps": list(get("failed_steps", []) or []),
        "plan_steps": len(plan),
        "interrupt_count": len(get("interrupts", []) or []),
    }


def plan_validate(steps):
    if not isinstance(steps, list):
        raise ValueError("steps must be a list.")
    ids = [step.get("id") for step in steps if isinstance(step, dict)]
    if len(ids) != len(steps):
        raise ValueError("Every step must be a dictionary.")
    if len(ids) != len(set(ids)):
        raise ValueError("Step IDs must be unique.")
    known = set(ids)
    errors = []
    for step in steps:
        depends = step.get("depends_on", []) or []
        if not isinstance(depends, list):
            errors.append(f"Step {step.get('id')} has invalid dependencies.")
            continue
        for dep in depends:
            if dep not in known:
                errors.append(
                    f"Step {step.get('id')} depends on unknown step {dep}."
                )
            if dep == step.get("id"):
                errors.append(
                    f"Step {step.get('id')} cannot depend on itself."
                )
    return {
        "valid": not errors,
        "step_count": len(steps),
        "errors": errors,
    }


def dependency_inspect(steps):
    if not isinstance(steps, list):
        raise ValueError("steps must be a list.")
    dependencies = {}
    dependents = {step.get("id"): [] for step in steps}
    for step in steps:
        step_id = step.get("id")
        deps = list(step.get("depends_on", []) or [])
        dependencies[step_id] = deps
        for dep in deps:
            dependents.setdefault(dep, []).append(step_id)
    roots = [
        step_id
        for step_id, deps in dependencies.items()
        if not deps
    ]
    leaves = [
        step_id
        for step_id, children in dependents.items()
        if not children
    ]
    return {
        "dependencies": dependencies,
        "dependents": dependents,
        "roots": roots,
        "leaves": leaves,
    }


def retry_policy(attempts=0, max_attempts=3, error=None):
    attempts = int(attempts)
    max_attempts = int(max_attempts)
    if attempts < 0:
        raise ValueError("attempts cannot be negative.")
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive.")
    retry = attempts < max_attempts
    return {
        "retry": retry,
        "attempt": attempts,
        "max_attempts": max_attempts,
        "remaining": max(0, max_attempts - attempts),
        "error": str(error) if error is not None else None,
    }


def execution_summary(results):
    if not isinstance(results, list):
        raise ValueError("results must be a list.")
    completed = 0
    failed = 0
    for item in results:
        if not isinstance(item, dict):
            continue
        if "error" in item:
            failed += 1
        elif "result" in item:
            completed += 1
    total = len(results)
    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "pending": max(0, total - completed - failed),
        "success_rate": completed / total if total else 0.0,
    }


def operational_diagnose(state):
    if state is None:
        raise ValueError("state is required.")
    if isinstance(state, dict):
        get = state.get
    else:
        get = lambda key, default=None: getattr(state, key, default)
    status = get("status", "unknown")
    failed = list(get("failed_steps", []) or [])
    interrupts = list(get("interrupts", []) or [])
    approval = get("approval")
    issues = []
    actions = []
    if status == "failed" or failed:
        issues.append("job_failure")
        actions.append("inspect_failed_step")
    if status == "waiting_approval":
        issues.append("approval_required")
        actions.append("resume_after_approval")
    if interrupts:
        issues.append("interrupts_present")
        actions.append("inspect_interrupts")
    if not issues:
        issues.append("no_operational_issue_detected")
        actions.append("continue")
    return {
        "status": status,
        "issues": issues,
        "recommended_actions": actions,
        "failed_steps": failed,
        "interrupt_count": len(interrupts),
        "approval_pending": approval is not None and status == "waiting_approval",
    }
