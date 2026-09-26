import re
import json

from .llm import ask_ollama
from .router import Router
from .executor import Executor
from .verifier import Verifier
from .explainer import Explainer
from .planner import Planner
from .orchestrator import Orchestrator
from tools.registry import ToolRegistry, Tool
from capabilities.capability import Capability
from capabilities.registry import CapabilityRegistry


class Agent:

    def __init__(self):
        self.tools = ToolRegistry()
        self.capabilities = CapabilityRegistry()
        self.router = Router()
        self.executor = Executor()
        self.verifier = Verifier()
        self.explainer = Explainer()

        self.planner = Planner(self.capabilities)

        self.orchestrator = Orchestrator(
            planner=self.planner,
            router=self.router,
            executor=self.executor,
            verifier=self.verifier,
            explainer=self.explainer,
            capabilities=self.capabilities
        )

    # =========================================================
    # TOOL REGISTRATION
    # =========================================================

    def discover_capabilities(self, query, limit=5):
        return self.capabilities.discover(query, limit=limit)

    def register_tool(
        self,
        name,
        description,
        function,
        input_schema=None,
        output_schema=None,
        permissions=None,
        risk="low",
    ):
        import inspect

        tool = Tool(
            name=name,
            description=description,
            function=function
        )

        self.tools.register(tool)

        if input_schema is None:
            properties = {}
            required = []

            for parameter in inspect.signature(function).parameters.values():
                parameter_type = "string"

                if parameter.name == "matrix":
                    parameter_type = "array"
                    properties[parameter.name] = {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "number"
                            }
                        }
                    }
                elif parameter.annotation is int:
                    parameter_type = "integer"
                    properties[parameter.name] = {
                        "type": parameter_type
                    }
                elif parameter.annotation is float:
                    parameter_type = "number"
                    properties[parameter.name] = {
                        "type": parameter_type
                    }
                elif parameter.annotation is bool:
                    parameter_type = "boolean"
                    properties[parameter.name] = {
                        "type": parameter_type
                    }
                elif parameter.annotation is dict:
                    parameter_type = "object"
                    properties[parameter.name] = {
                        "type": parameter_type
                    }
                elif parameter.annotation is list:
                    parameter_type = "array"
                    properties[parameter.name] = {
                        "type": parameter_type
                    }
                else:
                    properties[parameter.name] = {
                        "type": parameter_type
                    }

                if (
                    parameter.default is inspect.Parameter.empty
                    and parameter.kind
                    in {
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    }
                ):
                    required.append(parameter.name)

            input_schema = {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            }

        if output_schema is None:
            output_schema = {
                "type": "string"
            }

        self.capabilities.register(
            Capability(
                name=name,
                description=description,
                input_schema=input_schema,
                output_schema=output_schema,
                permissions=permissions or [],
                risk=risk,
                executor=lambda arguments: function(**arguments)
            )
        )

    def _find_tool(self, name):
        return self.tools.get(name)

    # =========================================================
    # MATH ROUTER
    # =========================================================

    def _local_math(self, text):

        from tools.mathematics import (
            calculate,
            derivative,
            nth_derivative,
            integral,
            definite_integral,
            limit,
            series,
            solve_equation,
            factor,
            expand,
            simplify,
            numerical
        )

        original = text.strip()
        s = original.lower().strip()

        # -----------------------------------------------------
        # 1. PURE ARITHMETIC
        # -----------------------------------------------------

        if re.fullmatch(
            r"[0-9+\-*/().%\s^]+",
            s
        ):
            try:
                return calculate(original)
            except Exception:
                pass

        # -----------------------------------------------------
        # 2. DERIVATIVE
        # -----------------------------------------------------

        m = re.search(
            r"(?:derivative|differentiate|differentiation)"
            r"(?:\s+of)?\s+(.+)",
            s
        )

        if m:
            expression = m.group(1).strip()

            # Remove common wording
            expression = re.sub(
                r"\s+(with\s+respect\s+to|wrt)\s+[a-z]\s*$",
                "",
                expression
            )

            try:
                return derivative(expression)
            except Exception:
                pass

        # -----------------------------------------------------
        # 3. INTEGRAL
        # -----------------------------------------------------

        m = re.search(
            r"(?:integral|integrate|integration)"
            r"(?:\s+of)?\s+(.+)",
            s
        )

        if m:

            expression = m.group(1).strip()

            # Detect definite integral:
            # integral of x^2 from 0 to 2
            definite = re.search(
                r"(.+?)\s+from\s+(.+?)\s+to\s+(.+)",
                expression
            )

            if definite:

                expr = definite.group(1).strip()
                lower = definite.group(2).strip()
                upper = definite.group(3).strip()

                try:
                    return definite_integral(
                        expr,
                        "x",
                        lower,
                        upper
                    )
                except Exception:
                    pass

            try:
                return integral(expression)
            except Exception:
                pass

        # -----------------------------------------------------
        # 4. LIMIT
        # -----------------------------------------------------

        m = re.search(
            r"(?:limit)\s+(?:of\s+)?(.+?)"
            r"\s+(?:as|when)\s+([a-zA-Z])\s*(?:->|to)\s*(.+)",
            s
        )

        if m:

            expression = m.group(1).strip()
            variable = m.group(2).strip()
            point = m.group(3).strip()

            try:
                return limit(
                    expression,
                    variable,
                    point
                )
            except Exception:
                pass

        # -----------------------------------------------------
        # 5. SOLVE EQUATION
        # -----------------------------------------------------

        m = re.search(
            r"(?:solve|solution\s+of|find\s+the\s+roots?)"
            r"\s+(.+)",
            s
        )

        if m:

            expression = m.group(1).strip()

            if "=" in expression:

                # Detect variable if possible
                variables = re.findall(
                    r"[a-zA-Z]",
                    expression
                )

                variable = "x"

                if variables:
                    variable = variables[0]

                try:
                    return solve_equation(
                        expression,
                        variable
                    )
                except Exception:
                    pass

        # -----------------------------------------------------
        # 6. FACTOR
        # -----------------------------------------------------

        m = re.search(
            r"(?:factor|factorize|factorise)"
            r"(?:\s+)?(?:the\s+expression\s+)?(.+)",
            s
        )

        if m:

            expression = m.group(1).strip()

            try:
                return factor(expression)
            except Exception:
                pass

        # -----------------------------------------------------
        # 7. EXPAND
        # -----------------------------------------------------

        m = re.search(
            r"(?:expand)"
            r"(?:\s+)?(?:the\s+expression\s+)?(.+)",
            s
        )

        if m:

            expression = m.group(1).strip()

            try:
                return expand(expression)
            except Exception:
                pass

        # -----------------------------------------------------
        # 8. SIMPLIFY
        # -----------------------------------------------------

        m = re.search(
            r"(?:simplify)"
            r"(?:\s+)?(?:the\s+expression\s+)?(.+)",
            s
        )

        if m:

            expression = m.group(1).strip()

            try:
                return simplify(expression)
            except Exception:
                pass

        # -----------------------------------------------------
        # 9. NUMERICAL APPROXIMATION
        # -----------------------------------------------------

        m = re.search(
            r"(?:numerical value|approximate|approximation)"
            r"(?:\s+of)?\s+(.+)",
            s
        )

        if m:

            expression = m.group(1).strip()

            try:
                return numerical(expression)
            except Exception:
                pass

        return None

    # =========================================================
    # LLM DECISION
    # =========================================================

    def decide(self, user_input):

        capabilities = self.discover_capabilities(
            user_input,
            limit=6
        )

        candidate_names = {
            capability.name
            for capability in capabilities
        }

        tool_text = "\n".join(
            f"- {capability.name}: {capability.description}"
            for capability in capabilities
        )

        if not tool_text:
            tool_text = "No strongly matched capabilities were found."

        prompt = f"""
You are JARVIS, a local AI assistant.

Discovered candidate capabilities:
{tool_text}

User request:
{user_input}

Decide whether a registered tool is required.

Return ONLY valid JSON:

{{
    "action": "answer",
    "tool": null,
    "arguments": {{}}
}}

OR

{{
    "action": "tool",
    "tool": "tool_name",
    "arguments": {{}}
}}

Rules:

1. Never invent tools.
2. You may select ONLY from the discovered candidate capabilities listed above.
3. Use a candidate capability only when appropriate.
4. Do not perform mathematical calculations yourself when a
   mathematical capability is available.
5. Arguments must match the selected tool's function parameters.
6. If no discovered capability is appropriate, return action=answer.
7. Return JSON only.
"""

        result = ask_ollama(prompt)

        try:
            decision = json.loads(result)

            if decision.get("action") == "tool":
                selected_tool = decision.get("tool")

                if selected_tool not in candidate_names:
                    return {
                        "action": "answer",
                        "tool": None,
                        "arguments": {}
                    }

            return decision

        except json.JSONDecodeError:

            # Sometimes local models add surrounding text.
            match = re.search(
                r"\{.*\}",
                result,
                re.DOTALL
            )

            if match:

                try:
                    return json.loads(
                        match.group(0)
                    )
                except Exception:
                    pass

        return {
            "action": "answer",
            "tool": None,
            "arguments": {}
        }

    # =========================================================
    # EXECUTION HISTORY
    # =========================================================

    def get_execution_history(self, job_id):
        """Return the execution history for a job."""
        return self.orchestrator.get_execution_history(job_id)

    # =========================================================
    # MAIN EXECUTION
    # =========================================================

    def resume(self, job_id):
        return self.orchestrator.resume(
            job_id,
            self.tools,
        )

    def run(self, user_input):
        return self.orchestrator.run(user_input, self.tools)
