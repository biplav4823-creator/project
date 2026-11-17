"""CP-59: read-only readiness audit across the design gap list.

`python -m core.readiness_audit [--live] [--json PATH]`
Statuses: PASS (verified), FAIL (defect, exit code 1), GAP (known,
not-yet-wired or missing capability), SKIP (not run). Never prints secrets
and never modifies the repository.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List

ROOT = Path(__file__).resolve().parent.parent
SECRET = "sk-AUDITPROBE1234567890"
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|bearer\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})", re.IGNORECASE)

RESULTS: List[Dict[str, str]] = []


def rec(area: str, check: str, status: str, detail: str = "") -> None:
    RESULTS.append({"area": area, "check": check, "status": status,
                    "detail": _SECRET_RE.sub("[REDACTED]", detail)[:300]})


def guarded(area: str, check: str, fn: Callable[[], None]) -> None:
    try:
        fn()
    except Exception as exc:  # type name only
        rec(area, check, "FAIL", f"audit step raised {type(exc).__name__}")


def make_agent(tmp: str):
    from core.agent import Agent
    from core.state_store import StateStore

    agent = Agent()
    agent.orchestrator.state_store = StateStore(os.path.join(tmp, "audit.sqlite"))
    return agent


# --------------------------------------------------------------- CP-44 provider
def audit_provider() -> None:
    area = "provider"
    from unittest import mock

    import core.llm as llm

    names = ("ask_messages", "ask_ollama", "get_active_model", "_ask_omniroute", "_ask_ollama")
    missing = [n for n in names if not hasattr(llm, n)]
    rec(area, "llm API present", "FAIL" if missing else "PASS", ",".join(missing))

    has_attr = hasattr(llm, "last_provider")
    rec(area, "provider attribution API", "PASS" if has_attr else "FAIL",
        "" if has_attr else "core.llm.last_provider missing (apply cp59 patch)")

    msgs = [{"role": "user", "content": "hi"}]
    with mock.patch.object(llm, "LLM_PROVIDER", "omniroute"), \
            mock.patch.object(llm, "get_active_model", lambda: "stub-model"):
        with mock.patch.object(llm, "_ask_omniroute", lambda m, model: "OMNI"):
            ok = llm.ask_messages(msgs) == "OMNI"
            who = llm.last_provider()["provider"] if has_attr else None
            rec(area, "OmniRoute path answers + attributed",
                "PASS" if ok and who == "omniroute" else "FAIL", f"attributed={who}")

        def omni_down(m, model):
            raise RuntimeError("gateway down")

        with mock.patch.object(llm, "_ask_omniroute", omni_down), \
                mock.patch.object(llm, "_ask_ollama", lambda m, u=None, mo=None: "OLLAMA"):
            ok = llm.ask_messages(msgs) == "OLLAMA"
            who = llm.last_provider()["provider"] if has_attr else None
            rec(area, "independent Ollama fallback + attributed",
                "PASS" if ok and who == "ollama" else "FAIL", f"attributed={who}")

        def leaky(*a, **k):
            raise RuntimeError(f"failure with {SECRET}")

        with mock.patch.object(llm, "_ask_omniroute", leaky), \
                mock.patch.object(llm, "_ask_ollama", leaky):
            try:
                llm.ask_messages(msgs)
                rec(area, "both-fail error is secret-safe", "FAIL", "no exception raised")
            except RuntimeError as exc:
                text = str(exc)
                safe = SECRET not in text and "OmniRoute" in text and "Ollama" in text
                rec(area, "both-fail error is secret-safe and actionable",
                    "PASS" if safe else "FAIL", "" if safe else "secret leaked or summary missing")


def audit_provider_live() -> None:
    area = "provider-live"
    try:
        proc = subprocess.run([sys.executable, "-m", "core.llm_diagnostics"], cwd=ROOT,
                              capture_output=True, text=True, timeout=90)
    except Exception as exc:
        rec(area, "provider diagnostics", "FAIL", type(exc).__name__)
        return
    out = _SECRET_RE.sub("[REDACTED]", (proc.stdout or "") + (proc.stderr or ""))
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()][:25]
    rec(area, "provider diagnostics exit code", "PASS" if proc.returncode == 0 else "GAP",
        f"rc={proc.returncode}")
    for ln in lines:
        print("    | " + ln[:160])


# ------------------------------------------------------------ CP-45 observability
def audit_observability() -> None:
    area = "observability"
    with tempfile.TemporaryDirectory() as tmp:
        agent = make_agent(tmp)

        def calculate(expression: str) -> str:
            return "5"

        agent.register_tool("calculate", "Evaluate arithmetic", calculate, risk="low")
        state = agent.run("calculate 2 + 3")
        events = agent.get_execution_history(state.job_id)
        trace = agent.get_trace(state.job_id)
        rec(area, "job-level trace available",
            "PASS" if trace["event_count"] > 0 and trace["totals"]["attempts"] >= 1 else "FAIL",
            f"events={trace['event_count']} attempts={trace['totals']['attempts']}")
        stamped = any(e.get("timestamp") or e.get("created_at") for e in events)
        latency = any(s["latency_seconds"] is not None for s in trace["steps"].values())
        rec(area, "latency metrics", "PASS" if latency else "GAP",
            "" if latency else "events carry no usable timestamps" if not stamped
            else "timestamps present but per-step span is empty")
        types = {e.get("event_type", "") for e in events}
        rec(area, "model-call events (tokens/cost)",
            "PASS" if any("model" in t for t in types) else "GAP",
            "runtime emits no model_call events; cost metrics are empty")
        rec(area, "planner decisions recorded",
            "PASS" if hasattr(agent.planner, "decisions") else "GAP",
            "planner exposes .decisions" if hasattr(agent.planner, "decisions")
            else "planner is not the CP-51 LLMPlanner")

        def failing(expression: str) -> str:
            raise ValueError(SECRET)

        agent2 = make_agent(tmp + "")
        agent2.register_tool("calculate", "Evaluate arithmetic", failing, risk="low")
        bad = agent2.run("calculate 2 + 3")
        dump = json.dumps(agent2.get_execution_history(bad.job_id), default=str)
        try:
            dump += json.dumps(agent2.orchestrator.state_store.load(bad.job_id), default=str)
        except Exception:
            pass
        rec(area, "secret-safe event records (tool error path)",
            "FAIL" if SECRET in dump else "PASS",
            "raw exception text persisted" if SECRET in dump else "")

    src = (ROOT / "core" / "orchestrator.py").read_text(encoding="utf-8", errors="replace")
    hits = [(i, ln.strip()[:100]) for i, ln in enumerate(src.splitlines(), 1)
            if re.search(r"\bstr\((exc|e|error)\)", ln)]
    rec(area, "no raw str(exc) in orchestrator", "FAIL" if hits else "PASS",
        "; ".join(f"L{i}: {t}" for i, t in hits[:6]))

    from core.evals import builtin_tasks, run_suite

    report = run_suite(builtin_tasks(), k=2)
    s = report["summary"]
    rec(area, "repeatable benchmark suite (pass^k=1, no false success)",
        "PASS" if s["pass_hat_k"] == 1.0 and s["false_success_rate"] == 0.0 else "FAIL",
        f"pass^k={s['pass_hat_k']} false_success={s['false_success_rate']}")


# --------------------------------------------------- CP-46 / CP-47 modules + wiring
def _wired(module: str) -> bool:
    pat = re.compile(rf"(from\s+(core\.|\.)?{module}\s+import|import\s+(core\.)?{module}|from\s+core\s+import\s+{module})")
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("verify_", "core/readiness_audit")) or rel == f"core/{module}.py" \
                or "/." in rel or rel.startswith("."):
            continue
        try:
            if pat.search(path.read_text(encoding="utf-8", errors="replace")):
                return True
        except OSError:
            continue
    return False


def audit_modules() -> None:
    area = "governance"
    from core.skill_manifest import McpAllowlist, McpDenied, SkillRegistry

    mcp = McpAllowlist(lambda s, t, a: {"ok": True})
    try:
        mcp.invoke("x", "y", {})
        rec(area, "MCP deny-by-default", "FAIL", "unlisted tool executed")
    except McpDenied:
        rec(area, "MCP deny-by-default", "PASS")
    reg = SkillRegistry()
    m = {"name": "a1", "version": "1.0.0", "description": "d", "capabilities": ["c"],
         "permissions": [], "risk": "low", "dependencies": [],
         "provenance": {"source": "s", "sha256": "0" * 64}}
    reg.register(m)
    rec(area, "manifest registry registers + validates", "PASS" if reg.names() == ["a1"] else "FAIL")

    from core.delegation import Budget, DelegationError, Delegator

    try:
        Delegator(Budget(permissions=frozenset({"read"}))).delegate(
            "c", lambda c: {}, {"write"}, {}, lambda o: True)
        rec(area, "delegation blocks permission escalation", "FAIL")
    except DelegationError:
        rec(area, "delegation blocks permission escalation", "PASS")

    for module, role in (("skill_manifest", "manifests + MCP allowlist"),
                         ("delegation", "bounded delegation"), ("owner", "owner policy"),
                         ("memory", "memory store"), ("vault", "secret broker"),
                         ("artifacts", "artifact store"), ("scheduler", "scheduler"),
                         ("dag", "DAG executor"), ("skill_scanner", "skill scanner"),
                         ("trace", "traces"), ("llm_planner", "LLM planner")):
        if not (ROOT / "core" / f"{module}.py").exists():
            rec("wiring", f"{role}", "SKIP", f"core/{module}.py not present")
            continue
        rec("wiring", f"{role} used by runtime",
            "PASS" if _wired(module) else "GAP", "" if _wired(module) else "standalone, not imported by runtime")


# ------------------------------------------------------------------- repo hygiene
def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=60).stdout


def audit_repo() -> None:
    area = "repo"
    dirty = _git("status", "--porcelain", "--untracked-files=no").strip()
    rec(area, "tracked files clean", "FAIL" if dirty else "PASS", dirty[:120])
    tags = set(_git("tag").split())
    need = {t for t in ("baseline-cp46", "baseline-cp47", "baseline-cp50", "baseline-cp51") if t not in tags}
    rec(area, "baseline tags present", "GAP" if need else "PASS", ",".join(sorted(need)))
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8", errors="replace") \
        if (ROOT / ".gitignore").exists() else ""
    missing = [p for p in (".env", "*.db", "*.sqlite") if p not in ignore]
    rec(area, ".gitignore covers secrets and databases", "FAIL" if missing else "PASS", ",".join(missing))

    tracked = [f for f in _git("ls-files").splitlines() if f]
    bad = [f for f in tracked if re.search(r"(^|/)\.env($|\.)|\.(db|sqlite)$", f)]
    rec(area, "no env/database files tracked", "FAIL" if bad else "PASS", ",".join(bad[:5]))
    leaks = []
    for f in tracked:
        p = ROOT / f
        if p.suffix.lower() in (".py", ".md", ".txt", ".yml", ".yaml", ".json", ".ps1", ".toml", ".cfg", ".ini") \
                and p.exists() and p.stat().st_size < 1_000_000:
            text = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)", text):
                leaks.append(f)
    rec(area, "no hard-coded secrets in tracked files", "FAIL" if leaks else "PASS", ",".join(leaks[:5]))
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    rec(area, "CI workflow present", "PASS" if ci.exists() else "FAIL")
    doc = ROOT / "docs" / "PRE_MASTER_PLAN_READINESS.md"
    if doc.exists():
        nums = [int(n) for n in re.findall(r"CP-(\d+)", doc.read_text(encoding="utf-8", errors="replace"))]
        top = max(nums) if nums else 0
        rec(area, "readiness doc current", "PASS" if top >= 58 else "GAP", f"highest checkpoint mentioned: CP-{top}")
    mem = ROOT / "core" / "memory.py"
    rec(area, "core/memory.py implemented", "PASS" if mem.exists() and mem.stat().st_size > 200 else "GAP")


def render(results: List[Dict[str, str]]) -> str:
    lines, area = [], None
    for r in results:
        if r["area"] != area:
            area = r["area"]
            lines.append(f"\n[{area}]")
        suffix = f"  - {r['detail']}" if r["detail"] else ""
        lines.append(f"  {r['status']:<4} {r['check']}{suffix}")
    counts = {s: sum(1 for r in results if r["status"] == s) for s in ("PASS", "FAIL", "GAP", "SKIP")}
    lines.append("\nSUMMARY: " + "  ".join(f"{k}={v}" for k, v in counts.items()))
    return "\n".join(lines)


def exit_code(results: List[Dict[str, str]]) -> int:
    return 1 if any(r["status"] == "FAIL" for r in results) else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core.readiness_audit")
    parser.add_argument("--live", action="store_true", help="also run provider diagnostics")
    parser.add_argument("--json", help="write results to this path")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))

    steps = [("provider", "static", audit_provider), ("observability", "all", audit_observability),
             ("governance", "all", audit_modules), ("repo", "all", audit_repo)]
    for area, check, fn in steps:
        guarded(area, check, fn)
    if args.live:
        guarded("provider-live", "diagnostics", audit_provider_live)
    print(render(RESULTS))
    if args.json:
        Path(args.json).write_text(json.dumps(RESULTS, indent=2), encoding="utf-8")
    return exit_code(RESULTS)


if __name__ == "__main__":
    sys.exit(main())