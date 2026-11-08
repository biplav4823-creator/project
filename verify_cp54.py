"""CP-54: scheduler with injected clock."""
import unittest

from core.scheduler import Scheduler


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.t = [1000.0]
        self.s = Scheduler(clock=lambda: self.t[0])
        self.addCleanup(self.s.close)

    def test_not_due_until_interval_elapses(self):
        self.s.add("a", 60)
        self.assertEqual(self.s.due(), [])
        self.t[0] = 1060.0
        self.assertEqual([j["name"] for j in self.s.due()], ["a"])

    def test_run_due_advances_without_catchup_flood(self):
        self.s.add("a", 60)
        calls = []
        self.t[0] = 5000.0  # many intervals missed
        self.s.run_due(lambda j: calls.append(j["name"]))
        self.s.run_due(lambda j: calls.append(j["name"]))
        self.assertEqual(calls, ["a"])
        self.assertEqual(self.s.get("a")["next_run"], 5060.0)

    def test_max_runs_disables_job(self):
        self.s.add("a", 10, max_runs=2)
        for step in (1010.0, 1020.0, 1030.0):
            self.s.run_due(lambda j: None, now=step)
        job = self.s.get("a")
        self.assertEqual(job["runs"], 2)
        self.assertFalse(job["enabled"])

    def test_circuit_breaker_after_three_consecutive_failures(self):
        self.s.add("a", 10)

        def boom(job):
            raise RuntimeError("secret detail")

        out = None
        for step in (1010.0, 1020.0, 1030.0):
            out = self.s.run_due(boom, now=step)
        self.assertEqual(out["disabled"], ["a"])
        self.assertFalse(self.s.get("a")["enabled"])
        self.assertEqual(self.s.run_due(boom, now=1040.0)["failed"], 0)

    def test_success_resets_failure_count(self):
        self.s.add("a", 10)
        flip = {"n": 0}

        def sometimes(job):
            flip["n"] += 1
            if flip["n"] in (1, 2):
                raise RuntimeError("x")

        for step in (1010.0, 1020.0, 1030.0, 1040.0):
            self.s.run_due(sometimes, now=step)
        self.assertEqual(self.s.get("a")["failures"], 0)
        self.assertTrue(self.s.get("a")["enabled"])

    def test_set_enabled_and_remove(self):
        self.s.add("a", 10)
        self.s.set_enabled("a", False)
        self.assertEqual(self.s.due(now=9999.0), [])
        self.s.set_enabled("a", True)
        self.assertEqual(len(self.s.due(now=9999.0)), 1)
        self.assertTrue(self.s.remove("a"))
        with self.assertRaises(ValueError):
            self.s.set_enabled("a", True)

    def test_validation(self):
        for args in (("bad name", 10), ("a", 0), ("a", True), ("a", 1.5)):
            with self.assertRaises(ValueError, msg=str(args)):
                self.s.add(*args)
        self.s.add("dup", 10)
        with self.assertRaises(ValueError):
            self.s.add("dup", 10)
        with self.assertRaises(ValueError):
            self.s.add("big", 10, payload={"x": "y" * 20000})
        with self.assertRaises(ValueError):
            self.s.add("mr", 10, max_runs=0)

    def test_payload_roundtrip_and_ordering(self):
        self.s.add("late", 10, payload={"k": 1}, start_at=1005.0)
        self.s.add("early", 10, start_at=1001.0)
        names = [j["name"] for j in self.s.due(now=1010.0)]
        self.assertEqual(names, ["early", "late"])
        self.assertEqual(self.s.get("late")["payload"], {"k": 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)