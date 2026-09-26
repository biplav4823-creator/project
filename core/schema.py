from typing import Any


class SchemaError(ValueError):
    pass


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        )
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return True


def validate(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    if not schema:
        return

    expected = schema.get("type")

    if expected and not _matches_type(value, expected):
        raise SchemaError(
            f"{path}: expected {expected}, got {type(value).__name__}"
        )

    if expected == "object":
        if not isinstance(value, dict):
            return

        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for name in required:
            if name not in value:
                raise SchemaError(
                    f"{path}: missing required property '{name}'"
                )

        if schema.get("additionalProperties") is False:
            unknown = set(value) - set(properties)
            if unknown:
                raise SchemaError(
                    f"{path}: unexpected properties {sorted(unknown)}"
                )

        for name, child_schema in properties.items():
            if name in value:
                validate(
                    value[name],
                    child_schema,
                    f"{path}.{name}",
                )

    elif expected == "array":
        item_schema = schema.get("items")

        if item_schema:
            for index, item in enumerate(value):
                validate(
                    item,
                    item_schema,
                    f"{path}[{index}]",
                )
