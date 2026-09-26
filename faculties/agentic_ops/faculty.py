from .capabilities import (
    job_inspect,
    plan_validate,
    dependency_inspect,
    retry_policy,
    execution_summary,
    operational_diagnose,
)


def register_agentic_ops(agent):
    agent.register_tool(
        "job_inspect",
        "Inspect operational state and execution progress of a JARVIS job.",
        job_inspect,
        input_schema={
            "type": "object",
            "properties": {"state": {"type": "object"}},
            "required": ["state"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "plan_validate",
        "Validate workflow step IDs and dependency references.",
        plan_validate,
        input_schema={
            "type": "object",
            "properties": {"steps": {"type": "array"}},
            "required": ["steps"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "dependency_inspect",
        "Inspect dependencies, dependents, roots and leaves of a workflow.",
        dependency_inspect,
        input_schema={
            "type": "object",
            "properties": {"steps": {"type": "array"}},
            "required": ["steps"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "retry_policy",
        "Determine whether a failed operation should be retried.",
        retry_policy,
        input_schema={
            "type": "object",
            "properties": {
                "attempts": {"type": "number"},
                "max_attempts": {"type": "number"},
                "error": {"type": "string"},
            },
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "execution_summary",
        "Summarize completed, failed and pending execution results.",
        execution_summary,
        input_schema={
            "type": "object",
            "properties": {"results": {"type": "array"}},
            "required": ["results"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "operational_diagnose",
        "Diagnose operational job state and identify recovery actions.",
        operational_diagnose,
        input_schema={
            "type": "object",
            "properties": {"state": {"type": "object"}},
            "required": ["state"],
        },
        output_schema={"type": "object"},
    )
    return agent
