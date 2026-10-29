"""Directory layer build step (ingest/build_directory.py): CSV -> public/data/directory.json. v1 and v2 formats, odd/missing values, the
300-mile rule, what may and may not be in the output, and that the layer is isolated from bids, alerts and the table."""
import csv, io, json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ingest import build_directory as bd, config

FIX = Path(__file__).parent / "fixtures"
PUBLIC = ROOT / "public"


def build_from(text, name="d.csv"):
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / name; p.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        doc, rep = bd.build(p, Path(t) / "out.json")
        return json.loads((Path(t) / "out.json").read_text(encoding="utf-8")), rep


def csv_text(header, *rows):
    b = io.StringIO(); w = csv.writer(b); w.writerow(header); w.writerows(rows); return b.getvalue()


BASE = ["name", "town", "state", "lat", "lon"]


class V2Format(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc, cls.rep = build_from((FIX / "directory_v2.csv").read_bytes())
        cls.by = {r["name"]: r for r in cls.doc["rows"]}

    def test_format_and_counts(self):
        self.assertEqual(self.doc["format"], "v2"); self.assertEqual(self.doc["schema"], "grain-directory-2")
        self.assertEqual(self.doc["count"], len(self.doc["rows"]))
        self.assertEqual(self.rep["read"], 32)
        self.assertEqual(self.doc["dropped"], {"bad_name": 1, "not_business": 4, "bad_town": 1, "bad_state": 0, "bad_coords": 3, "not_geocoded": 1, "outside_radius": 1, "individual": 1, "duplicate": 1})
        self.assertEqual(self.doc["cleared"], {"bad_link": 2, "bad_display_coords": 1})
        self.assertEqual(self.rep["kept"] + sum(self.doc["dropped"].values()), self.rep["read"])

    def test_v2_columns_used(self):
        r = self.by["Fixture Coop A"]
        self.assertEqual((r["category"], r["link"], r["gq"], r["src"]), ("elevator/co-op", "https://www.example.com/cash-bids", "census_place_centroid", ["SD"]))
        self.assertEqual(self.by["Coarse Geo Co"]["gq"], "county_centroid")             # kept, flagged: the UI words it differently
        self.assertEqual(self.by["Fixture Ethanol LLC"]["category"], "processor")
        self.assertEqual(self.by["Ks Far Co"]["state"], "KS")                              # a row in another state is kept if inside the 300 miles

    def test_dates_belong_to_the_list_not_the_row(self):
        s = self.doc["sources"]
        self.assertEqual((s["SD"]["date"], s["SD"]["kind"]), ("2026-10-23", "as of"))
        self.assertEqual((s["NE-LOC"]["date"], s["NE-LOC"]["kind"]), ("2026-10-28", "as of"))      # Location Capacity Report, "As of October 28, 2026"
        self.assertEqual((s["NE-DLR"]["date"], s["NE-DLR"]["kind"]), ("2026-09-29", "as of"))      # Grain Dealer List
        for k in ("ND", "IA", "MN"): self.assertEqual((s[k]["date"], s[k]["kind"]), ("2026-10-28", "fetched"), k)   # undated live pages: only the fetch date is known
        self.assertEqual(self.by["Ne Location Co"]["src"], ["NE-LOC"]); self.assertEqual(self.by["Ne Dealer Co"]["src"], ["NE-DLR"])
        self.assertEqual(self.by["Spaced Out Co"]["src"], ["ND"]); self.assertEqual(self.by["Ia Co"]["src"], ["IA"]); self.assertEqual(self.by["Mn Undated Co"]["src"], ["MN"])
        self.assertEqual(self.by["Two Lists Coop"]["src"], ["SD", "MN"])                  # merged row cites two lists; the messy source_list_date cell is not used
        self.assertEqual(self.by["Unknown Source Co"]["src"], []); self.assertEqual(self.by["Unknown Source Co"]["date"], "2026-10-23")   # unknown list: first readable date only
        self.assertEqual(set(self.doc["sources"]), {"SD", "ND", "NE-LOC", "NE-DLR", "IA", "MN"})      # only lists that rows cite

    def test_geocode_flags(self):
        self.assertEqual(self.by["Two Lists Coop"]["fl"], ["office"])
        self.assertEqual(self.by["Mn Undated Co"]["fl"], ["ambiguous", "check"]); self.assertEqual(self.by["Mn Undated Co"]["gq"], "census_township_centroid")
        self.assertNotIn("fl", self.by["Fixture Coop A"])

    def test_display_coordinates_for_placement_only(self):
        k = [r for r in self.doc["rows"] if r["town"] == "Kimball"]
        self.assertEqual(len(k), 3); self.assertEqual(len({(r["lat"], r["lon"]) for r in k}), 1, "true lat/lon stay the shared town point")
        self.assertEqual({(r["dlat"], r["dlon"]) for r in k}, {(43.75279, -98.9566), (43.74149, -98.94889), (43.74149, -98.96431)})
        self.assertEqual(len({(r["dlat"], r["dlon"]) for r in k}), 3, "co-located firms get distinct display points")
        self.assertEqual({r["mi"] for r in k}, {self.by["Fixture Grain Co"]["mi"]}, "distance uses the true coordinates")
        self.assertNotIn("dlat", self.by["Odd Display Co"])                                # display point > 2 mi from the true one: ignored (and counted)

    def test_links_only_when_safe(self):
        self.assertEqual(self.by["Bad Link Co"]["link"], ""); self.assertEqual(self.by["Creds Link Co"]["link"], "")
        for r in self.doc["rows"]:
            if r["link"]: self.assertRegex(r["link"], r"^https?://[^/@\s]+\.[^/@\s]+")

    def test_dropped_rows_are_gone(self):
        names = set(self.by)
        for gone in ("NAME", "Digits Town Co", "Bad Lat Co", "No Lat Co", "Zero Zero Co", "Far Away Co", "Not Found Co", "Plain Person", "Indiv Category Co"):
            self.assertNotIn(gone, names)
        self.assertEqual(sum(1 for r in self.doc["rows"] if r["name"].startswith("Fixture Coop A")), 1)      # duplicate (", Inc.", other case/state case) merged

    def test_individuals_are_dropped_conservatively(self):
        for gone in ("JOHN Q FIXTUREPERSON", "Fixtureperson Farms", "Fixtureperson & Sons", "Plain Person"): self.assertNotIn(gone, self.by)
        self.assertEqual(self.doc["dropped"]["not_business"], 4)
        self.assertIn("Fixtureperson Farm Service", self.by)                                # two different weak markers = a business (borderline, reported locally)
        self.assertNotIn("FIXTUREPERSON", json.dumps(self.doc).replace("Fixtureperson Farm Service", ""))      # no dropped name anywhere in the output
        self.assertEqual(self.rep["borderline_kept"].count(("Fixtureperson Farm Service", "Redfield", "SD")), 1)

    def test_odd_values_cleaned_not_repaired(self):
        self.assertIn("Spaced Out Co", self.by)                                           # control chars and spacing collapsed
        r = self.by['Fixture <b>Markup</b> & "Quotes" Grain']; self.assertEqual(r["town"], "Highmore")   # markup kept as text (the UI escapes it)

    def test_no_source_notes_licence_numbers_or_counties_in_output(self):
        raw = json.dumps(self.doc["rows"])                                           # (the sources table legitimately says "Licensed ...")
        for leak in ("SECRET-LIC", "90210", "Fixtureshire", "Count", "notes", "licence", "license", "crops", "warehouse/buyer"): self.assertNotIn(leak, raw, leak)
        self.assertEqual(self.rep["read"], 32)

    def test_state_uppercased_and_sorted_deterministically(self):
        self.assertTrue(all(re.fullmatch(r"[A-Z]{2}", r["state"]) for r in self.doc["rows"]))
        keys = [(r["state"], r["town"].upper(), r["name"].upper(), r["id"]) for r in self.doc["rows"]]
        self.assertEqual(keys, sorted(keys))
        again, _ = build_from((FIX / "directory_v2.csv").read_bytes()); self.assertEqual(again, self.doc)
        self.assertEqual(len({r["id"] for r in self.doc["rows"]}), len(self.doc["rows"]))

    def test_dropped_report_is_local_and_complete(self):
        with tempfile.TemporaryDirectory() as t:
            rep = Path(t) / "r.txt"; out = Path(t) / "o.json"
            self.assertEqual(bd.main(["--csv", str(FIX / "directory_v2.csv"), "--out", str(out), "--dropped-report", str(rep)]), 0)
            txt = rep.read_text()
            for n in ("not_business | Plain Person", "not_business | Fixtureperson Farms", "bad_name | NAME", "duplicate | Fixture Coop A, Inc."): self.assertIn(n, txt)
            self.assertNotIn("Plain Person", out.read_text())


class V1AndTolerance(unittest.TestCase):
    def test_v1_format_without_extra_columns(self):
        doc, _ = build_from((FIX / "directory_v1.csv").read_bytes())
        self.assertEqual(doc["format"], "v1")
        by = {r["name"]: r for r in doc["rows"]}
        self.assertEqual(by["Fixture Farm Supply"]["category"], ""); self.assertEqual(by["Fixture Farm Supply"]["link"], ""); self.assertEqual(by["Fixture Farm Supply"]["gq"], "town_centroid"); self.assertTrue(all("dlat" not in r for r in doc["rows"]))

    def test_notes_are_never_read_and_lists_come_from_the_url(self):
        t = csv_text(BASE + ["source_url", "notes"],
                     ["A Co", "Kimball", "SD", 43.747, -98.9566, "https://puc.sd.gov/commission/warehouse/Grain%20License%20Info.pdf", 'NOT BIDS; SD PUC list as of 10/23/2026; permit type F'],
                     ["B Co", "Bassett", "NE", 42.58, -99.54, "https://psc.nebraska.gov/sites/default/files/doc/2026-09-30%20Grain%20Warehouse%20List.pdf", "NE PSC license 1679"],
                     ["C Co", "Fargo", "ND", 46.8772, -96.7898, "https://lars.ndda.nd.gov/public/allLicenses/4/", "ND license 2085"])
        doc, _ = build_from(t); by = {r["name"]: r for r in doc["rows"]}
        self.assertEqual((by["A Co"]["src"], by["B Co"]["src"], by["C Co"]["src"]), (["SD"], ["NE"], ["ND"]))
        self.assertEqual(doc["sources"]["NE"]["date"], "")                                 # an NE list we do not know: no date is invented
        self.assertNotRegex(json.dumps(doc), r"permit|1679|2085|NOT BIDS")

    def test_extra_unknown_columns_and_bom_and_case(self):
        t = csv_text(["Name", "TOWN", "State", "Lat", "Lon", "phone", "future_column"], ["X Co", "Pierre", "SD", 44.37, -100.35, "605-555-0100", "?"])
        doc, _ = build_from(b"\xef\xbb\xbf" + t.encode())
        self.assertEqual(len(doc["rows"]), 1)
        self.assertNotIn("605-555", json.dumps(doc)); self.assertNotIn("phone", json.dumps(doc))      # unknown columns are never copied through

    def test_missing_required_column_is_an_error(self):
        with self.assertRaises(bd.DirectoryError): build_from(csv_text(["name", "town", "state", "lat"], ["X", "Pierre", "SD", 44.3]))
        with self.assertRaises(bd.DirectoryError): build_from(csv_text(BASE))                                  # no usable rows at all
        with self.assertRaises(bd.DirectoryError): bd.build(Path("/nonexistent/x.csv"), Path("/tmp/x.json"))
        self.assertEqual(bd.main(["--csv", "/nonexistent/x.csv", "--out", "/tmp/never.json"]), 1)

    def test_odd_values(self):
        t = csv_text(BASE + ["category", "geocode_quality", "bid_page_url"],
                     ["  Spaces  Co ", " Pierre ", " sd ", " 44.3683 ", " -100.351 ", "ELEVATOR", "Town Centroid", " https://example.com/x y"],      # space in link -> cleared
                     ["", "Pierre", "SD", 44.3, -100.3, "", "", ""],                                  # empty name
                     ["Nan Co", "Pierre", "SD", "nan", "inf", "", "", ""],
                     ["Lat Range Co", "Pierre", "SD", 144.3, -100.3, "", "", ""],
                     ["One Letter State Co", "Pierre", "S", 44.3, -100.3, "", "", ""],
                     ["Long Co " + "x" * 300, "Pierre", "SD", 44.3, -100.3, "", "", "ftp://example.com/file"],
                     ["", "", "", "", "", "", "", ""])
        doc, rep = build_from(t)
        self.assertEqual([r["name"][:10] for r in doc["rows"]], ["Long Co xx", "Spaces Co"])
        self.assertTrue(all(len(r["name"]) <= bd.NAME_MAX for r in doc["rows"]))
        sp = [r for r in doc["rows"] if r["name"] == "Spaces Co"][0]; self.assertEqual((sp["state"], sp["town"], sp["gq"], sp["link"]), ("SD", "Pierre", "town_centroid", ""))
        self.assertEqual(doc["cleared"]["bad_link"], 2); self.assertEqual(rep["read"], 6)                       # the all-blank line is not a row
        self.assertEqual(doc["dropped"]["bad_name"], 1); self.assertEqual(doc["dropped"]["bad_coords"], 2); self.assertEqual(doc["dropped"]["bad_state"], 1)


class Radius300(unittest.TestCase):
    def test_distance_recomputed_not_trusted(self):
        # Pierre SD is ~70 mi away; the CSV claims 5
        doc, _ = build_from(csv_text(BASE + ["miles_from_gann_valley"], ["P Co", "Pierre", "SD", 44.3683, -100.351, 5]))
        self.assertTrue(60 < doc["rows"][0]["mi"] < 80)

    def test_within_300_kept_just_over_tolerated_far_dropped(self):
        c = (config.CENTER_LAT, config.CENTER_LON)
        def point(miles):                                    # due north of the centre
            return c[0] + miles / 69.09, c[1]
        rows = [[f"M{m} Co", "Town", "ND", round(point(m)[0], 5), c[1]] for m in (299, 300.4, 301.0, 320)]
        doc, _ = build_from(csv_text(BASE, *rows)); names = [r["name"] for r in doc["rows"]]
        self.assertIn("M299 Co", names); self.assertIn("M300.4 Co", names)                  # rounding tolerance (the real list has two rows at 300.18/300.47)
        self.assertNotIn("M320 Co", names)
        self.assertEqual(doc["dropped"]["outside_radius"], 2)                                # 301.0 and 320 (301.0 is past the 1-mile tolerance)
        self.assertTrue(all(r["mi"] <= config.RADIUS_MILES + bd.ROUND_TOLERANCE_MILES for r in doc["rows"]))
        self.assertEqual(doc["center"], {"lat": config.CENTER_LAT, "lon": config.CENTER_LON, "radius_miles": config.RADIUS_MILES})


class CommittedData(unittest.TestCase):
    """The JSON that ships in the repo. These tests read ONLY the committed JSON: the source CSV is not in git and CI never has it."""
    @classmethod
    def setUpClass(cls):
        cls.json = json.loads((PUBLIC / "data" / "directory.json").read_text(encoding="utf-8"))

    def test_committed_json_validates(self):
        self.assertEqual(bd.validate_doc(self.json), [])
        self.assertEqual(bd.main(["--check", "--out", str(PUBLIC / "data" / "directory.json")]), 0)

    def test_output_has_only_the_allowed_fields_and_no_personal_or_price_data(self):
        allowed = {"id", "name", "town", "state", "lat", "lon", "dlat", "dlon", "mi", "category", "src", "link", "gq", "fl", "date"}
        for r in self.json["rows"]: self.assertLessEqual(set(r), allowed)
        raw = json.dumps(self.json["rows"])
        self.assertNotRegex(raw, r"\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}")                    # no phone numbers
        self.assertNotRegex(raw, r"[\w.+-]+@[\w-]+\.[\w.]+")                             # no email addresses
        self.assertNotRegex(raw.lower(), r"licen[sc]e|permit|bid_high|\$\d|\bnotes?\b|crops")   # no licence numbers/classes, permit types, notes or prices
        self.assertNotRegex(raw, r"(?i)\bcount(y|ies)\b(?! farmers| co| coop| elevator| grain)")   # no county column or note ("... County Farmers Coop" is only part of a business name)
        for r in self.json["rows"]:
            self.assertNotRegex(" ".join(str(r.get(f, "")) for f in ("town", "category", "gq", "link")), r"(?i)count(y|ies)")
        self.assertEqual(set(self.json["sources"]), {"SD", "ND", "NE-LOC", "NE-DLR", "IA", "MN"})
        self.assertEqual({k: (v["date"], v["kind"]) for k, v in self.json["sources"].items()},
                         {"SD": ("2026-10-23", "as of"), "ND": ("2026-10-28", "fetched"), "NE-LOC": ("2026-10-28", "as of"), "NE-DLR": ("2026-09-29", "as of"), "IA": ("2026-10-28", "fetched"), "MN": ("2026-10-28", "fetched")})

    def test_no_individuals_every_name_has_a_business_marker(self):
        for r in self.json["rows"]: self.assertTrue(bd.is_business(r["name"])[0], r["name"])
        self.assertGreater(self.json["dropped"]["not_business"], 0)                       # the rule did drop something on the real list

    def test_real_list_quality_gate(self):
        names = [r["name"] for r in self.json["rows"]]
        for bad in ("NAME", ""): self.assertNotIn(bad, names)
        self.assertFalse([r for r in self.json["rows"] if re.search(r"\d", r["town"])])
        self.assertGreater(self.json["count"], 700)
        self.assertEqual(self.json["count"], len({(bd.norm_name(r["name"]), r["town"].upper(), r["state"]) for r in self.json["rows"]}))
        self.assertTrue(all(r["mi"] <= 301 for r in self.json["rows"]))
        self.assertTrue(all("dlat" in r and "dlon" in r for r in self.json["rows"]), "every real row has display coordinates (the ring fallback is not needed)")
        self.assertTrue(all(r["src"] for r in self.json["rows"]))

    def test_display_points_are_near_true_points_and_colocated_rows_are_separated(self):
        for r in self.json["rows"]: self.assertLessEqual(bd.haversine(r["lat"], r["lon"], r["dlat"], r["dlon"]), 2.0, r["name"])
        pts = [(r["dlat"], r["dlon"]) for r in self.json["rows"]]
        self.assertEqual(len(set(pts)), len(pts), "no two listings share a drawn point")

    def test_sensitive_strings_not_in_committed_data(self):
        raw = json.dumps(self.json["rows"])
        for pat in (r"licen[sc]e\s*(no|number|#)?\s*[:#]?\s*\d", r"\b[A-Z]{1,3}-\d{3,}\b", r"(?i)roving|\bbroker\b"): self.assertNotRegex(raw, pat)


@unittest.skipUnless(bd.DEFAULT_CSV.is_file(), "local source CSV (data/source/, git-ignored) not present: staleness check skipped")
class LocalSourceFreshness(unittest.TestCase):
    def test_committed_json_matches_local_source_csv(self):
        doc, _ = build_from(bd.DEFAULT_CSV.read_bytes())
        self.assertEqual(doc, json.loads((PUBLIC / "data" / "directory.json").read_text(encoding="utf-8")), "directory.json is stale: python3 -m ingest.build_directory --csv ...")


class SourceCsvStaysOutOfGit(unittest.TestCase):
    def test_gitignored_and_untracked(self):
        gi = (ROOT / ".gitignore").read_text()
        self.assertIn("data/source/", gi); self.assertIn("data/elevator-directory*.csv", gi)
        r = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
        if r.returncode == 0:
            tracked = [f for f in r.stdout.splitlines() if f.endswith(".csv")]
            self.assertTrue(all(f.startswith("ingest/tests/fixtures/") for f in tracked), tracked)      # only the synthetic fixtures
    def test_fixtures_are_synthetic(self):
        for f in FIX.glob("*.csv"):
            names = [row["name"] for row in csv.DictReader(f.open(encoding="utf-8-sig"))]
            self.assertTrue(len(names) > 5 and all(not n or re.search(r"(?i)fixture|spaced|nd date|^name$|plain|bad |creds|zero|no lat|far away|not found|coarse geo|digits|odd display|unknown source|indiv|two lists|mn undated|ne |ia co|ks far|john q", n) for n in names), f.name)


class BuildScriptWiring(unittest.TestCase):
    def test_build_dist_validates_the_json_and_needs_no_csv(self):
        sh = (ROOT / "build_dist.sh").read_text()
        self.assertIn("ingest.build_directory --check", sh)
        code = "\n".join(l for l in sh.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("--csv", code); self.assertNotRegex(code, r"\.csv|elevator-directory|data/source")        # no executable line touches the source CSV
        self.assertLess(sh.index("ingest.build_directory --check"), sh.index("cp -r public/."))        # validated before dist is copied
        ci = (ROOT / "deploy" / "ci_check.py").read_text(); self.assertIn("data/directory.json", ci)

    def test_check_rejects_bad_json(self):
        good = json.loads((PUBLIC / "data" / "directory.json").read_text())
        def run(mod):
            d = json.loads(json.dumps(good)); mod(d)
            with tempfile.TemporaryDirectory() as t:
                p = Path(t) / "d.json"; p.write_text(json.dumps(d)); return bd.main(["--check", "--out", str(p)])
        self.assertEqual(run(lambda d: None), 0)
        self.assertEqual(run(lambda d: d.update(schema="x")), 1)
        self.assertEqual(run(lambda d: d.update(rows=[], count=0)), 1)
        self.assertEqual(run(lambda d: d["rows"][0].update(notes="SECRET")), 1)
        self.assertEqual(run(lambda d: d["rows"][0].update(name="John Q Public")), 1)           # an individual's name
        self.assertEqual(run(lambda d: d["rows"][0].update(link="javascript:alert(1)")), 1)
        self.assertEqual(run(lambda d: d["rows"][0].update(src=["XX"])), 1)
        self.assertEqual(bd.main(["--check", "--out", "/nonexistent/d.json"]), 1)

    def test_build_cli_without_csv_fails_clearly_and_check_runs_without_it(self):
        env = dict(os.environ); 
        r = subprocess.run([sys.executable, "-m", "ingest.build_directory", "--csv", "/nonexistent/x.csv", "--out", "/tmp/never.json"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("not in git", r.stderr)


if __name__ == "__main__":
    unittest.main()
