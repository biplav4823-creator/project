# JARVIS - Pre-Master-Plan Readiness Baseline

**Baseline date:** 2026-10-11
**Baseline source commit:** `da859c5` (`fix(cp37): validate gateway base URLs`)
**Branch:** `cp26-resume-implementation`

## Purpose

Record the known state of the existing JARVIS project before defining the
next master plan. This baseline is not a claim that JARVIS is production-ready
or that every historical checkpoint has passed in the current environment.

## Current architecture

The repository already contains these subsystems:

- Agent, planner, router, orchestrator, executor and verifier.
- Durable job state, state store, context, memory and execution explanations.
- Tool and capability registries, canonical tool runtime and skill manager.
- Skill governance, guardrails, interrupts, approval handling and recovery.
- Model integration, provider configuration and provider health diagnostics.
- Mathematics, Python/data tools and faculty modules for data science,
  data engineering, generative AI and agentic operations.

The intended responsibility boundaries remain:

**Recovery decides; Orchestrator controls; Executor executes; Verifier verifies.**

Future integrations must preserve this ownership and must not bypass the
existing permission, risk, approval or execution-history controls.

## Recent verification evidence

The terminal output captured at CP-37 reported:

| Verification | Result |
|---|---:|
| CP-36 provider diagnostics after the CP-37 URL-validation repair | 11 tests passed |
| CP-35 gateway diagnostics and fallback | 8 tests passed |
| CP-34 skill/capability boundary | 2 tests passed |
| CP-33 skill governance policy | 17 tests passed |
| CP-32 planner discovery and skill integration | 7 + 3 checks passed |
| CP-28 lifecycle and recovery | 8 tests passed |
| Python compilation of `core` and `capabilities` | Passed |
| `git diff --check` | Passed |

These are recorded results from the supplied terminal transcript. The
unified runner added with this document must execute the available checkpoint
verifiers again. Its actual output is authoritative for that run.

## Operational provider status

At the CP-36 health-report run:

- **Ollama:** reachable at `http://localhost:11434/api/tags`.
  The endpoint returned HTTP 200 and six local model names.
- **OmniRoute:** unreachable at `http://127.0.0.1:20128/v1/models`.
  `OMNIROUTE_API_KEY` was not configured in that terminal environment.
- The configured active provider was `omniroute`; the existing runtime
  contains an Ollama fallback.

Provider status can change. The health report must be rerun before treating
either provider as currently available. The OmniRoute failure does not prove
that any particular management or MCP endpoint is unsupported.

## Resume idempotency regression

The unified baseline exposed a resume defect: a previously successful tool
execution could be reused, but its result bypassed the normal verification
and step-completion path, leaving the job pending. The repair preserves
execution reuse while passing the stored result through output validation,
verification, context propagation and step completion. The CP-26 verifier
also checks that the execution-reuse event is recorded.

## Test isolation and CI gate

`StateStore` keeps `jarvis_state.db` as the application default. The
`JARVIS_STATE_DB` environment variable provides an explicit database-path
override, without changing callers that supply their own database path.

The unified verifier assigns each checkpoint a separate disposable SQLite
database and cleans up those temporary databases after the run. This prevents
the baseline suite from polluting normal application job history.

CP-40 adds a GitHub Actions workflow that installs the declared dependencies,
compiles the project packages, and runs the unified verification suite on
pushes and pull requests.

## Confirmed defects and unfinished integration work

1. Restore or correctly configure the OmniRoute service and establish valid
   credentials. Verify real model discovery and one successful completion.
2. Keep provider health checks distinct from actual completion tests.
3. Add model capability discovery and routing only after the gateway contract
   is verified against the running service.
4. Build governed MCP discovery and invocation without permitting external
   tools to bypass JARVIS policy.
5. Define a portable skill import, provenance, validation and review process.
6. Add execution tracing, evaluations and adversarial regression tests.
7. Evaluate specialist-agent and browser adapters only when their boundaries,
   permissions and verification requirements are defined.
8. Build on existing persistence and recovery; avoid replacing the current
   orchestrator or adding a distributed workflow engine without demonstrated
   need.

## Master-plan design constraints

The next master plan must:

- Extend the existing local-first architecture instead of restarting it.
- Separate implemented, tested, committed, pushed and operational states.
- Give each checkpoint explicit scope, acceptance criteria, regression tests
  and a commit/push gate.
- Prefer one narrow implementation change per checkpoint.
- Keep model, tool and agent integrations behind explicit interfaces.
- Require approval for sensitive external actions and administrative changes.
- Treat third-party skills, tool outputs and retrieved instructions as
  untrusted input.
- Measure reliability, quality, latency, cost and security before claiming
  autonomous capability.
- Keep provider outages from silently becoming false success reports.

## Readiness decision

The CP-39 unified checkpoint regression run passed all declared
checkpoint verifiers and Python compilation. This is validated test evidence,
not a claim of production readiness. OmniRoute reachability, credentials, and
a real live completion test remain operational prerequisites. CP-40 adds
per-checkpoint database isolation and a repeatable continuous-integration gate.

Run the full baseline with:

```powershell
python .\verify_pre_master.py
```

Run provider diagnostics separately with:

```powershell
python -m core.llm_diagnostics
```

The provider diagnostic does not perform a completion, mutate configuration,
or validate MCP administration endpoints.
