"""CP-47: end-state evaluation harness.

Grades what actually happened (tool outputs, call counts, final job status),
not what the agent reported. Each task runs k times on a fresh isolated
database; reports pass@1, pass^k (all k trials pass) and false-success rate
(job reported 'completed' but the end-state check failed).

Offline and deterministic: no LLM or network access is required.
"""
from __future__ import annotations

import argparse
import ast
import json
import operator
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., Any]
    risk: str = "low"
    idempotent: bool = False


@dataclass
class Trial:
    """Per-trial fixtures. Created fresh for every run so counters reset."""

    tools: List[ToolSpec]
    check: Callable[[Any, "Trial"], bool]
    calls: Dict[str, int] = field(default_factory=dict)
    outputs: List[Any] = field(default_factory=list)


@dataclass
class EvalTask:
    task_id: str
    goal: str
    prepare: Callable[[], Trial]
    expect_status: str = "completed"
    max_calls: Optional[int] = None


def _counting(trial: Trial, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args, **kwargs):
        trial.calls[name] = trial.calls.get(name, 0) + 1
        out = fn(*args, **kwargs)
        trial.outputs.append(out)
        return out

    wrapper.__name__ = getattr(fn, "__name__", name)
    wrapper.__doc__ = getattr(fn, "__doc__", None)
    wrapper.__annotations__ = dict(getattr(fn, "__annotations__", {}))
    return wrapper


def default_agent_factory(db_path: str):
    from core.agent import Agent
    from core.state_store import StateStore

    agent = Agent()
    agent.orchestrator.state_store = StateStore(db_path)
    return agent


def run_trial(task: EvalTask, agent_factory: Callable[[str], Any]) -> Dict[str, Any]:
    started = time.monotonic()
    result: Dict[str, Any] = {
        "status": None,
        "passed": False,
        "false_success": False,
        "calls": 0,
        "error_type": None,
        "reason": None,
    }
    with tempfile.TemporaryDirectory() as directory:
        trial = task.prepare()
        try:
            agent = agent_factory(str(Path(directory) / "eval.sqlite"))
            for spec in trial.tools:
                agent.register_tool(
                    spec.name,
                    spec.description,
                    _counting(trial, spec.name, spec.fn),
                    risk=spec.risk,
                    idempotent=spec.idempotent,
                )
            state = agent.run(task.goal)
            status = getattr(state, "status", None)
            result["status"] = status
            result["calls"] = sum(trial.calls.values())

            end_state_ok = bool(trial.check(state, trial))
            status_ok = status == task.expect_status
            calls_ok = task.max_calls is None or result["calls"] <= task.max_calls

            result["false_success"] = status == "completed" and not end_state_ok
            result["passed"] = end_state_ok and status_ok and calls_ok
            if not result["passed"]:
                result["reason"] = (
                    "end_state_mismatch" if not end_state_ok
                    else "unexpected_status" if not status_ok
                    else "too_many_calls"
                )
        except Exception as exc:  # report type only; never raw text
            result["status"] = "harness_error"
            result["error_type"] = type(exc).__name__
            result["reason"] = "exception"
    result["seconds"] = round(time.monotonic() - started, 4)
    return result


def run_suite(
    tasks: List[EvalTask],
    k: int = 3,
    agent_factory: Callable[[str], Any] = default_agent_factory,
) -> Dict[str, Any]:
    if k < 1:
        raise ValueError("k must be >= 1")
    per_task = []
    total = passes = false_successes = 0
    latencies: List[float] = []
    for task in tasks:
        trials = [run_trial(task, agent_factory) for _ in range(k)]
        ok = sum(1 for t in trials if t["passed"])
        total += k
        passes += ok
        false_successes += sum(1 for t in trials if t["false_success"])
        latencies += [t["seconds"] for t in trials]
        per_task.append(
            {
                "task_id": task.task_id,
                "trials": k,
                "passes": ok,
                "pass_at_1": round(ok / k, 4),
                "pass_hat_k": ok == k,
                "reasons": sorted({t["reason"] for t in trials if t["reason"]}),
            }
        )
    n_tasks = len(tasks)
    return {
        "k": k,
        "tasks": per_task,
        "summary": {
            "task_count": n_tasks,
            "pass_at_1": round(passes / total, 4) if total else 0.0,
            "pass_hat_k": round(
                sum(1 for t in per_task if t["pass_hat_k"]) / n_tasks, 4
            ) if n_tasks else 0.0,
            "false_success_rate": round(false_successes / total, 4) if total else 0.0,
            "median_trial_seconds": round(statistics.median(latencies), 4)
            if latencies else 0.0,
        },
    }


# ---------------------------------------------------------------- built-ins
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError("unsupported expression")


def _calculate(expression: str) -> str:
    value = _safe_eval(ast.parse(str(expression).strip(), mode="eval"))
    return str(int(value)) if float(value).is_integer() else str(value)


def _task_arithmetic() -> Trial:
    return Trial(
        tools=[ToolSpec("calculate", "Evaluate arithmetic expressions", _calculate)],
        check=lambda state, t: t.outputs == ["5"],
    )


def _task_no_retry_after_unknown() -> Trial:
    def calculate(expression: str) -> str:
        raise TimeoutError("eval-secret-detail")

    return Trial(
        tools=[ToolSpec("calculate", "Evaluate arithmetic expressions", calculate)],
        check=lambda state, t: t.calls.get("calculate") == 1,
    )


def _task_idempotent_retry() -> Trial:
    state = {"n": 0}

    def calculate(expression: str) -> str:
        state["n"] += 1
        if state["n"] == 1:
            raise TimeoutError("eval-secret-detail")
        return "5"

    return Trial(
        tools=[ToolSpec("calculate", "Evaluate arithmetic expressions",
                        calculate, idempotent=True)],
        check=lambda s, t: t.outputs == ["5"] and t.calls.get("calculate") == 2,
    )


def builtin_tasks() -> List[EvalTask]:
    return [
        EvalTask("arithmetic_end_state", "calculate 2 + 3", _task_arithmetic),
        EvalTask(
            "unknown_outcome_is_not_retried",
            "calculate 2 + 3",
            _task_no_retry_after_unknown,
            expect_status="failed",
            max_calls=1,
        ),
        EvalTask(
            "idempotent_timeout_retries_once",
            "calculate 2 + 3",
            _task_idempotent_retry,
            max_calls=2,
        ),
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core.evals")
    parser.add_argument("--k", type=int, default=3, help="trials per task")
    parser.add_argument("--out", help="write the JSON report to this path")
    parser.add_argument("--min-pass-k", type=float, default=1.0)
    args = parser.parse_args(argv)

    report = run_suite(builtin_tasks(), k=args.k)
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    ok = (
        report["summary"]["pass_hat_k"] >= args.min_pass_k
        and report["summary"]["false_success_rate"] == 0.0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())