"""CP-49: manifests, dependency/cycle validation, provenance, MCP allowlist."""
import hashlib
import unittest

from core.skill_manifest import (
    ManifestError, McpAllowlist, McpDenied, McpError, SkillRegistry,
    find_cycle, validate_manifest,
)

PAYLOAD = b"skill-body"
SHA = hashlib.sha256(PAYLOAD).hexdigest()


def manifest(name="alpha", deps=None, **over):
    m = {
        "name": name, "version": "1.0.0", "description": "d",
        "capabilities": [f"{name}_cap"], "permissions": ["read_files"],
        "risk": "low", "dependencies": deps or [],
        "provenance": {"source": "local", "author": "me", "sha256": SHA},
    }
    m.update(over)
    return m


class ManifestTests(unittest.TestCase):
    def test_valid_manifest(self):
        self.assertEqual(validate_manifest(manifest()), [])

    def test_schema_violations_are_all_reported(self):
        bad = manifest(name="Bad Name", version="1.0", risk="extreme", extra=1)
        errors = validate_manifest(bad)
        self.assertGreaterEqual(len(errors), 4)

    def test_permission_allowlist(self):
        errors = validate_manifest(manifest(permissions=["root"]), {"read_files"})
        self.assertTrue(any("not allowed" in e for e in errors))

    def test_provenance_hash_is_enforced(self):
        reg = SkillRegistry()
        with self.assertRaises(ManifestError):
            reg.register(manifest(), payload=b"tampered")
        reg.register(manifest(), payload=PAYLOAD)
        self.assertEqual(reg.names(), ["alpha"])

    def test_duplicate_and_missing_dependency(self):
        reg = SkillRegistry()
        reg.register(manifest())
        with self.assertRaises(ManifestError):
            reg.register(manifest())
        with self.assertRaises(ManifestError):
            reg.register(manifest("beta", deps=["ghost"]))

    def test_cycle_detection(self):
        self.assertIsNone(find_cycle({"a": ["b"], "b": []}))
        cycle = find_cycle({"a": ["b"], "b": ["c"], "c": ["a"]})
        self.assertEqual(cycle[0], cycle[-1])

    def test_self_dependency_rejected(self):
        self.assertTrue(validate_manifest(manifest(deps=["alpha"])))

    def test_safe_disable_enable_remove(self):
        reg = SkillRegistry()
        reg.register(manifest("base"))
        reg.register(manifest("top", deps=["base"]))
        with self.assertRaises(ManifestError):
            reg.disable("base")
        with self.assertRaises(ManifestError):
            reg.remove("base")
        reg.disable("top")
        reg.disable("base")
        with self.assertRaises(ManifestError):
            reg.enable("top")
        reg.enable("base")
        reg.enable("top")
        reg.disable("top")
        reg.remove("top")
        reg.remove("base")
        self.assertEqual(reg.names(), [])

    def test_unknown_skill(self):
        with self.assertRaises(ManifestError):
            SkillRegistry().disable("nope")


class McpTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def transport(server, tool, args):
            self.calls.append((server, tool, args))
            if tool == "boom":
                raise RuntimeError("SECRET-DETAIL")
            return {"ok": True}

        self.mcp = McpAllowlist(transport)
        self.mcp.allow("docs", "search", {"query": str})
        self.mcp.allow("docs", "boom")

    def test_allowlisted_call_succeeds(self):
        self.assertEqual(self.mcp.invoke("docs", "search", {"query": "x"}), {"ok": True})

    def test_unlisted_tool_and_server_are_denied_without_transport_call(self):
        with self.assertRaises(McpDenied):
            self.mcp.invoke("docs", "delete", {})
        with self.assertRaises(McpDenied):
            self.mcp.invoke("evil", "search", {"query": "x"})
        self.assertEqual(self.calls, [])

    def test_argument_validation(self):
        for args in ({}, {"query": 1}, {"query": "x", "extra": 1}):
            with self.assertRaises(ValueError):
                self.mcp.invoke("docs", "search", args)
        self.assertEqual(self.calls, [])

    def test_transport_error_is_redacted(self):
        with self.assertRaises(McpError) as ctx:
            self.mcp.invoke("docs", "boom")
        self.assertNotIn("SECRET-DETAIL", str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)

    def test_audit_has_no_argument_values(self):
        self.mcp.invoke("docs", "search", {"query": "private-text"})
        self.assertNotIn("private-text", str(self.mcp.audit))
        self.assertEqual(self.mcp.audit[-1]["outcome"], "ok")

    def test_revoke(self):
        self.mcp.revoke("docs", "search")
        with self.assertRaises(McpDenied):
            self.mcp.invoke("docs", "search", {"query": "x"})
        self.assertEqual(self.mcp.discover("docs"), ["boom"])


if __name__ == "__main__":
    unittest.main(verbosity=2)