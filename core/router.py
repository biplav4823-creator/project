from dataclasses import dataclass

@dataclass
class RouteDecision:
    action: str
    tool: str | None = None
    arguments: dict | None = None

class Router:
    def route(self, decision: dict):
        return RouteDecision(action=decision.get('action','answer'), tool=decision.get('tool'), arguments=decision.get('arguments', {}))
