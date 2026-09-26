import ast
import re
import uuid
from dataclasses import asdict

from core.state import JobState, StepState
from core.guardrail import Guardrail
from core.approval import ApprovalGate
from core.interrupt import InterruptEngine
from core.recovery import Recovery
from core.state_store import StateStore
from core.context import Context


class Orchestrator:
    def __init__(
        self,
        planner,
        router,
        executor,
        verifier,
        explainer,
        capabilities=None,
        guardrail=None,
        interrupt_engine=None,
        approval_gate=None,
        recovery=None,
        state_store=None,
        context=None,
    ):
        self.planner = planner
        self.router = router
        self.executor = executor
        self.verifier = verifier
        self.explainer = explainer
        self.capabilities = capabilities

        self.guardrail = guardrail or Guardrail(
            allow_medium=True,
            allow_high=True,
        )

        self.interrupt_engine = (
            interrupt_engine or InterruptEngine()
        )

        self.approval_gate = (
            approval_gate or ApprovalGate()
        )

        self.recovery = recovery or Recovery()
        self.state_store = state_store or StateStore()
        self.context = context or Context()

    # =========================================================
    # DEPENDENCY VALUES
    # =========================================================

    def _dependency_values(self, previous_results):
        values = {}

        for item in previous_results:
            step_id = item.get("step")
            result = item.get("result")

            if step_id is None or result is None:
                continue

            if isinstance(result, dict) and "result" in result:
                result = result["result"]

            values[f"$step{step_id}.result"] = result
            values[f"$step{step_id}"] = result

        return values

    # =========================================================
    # REFERENCE RESOLUTION
    # =========================================================

    def _resolve_references(self, text, previous_results):
        values = self._dependency_values(previous_results)
        resolved = text

        for reference, value in values.items():
            resolved = resolved.replace(
                reference,
                str(value),
            )

        if previous_results:
            latest = previous_results[-1].get("result")

            if isinstance(latest, dict) and "result" in latest:
                latest = latest["result"]

            latest_text = str(latest)

            resolved = re.sub(
                r"\b(the\s+)?(previous|prior|last)\s+(result|answer|value)\b",
                latest_text,
                resolved,
                flags=re.I,
            )

            resolved = re.sub(
                r"\bthe\s+result\b",
                latest_text,
                resolved,
                count=1,
                flags=re.I,
            )

        return resolved

    # =========================================================
    # ARGUMENT PARSING
    # =========================================================

    def _arguments(
        self,
        capability,
        description,
        previous_results,
    ):
        text = self._resolve_references(
            description.strip(),
            previous_results,
        )

        prefixes = {
            "calculate": "calculate ",
            "simplify": "simplify ",
            "factor": "factor ",
            "expand": "expand ",
            "derivative": "derivative ",
            "integral": "integral ",
            "definite_integral": "definite integral ",
            "limit": "limit ",
            "series": "series ",
            "numerical": "numerical ",
            "nth_derivative": "nth derivative ",
            "solve_equation": "solve ",
            "solve_system": "solve system ",
            "matrix_determinant": "determinant ",
            "matrix_inverse": "inverse ",
            "matrix_rank": "rank ",
            "run_python": "python ",
        }

        prefix = prefixes.get(
            capability,
            "",
        )

        expression = (
            text[len(prefix):].strip()
            if prefix
            and text.lower().startswith(prefix)
            else text
        )

        if capability == "calculate":
            patterns = [
                (
                    r"^multiply\s+(.+?)\s+by\s+(.+)$",
                    r"\1 * \2",
                ),
                (
                    r"^multiplied\s+(.+?)\s+by\s+(.+)$",
                    r"\1 * \2",
                ),
                (
                    r"^add\s+(.+?)\s+and\s+(.+)$",
                    r"\1 + \2",
                ),
                (
                    r"^add\s+(.+?)\s+to\s+(.+)$",
                    r"\2 + \1",
                ),
                (
                    r"^subtract\s+(.+?)\s+from\s+(.+)$",
                    r"\2 - \1",
                ),
                (
                    r"^divide\s+(.+?)\s+by\s+(.+)$",
                    r"\1 / \2",
                ),
            ]

            for pattern, replacement_expr in patterns:
                if re.match(
                    pattern,
                    expression,
                    flags=re.I,
                ):
                    expression = re.sub(
                        pattern,
                        replacement_expr,
                        expression,
                        flags=re.I,
                    )
                    break

        if capability in {
            "derivative",
            "nth_derivative",
        }:
            expression = re.sub(
                r"^\s*of\s+",
                "",
                expression,
                flags=re.I,
            )

            variable = None

            match = re.search(
                r"\s+(?:with\s+respect\s+to|wrt)\s+([A-Za-z_]\w*)\s*$",
                expression,
                flags=re.I,
            )

            if match:
                variable = match.group(1)
                expression = expression[
                    :match.start()
                ].strip()

            arguments = {
                "expression": expression
            }

            if variable:
                arguments["variable"] = variable

            return arguments

        if capability == "solve_equation":
            expression = re.sub(
                r"^\s*(?:the\s+)?equation\s+",
                "",
                expression,
                flags=re.I,
            )

            variable = None

            match = re.search(
                r"\s+(?:for|with\s+respect\s+to|wrt)\s+([A-Za-z_]\w*)\s*$",
                expression,
                flags=re.I,
            )

            if match:
                variable = match.group(1)
                expression = expression[
                    :match.start()
                ].strip()

            arguments = {
                "expression": expression
            }

            if variable:
                arguments["variable"] = variable

            return arguments

        if capability == "solve_system":
            equations_text = re.sub(
                r"^\s*(?:the\s+)?system\s+",
                "",
                expression,
                flags=re.I,
            )

            equations = [
                part.strip()
                for part in re.split(
                    r"\s+and\s+|,\s*",
                    equations_text,
                    flags=re.I,
                )
                if part.strip()
            ]

            if not equations:
                raise ValueError(
                    "No equations found for solve_system."
                )

            variables = sorted(
                set(
                    re.findall(
                        r"\b[A-Za-z_]\w*\b",
                        " ".join(equations),
                    )
                )
            )

            variables = [
                value
                for value in variables
                if value.lower() not in {
                    "and",
                    "or",
                    "the",
                    "system",
                    "solve",
                }
            ]

            return {
                "equations": ";".join(equations),
                "variables": ",".join(variables),
            }

        if capability in {
            "matrix_determinant",
            "matrix_inverse",
            "matrix_rank",
        }:
            match = re.search(
                r"\[\[.*?\]\]",
                text,
            )

            if not match:
                raise ValueError(
                    "Matrix data not found in request."
                )

            return {
                "matrix": ast.literal_eval(
                    match.group(0)
                )
            }

        return {
            "expression": expression
        }

    # =========================================================
    # STATE PERSISTENCE
    # =========================================================

    def _record_event(self, state, event_type, step_id=None, payload=None):
        self.state_store.record_event(
            state.job_id,
            event_type,
            step_id=step_id,
            payload=payload or {},
        )

    def _persist_state(self, state):
        self.state_store.save(
            state.job_id,
            asdict(state),
        )

    # =========================================================
    # CONTEXT UPDATE
    # =========================================================

    def _update_context(self, step_id, result):
        self.context.set(
            f"step{step_id}",
            result,
        )

        self.context.set(
            f"step{step_id}.result",
            result,
        )

        self.context.set(
            "last_result",
            result,
        )

    # =========================================================
    # EXECUTION HISTORY
    # =========================================================

    def _state_from_dict(self, data):
        plan = [
            StepState(
                id=s["id"],
                description=s["description"],
                status=s.get("status", "pending"),
                depends_on=s.get("depends_on", []),
                capability=s.get("capability"),
                candidates=s.get("candidates", []),
                result=s.get("result"),
            )
            for s in data.get("plan", [])
        ]

        return JobState(
            job_id=data["job_id"],
            user_input=data["user_input"],
            goal=data["goal"],
            plan=plan,
            current_step=data.get("current_step"),
            completed_steps=data.get("completed_steps", []),
            failed_steps=data.get("failed_steps", []),
            intermediate_results=data.get(
                "intermediate_results",
                [],
            ),
            execution_context=data.get(
                "execution_context",
                {},
            ),
            interrupts=data.get("interrupts", []),
            approval=data.get("approval"),
            recovery_attempts={
                int(k): v
                for k, v in data.get(
                    "recovery_attempts",
                    {},
                ).items()
            },
            max_recovery_attempts=data.get(
                "max_recovery_attempts",
                1,
            ),
            status=data.get("status", "created"),
        )

    def get_execution_history(self, job_id):
        """Return the recorded execution events for a job."""
        if not job_id:
            return []

        return self.state_store.get_events(job_id)

    # =========================================================
    # MAIN EXECUTION
    # =========================================================

    def resume(self, job_id, tools):
        data = self.state_store.load(job_id)

        if data is None:
            raise ValueError(
                f"No persisted job found for job_id: {job_id}"
            )

        state = self._state_from_dict(data)

        if state.status == "completed":
            return self.explainer.explain(state)

        if state.status == "waiting_approval":
            return self.explainer.explain(state)

        state.status = "running"

        plan = {
            "goal": state.goal,
            "steps": [
                {
                    "id": step.id,
                    "description": step.description,
                    "status": step.status,
                    "depends_on": step.depends_on,
                    "capability": step.capability,
                    "candidates": step.candidates,
                    "result": step.result,
                }
                for step in state.plan
            ],
        }

        self._record_event(
            state,
            "job_resumed",
            payload={
                "completed_steps": state.completed_steps,
                "current_step": state.current_step,
            },
        )
        self._persist_state(state)

        return self._execute_state(
            state,
            plan,
            tools,
        )

    def _execute_state(self, state, plan, tools):
        for raw, step in zip(
            plan["steps"],
            state.plan,
        ):
            if step.id in state.completed_steps or step.status == "completed":
                self._record_event(
                    state,
                    "step_skipped_on_resume",
                    step_id=step.id,
                    payload={"reason": "already_completed"},
                )
                self._persist_state(state)
                continue

            state.current_step = step.id
            recovery_attempts = state.recovery_attempts.get(
                step.id,
                0,
            )
            max_recovery_attempts = state.max_recovery_attempts
            self._record_event(
                state,
                "step_started",
                step_id=step.id,
                payload={
                    "description": step.description,
                    "depends_on": step.depends_on,
                },
            )
            self._persist_state(state)

            deps = [
                x
                for x in state.intermediate_results
                if x.get("step")
                in step.depends_on
            ]

            capability = raw.get(
                "capability"
            )

            if not capability:
                state.fail_step(
                    step.id,
                    "No capability found for: "
                    + step.description,
                )
                self._persist_state(state)
                break

            try:
                arguments = self._arguments(
                    capability,
                    step.description,
                    deps,
                )

                decision = {
                    "action": "tool",
                    "tool": capability,
                    "arguments": arguments,
                    "description": step.description,
                    "step_id": step.id,
                    "depends_on": step.depends_on,
                    "previous_results": deps,
                }

                route = self.router.route(
                    decision
                )

                if (
                    route.action != "tool"
                    or not route.tool
                ):
                    raise RuntimeError(
                        "Router did not select a tool for '"
                        + step.description
                        + "'"
                    )

                self._record_event(
                    state,
                    "capability_selected",
                    step_id=step.id,
                    payload={"capability": route.tool},
                )

                capability_contract = None

                if self.capabilities is not None:
                    capability_contract = (
                        self.capabilities.get(
                            route.tool
                        )
                    )

                    capability_contract.validate_input(
                        route.arguments
                    )

                    self.guardrail.check(
                        capability_contract,
                        route.arguments,
                    )

                    self._record_event(
                        state,
                        "guardrail_checked",
                        step_id=step.id,
                        payload={
                            "capability": route.tool,
                            "outcome": "allow",
                        },
                    )

                    interrupt_result = (
                        self.interrupt_engine.pre_execution(
                            capability_contract,
                            step_id=step.id,
                            arguments=route.arguments,
                        )
                    )

                    if interrupt_result.interrupts:
                        state.record_interrupts(
                            interrupt_result.interrupts
                        )

                        self._persist_state(
                            state
                        )

                    approval = (
                        self.approval_gate.evaluate(
                            capability_contract,
                            step_id=step.id,
                            arguments=route.arguments,
                            interrupts=(
                                interrupt_result.interrupts
                            ),
                        )
                    )

                    if approval.action != "allow":
                        self._record_event(
                            state,
                            "approval_requested",
                            step_id=step.id,
                            payload={
                                "action": approval.action,
                                "approval": str(approval),
                            },
                        )

                        state.wait_for_approval(
                            step.id,
                            approval,
                        )

                        self._persist_state(
                            state
                        )

                        break

                self._record_event(
                    state,
                    "execution_started",
                    step_id=step.id,
                    payload={"capability": route.tool},
                )

                result = self.executor.execute(
                    tools,
                    route.tool,
                    route.arguments,
                )

                self._record_event(
                    state,
                    "execution_completed",
                    step_id=step.id,
                    payload={"capability": route.tool},
                )

                if capability_contract is not None:
                    capability_contract.validate_output(
                        result
                    )

                verified = self.verifier.verify(
                    result
                )

                self._record_event(
                    state,
                    "verification_completed",
                    step_id=step.id,
                    payload={"capability": route.tool},
                )

                if capability_contract is not None:
                    post_interrupt = (
                        self.interrupt_engine.post_execution(
                            capability_contract,
                            verified,
                            step_id=step.id,
                        )
                    )

                    if post_interrupt.interrupts:
                        state.record_interrupts(
                            post_interrupt.interrupts
                        )

                    if (
                        post_interrupt.action
                        != "continue"
                    ):
                        raise RuntimeError(
                            "Post-execution interrupt: "
                            + str(
                                post_interrupt.interrupts
                            )
                        )

                state.complete_step(
                    step.id,
                    verified,
                )

                self._update_context(
                    step.id,
                    verified,
                )

                self._record_event(
                    state,
                    "step_completed",
                    step_id=step.id,
                    payload={"status": "completed"},
                )

                self._persist_state(
                    state,
                )

            except Exception as exc:
                recovery_result = (
                    self.recovery.recover(
                        exc
                    )
                )

                self._record_event(
                    state,
                    "recovery_attempted",
                    step_id=step.id,
                    payload={
                        "error": str(exc),
                        "recovery": str(recovery_result),
                    },
                )

                state.execution_context[
                    "recovery"
                ] = recovery_result

                if (
                    recovery_result.get("action") == "retry"
                    and recovery_attempts < max_recovery_attempts
                ):
                    recovery_attempts += 1

                    state.recovery_attempts[step.id] = recovery_attempts
                    state.execution_context[
                        "recovery_attempts"
                    ] = recovery_attempts

                    self._record_event(
                        state,
                        "recovery_retry",
                        step_id=step.id,
                        payload={
                            "attempt": recovery_attempts,
                            "max_attempts": max_recovery_attempts,
                            "reason": recovery_result.get("reason"),
                        },
                    )

                    self._persist_state(state)
                    continue

                state.fail_step(
                    step.id,
                    str(exc),
                )

                self._persist_state(
                    state,
                )

                break
        state.current_step = None
        state.finish()

        terminal_events = {
            'completed': 'job_completed',
            'failed': 'job_failed',
            'waiting_approval': 'approval_requested',
            'pending': 'job_pending',
        }

        terminal_event = terminal_events.get(state.status)

        if terminal_event is not None:
            self._record_event(
                state,
                terminal_event,
                payload={
                    'status': state.status,
                    'completed_steps': state.completed_steps,
                    'failed_steps': state.failed_steps,
                },
            )

        self._persist_state(state)
        return self.explainer.explain(
            state
        )


    def run(self, user_input, tools):
        plan = self.planner.plan(
            user_input
        )

        steps = [
            StepState(
                id=s["id"],
                description=s["description"],
                status=s.get(
                    "status",
                    "pending",
                ),
                depends_on=s.get(
                    "depends_on",
                    [],
                ),
                capability=s.get("capability"),
                candidates=s.get("candidates", []),
                result=s.get(
                    "result"
                ),
            )
            for s in plan["steps"]
        ]

        state = JobState(
            job_id=f"job-{uuid.uuid4().hex[:12]}",
            user_input=user_input,
            goal=plan["goal"],
            plan=steps,
        )

        state.start()
        self._record_event(
            state,
            "job_created",
            payload={
                "goal": state.goal,
                "step_count": len(state.plan),
            },
        )
        self._persist_state(state)

        return self._execute_state(state, plan, tools)
