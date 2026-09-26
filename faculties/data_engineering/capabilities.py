import csv
import io
import math
from collections import defaultdict
from typing import Any


def _records(rows):
    if not isinstance(rows, list):
        raise TypeError("rows must be a list.")
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("each row must be a dictionary.")
    return rows


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def csv_parse(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("CSV text must be a non-empty string.")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV header is missing.")

    return [dict(row) for row in reader]


def csv_serialize(rows):
    rows = _records(rows)
    if not rows:
        return ""

    columns = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=columns,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})

    return output.getvalue()


def schema_inspect(rows):
    rows = _records(rows)

    columns = []
    seen = set()

    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)

    result = {}

    for column in columns:
        values = [row.get(column) for row in rows]
        non_null = [value for value in values if value is not None and value != ""]
        types = sorted({type(value).__name__ for value in non_null})

        if not non_null:
            inferred = "null"
        elif all(_finite_number(value) for value in non_null):
            inferred = "number"
        elif all(isinstance(value, bool) for value in non_null):
            inferred = "boolean"
        elif all(isinstance(value, str) for value in non_null):
            inferred = "string"
        else:
            inferred = "mixed"

        result[column] = {
            "type": inferred,
            "nullable": len(non_null) != len(values),
            "null_count": len(values) - len(non_null),
            "unique_count": len({str(value) for value in non_null}),
            "observed_types": types,
        }

    return {
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": result,
    }


def data_validate(rows, schema):
    rows = _records(rows)

    if not isinstance(schema, dict):
        raise TypeError("schema must be a dictionary.")

    errors = []

    for index, row in enumerate(rows):
        for column, expected in schema.items():
            required = True
            expected_type = expected

            if isinstance(expected, dict):
                required = expected.get("required", True)
                expected_type = expected.get("type")

            value = row.get(column)

            if value is None or value == "":
                if required:
                    errors.append({
                        "row": index,
                        "column": column,
                        "error": "missing_required_value",
                    })
                continue

            valid = True

            if expected_type in {"number", "numeric"}:
                valid = _finite_number(value)
            elif expected_type == "string":
                valid = isinstance(value, str)
            elif expected_type == "boolean":
                valid = isinstance(value, bool)
            elif expected_type == "integer":
                valid = isinstance(value, int) and not isinstance(value, bool)
            elif expected_type not in {None, "any"}:
                valid = type(value).__name__ == expected_type

            if not valid:
                errors.append({
                    "row": index,
                    "column": column,
                    "error": "invalid_type",
                    "expected": expected_type,
                    "actual": type(value).__name__,
                })

    return {
        "valid": not errors,
        "row_count": len(rows),
        "error_count": len(errors),
        "errors": errors,
    }


def data_transform(rows, operations):
    rows = _records(rows)

    if not isinstance(operations, list):
        raise TypeError("operations must be a list.")

    result = [dict(row) for row in rows]

    for operation in operations:
        if not isinstance(operation, dict):
            raise TypeError("each operation must be a dictionary.")

        action = operation.get("action")

        if action == "select":
            columns = operation.get("columns", [])
            if not isinstance(columns, list):
                raise TypeError("select columns must be a list.")
            result = [
                {column: row.get(column) for column in columns}
                for row in result
            ]

        elif action == "rename":
            mapping = operation.get("mapping", {})
            if not isinstance(mapping, dict):
                raise TypeError("rename mapping must be a dictionary.")
            result = [
                {
                    mapping.get(column, column): value
                    for column, value in row.items()
                }
                for row in result
            ]

        elif action == "filter_equals":
            column = operation.get("column")
            value = operation.get("value")
            result = [
                row for row in result
                if row.get(column) == value
            ]

        elif action == "drop_nulls":
            columns = operation.get("columns")
            if columns is None:
                columns = list(result[0].keys()) if result else []

            result = [
                row for row in result
                if all(
                    row.get(column) is not None
                    and row.get(column) != ""
                    for column in columns
                )
            ]

        else:
            raise ValueError(f"Unsupported transform operation: {action}")

    return result


def data_aggregate(rows, group_by, aggregations):
    rows = _records(rows)

    if not isinstance(group_by, list):
        raise TypeError("group_by must be a list.")
    if not isinstance(aggregations, dict):
        raise TypeError("aggregations must be a dictionary.")

    groups = defaultdict(list)

    for row in rows:
        key = tuple(row.get(column) for column in group_by)
        groups[key].append(row)

    output = []

    for key, group in groups.items():
        result = {
            column: value
            for column, value in zip(group_by, key)
        }

        for output_name, spec in aggregations.items():
            if not isinstance(spec, dict):
                raise TypeError("aggregation specification must be a dictionary.")

            column = spec.get("column")
            operation = spec.get("operation")

            values = [
                row.get(column)
                for row in group
                if _finite_number(row.get(column))
            ]

            if operation == "count":
                result[output_name] = len(group)
            elif operation == "sum":
                result[output_name] = sum(values)
            elif operation == "mean":
                result[output_name] = sum(values) / len(values) if values else None
            else:
                raise ValueError(
                    f"Unsupported aggregation operation: {operation}"
                )

        output.append(result)

    return output
