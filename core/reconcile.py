"""CP-46: operator reconciliation for executions whose outcome is uncertain.

A job is blocked on resume while one of its incomplete steps has an execution
in RUNNING or UNKNOWN state with no later SUCCEEDED execution. Only a human can
establish what really happened, so resolution requires an explicit outcome and
an audit note. Notes are persisted: never put secrets in them.

CLI:
    python -m core.reconcile list
    python -m core.reconcile show JOB_ID
    python -m core.reconcile resolve JOB_ID --step N --outcome OUTCOME --note TEXT [--result TEXT]
    python -m core.reconcile resume JOB_ID

Outcomes:
    not_started  the side effect did NOT happen; resume will run the step again
    failed       the operation ran and failed; resume will run the step again
    succeeded    the side effect DID happen; requires --result; resume reuses it
"""
from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone

from core.state_store import StateStore

UNCERTAIN = frozenset({"RUNNING", "UNKNOWN"})
OUTCOMES = {
    "not_started": "NOT_STARTED",
    "failed": "FAILED",
    "succeeded": "SUCCEEDED",
}
MAX_NOTE_LENGTH = 500


class ReconciliationError(ValueError):
    """The requested reconciliation is invalid or not applicable."""


def blocked_executions(state: dict) -> list[tuple[int, dict]]:
    """Mirror the orchestrator resume guard: (index, execution) pairs."""
    executions = state.get("executions") or []
    completed = set(state.get("completed_steps") or [])
    incomplete = {
        step.get("id") for step in (state.get("plan") or [])
        if step.get("id") not in completed
    }
    last_success: dict = {}
    for index, execution in enumerate(executions):
        if execution.get("status") == "SUCCEEDED":
            last_success[execution.get("step_id")] = index
    return [
        (index, execution)
        for index, execution in enumerate(executions)
        if execution.get("step_id") in incomplete
        and execution.get("status") in UNCERTAIN
        and index > last_success.get(execution.get("step_id"), -1)
    ]


def list_blocked(store: StateStore) -> list[dict]:
    rows = []
    for job in store.list_jobs():
        state = store.load(job["job_id"])
        if not isinstance(state, dict):
            continue
        blocked = blocked_executions(state)
        if blocked:
            rows.append({
                "job_id": job["job_id"],
                "status": state.get("status"),
                "goal": state.get("goal"),
                "blocked": [
                    {
                        "step_id": e.get("step_id"),
                        "execution_id": e.get("execution_id"),
                        "attempt": e.get("attempt"),
                        "status": e.get("status"),
                    }
                    for _, e in blocked
                ],
            })
    return rows


def reconcile(
    store: StateStore,
    job_id: str,
    step_id: int,
    outcome: str,
    note: str,
    result=None,
    operator: str | None = None,
) -> dict:
    if outcome not in OUTCOMES:
        raise ReconciliationError(
            f"Outcome must be one of: {', '.join(sorted(OUTCOMES))}."
        )
    note = (note or "").strip()
    if not note:
        raise ReconciliationError("An audit note is required.")
    if len(note) > MAX_NOTE_LENGTH:
        raise ReconciliationError(
            f"Note is too long (max {MAX_NOTE_LENGTH} characters)."
        )
    if outcome == "succeeded" and result is None:
        raise ReconciliationError(
            "Outcome 'succeeded' requires the recorded result (--result)."
        )

    state = store.load(job_id)
    if state is None:
        raise ReconciliationError(f"Unknown job: {job_id}")

    targets = [
        (index, execution)
        for index, execution in blocked_executions(state)
        if execution.get("step_id") == step_id
    ]
    if not targets:
        raise ReconciliationError(
            f"Step {step_id} has no RUNNING or UNKNOWN execution blocking job {job_id}."
        )

    new_status = OUTCOMES[outcome]
    now = datetime.now(timezone.utc).isoformat()
    changes = []
    for _, execution in targets:
        changes.append({
            "execution_id": execution.get("execution_id"),
            "from": execution.get("status"),
            "to": new_status,
        })
        execution["status"] = new_status
        execution["completed_at"] = now
        if outcome == "succeeded":
            execution["result"] = result

    store.save(job_id, state)
    store.record_event(
        job_id,
        "execution_reconciled",
        step_id=step_id,
        payload={
            "outcome": outcome,
            "note": note,
            "operator": operator or "unknown",
            "executions": changes,
            "result_recorded": outcome == "succeeded",
        },
    )
    return {"job_id": job_id, "step_id": step_id, "changes": changes}


def _operator() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core.reconcile")
    parser.add_argument("--db", help="State database path (default: application default).")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List jobs blocked on uncertain executions.")

    show = sub.add_parser("show", help="Show a job's executions and recent events.")
    show.add_argument("job_id")

    resolve = sub.add_parser("resolve", help="Resolve uncertain executions of one step.")
    resolve.add_argument("job_id")
    resolve.add_argument("--step", type=int, required=True)
    resolve.add_argument("--outcome", required=True, choices=sorted(OUTCOMES))
    resolve.add_argument("--note", required=True)
    resolve.add_argument("--result", default=None)

    resume = sub.add_parser("resume", help="Resume a job after reconciliation.")
    resume.add_argument("job_id")

    args = parser.parse_args(argv)
    store = StateStore(args.db) if args.db else StateStore()

    try:
        if args.command == "list":
            rows = list_blocked(store)
            if not rows:
                print("No blocked jobs.")
            for row in rows:
                print(f"{row['job_id']}  status={row['status']}  goal={row['goal']!r}")
                for item in row["blocked"]:
                    print(
                        f"    step={item['step_id']} attempt={item['attempt']} "
                        f"status={item['status']} execution={item['execution_id']}"
                    )
            return 0

        if args.command == "show":
            state = store.load(args.job_id)
            if state is None:
                raise ReconciliationError(f"Unknown job: {args.job_id}")
            print(f"job={args.job_id} status={state.get('status')} goal={state.get('goal')!r}")
            for execution in state.get("executions") or []:
                print(
                    f"  step={execution.get('step_id')} attempt={execution.get('attempt')} "
                    f"status={execution.get('status')} execution={execution.get('execution_id')}"
                )
            for event in store.get_events(args.job_id)[-10:]:
                print(f"  event {event['event_id']}: {event['event_type']} step={event['step_id']}")
            return 0

        if args.command == "resolve":
            outcome = reconcile(
                store, args.job_id, args.step, args.outcome, args.note,
                result=args.result, operator=_operator(),
            )
            for change in outcome["changes"]:
                print(f"{change['execution_id']}: {change['from']} -> {change['to']}")
            print(f"Reconciled. Next: python -m core.reconcile resume {args.job_id}")
            return 0

        if args.command == "resume":
            from core.main import create_agent

            agent = create_agent()
            if args.db:
                agent.orchestrator.state_store = store
            print(agent.resume(args.job_id))
            return 0
    except (ReconciliationError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())