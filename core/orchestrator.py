class Orchestrator:
    def __init__(self, planner, router, executor, verifier, explainer):
        self.planner = planner
        self.router = router
        self.executor = executor
        self.verifier = verifier
        self.explainer = explainer

    def run(self, user_input, tools):
        plan = self.planner.plan(user_input)
        results = []

        for decision in plan:
            route = self.router.route(decision)

            if route.action == "tool" and route.tool:
                result = self.executor.execute(
                    tools,
                    route.tool,
                    route.arguments
                )

                verified = self.verifier.verify(result)
                results.append(verified)

        return self.explainer.explain(results)
