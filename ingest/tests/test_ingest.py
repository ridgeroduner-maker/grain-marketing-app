import json, sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ingest import geo, parse_pdf, mars_api

FIX = Path(__file__).parent / "fixtures"

class T(unittest.TestCase):
    def test_haversine(self):
        # Gann Valley -> Sioux Falls is ~ 100 mi
        d = geo.haversine_miles(44.0, -98.9, 43.5446, -96.7311)
        self.assertTrue(95 < d < 125, d)
        self.assertAlmostEqual(geo.haversine_miles(44, -98.9, 44, -98.9), 0)

    def _parse(self, name, slug, state):
        txt = parse_pdf.pdf_to_text((FIX / name).read_bytes())
        return parse_pdf.parse_report(txt, slug, "t", state)

    def test_sd_report(self):
        r = self._parse("ams_3186_20261026.pdf", 3186, "SD")
        self.assertEqual(r["report_date"], "2026-10-26")
        self.assertEqual(len(r["bids"]), 19)
        corn = [b for b in r["bids"] if b["commodity"] == "corn" and b["location"] == "Southeast"][0]
        self.assertEqual((corn["bid_low"], corn["bid_high"], corn["basis_low"], corn["basis_high"]), (3.95, 4.14, -60.0, -41.0))
        self.assertEqual(corn["basis_futures_month"], "Dec")
        self.assertTrue(any(f["commodity"] == "Corn" and f["contract"] == "Dec 26" and f["settle_cents"] == 455.0 for f in r["futures"]))
        self.assertFalse(any("Oats" in b["heading"] for b in r["bids"]))  # out of scope

    def test_national_sunflower(self):
        r = self._parse("ams_2887_20261026.pdf", 2887, None)
        sf = [b for b in r["bids"] if b["location"] == "Enderlin, ND" and b["delivery"] == "Current"]
        self.assertEqual(sf[0]["bid_high"], 25.9); self.assertEqual(sf[0]["unit"], "$/Cwt")
        self.assertFalse(any(b["commodity"] != "sunflowers" for b in r["bids"]))

    def test_locate(self):
        lat, lon, m = geo.locate(None, "Enderlin, ND")
        self.assertEqual(m, "gazetteer_town"); self.assertTrue(46 < lat < 47)
        self.assertEqual(geo.locate("SD", "Central")[2], "approx_region_centroid")
        self.assertIsNone(geo.locate("SD", "Nowhere Land"))

    def test_mars_normalize(self):
        # Row shape copied from a public MARS sample response (SD report 3186).
        row = {"report_date": "05/31/2023", "market_location_state": "SD", "slug_id": 3186, "commodity": "Soybeans",
               "trade_loc": "Central", "grade": "US #1", "protein": None, "delivery_point": "Country Elevators",
               "basis_unit": "¢/Bu", "sale Type": "Bid", "basis Min": 20, "basis Min Futures Month": "August (Q)",
               "basis Max": 30, "price_unit": "$ Per Bushel", "price Min": 12.3775, "price Max": 12.4775,
               "avg_price": 12.4108, "freight": "Delivered", "trans_mode": "Truck", "current": "Yes"}
        out, _ = mars_api.normalize_rows([row], 3186, "SD", "SD")
        self.assertEqual(out[0]["commodity"], "soybeans"); self.assertEqual(out[0]["location"], "Central")
        self.assertEqual(out[0]["basis_futures_month"], "Aug"); self.assertEqual(out[0]["bid_high"], 12.4775)

if __name__ == "__main__":
    unittest.main()
