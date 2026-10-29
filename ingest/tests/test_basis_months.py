"""USDA prints a different futures month at each end of one basis range, e.g. '-106.00F to -70.00X' (Jan low end, Nov high end).
Real cases from the saved 2026-10-28 reports: MN South (3049), SD Northeast (3186), ND East Central (3878)."""
import datetime, json, sqlite3, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ingest import db, export_json, ingest, parse_pdf

FIX = Path(__file__).parent / "fixtures"
CASES = [  # slug, state, location, grade, basis_low, basis_high, low_month, high_month
    (3049, "MN", "South", "US #1 Soybeans", -80.0, -50.0, "Jan", "Nov"),
    (3186, "SD", "Northeast", "US #1 Soybeans", -106.0, -70.0, "Jan", "Nov"),
    (3878, "ND", "East Central", "US #2 Soybeans", -85.0, -85.0, "Nov", "Jan"),   # high end is the later-listed month here
]

def parse(slug, state, name="ams_{}_20261028.pdf"):
    txt = parse_pdf.pdf_to_text((FIX / name.format(slug)).read_bytes())
    return parse_pdf.parse_report(txt, slug, "t", state)

class MixedMonths(unittest.TestCase):
    def test_parser_keeps_a_month_per_end(self):
        for slug, st, loc, grade, lo, hi, mlo, mhi in CASES:
            r = parse(slug, st)
            row = [b for b in r["bids"] if b["location"] == loc and b["grade"] == grade and b["delivery"] == "Current" and b["commodity"] == "soybeans"]
            self.assertEqual(len(row), 1, (slug, loc))
            b = row[0]
            self.assertEqual((b["basis_low"], b["basis_high"], b["basis_low_month"], b["basis_high_month"]), (lo, hi, mlo, mhi), (slug, loc))
            self.assertEqual(b["basis_futures_month"], mlo)               # legacy single field = low-end month

    def test_same_month_ranges_unchanged(self):
        r = parse(3186, "SD")
        same = [b for b in r["bids"] if b["location"] == "Southeast" and b["commodity"] == "corn"][0]
        self.assertEqual(same["basis_low_month"], same["basis_high_month"]); self.assertTrue(same["basis_low_month"])
        # every other soybean/corn row in the three reports keeps one month at both ends
        for slug, st, loc, grade, *_ in CASES:
            for b in parse(slug, st)["bids"]:
                if (b["location"], b["grade"]) != (loc, grade) and b["basis_low"] is not None:
                    self.assertEqual(b["basis_low_month"], b["basis_high_month"], (slug, b["location"], b["grade"]))

    def test_pdf_basis_matches_price_for_mixed_row(self):
        # sanity from the report itself: -106c on Jan 1238.00 = 11.32 and -70c on Nov 1224.50 = 11.545 (bid_low/high), so each end really uses its own month
        b = [x for x in parse(3186, "SD")["bids"] if x["location"] == "Northeast" and x["commodity"] == "soybeans"][0]
        fut = {f["contract"]: f["settle_cents"] for f in parse(3186, "SD")["futures"] if f["commodity"].lower().startswith("soy")}
        self.assertAlmostEqual(fut["Jan 27"] + b["basis_low"], b["bid_low"] * 100, places=0)
        self.assertAlmostEqual(fut["Nov 26"] + b["basis_high"], b["bid_high"] * 100, places=0)

    def _export(self, slug, state):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        con = db.connect(Path(tmp.name) / "t.db")
        p = parse(slug, state)
        ingest.upsert(con, p["bids"], [dict(f, report_date=p["report_date"], source_report=f"AMS_{slug}") for f in p["futures"]],
                      "pdf", state, posted_at="2026-10-28T14:15:33-05:00", status=p["status"])
        con.commit()
        out = Path(tmp.name) / "out"
        export_json.export(con, out, today=datetime.date(2026, 10, 28))
        return json.loads((out / "latest.json").read_text())

    def test_export_has_month_and_ref_per_end(self):
        rows = self._export(3186, "SD")
        mixed = [r for r in rows if r["location"] == "SD Northeast" and r["commodity"] == "soybeans"][0]
        self.assertEqual((mixed["basis_low_month"], mixed["basis_high_month"]), ("Jan", "Nov"))
        self.assertEqual((mixed["basis_ref_low"], mixed["basis_ref_high"]), ("CBOT Jan futures", "CBOT Nov futures"))
        plain = [r for r in rows if r["location"] == "SD Southeast" and r["commodity"] == "corn"][0]
        self.assertEqual(plain["basis_ref_low"], plain["basis_ref_high"]); self.assertEqual(plain["basis_ref_low"], plain["basis_ref"])

    def test_migration_adds_columns_and_backfills_old_database(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "old.db"
        con = sqlite3.connect(path)       # a pre-Job-9 database: bids without the two month columns
        con.executescript("""CREATE TABLE locations(id INTEGER PRIMARY KEY, state TEXT, name TEXT, section TEXT DEFAULT '', lat REAL, lon REAL, geo_method TEXT, distance_mi REAL, UNIQUE(state,name,section));
          CREATE TABLE bids(id INTEGER PRIMARY KEY, commodity TEXT NOT NULL, location_id INTEGER NOT NULL, grade TEXT NOT NULL DEFAULT '', protein TEXT NOT NULL DEFAULT '',
            bid_low REAL, bid_high REAL, bid_avg REAL, unit TEXT, basis_low REAL, basis_high REAL, basis_unit TEXT, basis_futures_month TEXT,
            delivery TEXT NOT NULL DEFAULT 'Current', freight TEXT, sale_type TEXT, report_date TEXT NOT NULL, source_report TEXT NOT NULL, source_title TEXT,
            fetched_at TEXT, posted_at TEXT, report_status TEXT, is_sample INTEGER NOT NULL DEFAULT 0,
            UNIQUE(report_date, source_report, commodity, grade, protein, location_id, delivery));
          INSERT INTO locations(id,state,name) VALUES (1,'SD','Central');
          INSERT INTO bids(commodity,location_id,bid_high,basis_low,basis_high,basis_futures_month,report_date,source_report) VALUES ('corn',1,4.0,-60,-41,'Dec','2026-10-26','AMS_3186');""")
        con.commit(); con.close()
        con = db.connect(path)
        row = con.execute("SELECT basis_low_month, basis_high_month FROM bids").fetchone()
        self.assertEqual((row[0], row[1]), ("Dec", "Dec"))
        flat = con.execute("SELECT basis_low_month, basis_high_month FROM bids_flat").fetchone()
        self.assertEqual((flat[0], flat[1]), ("Dec", "Dec"))
        db.connect(path)                  # idempotent

class UiLabel(unittest.TestCase):
    def test_app_js_labels_each_end(self):
        js = (Path(__file__).resolve().parents[2] / "public" / "app.js").read_text()
        self.assertIn("basis_ref_low", js); self.assertIn("basis_ref_high", js)
        self.assertRegex(js, r"r\.basis_low \+ '¢ vs ' \+ lo \+ ' to ' \+ r\.basis_high \+ '¢ vs ' \+ hi")

if __name__ == "__main__":
    unittest.main()
