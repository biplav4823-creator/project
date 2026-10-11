import unittest
from unittest.mock import Mock, patch

import requests

from core import llm_diagnostics as diag


class CP36ProviderDiagnosticsTests(unittest.TestCase):
    def response(self, status=200, payload=None):
        response = Mock()
        response.status_code = status
        response.json.return_value = payload
        return response

    def test_omniroute_discovers_models_without_exposing_key(self):
        response = self.response(200, {
            "data": [{"id": "z-model"}, {"id": "a-model"}, {}]
        })

        with patch.object(
            diag.requests, "get", return_value=response
        ) as get:
            result = diag.probe_omniroute(
                "https://user:pass@gateway.test/v1?token=hidden",
                api_key="never-print-this",
            )

        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["reachable"])
        self.assertEqual(result["model_count"], 2)
        self.assertEqual(result["models"], ["a-model", "z-model"])
        self.assertEqual(result["url"], "https://gateway.test/v1/models")
        self.assertTrue(result["api_key_configured"])
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"],
            "Bearer never-print-this",
        )
        self.assertNotIn("never-print-this", str(result))
        self.assertNotIn("hidden", str(result))

    def test_missing_key_and_unauthorized_endpoint_are_distinguished(self):
        with patch.object(
            diag.requests, "get",
            return_value=self.response(401, {"error": "private"}),
        ):
            result = diag.probe_omniroute(
                "http://gateway.test/v1", api_key=""
            )

        self.assertEqual(result["status"], "authentication_required")
        self.assertTrue(result["reachable"])
        self.assertFalse(result["api_key_configured"])
        self.assertNotIn("private", str(result))

    def test_rejected_configured_key_is_distinguished(self):
        with patch.object(
            diag.requests, "get",
            return_value=self.response(403, {"error": "private"}),
        ):
            result = diag.probe_omniroute(
                "http://gateway.test/v1", api_key="bad-key"
            )

        self.assertEqual(result["status"], "authentication_rejected")
        self.assertTrue(result["api_key_configured"])
        self.assertNotIn("bad-key", str(result))
        self.assertNotIn("private", str(result))

    def test_connection_refusal_reports_unreachable(self):
        with patch.object(
            diag.requests, "get",
            side_effect=requests.ConnectionError("private details"),
        ):
            result = diag.probe_omniroute(
                "http://127.0.0.1:20128/v1", api_key=""
            )

        self.assertEqual(result["status"], "unreachable")
        self.assertFalse(result["reachable"])
        self.assertNotIn("private details", str(result))

    def test_timeout_is_distinct_from_connection_refusal(self):
        with patch.object(
            diag.requests, "get", side_effect=requests.Timeout()
        ):
            result = diag.probe_omniroute(
                "http://gateway.test/v1", api_key=""
            )

        self.assertEqual(result["status"], "timeout")

    def test_unexpected_catalog_schema_is_not_marked_ready(self):
        with patch.object(
            diag.requests, "get",
            return_value=self.response(200, {"unexpected": []}),
        ):
            result = diag.probe_omniroute(
                "http://gateway.test/v1", api_key=""
            )

        self.assertEqual(result["status"], "invalid_response")
        self.assertTrue(result["reachable"])

    def test_404_identifies_missing_endpoint_without_body(self):
        with patch.object(
            diag.requests, "get",
            return_value=self.response(404, {"error": "secret body"}),
        ):
            result = diag.probe_omniroute(
                "http://gateway.test/v1", api_key=""
            )

        self.assertEqual(result["status"], "endpoint_not_found")
        self.assertTrue(result["reachable"])
        self.assertNotIn("secret body", str(result))

    def test_ollama_catalog_is_checked(self):
        with patch.object(
            diag.requests, "get",
            return_value=self.response(200, {
                "models": [{"name": "qwen-local"}, {"name": "llama-local"}]
            }),
        ) as get:
            result = diag.probe_ollama("http://localhost:11434")

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["model_count"], 2)
        self.assertEqual(
            get.call_args.args[0], "http://localhost:11434/api/tags"
        )

    def test_invalid_url_fails_without_network_access(self):
        with patch.object(diag.requests, "get") as get:
            result = diag.probe_omniroute("not-a-url", api_key="")

        self.assertEqual(result["status"], "invalid_configuration")
        get.assert_not_called()

    def test_provider_report_contains_both_providers(self):
        with patch.object(
            diag, "probe_omniroute",
            return_value={"status": "unreachable"},
        ), patch.object(
            diag, "probe_ollama",
            return_value={"status": "ready"},
        ), patch.object(diag, "LLM_PROVIDER", "omniroute"):
            report = diag.diagnose_providers()

        self.assertEqual(report["active_provider"], "omniroute")
        self.assertIn("omniroute", report)
        self.assertIn("ollama", report)
        self.assertEqual(report["ollama"]["status"], "ready")


if __name__ == "__main__":
    unittest.main(verbosity=2)
