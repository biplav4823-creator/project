"""CP-49: portable skill manifests and a governed MCP allowlist.

Pure and offline. Manifests are validated (schema, provenance, dependencies,
cycles) before registration; MCP tools are callable only when explicitly
allowlisted, with arguments validated and no argument values logged.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Callable, Dict, List, Optional

NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENT_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
RISKS = {"low", "medium", "high", "critical"}
FIELDS = {
    "name", "version", "description", "capabilities", "permissions",
    "risk", "dependencies", "provenance",
}
PROVENANCE_FIELDS = {"source", "author", "sha256"}


class ManifestError(ValueError):
    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def validate_manifest(
    manifest: Any, allowed_permissions: Optional[set] = None
) -> List[str]:
    errors: List[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]
    for extra in sorted(set(manifest) - FIELDS):
        errors.append(f"unknown field: {extra}")
    if not isinstance(manifest.get("name"), str) or not NAME_RE.match(manifest["name"]):
        errors.append("name invalid")
    if not isinstance(manifest.get("version"), str) or not VERSION_RE.match(manifest["version"]):
        errors.append("version must be MAJOR.MINOR.PATCH")
    if not isinstance(manifest.get("description"), str) or not manifest["description"].strip():
        errors.append("description required")
    caps = manifest.get("capabilities")
    if not isinstance(caps, list) or not caps or not all(
        isinstance(c, str) and IDENT_RE.match(c) for c in caps
    ):
        errors.append("capabilities must be a non-empty list of identifiers")
    elif len(set(caps)) != len(caps):
        errors.append("capabilities contain duplicates")
    perms = manifest.get("permissions", [])
    if not isinstance(perms, list) or not all(
        isinstance(p, str) and IDENT_RE.match(p) for p in perms
    ):
        errors.append("permissions must be a list of identifiers")
    elif allowed_permissions is not None:
        for p in perms:
            if p not in allowed_permissions:
                errors.append(f"permission not allowed: {p}")
    if manifest.get("risk") not in RISKS:
        errors.append("risk must be one of low, medium, high, critical")
    deps = manifest.get("dependencies", [])
    if not isinstance(deps, list) or not all(
        isinstance(d, str) and NAME_RE.match(d) for d in deps
    ):
        errors.append("dependencies must be a list of skill names")
    elif manifest.get("name") in deps:
        errors.append("skill cannot depend on itself")
    prov = manifest.get("provenance")
    if not isinstance(prov, dict):
        errors.append("provenance required")
    else:
        for extra in sorted(set(prov) - PROVENANCE_FIELDS):
            errors.append(f"unknown provenance field: {extra}")
        if not isinstance(prov.get("source"), str) or not prov["source"].strip():
            errors.append("provenance.source required")
        if not isinstance(prov.get("sha256"), str) or not SHA256_RE.match(prov["sha256"]):
            errors.append("provenance.sha256 must be 64 lowercase hex characters")
    return errors


def find_cycle(graph: Dict[str, List[str]]) -> Optional[List[str]]:
    """Return one dependency cycle as a list of names, or None."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph}
    stack: List[str] = []

    def visit(node: str) -> Optional[List[str]]:
        color[node] = GREY
        stack.append(node)
        for dep in graph.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GREY:
                return stack[stack.index(dep):] + [dep]
            if color[dep] == WHITE:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        color[node] = BLACK
        return None

    for name in list(graph):
        if color[name] == WHITE:
            found = visit(name)
            if found:
                return found
    return None


