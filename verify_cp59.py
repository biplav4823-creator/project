"""CP-59: provider attribution, secret-safe provider errors, audit helpers."""
import unittest
from unittest import mock

import core.llm as llm
from core.readiness_audit import exit_code, render

SECRET = "sk-LEAKLEAKLEAK1234567890"
MSGS = [{"role": "user", "content": "hi"}]


def boom(*args, **kwargs):
    raise RuntimeError(f"failed with {SECRET}")


class ProviderTests(unittest.TestCase):
    def test_error_summary_scrubs_secrets(self):
        self.assertNotIn(SECRET, llm._error_summary(RuntimeError(f"x {SECRET}")))

    def test_omniroute_answer_is_attributed(self):
        with mock.patch.object(llm, "LLM_PROVIDER", "omniroute"), \
                mock.patch.object(llm, "get_active_model", lambda: "model-a"), \
                mock.patch.object(llm, "_ask_omniroute", lambda m, model: "OMNI"):
            self.assertEqual(llm.ask_messages(MSGS), "OMNI")
        self.assertEqual(llm.last_provider(), {"provider": "omniroute", "model": "model-a"})

    def test_fallback_to_ollama_is_attributed(self):
        with mock.patch.object(llm, "LLM_PROVIDER", "omniroute"), \
                mock.patch.object(llm, "get_active_model", lambda: "model-a"), \
                mock.patch.object(llm, "_ask_omniroute", boom), \
                mock.patch.object(llm, "_ask_ollama", lambda m, u=None, mo=None: "OLLAMA"):
            self.assertEqual(llm.ask_messages(MSGS), "OLLAMA")
        self.assertEqual(llm.last_provider()["provider"], "ollama")

    def test_explicit_ollama_provider_is_attributed_and_skips_gateway(self):
        gateway = mock.Mock(side_effect=AssertionError("gateway must not be called"))
        with mock.patch.object(llm, "LLM_PROVIDER", "ollama"), \
                mock.patch.object(llm, "_ask_omniroute", gateway), \
                mock.patch.object(llm, "_ask_ollama", lambda m, u=None, mo=None: "OLLAMA"):
            self.assertEqual(llm.ask_messages(MSGS, ollama_model="custom"), "OLLAMA")
        self.assertEqual(llm.last_provider(), {"provider": "ollama", "model": "custom"})

    def test_both_fail_reports_both_without_secret(self):
        with mock.patch.object(llm, "LLM_PROVIDER", "omniroute"), \
                mock.patch.object(llm, "get_active_model", lambda: "m"), \
                mock.patch.object(llm, "_ask_omniroute", boom), \
                mock.patch.object(llm, "_ask_ollama", boom):
            with self.assertRaises(RuntimeError) as ctx:
                llm.ask_messages(MSGS)
        text = str(ctx.exception)
        self.assertNotIn(SECRET, text)
        self.assertIn("OmniRoute", text)
        self.assertIn("Ollama", text)

    def test_last_provider_returns_a_copy(self):
        snapshot = llm.last_provider()
        snapshot["provider"] = "tampered"
        self.assertNotEqual(llm.last_provider()["provider"], "tampered")


class AuditHelperTests(unittest.TestCase):
    def test_exit_code_only_fails_on_fail(self):
        ok = [{"area": "a", "check": "c", "status": "GAP", "detail": ""}]
        bad = ok + [{"area": "a", "check": "d", "status": "FAIL", "detail": "x"}]
        self.assertEqual(exit_code(ok), 0)
        self.assertEqual(exit_code(bad), 1)

    def test_render_groups_and_summarises(self):
        text = render([{"area": "provider", "check": "c", "status": "PASS", "detail": ""},
                       {"area": "repo", "check": "d", "status": "GAP", "detail": "why"}])
        self.assertIn("[provider]", text)
        self.assertIn("SUMMARY: PASS=1  FAIL=0  GAP=1  SKIP=0", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)