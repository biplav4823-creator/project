"""CP-55: bounded concurrent DAG execution.

Tasks run when all dependencies succeeded; independent branches run in
parallel on a bounded worker pool. A failed task causes its descendants to be
skipped. Only exception TYPES are reported (no raw messages).
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Callable, Dict, List, Tuple

from core.skill_manifest import find_cycle

Task = Tuple[Callable[[Dict[str, Any]], Any], List[str]]


class DagError(ValueError):
    pass


def validate(tasks: Dict[str, Task]) -> None:
    if not isinstance(tasks, dict) or not tasks:
        raise DagError("tasks must be a non-empty mapping")
    graph: Dict[str, List[str]] = {}
    for name, spec in tasks.items():
        if not isinstance(name, str) or not name:
            raise DagError("task names must be non-empty strings")
        if not (isinstance(spec, tuple) and len(spec) == 2 and callable(spec[0])
                and isinstance(spec[1], list)):
            raise DagError(f"task {name!r} must be (callable, [deps])")
        for dep in spec[1]:
            if dep not in tasks:
                raise DagError(f"task {name!r} depends on unknown task {dep!r}")
        if name in spec[1]:
            raise DagError(f"task {name!r} depends on itself")
        graph[name] = list(spec[1])
    cycle = find_cycle(graph)
    if cycle:
        raise DagError("dependency cycle: " + " -> ".join(cycle))


def run_dag(
    tasks: Dict[str, Task], max_workers: int = 4, fail_fast: bool = False
) -> Dict[str, Dict[str, Any]]:
    validate(tasks)
    if not isinstance(max_workers, int) or max_workers < 1:
        raise DagError("max_workers must be >= 1")

    results: Dict[str, Dict[str, Any]] = {}
    pending = set(tasks)
    running: Dict[Any, str] = {}
    stop = False

    def settle_skips() -> None:
        changed = True
        while changed:
            changed = False
            for name in sorted(pending):
                if any(results.get(d, {}).get("status") in ("failed", "skipped")
                       for d in tasks[name][1]):
                    results[name] = {"status": "skipped", "reason": "dependency_failed"}
                    pending.discard(name)
                    changed = True

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        while pending or running:
            settle_skips()
            if stop:
                for name in sorted(pending):
                    results[name] = {"status": "skipped", "reason": "fail_fast"}
                pending.clear()
            ready = sorted(
                n for n in pending
                if all(results.get(d, {}).get("status") == "ok" for d in tasks[n][1])
            )
            for name in ready:
                if len(running) >= max_workers:
                    break
                inputs = {d: results[d]["result"] for d in tasks[name][1]}
                running[pool.submit(tasks[name][0], inputs)] = name
                pending.discard(name)
            if not running:
                break
            done, _ = wait(list(running), return_when=FIRST_COMPLETED)
            for future in done:
                name = running.pop(future)
                try:
                    results[name] = {"status": "ok", "result": future.result()}
                except Exception as exc:
                    results[name] = {"status": "failed", "error_type": type(exc).__name__}
                    if fail_fast:
                        stop = True
    return results