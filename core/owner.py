"""CP-53: Owner Input layer and policy decisions (offline, deterministic).

Owner preferences: spending cap, approval bar, allowed folders, blocked
actions, quiet hours and named interrupt triggers. `OwnerPolicy.decide`
returns allow / needs-approval / deny with a reason code; it never executes.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Optional, Tuple

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
INTERRUPTS = frozenset(
    {"spend_over_budget", "irreversible_action", "external_message",
     "credential_use", "low_confidence", "policy_violation"}
)


@dataclass(frozen=True)
class OwnerProfile:
    budget_cap_usd: float = 0.0
    approval_at_or_above: str = "medium"
    allowed_dirs: Tuple[str, ...] = ()
    blocked_actions: FrozenSet[str] = frozenset()
    quiet_hours: Optional[Tuple[int, int]] = None
    interrupt_on: FrozenSet[str] = INTERRUPTS

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "OwnerProfile":
        if not isinstance(data, dict):
            raise ValueError("profile must be an object")
        unknown = set(data) - {
            "budget_cap_usd", "approval_at_or_above", "allowed_dirs",
            "blocked_actions", "quiet_hours", "interrupt_on",
        }
        if unknown:
            raise ValueError(f"unknown fields: {sorted(unknown)}")
        cap = data.get("budget_cap_usd", 0.0)
        if isinstance(cap, bool) or not isinstance(cap, (int, float)) or cap < 0:
            raise ValueError("budget_cap_usd must be a non-negative number")
        bar = data.get("approval_at_or_above", "medium")
        if bar not in RISK_ORDER:
            raise ValueError("approval_at_or_above invalid")
        dirs = data.get("allowed_dirs", [])
        if not isinstance(dirs, list) or not all(isinstance(d, str) and d for d in dirs):
            raise ValueError("allowed_dirs must be a list of paths")
        blocked = data.get("blocked_actions", [])
        if not isinstance(blocked, list) or not all(isinstance(b, str) for b in blocked):
            raise ValueError("blocked_actions must be a list of names")
        quiet = data.get("quiet_hours")
        if quiet is not None:
            if (not isinstance(quiet, (list, tuple)) or len(quiet) != 2
                    or not all(isinstance(h, int) and 0 <= h <= 23 for h in quiet)):
                raise ValueError("quiet_hours must be [start_hour, end_hour] in 0-23")
            quiet = (quiet[0], quiet[1])
        interrupts = data.get("interrupt_on", sorted(INTERRUPTS))
        if not isinstance(interrupts, list) or not set(interrupts) <= INTERRUPTS:
            raise ValueError("interrupt_on contains unknown triggers")
        return OwnerProfile(
            float(cap), bar, tuple(dirs), frozenset(blocked), quiet, frozenset(interrupts)
        )

    @staticmethod
    def load(path: str) -> "OwnerProfile":
        with open(path, "r", encoding="utf-8") as handle:
            return OwnerProfile.from_dict(json.load(handle))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget_cap_usd": self.budget_cap_usd,
            "approval_at_or_above": self.approval_at_or_above,
            "allowed_dirs": list(self.allowed_dirs),
            "blocked_actions": sorted(self.blocked_actions),
            "quiet_hours": list(self.quiet_hours) if self.quiet_hours else None,
            "interrupt_on": sorted(self.interrupt_on),
        }


@dataclass(frozen=True)
class Decision:
    allow: bool
    requires_approval: bool
    reason: str


def _inside(path: str, roots: Tuple[str, ...]) -> bool:
    real = os.path.realpath(path)
    for root in roots:
        base = os.path.realpath(root)
        try:
            if os.path.commonpath([real, base]) == base:
                return True
        except ValueError:  # different drives on Windows
            continue
    return False


class OwnerPolicy:
    def __init__(self, profile: OwnerProfile):
        self.profile = profile

    def should_interrupt(self, trigger: str) -> bool:
        return trigger in self.profile.interrupt_on

    def decide(
        self,
        action: Dict[str, Any],
        hour: Optional[int] = None,
        spent_usd: float = 0.0,
    ) -> Decision:
        p = self.profile
        name = action.get("name")
        risk = action.get("risk", "critical")
        if risk not in RISK_ORDER:
            return Decision(False, False, "unknown_risk")
        if name in p.blocked_actions:
            return Decision(False, False, "blocked_action")
        cost = action.get("cost_usd", 0.0)
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0:
            return Decision(False, False, "invalid_cost")
        if cost > 0 and spent_usd + cost > p.budget_cap_usd:
            return Decision(False, False, "over_budget")
        path = action.get("path")
        if path is not None and not (p.allowed_dirs and _inside(str(path), p.allowed_dirs)):
            return Decision(False, False, "path_outside_allowed")
        if RISK_ORDER[risk] >= RISK_ORDER[p.approval_at_or_above]:
            return Decision(True, True, "risk_requires_approval")
        if p.quiet_hours is not None and hour is not None:
            start, end = p.quiet_hours
            quiet = (start <= hour < end) if start <= end else (hour >= start or hour < end)
            if quiet:
                return Decision(True, True, "quiet_hours")
        return Decision(True, False, "allowed")