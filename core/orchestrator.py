python -m py_compile core\orchestrator.py
python -c "from core.orchestrator import Orchestrator; from core.planner import Planner; from core.router import Router; from core.executor import Executor; from core.verifier import Verifier; from core.explainer import Explainer; o=Orchestrator(Planner(),Router(),Executor(),Verifier(),Explainer()); print('CP-05 ORCHESTRATOR=',type(o).__name__,'PASS')"
