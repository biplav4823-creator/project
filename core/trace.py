"""CP-48: secret-safe job traces and metrics built from recorded events.

Pure functions over event dicts (event_type, step_id, payload, timestamp).
No network, no LLM. Payloads are redacted before they leave this module.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SECRET_KEY = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|authorization|credential|cookie)",
    re.IGNORECASE,
)
SECRET_VALUE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|bearer\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})",
    re.IGNORECASE,
)
FAILURE_EVENTS = {"execution_failed", "execution_unknown", "execution_not_started"}
DECISION_HINTS = ("plan", "route", "skill", "tool", "model", "recovery", "approval")
MAX_STR = 500


def redact(value: Any, _depth: int = 0) -> Any:
    if _depth > 8:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        return {
            str(k): ("[REDACTED]" if SECRET_KEY.search(str(k)) else redact(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v, _depth + 1) for v in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub("[REDACTED]", value)[:MAX_STR]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return f"<{type(value).__name__}>"


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _num(payload: Dict[str, Any], key: str) -> float:
    value = payload.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def build_trace(job_id: str, events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    events = list(events)
    by_type: Counter = Counter()
    steps: Dict[Any, Dict[str, Any]] = {}
    decisions: List[Dict[str, Any]] = []
    totals = {"prompt_tokens": 0.0, "completion_tokens": 0.0, "cost_usd": 0.0}

    for event in events:
        etype = str(event.get("event_type"))
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        step_id = event.get("step_id")
        ts = _parse_ts(event.get("timestamp") or event.get("created_at"))
        by_type[etype] += 1

        for key in totals:
            totals[key] += _num(payload, key)

        if step_id is not None:
            step = steps.setdefault(
                step_id,
                {"attempts": 0, "reused": 0, "failures": 0, "_first": None, "_last": None},
            )
            if etype == "execution_started":
                step["attempts"] += 1
            elif etype == "execution_reused":
                step["reused"] += 1
            elif etype in FAILURE_EVENTS:
                step["failures"] += 1
            if ts is not None:
                step["_first"] = step["_first"] or ts
                step["_last"] = ts

        if any(hint in etype for hint in DECISION_HINTS):
            decisions.append(
                {"event_type": etype, "step_id": step_id, "payload": redact(payload)}
            )

    per_step = {}
    for step_id, step in steps.items():
        latency = None
        if step["_first"] and step["_last"]:
            latency = round((step["_last"] - step["_first"]).total_seconds(), 4)
        per_step[str(step_id)] = {
            "attempts": step["attempts"],
            "reused": step["reused"],
            "failures": step["failures"],
            "latency_seconds": latency,
        }

    return {
        "job_id": job_id,
        "event_count": len(events),
        "events_by_type": dict(sorted(by_type.items())),
        "steps": per_step,
        "decisions": decisions,
        "totals": {
            "attempts": sum(s["attempts"] for s in per_step.values()),
            "failures": sum(s["failures"] for s in per_step.values()),
            "prompt_tokens": int(totals["prompt_tokens"]),
            "completion_tokens": int(totals["completion_tokens"]),
            "cost_usd": round(totals["cost_usd"], 6),
        },
    }


def export_jsonl(trace: Dict[str, Any], path: str) -> None:
    lines = [{"kind": "summary", **{k: v for k, v in trace.items() if k != "decisions"}}]
    lines += [{"kind": "decision", "job_id": trace["job_id"], **d} for d in trace["decisions"]]
    Path(path).write_text(
        "\n".join(json.dumps(line, sort_keys=True) for line in lines) + "\n",
        encoding="utf-8",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core.trace")
    parser.add_argument("job_id")
    parser.add_argument("--db", help="State database path (default: application default).")
    parser.add_argument("--out", help="Write JSON Lines export to this path.")
    args = parser.parse_args(argv)

    from core.agent import Agent

    agent = Agent()
    if args.db:
        from core.state_store import StateStore

        agent.orchestrator.state_store = StateStore(args.db)
    try:
        events = agent.get_execution_history(args.job_id)
    except Exception as exc:
        print(f"ERROR: cannot read history ({type(exc).__name__}).", file=sys.stderr)
        return 1
    trace = build_trace(args.job_id, events)
    print(json.dumps(trace, indent=2))
    if args.out:
        export_jsonl(trace, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())