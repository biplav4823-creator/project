from dataclasses import asdict
from core.main import create_agent
from core.state_store import StateStore

agent = create_agent()
state = agent.orchestrator.run("calculate 25 + 15 and then calculate 10 + 5", agent.tools)
job_id = state.job_id

state.plan[0].status = "completed"
state.completed_steps = [1]
state.plan[1].status = "pending"
state.plan[1].result = None
state.status = "running"

StateStore().save(job_id, asdict(state))

resumed = agent.orchestrator.resume(job_id, agent.tools)

print("STATUS=", resumed.status)
print("STEP1_STATUS=", resumed.plan[0].status)
print("STEP2_RESULT=", resumed.plan[1].result)

assert resumed.status == "completed", f"status={resumed.status}"
assert resumed.plan[0].status == "completed"
assert resumed.plan[1].result["result"] == "15", f"got {resumed.plan[1].result!r}"
print("CP26 RESUME TEST: PASS")