class SkillRegistry:
    def __init__(self, allowed_permissions: Optional[set] = None):
        self._allowed = allowed_permissions
        self._skills: Dict[str, Dict[str, Any]] = {}

    def register(self, manifest: Dict[str, Any], payload: Optional[bytes] = None) -> None:
        errors = validate_manifest(manifest, self._allowed)
        if errors:
            raise ManifestError(errors)
        name = manifest["name"]
        if name in self._skills:
            raise ManifestError([f"already registered: {name}"])
        if payload is not None:
            if hashlib.sha256(payload).hexdigest() != manifest["provenance"]["sha256"]:
                raise ManifestError(["payload does not match provenance.sha256"])
        missing = [d for d in manifest.get("dependencies", []) if d not in self._skills]
        if missing:
            raise ManifestError([f"missing dependency: {d}" for d in missing])
        graph = {n: list(s["manifest"].get("dependencies", [])) for n, s in self._skills.items()}
        graph[name] = list(manifest.get("dependencies", []))
        cycle = find_cycle(graph)
        if cycle:
            raise ManifestError(["dependency cycle: " + " -> ".join(cycle)])
        self._skills[name] = {"manifest": dict(manifest), "enabled": True}

    def _dependents(self, name: str, enabled_only: bool) -> List[str]:
        return sorted(
            n for n, s in self._skills.items()
            if name in s["manifest"].get("dependencies", [])
            and (s["enabled"] or not enabled_only)
        )

    def _get(self, name: str) -> Dict[str, Any]:
        if name not in self._skills:
            raise ManifestError([f"unknown skill: {name}"])
        return self._skills[name]

    def disable(self, name: str) -> None:
        skill = self._get(name)
        blockers = self._dependents(name, enabled_only=True)
        if blockers:
            raise ManifestError([f"enabled dependents: {', '.join(blockers)}"])
        skill["enabled"] = False

    def enable(self, name: str) -> None:
        skill = self._get(name)
        off = [d for d in skill["manifest"].get("dependencies", [])
               if not self._skills[d]["enabled"]]
        if off:
            raise ManifestError([f"disabled dependencies: {', '.join(off)}"])
        skill["enabled"] = True

    def remove(self, name: str) -> None:
        self._get(name)
        blockers = self._dependents(name, enabled_only=False)
        if blockers:
            raise ManifestError([f"dependents exist: {', '.join(blockers)}"])
        del self._skills[name]

    def is_enabled(self, name: str) -> bool:
        return name in self._skills and self._skills[name]["enabled"]

    def names(self) -> List[str]:
        return sorted(self._skills)


class McpDenied(PermissionError):
    pass


class McpError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"MCP call failed ({code}).")


class McpAllowlist:
    """Allowlisted MCP invocation through an injected transport."""

    def __init__(self, transport: Callable[[str, str, Dict[str, Any]], Any]):
        self._transport = transport
        self._allowed: Dict[str, Dict[str, Dict[str, type]]] = {}
        self.audit: List[Dict[str, Any]] = []

    def allow(self, server: str, tool: str, schema: Optional[Dict[str, type]] = None) -> None:
        if not (IDENT_RE.match(server) and IDENT_RE.match(tool)):
            raise ValueError("invalid server or tool identifier")
        self._allowed.setdefault(server, {})[tool] = dict(schema or {})

    def revoke(self, server: str, tool: Optional[str] = None) -> None:
        if tool is None:
            self._allowed.pop(server, None)
        else:
            self._allowed.get(server, {}).pop(tool, None)

    def discover(self, server: str) -> List[str]:
        return sorted(self._allowed.get(server, {}))

    def invoke(self, server: str, tool: str, args: Optional[Dict[str, Any]] = None) -> Any:
        args = args or {}
        schema = self._allowed.get(server, {}).get(tool)
        if schema is None:
            self._log(server, tool, args, "denied")
            raise McpDenied(f"{server}/{tool} is not allowlisted.")
        extra = set(args) - set(schema)
        missing = set(schema) - set(args)
        wrong = [k for k, t in schema.items() if k in args and not isinstance(args[k], t)]
        if extra or missing or wrong:
            self._log(server, tool, args, "invalid_arguments")
            raise ValueError("arguments do not match the allowlisted schema")
        try:
            result = self._transport(server, tool, dict(args))
        except Exception as exc:
            self._log(server, tool, args, "error")
            raise McpError(type(exc).__name__) from None
        self._log(server, tool, args, "ok")
        return result

    def _log(self, server: str, tool: str, args: Dict[str, Any], outcome: str) -> None:
        self.audit.append(
            {"server": server, "tool": tool, "arg_keys": sorted(args), "outcome": outcome}
        )