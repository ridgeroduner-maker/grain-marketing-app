"""build_dist.sh / serve.py: key injection never touches public/ or git, data-sample never reaches dist/."""
import os, subprocess, sys, shutil, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
KEY = "TESTKEY-0123456789abcdefghijklmnop"

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
        env = {k: v for k, v in os.environ.items() if k != "MAP_TILES_KEY"}
        if key: env["MAP_TILES_KEY"] = key
        return subprocess.run(["bash", str(ROOT / "build_dist.sh")], cwd=ROOT, env=env, capture_output=True, text=True)

    def test_without_key(self):
        r = self.build(None); self.assertEqual(r.returncode, 0, r.stderr)
        cfg = (ROOT / "dist" / "config.js").read_text()
        self.assertEqual(cfg, self.public_cfg)
        self.assertFalse((ROOT / "dist" / "data-sample").exists())

    def test_with_key_is_appended_to_dist_only(self):
        r = self.build(KEY); self.assertEqual(r.returncode, 0, r.stderr)
        cfg = (ROOT / "dist" / "config.js").read_text()
        self.assertIn(f'window.GRAIN_CONFIG.MAP_TILES_KEY = "{KEY}";', cfg)
        self.assertEqual((ROOT / "public" / "config.js").read_text(), self.public_cfg)    # source config untouched
        self.assertNotIn(KEY, (ROOT / "public" / "config.js").read_text())
        self.assertFalse((ROOT / "dist" / "data-sample").exists())
        self.assertFalse(any("data-sample" in str(p) for p in (ROOT / "dist").rglob("*")))

    def test_test_scripts_are_not_shipped_and_nojekyll_added(self):
        self.assertTrue(list((ROOT / "public").glob("*.test.js")), "public/ still has node tests (the exclusion must be exercised)")
        r = self.build(None); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([str(p) for p in (ROOT / "dist").rglob("*.test.js")], [])
        self.assertTrue((ROOT / "dist" / ".nojekyll").is_file())
        self.assertTrue((ROOT / "dist" / "alerts-core.js").is_file())            # the real code beside them is still there
        self.assertIn("*.test.js", (ROOT / "build_dist.sh").read_text())         # and the script keeps a leak check
        self.assertIn("a *.test.js file leaked", (ROOT / "build_dist.sh").read_text())

    def test_pmtiles_file_is_gitignored_and_copied_when_present(self):
        gi = (ROOT / ".gitignore").read_text().split()
        self.assertIn("public/tiles/*.pmtiles", gi)                       # the ~17 MB archive is built, never committed
        tiled = subprocess.run(["git", "ls-files", "public/tiles"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertNotIn(".pmtiles", tiled)
        tdir = ROOT / "public" / "tiles"; f = tdir / "plains.pmtiles"
        had = f.exists(); tdir.mkdir(exist_ok=True)
        if not had: f.write_bytes(b"PMTiles-test")
        self.addCleanup(lambda: (f.unlink() if not had and f.exists() else None))
        r = self.build(None); self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((ROOT / "dist" / "tiles" / "plains.pmtiles").exists())
        self.assertIn("Range", r.stdout)

    def test_serve_range_parser(self):
        import serve
        self.assertEqual(serve.parse_range("bytes=0-99", 1000), (0, 99))
        self.assertEqual(serve.parse_range("bytes=900-", 1000), (900, 999))
        self.assertEqual(serve.parse_range("bytes=-100", 1000), (900, 999))
        self.assertEqual(serve.parse_range("bytes=990-5000", 1000), (990, 999))
        self.assertIsNone(serve.parse_range("bytes=1000-1001", 1000))
        self.assertIsNone(serve.parse_range("bytes=0-1,5-6", 1000))
        self.assertIsNone(serve.parse_range("", 1000))

    def test_build_tiles_script_documents_free_no_account_extract(self):
        sh = (ROOT / "build_tiles.sh").read_text()
        self.assertIn("pmtiles", sh); self.assertIn("extract", sh); self.assertIn("--maxzoom", sh); self.assertIn("--bbox", sh)
        self.assertIn("build.protomaps.com", sh)
        r = subprocess.run(["bash", "-n", str(ROOT / "build_tiles.sh")], capture_output=True, text=True); self.assertEqual(r.returncode, 0, r.stderr)

    def test_serve_suffix_is_json_escaped(self):
        import serve
        self.assertEqual(serve.config_suffix(""), "")
        s = serve.config_suffix('ab"c\\d')
        self.assertIn('"ab\\"c\\\\d"', s)

    def test_env_files_ignored_and_example_has_placeholder_only(self):
        gi = (ROOT / ".gitignore").read_text().split()
        self.assertIn(".env", gi); self.assertIn("dist/", gi)
        ex = (ROOT / ".env.example").read_text()
        self.assertRegex(ex, r"(?m)^MAP_TILES_KEY=\s*$")
        tracked = subprocess.run(["git", "ls-files", ".env"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertEqual(tracked.strip(), "")

if __name__ == "__main__":
    unittest.main()
