from .registry import CapabilityRegistry

class CapabilityManager:
    def __init__(self):
        self.registry = CapabilityRegistry()

    def list_capabilities(self):
        return self.registry.list()

    def get_capability(self, name):
        return self.registry.get(name)

    def available(self):
        return [c for c in self.list_capabilities() if c.get('status') == 'available']
