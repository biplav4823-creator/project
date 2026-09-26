import re
from .capability import Capability


class CapabilityRegistry:
    def __init__(self):
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability):
        if capability.name in self._capabilities:
            raise ValueError(
                f"Capability '{capability.name}' is already registered."
            )

        self._capabilities[capability.name] = capability

    def get(self, name: str) -> Capability:
        if name not in self._capabilities:
            raise KeyError(
                f"Capability '{name}' is not registered."
            )

        return self._capabilities[name]

    def has(self, name: str) -> bool:
        return name in self._capabilities

    def list(self) -> list[str]:
        return sorted(self._capabilities.keys())

    def discover(self, query, limit=5):
        """Return capabilities matched by explicit user intent."""
        if not query:
            return []

        try:
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            limit = 5

        q = str(query).lower().strip()

        # Ordered from most specific to most general.
        intents = [
            (
                "nth_derivative",
                (
                    "nth derivative",
                    "second derivative",
                    "third derivative",
                    "fourth derivative",
                    "higher derivative",
                    "higher order derivative",
                ),
            ),
            (
                "definite_integral",
                (
                    "definite integral",
                    "integral from",
                    "integral between",
                    "integral over",
                    "bounds",
                ),
            ),
            (
                "solve_system",
                (
                    "solve system",
                    "system of equations",
                    "simultaneous equations",
                ),
            ),
            (
                "matrix_determinant",
                (
                    "matrix determinant",
                    "determinant",
                    "det of",
                ),
            ),
            (
                "matrix_inverse",
                (
                    "matrix inverse",
                    "inverse of a matrix",
                    "inverse of matrix",
                    "invert matrix",
                ),
            ),
            (
                "matrix_rank",
                (
                    "matrix rank",
                    "rank of a matrix",
                    "rank of matrix",
                ),
            ),
            (
                "derivative",
                (
                    "differentiate",
                    "derivative",
                    "differentiation",
                    "find derivative",
                    "calculate derivative",
                ),
            ),
            (
                "integral",
                (
                    "integrate",
                    "integral",
                    "integration",
                    "antiderivative",
                    "indefinite integral",
                ),
            ),
            (
                "solve_equation",
                (
                    "solve",
                    "equation",
                    "root",
                    "roots",
                ),
            ),
            (
                "factor",
                (
                    "factor",
                    "factorize",
                    "factorise",
                    "factoring",
                ),
            ),
            (
                "expand",
                (
                    "expand",
                    "expansion",
                    "expanded",
                ),
            ),
            (
                "simplify",
                (
                    "simplify",
                    "simplification",
                    "reduce expression",
                ),
            ),
            (
                "limit",
                (
                    "limit",
                    "limiting",
                    "approaches",
                    "tends to",
                ),
            ),
            (
                "series",
                (
                    "series",
                    "taylor",
                    "maclaurin",
                    "power series",
                ),
            ),
            (
                "numerical",
                (
                    "numerical",
                    "numeric",
                    "approximate",
                    "approximation",
                    "decimal approximation",
                ),
            ),
            (
                "calculate",
                (
                    "calculate",
                    "calculation",
                    "compute",
                    "evaluate",
                    "evaluation",
                    "arithmetic",
                    "multiply",
                    "multiplied",
                    "times",
                    "add",
                    "plus",
                    "subtract",
                    "minus",
                    "divide",
                    "divided",
                ),
            ),
            (
                "run_python",
                (
                    "python",
                    "python code",
                    "run code",
                    "execute code",
                    "numpy",
                    "pandas",
                ),
            ),
        ]

        matches = []

        for name, phrases in intents:
            if any(phrase in q for phrase in phrases):
                capability = self._capabilities.get(name)
                if capability is not None:
                    matches.append(capability)

        return matches[:limit]

    def execute(self, name: str, arguments=None):
        capability = self.get(name)
        return capability.execute(arguments)
