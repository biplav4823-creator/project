"""CP-52: memory store. Offline; in-memory SQLite."""
import unittest

from core.memory import MemoryStore


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.m = MemoryStore()
        self.addCleanup(self.m.close)

    def test_add_and_search_ranks_relevant_first(self):
        self.m.add("The invoice for Acme is due on Friday", source="email")
        self.m.add("Grocery list: milk eggs bread", source="note")
        hits = self.m.search("when is the Acme invoice due")
        self.assertTrue(hits)
        self.assertIn("Acme", hits[0]["text"])
        self.assertEqual(hits[0]["source"], "email")

    def test_namespaces_are_isolated(self):
        self.m.add("alpha secret plan", namespace="work", source="s")
        self.assertEqual(self.m.search("alpha", namespace="home"), [])
        self.assertEqual(len(self.m.search("alpha", namespace="work")), 1)

    def test_secrets_are_redacted_on_write(self):
        mid = self.m.add("token sk-LIVEKEY1234567890 stays private", source="s")
        stored = self.m.get(mid)["text"]
        self.assertNotIn("LIVEKEY", stored)
        self.assertIn("[REDACTED]", stored)

    def test_validation(self):
        for bad in ("", "   "):
            with self.assertRaises(ValueError):
                self.m.add(bad, source="s")
        with self.assertRaises(ValueError):
            self.m.add("x", source="")
        with self.assertRaises(ValueError):
            self.m.add("x" * 20001, source="s")
        with self.assertRaises(ValueError):
            self.m.add("x", namespace="Bad Name", source="s")

    def test_query_with_fts_syntax_is_safe(self):
        self.m.add("plain text here", source="s")
        for q in ('"', "AND OR NOT", "a* NEAR(b)", "'; DROP TABLE mem;--", ""):
            self.m.search(q)  # must not raise
        self.assertEqual(self.m.count(), 1)

    def test_delete_and_forget(self):
        a = self.m.add("one two", source="s")
        self.m.add("three four", namespace="other", source="s")
        self.assertTrue(self.m.delete(a))
        self.assertFalse(self.m.delete(a))
        self.assertEqual(self.m.search("one"), [])
        self.assertEqual(self.m.forget_namespace("other"), 1)
        self.assertEqual(self.m.count(), 0)

    def test_tags_and_job_id_roundtrip(self):
        mid = self.m.add("note", source="s", tags=["b", "a", "a"], job_id="job-1")
        rec = self.m.get(mid)
        self.assertEqual(rec["tags"], ["a", "b"])
        self.assertEqual(rec["job_id"], "job-1")

    def test_limit_is_bounded(self):
        for i in range(10):
            self.m.add(f"shared word {i}", source="s")
        self.assertEqual(len(self.m.search("shared", limit=3)), 3)

    def test_fallback_without_fts(self):
        m = MemoryStore()
        m._fts = False
        m.add("fallback search works", source="s")
        self.assertEqual(len(m.search("fallback")), 1)
        m.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)