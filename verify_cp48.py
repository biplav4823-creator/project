"""CP-48: secret-safe traces and metrics. Pure and offline."""
import json
import tempfile
import unittest
from pathlib import Path

from core.trace import build_trace, export_jsonl, redact

SECRET = "sk-LIVEKEY1234567890"

EVENTS = [
    {"event_type": "plan_created", "step_id": None,
     "payload": {"steps": 2, "api_key": SECRET}},
    {"event_type": "execution_started", "step_id": 1,
     "timestamp": "2026-11-07T10:00:00+00:00", "payload": {"capability": "calculate"}},
    {"event_type": "execution_unknown", "step_id": 1,
     "timestamp": "2026-11-07T10:00:02+00:00",
     "payload": {"reason": f"Bearer abcdefghijklmnop {SECRET}"}},
    {"event_type": "execution_started", "step_id": 1,
     "timestamp": "2026-11-07T10:00:05+00:00", "payload": {}},
    {"event_type": "execution_reused", "step_id": 2, "payload": {}},
    {"event_type": "model_call", "step_id": None,
     "payload": {"prompt_tokens": 100, "completion_tokens": 20, "cost_usd": 0.0012}},
]


class TraceTests(unittest.TestCase):
    def test_secrets_never_appear_in_output(self):
        text = json.dumps(build_trace("j", EVENTS))
        self.assertNotIn(SECRET, text)
        self.assertNotIn("abcdefghijklmnop", text)
        self.assertIn("[REDACTED]", text)

    def test_redact_handles_nesting_and_foreign_types(self):
        out = redact({"a": {"password": "x", "n": [1, {"token": "t"}]}, "o": object()})
        self.assertEqual(out["a"]["password"], "[REDACTED]")
        self.assertEqual(out["a"]["n"][1]["token"], "[REDACTED]")
        self.assertEqual(out["o"], "<object>")

    def test_attempts_failures_reuse_and_latency(self):
        trace = build_trace("j", EVENTS)
        step1 = trace["steps"]["1"]
        self.assertEqual(step1["attempts"], 2)
        self.assertEqual(step1["failures"], 1)
        self.assertEqual(step1["latency_seconds"], 5.0)
        self.assertEqual(trace["steps"]["2"]["reused"], 1)
        self.assertEqual(trace["totals"]["attempts"], 2)
        self.assertEqual(trace["totals"]["failures"], 1)

    def test_token_and_cost_totals(self):
        totals = build_trace("j", EVENTS)["totals"]
        self.assertEqual(totals["prompt_tokens"], 100)
        self.assertEqual(totals["completion_tokens"], 20)
        self.assertAlmostEqual(totals["cost_usd"], 0.0012)

    def test_decisions_are_captured(self):
        types = [d["event_type"] for d in build_trace("j", EVENTS)["decisions"]]
        self.assertIn("plan_created", types)
        self.assertIn("model_call", types)

    def test_malformed_events_do_not_crash(self):
        trace = build_trace("j", [{}, {"event_type": None, "payload": "x"},
                                  {"event_type": "execution_started", "step_id": 1,
                                   "timestamp": "garbage"}])
        self.assertEqual(trace["event_count"], 3)
        self.assertIsNone(trace["steps"]["1"]["latency_seconds"])

    def test_jsonl_export_is_valid_and_secret_free(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.jsonl"
            export_jsonl(build_trace("j", EVENTS), str(path))
            text = path.read_text(encoding="utf-8")
            rows = [json.loads(line) for line in text.splitlines()]
        self.assertEqual(rows[0]["kind"], "summary")
        self.assertNotIn(SECRET, text)

    def test_empty_history(self):
        trace = build_trace("j", [])
        self.assertEqual(trace["event_count"], 0)
        self.assertEqual(trace["totals"]["attempts"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)