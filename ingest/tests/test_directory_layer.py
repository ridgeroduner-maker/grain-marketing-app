"""Directory layer front end: the layer is isolated from bids/alerts/table, off by default, uses the reviewer's wording, and the README documents the build step."""
import re, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "public"


class DocsAndWiring(unittest.TestCase):
    def test_readme_documents_it(self):
        rd = (ROOT / "README.md").read_text()
        for must in ("ingest.build_directory", "directory.json", "elevator-directory.csv", "source_list_date", "bid_page_url", "geocode_quality"):
            self.assertIn(must, rd, must)


class LayerIsIsolatedFromBids(unittest.TestCase):
    """Static checks on the front-end wiring: directory rows never enter the bid state, ranking, alerts, table or service-worker alert check."""
    @classmethod
    def setUpClass(cls):
        cls.app = (PUBLIC / "app.js").read_text(); cls.dirjs = (PUBLIC / "directory.js").read_text()
        cls.core = (PUBLIC / "alerts-core.js").read_text(); cls.sw = (PUBLIC / "sw.js").read_text(); cls.html = (PUBLIC / "index.html").read_text()

    def test_directory_data_never_touches_bid_state(self):
        self.assertNotIn("directory", self.core.lower()); self.assertNotIn("directory", self.sw.split("const SHELL", 1)[1].split("self.addEventListener('install'", 1)[0].replace("'directory.js'", ""))
        for fn in ("filtered", "renderTable", "renderBest", "renderAlerts", "checkAlerts", "renderOutside"):
            m = re.search(r"function %s\b.*?\n}\n" % fn, self.app, re.S)
            if m: self.assertNotRegex(m.group(0).lower(), r"directory|\bdir[a-z]*\(", fn)
        self.assertNotIn("state.latest.push", self.dirjs); self.assertNotIn("state.latest", self.dirjs)
        self.assertNotIn("directory.json", "".join(re.findall(r"fetch\([^)]*\)", self.core)))

    def test_default_off_and_separate_toggle(self):
        m = re.search(r'<input[^>]*id="dirToggle"[^>]*>', self.html); self.assertIsNotNone(m)
        self.assertNotIn("checked", m.group(0)); self.assertIn('type="checkbox"', m.group(0))
        self.assertNotIn("localStorage", self.dirjs)                                                       # the choice is not stored: off on every visit

    def test_exact_review_wording_present(self):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", self.html))
        for w in ("Directory only, NOT bids", "Licensed grain buyers and warehouses from state lists. Names and towns only. No prices."): self.assertIn(w, text)
        for w in ("Directory listing, NOT a bid.", "No prices shown.", "A listing does not mean this firm takes part in this app, endorses it, or is offering any price here, or that it is open or buying today.",
                  "Location is the town\\u2019s approximate center, not the facility.", "Call the elevator for current bids."):
            self.assertIn(w, self.dirjs)


if __name__ == "__main__":
    unittest.main()
