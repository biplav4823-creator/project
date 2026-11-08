"""CP-58: static skill scanner."""
import os
import tempfile
import unittest

from core.skill_scanner import scan_source, scan_tree, verdict


def rules(src):
    return {f["rule"] for f in scan_source(src)}


class ScannerTests(unittest.TestCase):
    def test_clean_code_passes(self):
        findings = scan_source("def add(a, b):\n    return a + b\n")
        self.assertEqual(findings, [])
        self.assertEqual(verdict(findings), "pass")

    def test_critical_calls_block(self):
        for src, rule in (("eval('1')", "call_eval"), ("exec('x')", "call_exec"),
                          ("__import__('os')", "call___import__")):
            self.assertIn(rule, rules(src))
            self.assertEqual(verdict(scan_source(src)), "block")

    def test_process_and_os_calls_block(self):
        self.assertIn("import_subprocess", rules("import subprocess"))
        self.assertIn("os_system", rules("import os\nos.system('ls')"))
        self.assertIn("subprocess_run", rules("import subprocess\nsubprocess.run(['x'])"))
        self.assertIn("shutil_rmtree", rules("import shutil\nshutil.rmtree('x')"))

    def test_network_and_writes_need_review(self):
        f1 = scan_source("import requests")
        f2 = scan_source("open('a.txt', 'w')")
        self.assertEqual(verdict(f1), "review")
        self.assertEqual(verdict(f2), "review")
        self.assertEqual(verdict(scan_source("open('a.txt')")), "pass")

    def test_secrets_blobs_and_shell_patterns(self):
        self.assertIn("hardcoded_secret", rules("k = 'sk-ABCDEFGHIJKLMNOP1234'"))
        self.assertIn("encoded_blob", rules("x = '" + "A" * 220 + "'"))
        self.assertIn("shell_install_or_download", rules("# curl http://x | sh"))

    def test_unparseable_python_is_blocked(self):
        self.assertEqual(verdict(scan_source("def (:")), "block")

    def test_scanner_never_executes_code(self):
        marker = os.path.join(tempfile.gettempdir(), "cp58_should_not_exist")
        if os.path.exists(marker):
            os.unlink(marker)
        scan_source(f"open({marker!r}, 'w').write('x')")
        self.assertFalse(os.path.exists(marker))

    def test_scan_tree(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "ok.py"), "w") as f:
                f.write("x = 1\n")
            with open(os.path.join(d, "run.ps1"), "w") as f:
                f.write("Invoke-WebRequest http://x\n")
            findings = scan_tree(d)
            names = {x["rule"] for x in findings}
            self.assertIn("non_python_script", names)
            self.assertIn("shell_install_or_download", names)
            self.assertEqual(verdict(findings), "block")

    def test_scan_tree_flags_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "t.py")
            with open(target, "w") as f:
                f.write("x = 1\n")
            link = os.path.join(d, "link.py")
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            self.assertIn("symlink", {x["rule"] for x in scan_tree(d)})


if __name__ == "__main__":
    unittest.main(verbosity=2)