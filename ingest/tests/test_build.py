"""build_dist.sh / serve.py: key injection never touches public/ or git, data-sample never reaches dist/."""
import os, subprocess, sys, shutil, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
KEY = "AIzaSyTESTKEY-0123456789abcdefghijklmnop"

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.sample = ROOT / "public" / "data-sample"
        self.made = not self.sample.exists()
        if self.made:
            self.sample.mkdir(); (self.sample / "latest.json").write_text("[]")      # ensure the exclusion is really exercised
        self.addCleanup(lambda: (shutil.rmtree(self.sample) if self.made else None))
        self.addCleanup(lambda: shutil.rmtree(ROOT / "dist", ignore_errors=True))
        self.public_cfg = (ROOT / "public" / "config.js").read_text()

    def build(self, key):
        env = {k: v for k, v in os.environ.items() if k != "GOOGLE_MAPS_API_KEY"}
        if key: env["GOOGLE_MAPS_API_KEY"] = key
        return subprocess.run(["bash", str(ROOT / "build_dist.sh")], cwd=ROOT, env=env, capture_output=True, text=True)

    def test_without_key(self):
        r = self.build(None); self.assertEqual(r.returncode, 0, r.stderr)
        cfg = (ROOT / "dist" / "config.js").read_text()
        self.assertEqual(cfg, self.public_cfg)
        self.assertFalse((ROOT / "dist" / "data-sample").exists())

    def test_with_key_is_appended_to_dist_only(self):
        r = self.build(KEY); self.assertEqual(r.returncode, 0, r.stderr)
        cfg = (ROOT / "dist" / "config.js").read_text()
        self.assertIn(f'window.GRAIN_CONFIG.GOOGLE_MAPS_API_KEY = "{KEY}";', cfg)
        self.assertEqual((ROOT / "public" / "config.js").read_text(), self.public_cfg)    # source config untouched
        self.assertNotIn(KEY, (ROOT / "public" / "config.js").read_text())
        self.assertFalse((ROOT / "dist" / "data-sample").exists())
        self.assertFalse(any("data-sample" in str(p) for p in (ROOT / "dist").rglob("*")))

    def test_serve_suffix_is_json_escaped(self):
        import serve
        self.assertEqual(serve.config_suffix(""), "")
        s = serve.config_suffix('ab"c\\d')
        self.assertIn('"ab\\"c\\\\d"', s)

    def test_env_files_ignored_and_example_has_placeholder_only(self):
        gi = (ROOT / ".gitignore").read_text().split()
        self.assertIn(".env", gi); self.assertIn("dist/", gi)
        ex = (ROOT / ".env.example").read_text()
        self.assertRegex(ex, r"(?m)^GOOGLE_MAPS_API_KEY=\s*$")
        tracked = subprocess.run(["git", "ls-files", ".env"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertEqual(tracked.strip(), "")

if __name__ == "__main__":
    unittest.main()
