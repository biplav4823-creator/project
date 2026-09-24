from __future__ import annotations
import re

class Planner:
    def __init__(self, capabilities=None):
        self.capabilities = capabilities

    def _split(self, user_input):
        parts = re.split(r"\s+(?:and then|then|after that|followed by)\s+", user_input.strip(), flags=re.I)
        return [p.strip() for p in parts if p.strip()]

    def plan(self, user_input):
        goal = user_input.strip()
        descriptions = self._split(goal)
        steps = []

        for i, description in enumerate(descriptions, 1):
            capability = None
            candidates = []

            if self.capabilities:
                found = self.capabilities.discover(description, limit=3)
                candidates = [c.name for c in found]
                if candidates:
                    capability = candidates[0]

            steps.append({
                "id": i,
                "description": description,
                "status": "pending",
                "depends_on": [i - 1] if i > 1 else [],
                "capability": capability,
                "candidates": candidates,
                "result": None,
            })

        return {"goal": goal, "steps": steps}

