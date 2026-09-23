from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepState:
    id: int
    description: str
    status: str = "pending"
    depends_on: list[int] = field(default_factory=list)
    result: Any = None


@dataclass
class JobState:
    job_id: str
    user_input: str
    goal: str
    plan: list[StepState] = field(default_factory=list)

    current_step: int | None = None
    completed_steps: list[int] = field(default_factory=list)
    failed_steps: list[int] = field(default_factory=list)

    intermediate_results: list[dict[str, Any]] = field(default_factory=list)

    execution_context: dict[str, Any] = field(default_factory=dict)

    status: str = "created"

    def start(self):
        self.status = "running"

    def complete_step(self, step_id: int, result: Any):
        for step in self.plan:
            if step.id == step_id:
                step.status = "completed"
                step.result = result
                break

        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)

        self.intermediate_results.append({
            "step": step_id,
            "result": result
        })

    def fail_step(self, step_id: int, error: Any):
        for step in self.plan:
            if step.id == step_id:
                step.status = "failed"
                step.result = error
                break

        if step_id not in self.failed_steps:
            self.failed_steps.append(step_id)

        self.intermediate_results.append({
            "step": step_id,
            "error": error
        })

        self.status = "failed"

    def finish(self):
        if self.failed_steps:
            self.status = "failed"
        elif len(self.completed_steps) == len(self.plan):
            self.status = "completed"
        else:
            self.status = "pending"
