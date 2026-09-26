from .capabilities import (
    data_statistics,
    data_correlation,
    linear_regression,
    dataset_profile,
)


def register_data_science(agent):
    """Register the Data Science Faculty with the existing JARVIS control plane."""

    agent.register_tool(
        "data_statistics",
        "Calculate descriptive statistics for a numeric dataset.",
        data_statistics,
        input_schema={
            "type": "object",
            "properties": {
                "values": {
                    "type": "array",
                    "items": {"type": "number"},
                }
            },
            "required": ["values"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "mean": {"type": "number"},
                "median": {"type": "number"},
                "minimum": {"type": "number"},
                "maximum": {"type": "number"},
                "sum": {"type": "number"},
                "sample_variance": {
                    "type": ["number", "null"]
                },
                "sample_stddev": {
                    "type": ["number", "null"]
                },
            },
            "required": [
                "count",
                "mean",
                "median",
                "minimum",
                "maximum",
                "sum",
                "sample_variance",
                "sample_stddev",
            ],
            "additionalProperties": False,
        },
    )

    agent.register_tool(
        "data_correlation",
        "Calculate Pearson correlation between two numeric datasets.",
        data_correlation,
        input_schema={
            "type": "object",
            "properties": {
                "x": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "y": {
                    "type": "array",
                    "items": {"type": "number"},
                },
            },
            "required": ["x", "y"],
            "additionalProperties": False,
        },
        output_schema={"type": "number"},
    )

    agent.register_tool(
        "linear_regression",
        "Fit simple ordinary least-squares linear regression.",
        linear_regression,
        input_schema={
            "type": "object",
            "properties": {
                "x": {
                    "type": "array",
                    "items": {"type": "number"},
                },
                "y": {
                    "type": "array",
                    "items": {"type": "number"},
                },
            },
            "required": ["x", "y"],
            "additionalProperties": False,
        },
        output_schema={
            "type": "object",
            "properties": {
                "slope": {"type": "number"},
                "intercept": {"type": "number"},
                "r_squared": {"type": "number"},
                "equation": {"type": "string"},
            },
            "required": [
                "slope",
                "intercept",
                "r_squared",
                "equation",
            ],
            "additionalProperties": False,
        },
    )

    agent.register_tool(
        "dataset_profile",
        "Profile rows, columns, nulls, unique values and basic numeric statistics.",
        dataset_profile,
        input_schema={
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "items": {"type": "object"},
                }
            },
            "required": ["rows"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
    )

    return agent
