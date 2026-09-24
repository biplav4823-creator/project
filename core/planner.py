class Planner:
    def __init__(self, capabilities=None):
        self.capabilities = capabilities

    def plan(self, user_input):
        text = user_input.strip()

        separators = [
            " and then ",
            " then ",
            " after that ",
            " followed by ",
        ]

        steps = None

        for separator in separators:
            lower_text = text.lower()
            position = lower_text.find(separator)

            if position != -1:
                parts = []
                start = 0

                while position != -1:
                    part = text[start:position].strip()

                    if part:
                        parts.append(part)

                    start = position + len(separator)
                    position = lower_text.find(separator, start)

                final_part = text[start:].strip()

                if final_part:
                    parts.append(final_part)

                steps = parts
                break

        if not steps:
            steps = [text]

        planned_steps = []

        for index, step in enumerate(steps, start=1):
            dependencies = [index - 1] if index > 1 else []

            candidates = []

            if self.capabilities is not None:
                candidates = self.capabilities.discover(
                    step,
                    limit=3
                )

            capability = (
                candidates[0].name
                if candidates
                else None
            )

            planned_steps.append({
                "id": index,
                "description": step,
                "status": "pending",
                "depends_on": dependencies,
                "capability": capability,
                "candidates": [
                    item.name for item in candidates
                ],
                "result": None,
            })

        return {
            "goal": user_input,
            "steps": planned_steps,
        }
