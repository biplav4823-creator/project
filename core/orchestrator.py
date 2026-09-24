from core.state import JobState, StepState

class Orchestrator:
    def __init__(self, planner, router, executor, verifier, explainer):
        self.planner = planner
        self.router = router
        self.executor = executor
        self.verifier = verifier
        self.explainer = explainer

    def _arguments(self, capability, description, previous_results):
        text = description.strip()

        if capability == "calculate":
            expression = text
            if expression.lower().startswith("calculate "):
                expression = expression[10:].strip()
            return {"expression": expression}

        if capability in {
            "simplify",
            "factor",
            "expand",
            "derivative",
            "integral",
            "definite_integral",
            "limit",
            "series",
            "numerical",
            "nth_derivative",
            "solve_equation",
            "solve_system",
            "matrix_determinant",
            "matrix_inverse",
            "matrix_rank",
            "run_python",
        }:
            return {"expression": text}

        return {"input": text}

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
                x for x in state.intermediate_results
                if x.get("step") in step.depends_on
            ]

            capability = raw.get("capability")

            if not capability:
                state.fail_step(
                    step.id,
                    "No capability found for: " + step.description
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

                result = self.executor.execute(
                    tools,
                    route.tool,
                    route.arguments,
                )

                verified = self.verifier.verify(result)
                state.complete_step(step.id, verified)

            except Exception as exc:
                state.fail_step(step.id, str(exc))
                break

        state.current_step = None
        state.finish()

        return self.explainer.explain(state)
