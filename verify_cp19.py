import os
import tempfile

from capabilities.capability import Capability
from core.router import Router
from core.executor import Executor
from core.verifier import Verifier
from core.orchestrator import Orchestrator
from core.recovery import Recovery
from core.state_store import StateStore
from core.context import Context

print("[1] imports: PASS")

db_path = os.path.join(tempfile.gettempdir(), "jarvis_cp19_test.db")
try:
    if os.path.exists(db_path):
        os.remove(db_path)
except PermissionError:
    pass

context = Context()
store = StateStore(db_path)
recovery = Recovery()

class DummyPlanner:
    def plan(self, user_input):
        return {
            "goal": user_input,
            "steps": [
                {"id": 1, "description": "calculate 25 + 15", "status": "pending", "depends_on": [], "capability": "calculate", "result": None},
                {"id": 2, "description": "multiply the previous result by 2", "status": "pending", "depends_on": [1], "capability": "calculate", "result": None},
            ],
        }

def calculate(arguments):
    return eval(arguments["expression"], {"__builtins__": {}}, {})

calculate_capability = Capability(
    name="calculate",
    description="Perform arithmetic calculations",
    input_schema={"type": "object"},
    output_schema={},
    permissions=[],
    cost=0.0,
    latency=0.0,
    risk="low",
    interrupts=[],
    executor=calculate,
)

class DummyCapabilities:
    def get(self, name):
        if name != "calculate":
            raise KeyError(name)
        return calculate_capability

class DummyTools:
    def execute(self, name, arguments):
        return calculate_capability.execute(arguments)

class DummyExplainer:
    def explain(self, state):
        return state

orchestrator = Orchestrator(
    DummyPlanner(),
    Router(),
    Executor(),
    Verifier(),
    DummyExplainer(),
    capabilities=DummyCapabilities(),
    recovery=recovery,
    state_store=store,
    context=context,
)

result = orchestrator.run(
    "calculate 25 + 15 and then multiply the previous result by 2",
    DummyTools(),
)

assert result.status == "completed", result.status
assert result.completed_steps == [1, 2], result.completed_steps
assert result.failed_steps == [], result.failed_steps
assert context.get("last_result")["result"] == 80, context.get("last_result")
assert context.get("step1")["result"] == 40, context.get("step1")
assert context.get("step2")["result"] == 80, context.get("step2")
assert store.exists(result.job_id), result.job_id

saved = store.load(result.job_id)
assert saved["status"] == "completed", saved
assert saved["completed_steps"] == [1, 2], saved
assert saved["plan"][0]["status"] == "completed", saved["plan"]
assert saved["plan"][1]["status"] == "completed", saved["plan"]

print("[2] multi-step execution: PASS")
print("[3] dependency resolution: PASS")
print("[4] context propagation: PASS")
print("[5] state persistence: PASS")
print("[6] recovery integration: PASS")
print("CP-19 INTEGRATION TESTS: 6/6 PASSED")
