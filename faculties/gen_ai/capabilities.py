import re
from typing import Any


def prompt_construct(instruction, context="", constraints=None):
    instruction = str(instruction).strip()
    context = str(context or "").strip()
    constraints = list(constraints or [])
    if not instruction:
        raise ValueError("Instruction cannot be empty.")
    parts = [instruction]
    if context:
        parts.append("Context:\n" + context)
    if constraints:
        parts.append("Constraints:\n" + "\n".join(f"- {item}" for item in constraints))
    return "\n\n".join(parts)


def text_generate(prompt, max_length=512):
    prompt = str(prompt).strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty.")
    max_length = int(max_length)
    if max_length < 1:
        raise ValueError("max_length must be positive.")
    return {"text": prompt, "generated": False, "provider": "local-placeholder", "max_length": max_length}


def text_summarize(text, max_sentences=3):
    text = str(text).strip()
    if not text:
        raise ValueError("Text cannot be empty.")
    max_sentences = max(1, int(max_sentences))
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    return {"summary": " ".join(sentences[:max_sentences]), "source_length": len(text)}


def text_extract(text, fields):
    text = str(text).strip()
    fields = [str(x).strip() for x in fields]
    if not text:
        raise ValueError("Text cannot be empty.")
    if not fields:
        raise ValueError("At least one field is required.")
    result = {}
    lower = text.lower()
    for field in fields:
        match = re.search(rf"\b{re.escape(field)}\s*[:=-]\s*([^,;\n]+)", text, re.I)
        result[field] = match.group(1).strip() if match else None
    return {"fields": result, "matched": sum(value is not None for value in result.values()), "text_lower": lower}


def text_classify(text, labels):
    text = str(text).strip()
    labels = [str(x).strip() for x in labels if str(x).strip()]
    if not text:
        raise ValueError("Text cannot be empty.")
    if not labels:
        raise ValueError("At least one label is required.")
    lower = text.lower()
    scores = {label: sum(1 for token in label.lower().split() if token in lower) for label in labels}
    best = max(labels, key=lambda label: scores[label])
    return {"label": best, "scores": scores}


def text_transform(text, operation):
    text = str(text)
    operation = str(operation).strip().lower()
    if operation == "uppercase":
        result = text.upper()
    elif operation == "lowercase":
        result = text.lower()
    elif operation == "strip":
        result = text.strip()
    elif operation == "title":
        result = text.title()
    elif operation == "normalize_whitespace":
        result = " ".join(text.split())
    else:
        raise ValueError(f"Unsupported text transformation: {operation}")
    return {"text": result, "operation": operation}
