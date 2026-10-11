from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

CHECKPOINTS = [
    "verify_cp11_cp12.py",
    "verify_cp13.py",
    "verify_cp14.py",
    "verify_cp15.py",
    "verify_cp16.py",
    "verify_cp17.py",
    "verify_cp18.py",
    "verify_cp19.py",
    "verify_cp26.py",
    "verify_cp28.py",
    "verify_cp32.py",
    "verify_cp33.py",
    "verify_cp34.py",
    "verify_cp35.py",
    "verify_cp36.py",
]

REQUIRED_FILES = [
    "core/agent.py",
    "core/planner.py",
    "core/router.py",
    "core/orchestrator.py",
    "core/executor.py",
    "core/verifier.py",
    "core/recovery.py",
    "core/state.py",
    "core/state_store.py",
    "core/approval.py",
    "core/guardrail.py",
    "core/skill_manager.py",
    "core/skill_policy.py",
    "core/tool_runtime.py",
    "core/llm.py",
    "core/llm_diagnostics.py",
    "capabilities/registry.py",
    "docs/PRE_MASTER_PLAN_READINESS.md",
]


def main():
    failures = []

    print("JARVIS PRE-MASTER-PLAN VERIFICATION", flush=True)
    print(f"Repository: {ROOT}", flush=True)

    print("\n=== Architecture and documentation inventory ===", flush=True)
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if path.is_file():
            print(f"[PASS] {relative}", flush=True)
        else:
            print(f"[FAIL] Missing {relative}", flush=True)
            failures.append(f"inventory:{relative}")

    document = ROOT / "docs/PRE_MASTER_PLAN_READINESS.md"
    if document.is_file():
        contents = document.read_text(encoding="utf-8")
        for marker in (
            "## Current architecture",
            "## Operational provider status",
            "## Confirmed defects and unfinished integration work",
            "## Master-plan design constraints",
            "## Readiness decision",
        ):
            if marker in contents:
                print(f"[PASS] Readiness section: {marker}", flush=True)
            else:
                print(f"[FAIL] Readiness section missing: {marker}", flush=True)
                failures.append(f"documentation:{marker}")

    print("\n=== Historical and current checkpoint verifiers ===", flush=True)
    for script in CHECKPOINTS:
        path = ROOT / script
        if not path.is_file():
            print(f"[FAIL] Missing checkpoint verifier: {script}", flush=True)
            failures.append(f"missing:{script}")
            continue

        print(f"\n--- {script} ---", flush=True)
        try:
            result = subprocess.run(
                [sys.executable, str(path)],
                cwd=ROOT,
                check=False,
            )
        except OSError as exc:
            print(f"[FAIL] Could not run {script}: {type(exc).__name__}", flush=True)
            failures.append(f"launch:{script}")
            continue

        if result.returncode == 0:
            print(f"[PASS] {script}", flush=True)
        else:
            print(
                f"[FAIL] {script} exited with code {result.returncode}",
                flush=True,
            )
            failures.append(f"checkpoint:{script}")

    print("\n=== Compilation ===", flush=True)
    result = subprocess.run(
        [
            sys.executable, "-m", "compileall", "-q",
            "core", "capabilities", "faculties", "tools",
        ],
        cwd=ROOT,
        check=False,
    )
    if result.returncode == 0:
        print("[PASS] Python compilation", flush=True)
    else:
        print(f"[FAIL] Compilation exited {result.returncode}", flush=True)
        failures.append("compileall")

    print("\n=== Baseline summary ===", flush=True)
    passed = len(CHECKPOINTS) + len(REQUIRED_FILES) + 5 + 1
    # The total above is informational; failures, not the count, decide success.
    print(f"Checkpoint verifiers declared: {len(CHECKPOINTS)}")
    print(f"Required files checked: {len(REQUIRED_FILES)}")

    if failures:
        print(f"\nBASELINE FAILED: {len(failures)} item(s)", flush=True)
        for failure in failures:
            print(f" - {failure}", flush=True)
        print("Do not mark the pre-master-plan stage complete.", flush=True)
        return 1

    print("\nBASELINE PASSED", flush=True)
    print("All declared checkpoint verifiers and inventory checks passed.", flush=True)
    print("Live provider health is a separate operational check.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
