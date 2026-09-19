class Planner:
    def plan(self, user_input):
        text = user_input.strip()

        separators = [
            " and then ",
            " then ",
            " after that ",
            " followed by "
        ]

        steps = None

        for separator in separators:
            if separator in text.lower():
                parts = text.lower().split(separator)
                steps = [
                    part.strip()
                    for part in parts
                    if part.strip()
                ]
                break

        if not steps:
            steps = [text]

        planned_steps = []

        for index, step in enumerate(steps, start=1):
            planned_steps.append({
                "id": index,
                "description": step,
                "status": "pending"
            })

        return {
            "goal": user_input,
            "steps": planned_steps
        }
