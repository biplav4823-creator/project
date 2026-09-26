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
    # MAIN EXECUTION
    # =========================================================

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
        self._persist_state(state)

        for raw, step in zip(
            plan["steps"],
            state.plan,
        ):
            state.current_step = step.id
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
                        state.wait_for_approval(
                            step.id,
                            approval,
                        )

                        self._persist_state(
                            state
                        )

                        break

                result = self.executor.execute(
                    tools,
                    route.tool,
                    route.arguments,
                )

                if capability_contract is not None:
                    capability_contract.validate_output(
                        result
                    )

                verified = self.verifier.verify(
                    result
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

                self._persist_state(
                    state,
                )

            except Exception as exc:
                recovery_result = (
                    self.recovery.recover(
                        exc
                    )
                )

                state.execution_context[
                    "recovery"
                ] = recovery_result

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
        self._persist_state(state)

        return self.explainer.explain(
            state
        )
