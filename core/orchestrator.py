import ast
import re
import uuid
from datetime import datetime, timezone
from dataclasses import asdict

from core.state import JobState, StepState, ExecutionRecord
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


    def get_execution_history(self, job_id):
        """Return the recorded execution events for a job."""
        if not job_id:
            return []

        return self.state_store.get_events(job_id)

    # =========================================================
    # MAIN EXECUTION
    # =========================================================




    # =========================================================
    # CP-28: DURABLE LIFECYCLE
    # =========================================================

    def _persist_state(self, state):
        self.state_store.save(state.job_id, state.to_dict())

    def _state_from_dict(self, data):
        return JobState.from_dict(data)

    def _load_state(self, job_id):
        data = self.state_store.load(job_id)

        if data is None:
            raise ValueError(
                f"No persisted job found for job_id: {job_id}"
            )

        return self._state_from_dict(data)

    def _plan_from_state(self, state):
        return {
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

    def _waiting_step(self, state, step_id=None):
        waiting = [
            s.id for s in state.plan
            if s.status == "waiting_approval"
        ]

        if not waiting:
            raise ValueError("Job has no step waiting for approval.")

        if step_id is None:
            return waiting[0]

        if step_id not in waiting:
            raise ValueError(
                f"Step {step_id} is not waiting for approval."
            )

        return step_id

    def resume(self, job_id, tools):
        state = self._load_state(job_id)

        if state.status in ("completed", "waiting_approval"):
            return self.explainer.explain(state)

        rejected = (
            isinstance(state.approval, dict)
            and state.approval.get("decision") == "rejected"
        )

        if state.status == "failed" and rejected:
            return self.explainer.explain(state)

        if state.status == "failed":
            state.reset_failed()

        state.status = "running"

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
            self._plan_from_state(state),
            tools,
        )

    def approve(self, job_id, tools, step_id=None):
        state = self._load_state(job_id)

        if state.status != "waiting_approval":
            raise ValueError(
                "Job is not waiting for approval (status: "
                + state.status + ")."
            )

        target = self._waiting_step(state, step_id)
        state.approve(target)

        self._record_event(
            state,
            "approval_granted",
            step_id=target,
            payload={"decision": "approved"},
        )
        self._persist_state(state)

        return self._execute_state(
            state,
            self._plan_from_state(state),
            tools,
        )

    def reject(self, job_id, reason="rejected by user", step_id=None):
        state = self._load_state(job_id)

        if state.status != "waiting_approval":
            raise ValueError(
                "Job is not waiting for approval (status: "
                + state.status + ")."
            )

        target = self._waiting_step(state, step_id)
        state.reject(target, reason)
        state.current_step = None
        state.finish()

        self._record_event(
            state,
            "approval_rejected",
            step_id=target,
            payload={"decision": "rejected", "reason": reason},
        )
        self._record_event(
            state,
            "job_failed",
            payload={
                "status": state.status,
                "completed_steps": state.completed_steps,
                "failed_steps": state.failed_steps,
            },
        )
        self._persist_state(state)

        return self.explainer.explain(state)

    def _execute_state(self, state, plan, tools):
        for raw, step in zip(plan["steps"], state.plan):
            if (
                step.id in state.completed_steps
                or step.status == "completed"
            ):
                self._record_event(
                    state,
                    "step_skipped_on_resume",
                    step_id=step.id,
                    payload={"reason": "already_completed"},
                )
                self._persist_state(state)
                continue

            outcome = self._run_step(state, raw, step, tools)

            if outcome != "completed":
                break

        state.current_step = None
        state.finish()

        terminal_events = {
            "completed": "job_completed",
            "failed": "job_failed",
            "waiting_approval": "job_waiting_approval",
            "pending": "job_pending",
        }

        terminal_event = terminal_events.get(state.status)

        if terminal_event is not None:
            self._record_event(
                state,
                terminal_event,
                payload={
                    "status": state.status,
                    "completed_steps": state.completed_steps,
                    "failed_steps": state.failed_steps,
                },
            )

        self._persist_state(state)

        return self.explainer.explain(state)

    def _run_step(self, state, raw, step, tools):
        state.current_step = step.id
        state.begin_step(step.id)

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

        done = set(state.completed_steps) | {
            s.id for s in state.plan if s.status == "completed"
        }
        unmet = [d for d in step.depends_on if d not in done]

        if unmet:
            state.fail_step(
                step.id,
                f"Unmet dependencies: {unmet}",
            )
            self._persist_state(state)
            return "failed"

        deps = [
            x
            for x in state.intermediate_results
            if x.get("step") in step.depends_on
        ]

        capability = raw.get("capability")

        if not capability:
            state.fail_step(
                step.id,
                "No capability found for: " + step.description,
            )
            self._persist_state(state)
            return "failed"

        max_attempts = state.max_recovery_attempts

        while True:
            try:
                return self._attempt_step(
                    state,
                    step,
                    capability,
                    deps,
                    tools,
                )

            except Exception as exc:
                attempts = state.recovery_attempts.get(step.id, 0)
                recovery_result = self.recovery.recover(exc)

                self._record_event(
                    state,
                    "recovery_attempted",
                    step_id=step.id,
                    payload={
                        "error": str(exc),
                        "recovery": str(recovery_result),
                    },
                )

                state.execution_context["recovery"] = recovery_result

                if (
                    recovery_result.get("action") == "retry"
                    and attempts < max_attempts
                ):
                    attempts += 1
                    state.recovery_attempts[step.id] = attempts
                    state.execution_context["recovery_attempts"] = attempts

                    self._record_event(
                        state,
                        "recovery_retry",
                        step_id=step.id,
                        payload={
                            "attempt": attempts,
                            "max_attempts": max_attempts,
                            "reason": recovery_result.get("reason"),
                        },
                    )
                    self._persist_state(state)
                    continue

                state.fail_step(step.id, str(exc))
                self._persist_state(state)
                return "failed"

    def _attempt_step(self, state, step, capability, deps, tools):
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

        route = self.router.route(decision)

        if route.action != "tool" or not route.tool:
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
            capability_contract = self.capabilities.get(route.tool)
            capability_contract.validate_input(route.arguments)

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

            interrupt_result = self.interrupt_engine.pre_execution(
                capability_contract,
                step_id=step.id,
                arguments=route.arguments,
            )

            if interrupt_result.interrupts:
                state.record_interrupts(interrupt_result.interrupts)
                self._persist_state(state)

            if step.id not in state.approved_steps:
                approval = self.approval_gate.evaluate(
                    capability_contract,
                    step_id=step.id,
                    arguments=route.arguments,
                    interrupts=interrupt_result.interrupts,
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
                    state.wait_for_approval(step.id, approval)
                    self._persist_state(state)
                    return "waiting"

        execution_attempt = state.recovery_attempts.get(step.id, 0) + 1
        idempotency_key = (
            f"{state.job_id}:step:{step.id}:attempt:{execution_attempt}"
        )
        execution = ExecutionRecord(
            execution_id=str(uuid.uuid4()),
            job_id=state.job_id,
            step_id=step.id,
            attempt=execution_attempt,
            idempotency_key=idempotency_key,
            status="RUNNING",
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        state.executions.append(execution)
        execution_id = execution.execution_id

        existing_execution = next(
            (
                item
                for item in state.executions
                if item.idempotency_key == idempotency_key
                and item.status == "SUCCEEDED"
            ),
            None,
        )

        if existing_execution is not None:
            execution.status = "SUCCEEDED"
            execution.completed_at = datetime.now(timezone.utc).isoformat()
            execution.result = existing_execution.result
            self._persist_state(state)

            self._record_event(
                state,
                "execution_reused",
                step_id=step.id,
                payload={
                    "execution_id": execution_id,
                    "source_execution_id": existing_execution.execution_id,
                    "idempotency_key": idempotency_key,
                },
            )
            return existing_execution.result

        self._record_event(
            state,
            "execution_started",
            step_id=step.id,
            payload={
                "capability": route.tool,
                "execution_id": execution_id,
                "attempt": execution_attempt,
            },
        )

        result = self.executor.execute(
            tools,
            route.tool,
            route.arguments,
        )

        execution.status = "SUCCEEDED"
        execution.completed_at = datetime.now(timezone.utc).isoformat()
        execution.result = result
        self._persist_state(state)

        self._record_event(
            state,
            "execution_completed",
            step_id=step.id,
            payload={"capability": route.tool},
        )

        if capability_contract is not None:
            capability_contract.validate_output(result)

        verified = self.verifier.verify(result)

        self._record_event(
            state,
            "verification_completed",
            step_id=step.id,
            payload={"capability": route.tool},
        )

        if capability_contract is not None:
            post_interrupt = self.interrupt_engine.post_execution(
                capability_contract,
                verified,
                step_id=step.id,
            )

            if post_interrupt.interrupts:
                state.record_interrupts(post_interrupt.interrupts)

            if post_interrupt.action != "continue":
                raise RuntimeError(
                    "Post-execution interrupt: "
                    + str(post_interrupt.interrupts)
                )

        state.complete_step(step.id, verified)
        self._update_context(step.id, verified)

        self._record_event(
            state,
            "step_completed",
            step_id=step.id,
            payload={"status": "completed"},
        )
        self._persist_state(state)

        return "completed"

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


