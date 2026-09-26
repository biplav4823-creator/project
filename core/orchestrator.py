import ast
import re

from core.state import JobState, StepState
from core.guardrail import Guardrail
from core.approval import ApprovalGate
from core.interrupt import InterruptEngine


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
        self.interrupt_engine = interrupt_engine or InterruptEngine()
        self.approval_gate = approval_gate or ApprovalGate()

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

    def _resolve_references(self, text, previous_results):
        values = self._dependency_values(previous_results)
        resolved = text

        for reference, value in values.items():
            resolved = resolved.replace(reference, str(value))

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

    def _arguments(self, capability, description, previous_results):
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

        prefix = prefixes.get(capability, "")
        expression = (
            text[len(prefix):].strip()
            if prefix and text.lower().startswith(prefix)
            else text
        )

        if capability == "calculate":
            patterns = [
                (r"^multiply\s+(.+?)\s+by\s+(.+)$", r"\1 * \2"),
                (r"^multiplied\s+(.+?)\s+by\s+(.+)$", r"\1 * \2"),
                (r"^add\s+(.+?)\s+and\s+(.+)$", r"\1 + \2"),
                (r"^add\s+(.+?)\s+to\s+(.+)$", r"\2 + \1"),
                (r"^subtract\s+(.+?)\s+from\s+(.+)$", r"\2 - \1"),
                (r"^divide\s+(.+?)\s+by\s+(.+)$", r"\1 / \2"),
            ]

            for pattern, replacement_expr in patterns:
                if re.match(pattern, expression, flags=re.I):
                    expression = re.sub(
                        pattern,
                        replacement_expr,
                        expression,
                        flags=re.I,
                    )
                    break

        if capability in {"solve_equation", "solve_system"}:
            return {"expression": expression}

        if capability in {
            "matrix_determinant",
            "matrix_inverse",
            "matrix_rank",
        }:
            match = re.search(r"\[\[.*?\]\]", text)

            if not match:
                raise ValueError("Matrix data not found in request.")

            return {"matrix": ast.literal_eval(match.group(0))}

        return {"expression": expression}

    def run(self, user_input, tools):
        plan = self.planner.plan(user_input)

        steps = [
            StepState(
                id=s["id"],
                description=s["description"],
                status=s.get("status", "pending"),
                depends_on=s.get("depends_on", []),
                result=s.get("result"),
            )
            for s in plan["steps"]
        ]

        state = JobState(
            job_id="local-job",
            user_input=user_input,
            goal=plan["goal"],
            plan=steps,
        )

        state.start()

        for raw, step in zip(plan["steps"], state.plan):
            state.current_step = step.id

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

                route = self.router.route(decision)

                if route.action != "tool" or not route.tool:
                    raise RuntimeError(
                        f"Router did not select a tool for '{step.description}'"
                    )

                if self.capabilities is not None:
                    capability_contract = self.capabilities.get(route.tool)
                    capability_contract.validate_input(route.arguments)

                    self.guardrail.check(
                        capability_contract,
                        route.arguments,
                    )

                    interrupt_result = self.interrupt_engine.pre_execution(
                        capability_contract,
                        step_id=step.id,
                        arguments=route.arguments,
                    )

                    if interrupt_result.interrupts:
                        state.record_interrupts(
                            interrupt_result.interrupts
                        )

                    approval = self.approval_gate.evaluate(
                        capability_contract,
                        step_id=step.id,
                        arguments=route.arguments,
                        interrupts=interrupt_result.interrupts,
                    )

                    if approval.action != "allow":
                        state.wait_for_approval(
                            step.id,
                            approval,
                        )
                        break

                result = self.executor.execute(
                    tools,
                    route.tool,
                    route.arguments,
                )

                if self.capabilities is not None:
                    capability_contract.validate_output(result)

                verified = self.verifier.verify(result)

                if self.capabilities is not None:
                    post_interrupt = self.interrupt_engine.post_execution(
                        capability_contract,
                        verified,
                        step_id=step.id,
                    )

                    if post_interrupt.interrupts:
                        state.record_interrupts(
                            post_interrupt.interrupts
                        )

                    if post_interrupt.action != "continue":
                        raise RuntimeError(
                            "Post-execution interrupt: "
                            + str(post_interrupt.interrupts)
                        )

                state.complete_step(step.id, verified)

            except Exception as exc:
                state.fail_step(step.id, str(exc))
                break

        state.current_step = None
        state.finish()

        return self.explainer.explain(state)
