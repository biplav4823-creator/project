import unittest
from unittest.mock import Mock, patch

import requests
import core.llm as llm


class CP35GatewayDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.base = "http://gateway.test/v1"
        patcher = patch.object(llm, "OMNIROUTE_BASE_URL", self.base)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_model_catalog_is_parsed_and_sorted(self):
        response = Mock()
        response.json.return_value = {
            "data": [{"id": "z-model"}, {"id": "a-model"}, {}, None]
        }

        with patch.object(llm, "_api_key", return_value="test-secret"), \
             patch.object(llm.requests, "get", return_value=response) as get:
            self.assertEqual(
                llm.list_omniroute_models(), ["a-model", "z-model"]
            )

        self.assertEqual(
            get.call_args.args[0], self.base + "/models"
        )
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"],
            "Bearer test-secret",
        )
        response.raise_for_status.assert_called_once()

    def test_connection_error_is_actionable_and_secret_safe(self):
        with patch.object(llm, "_api_key", return_value="never-print-this"), \
             patch.object(
                 llm.requests, "get",
                 side_effect=requests.ConnectionError("connection refused"),
             ):
            with self.assertRaises(RuntimeError) as caught:
                llm.list_omniroute_models()

        message = str(caught.exception)
        self.assertIn("cannot connect", message)
        self.assertIn(self.base, message)
        self.assertNotIn("never-print-this", message)
        self.assertNotIn("connection refused", message)

    def test_timeout_is_actionable(self):
        with patch.object(llm, "_api_key", return_value="test-secret"), \
             patch.object(
                 llm.requests, "get",
                 side_effect=requests.Timeout("private response details"),
             ):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                llm.list_omniroute_models()

    def test_http_failure_reports_status_not_response_body(self):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError(
            "PRIVATE RESPONSE BODY",
            response=Mock(status_code=401),
        )

        with patch.object(llm, "_api_key", return_value="test-secret"), \
             patch.object(llm.requests, "get", return_value=response):
            with self.assertRaises(RuntimeError) as caught:
                llm.list_omniroute_models()

        message = str(caught.exception)
        self.assertIn("HTTP 401", message)
        self.assertNotIn("PRIVATE RESPONSE BODY", message)
        self.assertNotIn("test-secret", message)

    def test_chat_completion_success(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "gateway reply"}}]
        }

        with patch.object(llm, "_api_key", return_value="test-secret"), \
             patch.object(llm.requests, "post", return_value=response) as post:
            answer = llm._ask_omniroute(
                [{"role": "user", "content": "hello"}], "test-model"
            )

        self.assertEqual(answer, "gateway reply")
        self.assertEqual(
            post.call_args.args[0], self.base + "/chat/completions"
        )
        response.raise_for_status.assert_called_once()

    def test_chat_connection_error_is_actionable(self):
        with patch.object(llm, "_api_key", return_value="test-secret"), \
             patch.object(
                 llm.requests, "post",
                 side_effect=requests.ConnectionError("connection refused"),
             ):
            with self.assertRaisesRegex(
                RuntimeError, "chat completion failed: cannot connect"
            ):
                llm._ask_omniroute(
                    [{"role": "user", "content": "hello"}], "test-model"
                )

    def test_fallback_reports_both_failure_reasons(self):
        with patch.object(llm, "LLM_PROVIDER", "omniroute"), \
             patch.object(
                 llm, "_ask_omniroute",
                 side_effect=RuntimeError("gateway cannot connect"),
             ), \
             patch.object(
                 llm, "_ask_ollama",
                 side_effect=requests.ConnectionError("local connection refused"),
             ):
            with self.assertRaises(RuntimeError) as caught:
                llm.ask_messages([{"role": "user", "content": "hello"}])

        message = str(caught.exception)
        self.assertIn("gateway cannot connect", message)
        self.assertIn("Ollama:", message)
        self.assertIn("connection failed", message)

    def test_explicit_ollama_provider_does_not_call_gateway(self):
        with patch.object(llm, "LLM_PROVIDER", "ollama"), \
             patch.object(llm, "_ask_ollama", return_value="local reply"), \
             patch.object(llm, "_ask_omniroute") as gateway:
            answer = llm.ask_messages(
                [{"role": "user", "content": "hello"}]
            )

        self.assertEqual(answer, "local reply")
        gateway.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
