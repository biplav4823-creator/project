"""CP-56: artifact store."""
import os
import tempfile
import unittest

from core.artifacts import ArtifactError, ArtifactStore


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.s = ArtifactStore(os.path.join(self.tmp.name, "store"))

    def test_put_get_roundtrip_is_content_addressed(self):
        a = self.s.put(b"hello", "text", producer={"job": "j1"})
        b = self.s.put(b"hello", "text", producer={"job": "j2"})
        self.assertEqual(a, b)
        self.assertEqual(self.s.get(a), b"hello")
        self.assertEqual(len(self.s.info(a)["produced_by"]), 2)
        self.assertEqual(self.s.list(), [a])

    def test_tampering_is_detected(self):
        aid = self.s.put(b"original", "text")
        with open(self.s._blob(aid), "wb") as f:
            f.write(b"tampered")
        self.assertFalse(self.s.verify(aid))
        with self.assertRaises(ArtifactError):
            self.s.get(aid)

    def test_lineage_is_transitive(self):
        a = self.s.put(b"a", "raw")
        b = self.s.put(b"b", "derived", parents=[a])
        c = self.s.put(b"c", "report", parents=[b])
        self.assertEqual(self.s.lineage(c), [b, a])
        self.assertEqual(self.s.lineage(a), [])

    def test_unknown_parent_and_ids_rejected(self):
        with self.assertRaises(ArtifactError):
            self.s.put(b"x", "text", parents=["0" * 64])
        for bad in ("../../etc/passwd", "short", None, "G" * 64):
            with self.assertRaises(ArtifactError, msg=str(bad)):
                self.s.get(bad)

    def test_input_validation(self):
        with self.assertRaises(ArtifactError):
            self.s.put("not bytes", "text")
        with self.assertRaises(ArtifactError):
            self.s.put(b"x", "Bad Kind")

    def test_list_by_kind(self):
        a = self.s.put(b"a", "raw")
        self.s.put(b"b", "report")
        self.assertEqual(self.s.list("raw"), [a])

    def test_unknown_artifact(self):
        with self.assertRaises(ArtifactError):
            self.s.get("a" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)