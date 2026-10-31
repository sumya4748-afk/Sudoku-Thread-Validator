"""Regression checks for dashboard script and Sudoku text-file parser."""
from pathlib import Path
import re
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "dashboard.html"


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")
        scripts = re.findall(r"<script>(.*?)</script>", cls.html, flags=re.S)
        assert len(scripts) == 1, "Expected one dashboard script"
        cls.script = scripts[0]

    def test_required_controls_exist(self):
        for control in ("demo-play", "demo-stop", "demo-speed", "demo-steps", "demo-status"):
            self.assertIn('id="' + control + '"', self.html)
        self.assertIn("function stopDemo()", self.script)
        self.assertIn("function playDemo()", self.script)
        self.assertNotIn('id="sudoku-file"', self.html)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_javascript_syntax(self):
        proc = subprocess.run(["node", "--check", "--input-type=commonjs"],
                              input=self.script, text=True, encoding='utf-8', capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)



if __name__ == "__main__":
    unittest.main()
