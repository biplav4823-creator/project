"""CP-50: bounded delegation. Pure and offline."""
import unittest

from core.delegation import Budget, DelegationError, Delegator, compare

OK = lambda out: True


def root(**over):
    base = dict(max_depth=2, max_fanout=2, max_calls=10,
                permissions=frozenset({"read", "write"}))
    base.update(over)
    return Delegator(Budget(**base))


class DelegationTests(unittest.TestCase):
    def code(self, fn):
        with self.assertRaises(DelegationError) as ctx:
            fn()
        return ctx.exception.code

    def test_happy_path_returns_verified_typed_output(self):
        out = root().delegate("s", lambda c: {"n": 3}, {"read"}, {"n": int}, OK)
        self.assertEqual(out, {"n": 3})

    def test_permission_escalation_is_blocked(self):
        self.assertEqual(
            self.code(lambda: root().delegate("s", lambda c: {}, {"network"}, {}, OK)),
            "permission_escalation",
        )

    def test_child_cannot_exceed_its_own_inherited_permissions(self):
        def parent_fn(child):
            return child.delegate("g", lambda c: {}, {"write"}, {}, OK)

        self.assertEqual(
            self.code(lambda: root().delegate("p", parent_fn, {"read"}, {}, OK)),
            "permission_escalation",
        )

    def test_depth_limit(self):
        def nest(child):
            return child.delegate("g", lambda c: c.delegate(
                "gg", lambda x: {}, {"read"}, {}, OK), {"read"}, {}, OK)

        self.assertEqual(
            self.code(lambda: root(max_depth=2).delegate("p", nest, {"read"}, {}, OK)),
            "max_depth",
        )

    def test_fanout_limit(self):
        r = root(max_fanout=2)
        for i in range(2):
            r.delegate(f"s{i}", lambda c: {}, {"read"}, {}, OK)
        self.assertEqual(
            self.code(lambda: r.delegate("s3", lambda c: {}, {"read"}, {}, OK)),
            "max_fanout",
        )

    def test_shared_call_budget_spans_the_tree(self):
        r = root(max_fanout=5, max_calls=2, max_depth=3)

        def parent(child):
            child.delegate("a", lambda c: {}, {"read"}, {}, OK)
            return {}

        r.delegate("p", parent, {"read"}, {}, OK)  # uses 2 calls
        self.assertEqual(r.calls_used, 2)
        self.assertEqual(
            self.code(lambda: r.delegate("q", lambda c: {}, {"read"}, {}, OK)),
            "call_budget",
        )

    def test_typed_output_validation(self):
        d = lambda out: root().delegate("s", lambda c: out, {"read"}, {"n": int}, OK)
        self.assertEqual(self.code(lambda: d("text")), "output_not_object")
        self.assertEqual(self.code(lambda: d({"n": 1, "x": 2})), "output_fields_mismatch")
        self.assertEqual(self.code(lambda: d({"n": "1"})), "output_type_mismatch")
        self.assertEqual(self.code(lambda: d({"n": True})), "output_type_mismatch")

    def test_parent_verification_is_mandatory(self):
        self.assertEqual(
            self.code(lambda: root().delegate(
                "s", lambda c: {"n": 1}, {"read"}, {"n": int}, lambda o: o["n"] == 2)),
            "parent_verification_failed",
        )
        self.assertEqual(
            self.code(lambda: root().delegate("s", lambda c: {}, {"read"}, {}, None)),
            "verifier_required",
        )

    def test_benchmark_compare(self):
        tasks = [1, 2, 3, 4]
        report = compare(
            tasks,
            single=lambda t: t if t % 2 == 0 else -1,
            delegated=lambda t: t,
            check=lambda t, out: out == t,
        )
        self.assertEqual(report["single"]["rate"], 0.5)
        self.assertEqual(report["delegated"]["rate"], 1.0)
        self.assertEqual(report["delegation_gain"], 0.5)

    def test_benchmark_counts_exceptions_as_failures(self):
        def boom(t):
            raise RuntimeError("x")

        report = compare([1], boom, lambda t: t, lambda t, o: o == t)
        self.assertEqual(report["single"]["passed"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)