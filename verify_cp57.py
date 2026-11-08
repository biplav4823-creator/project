"""CP-57: secret broker."""
import unittest

from core.vault import SecretBroker, SecretUnavailable

ENV = {"MY_KEY": "sk-LIVEKEY1234567890", "SHORT": "abc"}


def broker():
    b = SecretBroker(env=dict(ENV))
    b.register("api", "MY_KEY")
    b.register("short", "SHORT")
    b.register("missing", "NOT_SET")
    return b


class VaultTests(unittest.TestCase):
    def test_get_returns_value_and_audits_without_it(self):
        b = broker()
        self.assertEqual(b.get("api", "call provider"), ENV["MY_KEY"])
        self.assertNotIn("LIVEKEY", str(b.audit))
        self.assertEqual(b.audit[-1]["outcome"], "ok")

    def test_unavailable_and_unregistered(self):
        b = broker()
        for name in ("missing", "ghost"):
            with self.assertRaises(SecretUnavailable):
                b.get(name, "x")
        self.assertEqual(b.audit[-1]["outcome"], "unavailable")
        self.assertFalse(b.available("missing"))
        self.assertTrue(b.available("api"))

    def test_purpose_is_required(self):
        with self.assertRaises(ValueError):
            broker().get("api", "  ")

    def test_scrub_removes_values_everywhere(self):
        b = broker()
        text = f"error calling with {ENV['MY_KEY']} and again {ENV['MY_KEY']}"
        cleaned = b.scrub(text)
        self.assertNotIn("LIVEKEY", cleaned)
        self.assertIn("[REDACTED:api]", cleaned)

    def test_short_values_are_not_scrubbed(self):
        self.assertEqual(broker().scrub("abc abc"), "abc abc")

    def test_repr_never_contains_values(self):
        b = broker()
        b.get("api", "x")
        self.assertNotIn("LIVEKEY", repr(b))

    def test_registration_validation(self):
        b = SecretBroker(env={})
        for args in (("Bad", "X"), ("ok", "1BAD"), ("", "X")):
            with self.assertRaises(ValueError, msg=str(args)):
                b.register(*args)


if __name__ == "__main__":
    unittest.main(verbosity=2)