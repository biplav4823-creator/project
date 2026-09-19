import io
import contextlib
import traceback
import math
import statistics

import numpy as np
import pandas as pd
import sympy as sp


def run_python(code: str):
    """Run Python code for JARVIS scientific and data tasks."""

    if not isinstance(code, str) or not code.strip():
        raise ValueError("No Python code provided.")

    namespace = {
        "math": math,
        "statistics": statistics,
        "numpy": np,
        "np": np,
        "pandas": pd,
        "pd": pd,
        "sympy": sp,
        "sp": sp,
    }

    output = io.StringIO()

    try:
        with contextlib.redirect_stdout(output):
            exec(code, namespace, namespace)

        result = output.getvalue().strip()

        if result:
            return result

        return "Python execution completed successfully."

    except Exception:
        return traceback.format_exc()
