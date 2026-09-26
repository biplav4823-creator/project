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
            ("job_inspect", ("inspect job", "job status", "inspect execution", "execution status")),
            ("plan_validate", ("validate plan", "validate workflow", "check plan dependencies", "plan validation")),
            ("dependency_inspect", ("inspect dependencies", "dependency graph", "dependency analysis", "workflow dependencies")),
            ("retry_policy", ("retry policy", "should retry", "retry decision", "retry operation")),
            ("execution_summary", ("execution summary", "summarize execution", "job summary", "execution results")),
            ("operational_diagnose", ("diagnose job", "diagnose execution", "operational diagnosis", "debug job")),

            ("prompt_construct", ("construct prompt", "build prompt", "create prompt", "prompt construction")),
            ("text_generate", ("generate text", "generate response", "write text", "text generation")),
            ("text_summarize", ("summarize text", "summarize", "make a summary", "text summary")),
            ("text_extract", ("extract fields", "extract information", "extract data", "information extraction")),
            ("text_classify", ("classify text", "text classification", "categorize text", "classify")),
            ("text_transform", ("transform text", "change text", "uppercase text", "lowercase text", "normalize whitespace")),

            ("csv_parse", (
                "parse csv data",
                "parse csv",
                "read csv",
                "csv parsing",
            )),
            ("csv_serialize", (
                "serialize records to csv",
                "serialize to csv",
                "write csv",
                "csv serialization",
            )),
            ("schema_inspect", (
                "inspect dataset schema",
                "inspect schema",
                "schema inspection",
                "infer schema",
            )),
            ("data_validate", (
                "validate data against schema",
                "validate dataset",
                "validate records",
                "data validation",
            )),
            ("data_transform", (
                "transform records",
                "transform data",
                "data transformation",
                "filter records",
                "rename columns",
            )),
            ("data_aggregate", (
                "aggregate data",
                "aggregate records",
                "group and aggregate",
                "group by data",
                "data aggregation",
            )),

            (
                "data_statistics",
                (
                    "data statistics",
                    "descriptive statistics",
                    "statistics of data",
                    "summarize dataset",
                    "summary statistics",
                    "mean median standard deviation",
                ),
            ),
            (
                "data_correlation",
                (
                    "correlation",
                    "correlation coefficient",
                    "pearson correlation",
                    "correlate",
                ),
            ),
            (
                "linear_regression",
                (
                    "linear regression",
                    "regression line",
                    "least squares regression",
                    "fit a line",
                    "fit linear model",
                ),
            ),
            (
                "dataset_profile",
                (
                    "profile dataset",
                    "dataset profile",
                    "data profile",
                    "profile the data",
                    "inspect dataset",
                ),
            ),
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
