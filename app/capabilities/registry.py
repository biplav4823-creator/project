import json
from pathlib import Path

class CapabilityRegistry:
    def __init__(self, manifest_dir='app/capabilities/manifests'):
        self.manifest_dir = Path(manifest_dir)

    def list(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in self.manifest_dir.glob('*.json')]

    def get(self, name):
        path = self.manifest_dir / f'{name}.json'
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding='utf-8'))
