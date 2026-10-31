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
        for control in ("sudoku-file", "file-feedback", "demo-play",
                        "demo-stop", "demo-speed", "demo-steps", "demo-status"):
            self.assertIn('id="' + control + '"', self.html)
        self.assertIn("function stopDemo()", self.script)
        self.assertIn("function playDemo()", self.script)
        self.assertIn("function parseSudokuFile(raw)", self.script)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_javascript_syntax(self):
        proc = subprocess.run(["node", "--check", "--input-type=commonjs"],
                              input=self.script, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node.js unavailable")
    def test_file_parser_valid_and_invalid(self):
        # Extract the pure parser, not the browser DOM event handler.
        start = self.script.index("function parseSudokuFile(raw)")
        end = self.script.index("$('sudoku-file').addEventListener", start)
        parser = self.script[start:end]
        js = parser + r"""
const assert = require('node:assert/strict');
const solved = '534678912672195348198342567859761423426853791713924856961537284287419635345286179';
assert.deepEqual(parseSudokuFile(solved), [...solved].map(Number));
assert.deepEqual(parseSudokuFile('\uFEFF'+solved.match(/.{9}/g).join('\r\n')),
                 [...solved].map(Number));
assert.equal(parseSudokuFile('.'+solved.slice(1))[0], 0);
assert.equal(parseSudokuFile('0'+solved.slice(1))[0], 0);
assert.deepEqual(parseSudokuFile(solved.match(/.{9}/g).join('\n')+'\n# comment'),
                 [...solved].map(Number));
for(const bad of [solved.slice(1), solved+'2', solved.slice(0,10)+'x'+solved.slice(11),
                  solved.match(/.{9}/g).slice(0,8).join('\n')]){
  assert.throws(()=>parseSudokuFile(bad));
}
"""
        proc = subprocess.run(["node", "-"], input=js, text=True, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
