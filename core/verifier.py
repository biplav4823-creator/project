"""Explicit execution-output verification contract.

This checks the returned output envelope, not the semantic correctness
of the underlying computation. Applications needing semantic guarantees
must supply an independent domain-specific checker.
"""


class Verifier:
    def verify(self, result):
        """Return a structured verification result while preserving legacy fields."""
        status = "passed"
        reason = "A non-None execution output was returned."
        if result is None:
            status = "indeterminate"
            reason = "No output was returned; correctness cannot be established."
        elif isinstance(result, dict):
            declared_status = result.get("status")
            if result.get("verified") is False or declared_status in (
                "failed", "indeterminate", "rejected"
            ):
                status = "failed" if declared_status == "failed" or result.get("verified") is False else "indeterminate"
                reason = "The returned result explicitly reports an unsuccessful or indeterminate outcome."

        return {
            "verified": status == "passed",
            "status": status,
            "verification_kind": "execution_output",
            "reason": reason,
            "evidence": {
                "output_present": result is not None,
                "output_type": type(result).__name__,
            },
            "result": result,
        }
