from .capabilities import (
    csv_parse,
    csv_serialize,
    schema_inspect,
    data_validate,
    data_transform,
    data_aggregate,
)


def register_data_engineering(agent):
    agent.register_tool(
        "csv_parse",
        "Parse CSV text into structured records.",
        csv_parse,
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        output_schema={"type": "array"},
    )

    agent.register_tool(
        "csv_serialize",
        "Serialize structured records into CSV text.",
        csv_serialize,
        input_schema={
            "type": "object",
            "properties": {"rows": {"type": "array"}},
            "required": ["rows"],
        },
        output_schema={"type": "string"},
    )

    agent.register_tool(
        "schema_inspect",
        "Inspect the schema, types, nullability and uniqueness of records.",
        schema_inspect,
        input_schema={
            "type": "object",
            "properties": {"rows": {"type": "array"}},
            "required": ["rows"],
        },
        output_schema={"type": "object"},
    )

    agent.register_tool(
        "data_validate",
        "Validate structured records against a data schema.",
        data_validate,
        input_schema={
            "type": "object",
            "properties": {
                "rows": {"type": "array"},
                "schema": {"type": "object"},
            },
            "required": ["rows", "schema"],
        },
        output_schema={"type": "object"},
    )

    agent.register_tool(
        "data_transform",
        "Apply deterministic select, rename, filter and null-removal transformations.",
        data_transform,
        input_schema={
            "type": "object",
            "properties": {
                "rows": {"type": "array"},
                "operations": {"type": "array"},
            },
            "required": ["rows", "operations"],
        },
        output_schema={"type": "array"},
    )

    agent.register_tool(
        "data_aggregate",
        "Group records and calculate count, sum or mean aggregations.",
        data_aggregate,
        input_schema={
            "type": "object",
            "properties": {
                "rows": {"type": "array"},
                "group_by": {"type": "array"},
                "aggregations": {"type": "object"},
            },
            "required": ["rows", "group_by", "aggregations"],
        },
        output_schema={"type": "array"},
    )

    return agent
