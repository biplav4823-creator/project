class Orchestrator:
    def __init__(self, planner, router, executor, verifier, explainer):
        self.planner = planner
        self.router = router
        self.executor = executor
        self.verifier = verifier
        self.explainer = explainer

    def run(self, user_input, tools):
        plan = self.planner.plan(user_input)

        state = {
            "goal": plan["goal"],
            "plan": plan["steps"],
            "current_step": None,
            "completed_steps": [],
            "failed_steps": [],
            "results": [],
            "status": "running"
        }

        for step in state["plan"]:
            state["current_step"] = step["id"]

            dependencies = step.get("depends_on", [])

            dependency_results = [
                item
                for item in state["results"]
                if item["step"] in dependencies
            ]

            decision = {
                "action": "answer",
                "tool": None,
                "arguments": {},
                "description": step["description"],
                "step_id": step["id"],
                "depends_on": dependencies,
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

                    step["status"] = "completed"
                    step["result"] = verified

                    state["completed_steps"].append(step["id"])

                    state["results"].append({
                        "step": step["id"],
                        "description": step["description"],
                        "result": verified,
                        "previous_results": dependency_results
                    })

                except Exception as exc:
                    step["status"] = "failed"
                    step["result"] = {
                        "error": str(exc)
                    }

                    state["failed_steps"].append(step["id"])

                    state["results"].append({
                        "step": step["id"],
                        "description": step["description"],
                        "error": str(exc),
                        "previous_results": dependency_results
                    })

                    state["status"] = "failed"
                    break

            else:
                step["status"] = "pending"

                state["results"].append({
                    "step": step["id"],
                    "description": step["description"],
                    "status": "pending",
                    "previous_results": dependency_results
                })

        state["current_step"] = None

        if state["status"] != "failed":
            if len(state["completed_steps"]) == len(state["plan"]):
                state["status"] = "completed"
            else:
                state["status"] = "pending"

        return self.explainer.explain(state)
