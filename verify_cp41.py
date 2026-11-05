import unittest
from core.verifier import Verifier


class VerifierContractTests(unittest.TestCase):
    def setUp(self):
        self.verifier = Verifier()

    def test_non_none_output_has_explicit_contract_status(self):
        result = self.verifier.verify({"answer": 42})
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["verified"])
        self.assertEqual(result["verification_kind"], "execution_output")
        self.assertEqual(result["result"], {"answer": 42})

    def test_none_output_is_indeterminate(self):
        result = self.verifier.verify(None)
        self.assertEqual(result["status"], "indeterminate")
        self.assertFalse(result["verified"])

    def test_explicit_failure_is_not_verified(self):
        result = self.verifier.verify({"verified": False, "error": "failed"})
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["verified"])

    def test_explicit_indeterminate_status_is_preserved(self):
        result = self.verifier.verify({"status": "indeterminate"})
        self.assertEqual(result["status"], "indeterminate")
        self.assertFalse(result["verified"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
