import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.state_store import StateStore


class CP40StateStoreIsolationTests(unittest.TestCase):
    def test_environment_override_is_used_for_default_store(self):
        with tempfile.TemporaryDirectory(prefix="cp40_env_") as root:
            database = str(Path(root) / "isolated.db")

            with patch.dict(os.environ, {"JARVIS_STATE_DB": database}):
                store = StateStore()
                store.save("cp40-job", {"status": "isolated"})

                self.assertEqual(store.database_path, database)
                self.assertEqual(
                    store.load("cp40-job"), {"status": "isolated"}
                )
                self.assertTrue(Path(database).is_file())

    def test_explicit_database_path_overrides_environment(self):
        with tempfile.TemporaryDirectory(prefix="cp40_explicit_") as root:
            env_database = str(Path(root) / "from_env.db")
            explicit_database = str(Path(root) / "explicit.db")

            with patch.dict(os.environ, {"JARVIS_STATE_DB": env_database}):
                store = StateStore(explicit_database)
                store.save("explicit-job", {"value": 7})

                self.assertEqual(store.database_path, explicit_database)
                self.assertEqual(
                    store.load("explicit-job"), {"value": 7}
                )
                self.assertFalse(Path(env_database).exists())

    def test_legacy_default_is_preserved_without_environment_override(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(StateStore, "_initialize") as initialize:
                store = StateStore()

        self.assertEqual(store.database_path, "jarvis_state.db")
        initialize.assert_called_once_with()

    def test_separate_database_paths_do_not_share_jobs(self):
        with tempfile.TemporaryDirectory(prefix="cp40_separate_") as root:
            first_path = str(Path(root) / "first.db")
            second_path = str(Path(root) / "second.db")

            first = StateStore(first_path)
            second = StateStore(second_path)

            first.save("only-first", {"owner": "first"})
            second.save("only-second", {"owner": "second"})

            self.assertEqual(
                first.load("only-first"), {"owner": "first"}
            )
            self.assertIsNone(first.load("only-second"))
            self.assertEqual(
                second.load("only-second"), {"owner": "second"}
            )
            self.assertIsNone(second.load("only-first"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
