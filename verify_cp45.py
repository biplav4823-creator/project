"""CP-45: whole-word capability discovery matching."""
import unittest

from capabilities.registry import _phrase_matches


class DiscoveryMatchTests(unittest.TestCase):
    def test_substring_inside_word_does_not_match(self):
        self.assertFalse(_phrase_matches("sum", "please summarize this"))
        self.assertFalse(_phrase_matches("add", "what is my address"))
        self.assertFalse(_phrase_matches("mean", "that is meaningful"))

    def test_whole_word_matches(self):
        self.assertTrue(_phrase_matches("sum", "sum 2 and 3"))
        self.assertTrue(_phrase_matches("analyze data", "please analyze data now"))
        self.assertTrue(_phrase_matches("Add", "ADD 1 and 2"))

    def test_simple_inflection_matches(self):
        self.assertTrue(_phrase_matches("sum", "sums of lists"))
        self.assertTrue(_phrase_matches("calculate", "calculates 2+2"))

    def test_punctuation_boundaries(self):
        self.assertTrue(_phrase_matches("sum", "(sum)"))
        self.assertTrue(_phrase_matches("mean", "mean, median"))

    def test_invalid_input_is_safe(self):
        self.assertFalse(_phrase_matches("", "anything"))
        self.assertFalse(_phrase_matches(None, "anything"))
        self.assertFalse(_phrase_matches("x", None))


if __name__ == "__main__":
    unittest.main(verbosity=2)