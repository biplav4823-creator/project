from __future__ import annotations

import math
import statistics
from collections import Counter


def _numbers(values):
    if not isinstance(values, list) or not values:
        raise ValueError("values must be a non-empty list.")

    numbers = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("values must contain only numeric values.")
        if not math.isfinite(float(value)):
            raise ValueError("values must contain finite numbers.")
        numbers.append(float(value))

    return numbers


def data_statistics(values):
    """Return descriptive statistics for a numeric dataset."""
    numbers = _numbers(values)

    result = {
        "count": len(numbers),
        "mean": statistics.mean(numbers),
        "median": statistics.median(numbers),
        "minimum": min(numbers),
        "maximum": max(numbers),
        "sum": sum(numbers),
    }

    if len(numbers) > 1:
        result["sample_variance"] = statistics.variance(numbers)
        result["sample_stddev"] = statistics.stdev(numbers)
    else:
        result["sample_variance"] = None
        result["sample_stddev"] = None

    return result


def data_correlation(x, y):
    """Calculate Pearson correlation coefficient."""
    x_values = _numbers(x)
    y_values = _numbers(y)

    if len(x_values) != len(y_values):
        raise ValueError("x and y must contain the same number of values.")

    if len(x_values) < 2:
        raise ValueError("At least two paired observations are required.")

    mean_x = statistics.mean(x_values)
    mean_y = statistics.mean(y_values)

    numerator = sum(
        (a - mean_x) * (b - mean_y)
        for a, b in zip(x_values, y_values)
    )

    denominator_x = math.sqrt(
        sum((a - mean_x) ** 2 for a in x_values)
    )
    denominator_y = math.sqrt(
        sum((b - mean_y) ** 2 for b in y_values)
    )

    if denominator_x == 0 or denominator_y == 0:
        raise ValueError(
            "Correlation is undefined when either variable has zero variance."
        )

    return numerator / (denominator_x * denominator_y)


def linear_regression(x, y):
    """Fit simple ordinary least-squares linear regression y = slope*x + intercept."""
    x_values = _numbers(x)
    y_values = _numbers(y)

    if len(x_values) != len(y_values):
        raise ValueError("x and y must contain the same number of values.")

    if len(x_values) < 2:
        raise ValueError("At least two paired observations are required.")

    mean_x = statistics.mean(x_values)
    mean_y = statistics.mean(y_values)

    ss_x = sum((value - mean_x) ** 2 for value in x_values)

    if ss_x == 0:
        raise ValueError("Linear regression requires variation in x.")

    covariance = sum(
        (a - mean_x) * (b - mean_y)
        for a, b in zip(x_values, y_values)
    )

    slope = covariance / ss_x
    intercept = mean_y - slope * mean_x

    predictions = [
        slope * value + intercept
        for value in x_values
    ]

    ss_res = sum(
        (actual - predicted) ** 2
        for actual, predicted in zip(y_values, predictions)
    )

    ss_tot = sum(
        (actual - mean_y) ** 2
        for actual in y_values
    )

    r_squared = (
        1.0 - ss_res / ss_tot
        if ss_tot != 0
        else 1.0
    )

    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "equation": f"y = {slope} * x + {intercept}",
    }


def dataset_profile(rows):
    """Profile a list of record dictionaries."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows must be a non-empty list of dictionaries.")

    if not all(isinstance(row, dict) for row in rows):
        raise TypeError("rows must contain only dictionaries.")

    columns = sorted({
        key
        for row in rows
        for key in row.keys()
    })

    profile = {
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": {},
    }

    for column in columns:
        values = [row.get(column) for row in rows]
        non_null = [value for value in values if value is not None]

        numeric = [
            value for value in non_null
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]

        column_info = {
            "non_null_count": len(non_null),
            "null_count": len(values) - len(non_null),
            "unique_count": len({
                repr(value) for value in non_null
            }),
        }

        if numeric and len(numeric) == len(non_null):
            column_info["type"] = "numeric"
            column_info["mean"] = statistics.mean(numeric)
            column_info["minimum"] = min(numeric)
            column_info["maximum"] = max(numeric)
        else:
            types = Counter(
                type(value).__name__
                for value in non_null
            )
            column_info["type"] = "categorical_or_other"
            column_info["types"] = dict(types)

        profile["columns"][column] = column_info

    return profile
