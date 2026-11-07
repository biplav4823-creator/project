"""CP-50: bounded delegation to specialist agents.

Enforces depth, fan-out, shared call budget and permission inheritance
(child permissions must be a subset of the parent's), validates typed child
output, and requires parent verification. Pure and offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional


class DelegationError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Delegation refused ({code}).")


@dataclass(frozen=True)
class Budget:
    max_depth: int = 2
    max_fanout: int = 3
    max_calls: int = 20
    permissions: FrozenSet[str] = frozenset()


class Delegator:
    def __init__(self, budget: Budget, depth: int = 0, _shared: Optional[Dict[str, int]] = None):
        self.budget = budget
        self.depth = depth
        self._shared = _shared if _shared is not None else {"calls": 0}
        self._children = 0

    @property
    def calls_used(self) -> int:
        return self._shared["calls"]

    def delegate(
        self,
        name: str,
        fn: Callable[["Delegator"], Any],
        permissions: Iterable[str],
        output_schema: Dict[str, type],
        verify: Callable[[Dict[str, Any]], bool],
    ) -> Dict[str, Any]:
        perms = frozenset(permissions)
        if self.depth + 1 > self.budget.max_depth:
            raise DelegationError("max_depth")
        if self._children >= self.budget.max_fanout:
            raise DelegationError("max_fanout")
        if self._shared["calls"] >= self.budget.max_calls:
            raise DelegationError("call_budget")
        if not perms <= self.budget.permissions:
            raise DelegationError("permission_escalation")
        if not callable(verify):
            raise DelegationError("verifier_required")

        self._children += 1
        self._shared["calls"] += 1
        child = Delegator(
            Budget(self.budget.max_depth, self.budget.max_fanout,
                   self.budget.max_calls, perms),
            self.depth + 1,
            self._shared,
        )
        output = fn(child)
        self._check_type(output, output_schema)
        if not verify(output):
            raise DelegationError("parent_verification_failed")
        return output

    @staticmethod
    def _check_type(output: Any, schema: Dict[str, type]) -> None:
        if not isinstance(output, dict):
            raise DelegationError("output_not_object")
        if set(output) != set(schema):
            raise DelegationError("output_fields_mismatch")
        for key, expected in schema.items():
            value = output[key]
            if isinstance(value, bool) and expected is not bool:
                raise DelegationError("output_type_mismatch")
            if not isinstance(value, expected):
                raise DelegationError("output_type_mismatch")


def compare(
    tasks: List[Any],
    single: Callable[[Any], Any],
    delegated: Callable[[Any], Any],
    check: Callable[[Any, Any], bool],
) -> Dict[str, Any]:
    """Success rate of a single-agent vs delegated strategy on the same tasks."""
    results = {}
    for label, strategy in (("single", single), ("delegated", delegated)):
        ok = 0
        for task in tasks:
            try:
                ok += 1 if check(task, strategy(task)) else 0
            except Exception:
                pass
        results[label] = {
            "passed": ok,
            "total": len(tasks),
            "rate": round(ok / len(tasks), 4) if tasks else 0.0,
        }
    results["delegation_gain"] = round(
        results["delegated"]["rate"] - results["single"]["rate"], 4
    )
    return results