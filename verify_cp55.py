"""CP-55: DAG execution."""
import threading
import time
import unittest

from core.dag import DagError, run_dag


class DagTests(unittest.TestCase):
    def test_dataflow_between_dependent_tasks(self):
        tasks = {
            "a": (lambda i: 2, []),
            "b": (lambda i: i["a"] * 10, ["a"]),
            "c": (lambda i: i["a"] + i["b"], ["a", "b"]),
        }
        out = run_dag(tasks)
        self.assertEqual(out["c"], {"status": "ok", "result": 22})

    def test_independent_branches_run_concurrently(self):
        barrier = threading.Barrier(2, timeout=3)

        def branch(i):
            barrier.wait()  # both must be running at once or this times out
            return "ok"

        out = run_dag({"x": (branch, []), "y": (branch, [])}, max_workers=2)
        self.assertEqual(out["x"]["status"], "ok")
        self.assertEqual(out["y"]["status"], "ok")

    def test_worker_bound_is_respected(self):
        live, peak, lock = [0], [0], threading.Lock()

        def work(i):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.05)
            with lock:
                live[0] -= 1

        run_dag({f"t{n}": (work, []) for n in range(6)}, max_workers=2)
        self.assertLessEqual(peak[0], 2)

    def test_failure_skips_descendants_but_not_siblings(self):
        def boom(i):
            raise RuntimeError("SECRET-123")

        tasks = {
            "bad": (boom, []),
            "child": (lambda i: 1, ["bad"]),
            "grandchild": (lambda i: 1, ["child"]),
            "sibling": (lambda i: 7, []),
        }
        out = run_dag(tasks)
        self.assertEqual(out["bad"], {"status": "failed", "error_type": "RuntimeError"})
        self.assertEqual(out["child"]["status"], "skipped")
        self.assertEqual(out["grandchild"]["status"], "skipped")
        self.assertEqual(out["sibling"]["result"], 7)
        self.assertNotIn("SECRET-123", str(out))

    def test_fail_fast_skips_unstarted_work(self):
        def boom(i):
            raise RuntimeError("x")

        tasks = {"bad": (boom, []), "late": (lambda i: 1, ["bad"]),
                 "other": (lambda i: 1, ["other_dep"]), "other_dep": (lambda i: 1, [])}
        out = run_dag(tasks, max_workers=1, fail_fast=True)
        self.assertEqual(out["late"]["status"], "skipped")

    def test_validation_errors(self):
        f = lambda i: 1
        for bad in ({}, {"a": (f, ["ghost"])}, {"a": (f, ["a"])},
                    {"a": (f, ["b"]), "b": (f, ["a"])}, {"a": (f, "b")},
                    {"a": ("notcallable", [])}):
            with self.assertRaises(DagError, msg=str(bad)):
                run_dag(bad)
        with self.assertRaises(DagError):
            run_dag({"a": (f, [])}, max_workers=0)


if __name__ == "__main__":
    unittest.main(verbosity=2)