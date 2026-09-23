from core.state import JobState, StepState


class Orchestrator:
    def __init__(self, planner, router, executor, verifier, explainer):
        self.planner = planner
        self.router = router
        self.executor = executor
        self.verifier = verifier
        self.explainer = explainer

    def run(self, user_input, tools):
        plan = self.planner.plan(user_input)

        steps = [
            StepState(
                id=step["id"],
                description=step["description"],
                status=step.get("status", "pending"),
                depends_on=step.get("depends_on", []),
                result=step.get("result")
            )
            for step in plan["steps"]
        ]

        state = JobState(
            job_id="local-job",
            user_input=user_input,
            goal=plan["goal"],
            plan=steps
        )

        state.start()

        for step in state.plan:
            state.current_step = step.id

            dependency_results = [
                item
                for item in state.intermediate_results
                if item["step"] in step.depends_on
            ]

            decision = {
                "action": "answer",
                "tool": None,
                "arguments": {},
                "description": step.description,
                "step_id": step.id,
                "depends_on": step.depends_on,
                "previous_results": dependency_results
            }

            route = self.router.route(decision)

            if route.action == "tool" and route.tool:
                try:
                    result = self.executor.execute(
                        tools,
                        route.tool,
                        route.arguments
                    )

                    verified = self.verifier.verify(result)

                    state.complete_step(step.id, verified)

                except Exception as exc:
                    state.fail_step(step.id, str(exc))
                    break

            else:
                state.intermediate_results.append({
                    "step": step.id,
                    "description": step.description,
                    "status": "pending",
                    "previous_results": dependency_results
                })

        state.current_step = None
        state.finish()

        return self.explainer.explain(state)
