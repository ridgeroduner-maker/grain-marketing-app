"""Runs public/directory.test.js (the Directory layer's pure helpers) under node, so the Python suite - and CI, which has node - covers it."""
import shutil, subprocess, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]


class DirectoryJs(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_node_tests(self):
        r = subprocess.run(["node", str(ROOT / "public" / "directory.test.js")], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("directory ok", r.stdout)

    def test_test_file_is_not_shipped(self):
        self.assertIn("*.test.js", (ROOT / "build_dist.sh").read_text())


if __name__ == "__main__":
    unittest.main()
