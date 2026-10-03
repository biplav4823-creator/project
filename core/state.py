from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class StepState:
    id: int
    description: str
    status: str = "pending"
    depends_on: list[int] = field(default_factory=list)
    capability: str | None = None
    candidates: list[str] = field(default_factory=list)
    result: Any = None


@dataclass
class ExecutionRecord:
    execution_id: str
    job_id: str
    step_id: int
    attempt: int = 1
    idempotency_key: str | None = None
    status: str = "NOT_STARTED"
    started_at: str | None = None
    completed_at: str | None = None
    result: Any = None

    VALID_STATUSES = {"NOT_STARTED", "RUNNING", "SUCCEEDED", "FAILED", "UNKNOWN"}

    def __post_init__(self):
        if self.status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid execution status: {self.status}")


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
    executions: list[ExecutionRecord] = field(default_factory=list)
    interrupts: list[Any] = field(default_factory=list)
    approval: Any = None
    recovery_attempts: dict[int, int] = field(default_factory=dict)
    max_recovery_attempts: int = 1
    status: str = "created"
    approved_steps: list[int] = field(default_factory=list)

    # ---- lookup -------------------------------------------------------
    def get_step(self, step_id: int):
        for step in self.plan:
            if step.id == step_id:
                return step
        return None

    # ---- lifecycle ----------------------------------------------------
    def start(self):
        self.status = "running"

    def begin_step(self, step_id: int):
        step = self.get_step(step_id)
        if step is not None and step.status != "completed":
            step.status = "running"

    def complete_step(self, step_id: int, result: Any):
        step = self.get_step(step_id)
        if step is not None:
            step.status = "completed"
            step.result = result

        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)

        if step_id in self.failed_steps:
            self.failed_steps.remove(step_id)

        if self.status == "failed" and not self.failed_steps:
            self.status = "running"

        self.intermediate_results.append({
            "step": step_id,
            "result": result,
        })

    def wait_for_approval(self, step_id: int, approval: Any):
        step = self.get_step(step_id)
        if step is not None:
            step.status = "waiting_approval"
            step.result = approval

        self.approval = approval
        self.status = "waiting_approval"

    def approve(self, step_id: int):
        step = self.get_step(step_id)
        if step is None or step.status != "waiting_approval":
            raise ValueError(f"Step {step_id} is not waiting for approval.")

        step.status = "pending"
        step.result = None

        if step_id not in self.approved_steps:
            self.approved_steps.append(step_id)

        self.approval = {"step": step_id, "decision": "approved"}
        self.status = "running"

    def reject(self, step_id: int, reason: str = "rejected by user"):
        step = self.get_step(step_id)
        if step is None or step.status != "waiting_approval":
            raise ValueError(f"Step {step_id} is not waiting for approval.")

        self.fail_step(step_id, reason)
        self.approval = {
            "step": step_id,
            "decision": "rejected",
            "reason": reason,
        }

    def record_interrupts(self, interrupts):
        self.interrupts.extend(interrupts)

    def fail_step(self, step_id: int, error: Any):
        step = self.get_step(step_id)
        if step is not None:
            step.status = "failed"
            step.result = error

        if step_id not in self.failed_steps:
            self.failed_steps.append(step_id)

        self.intermediate_results.append({
            "step": step_id,
            "error": error,
        })

        self.status = "failed"

    def reset_failed(self):
        for step_id in list(self.failed_steps):
            step = self.get_step(step_id)
            if step is not None:
                step.status = "pending"
                step.result = None

        self.failed_steps.clear()

    def finish(self):
        if self.status == "waiting_approval":
            return

        if self.failed_steps:
            self.status = "failed"
        elif len(self.completed_steps) == len(self.plan):
            self.status = "completed"
        else:
            self.status = "pending"

    # ---- serialization ------------------------------------------------
    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        plan = [
            StepState(
                id=s["id"],
                description=s["description"],
                status=s.get("status", "pending"),
                depends_on=list(s.get("depends_on", [])),
                capability=s.get("capability"),
                candidates=list(s.get("candidates", [])),
                result=s.get("result"),
            )
            for s in data.get("plan", [])
        ]

        return cls(
            job_id=data["job_id"],
            user_input=data.get("user_input", data.get("goal", "")),
            goal=data.get("goal", data.get("user_input", "")),
            plan=plan,
            current_step=data.get("current_step"),
            completed_steps=list(data.get("completed_steps", [])),
            failed_steps=list(data.get("failed_steps", [])),
            intermediate_results=list(data.get("intermediate_results", [])),
            execution_context=dict(data.get("execution_context", {})),
            interrupts=list(data.get("interrupts", [])),
            approval=data.get("approval"),
            recovery_attempts={
                int(k): v
                for k, v in (data.get("recovery_attempts") or {}).items()
            },
            max_recovery_attempts=data.get("max_recovery_attempts", 1),
            status=data.get("status", "created"),
            approved_steps=list(data.get("approved_steps", [])),
        )

