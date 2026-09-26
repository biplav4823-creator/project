from .capabilities import (
    prompt_construct,
    text_generate,
    text_summarize,
    text_extract,
    text_classify,
    text_transform,
)


def register_gen_ai(agent):
    agent.register_tool(
        "prompt_construct",
        "Construct a structured prompt from an instruction, context and constraints.",
        prompt_construct,
        input_schema={
            "type": "object",
            "properties": {
                "instruction": {"type": "string"},
                "context": {"type": "string"},
                "constraints": {"type": "array"},
            },
            "required": ["instruction"],
        },
        output_schema={"type": "string"},
    )
    agent.register_tool(
        "text_generate",
        "Generate text through the Gen-AI capability interface.",
        text_generate,
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "max_length": {"type": "number"},
            },
            "required": ["prompt"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "text_summarize",
        "Summarize text into a limited number of sentences.",
        text_summarize,
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "max_sentences": {"type": "number"},
            },
            "required": ["text"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "text_extract",
        "Extract named fields from structured or semi-structured text.",
        text_extract,
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "fields": {"type": "array"},
            },
            "required": ["text", "fields"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "text_classify",
        "Classify text against a supplied set of labels.",
        text_classify,
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "labels": {"type": "array"},
            },
            "required": ["text", "labels"],
        },
        output_schema={"type": "object"},
    )
    agent.register_tool(
        "text_transform",
        "Transform text using a controlled text operation.",
        text_transform,
        input_schema={
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "operation": {"type": "string"},
            },
            "required": ["text", "operation"],
        },
        output_schema={"type": "object"},
    )
    return agent
