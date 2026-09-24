from core.state import JobState, StepState

class Orchestrator:
    def __init__(self, planner, router, executor, verifier, explainer):
        self.planner=planner
        self.router=router
        self.executor=executor
        self.verifier=verifier
        self.explainer=explainer

    def run(self,user_input,tools):
        plan=self.planner.plan(user_input)
        steps=[StepState(id=s["id"],description=s["description"],status=s.get("status","pending"),depends_on=s.get("depends_on",[]),result=s.get("result")) for s in plan["steps"]]
        state=JobState(job_id="local-job",user_input=user_input,goal=plan["goal"],plan=steps)
        state.start()
        for raw,step in zip(plan["steps"],state.plan):
            state.current_step=step.id
            deps=[x for x in state.intermediate_results if x["step"] in step.depends_on]
            capability=raw.get("capability")
            if not capability:
                state.intermediate_results.append({"step":step.id,"description":step.description,"status":"pending","previous_results":deps})
                continue
            try:
                decision={"action":"tool","tool":capability,"arguments":{"expression":step.description.replace("calculate ","",1)},"description":step.description,"step_id":step.id,"depends_on":step.depends_on,"previous_results":deps}
                route=self.router.route(decision)
                result=self.executor.execute(tools,route.tool,route.arguments)
                verified=self.verifier.verify(result)
                state.complete_step(step.id,verified)
            except Exception as exc:
                state.fail_step(step.id,str(exc))
                break
        state.current_step=None
        state.finish()
        return self.explainer.explain(state)
