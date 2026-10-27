"""Tests for staleness, expiry, grade/freight separation, futures switch, failure handling, skipped rows, static guards."""
import datetime, json, os, re, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ingest import config, db, export_json, ingest, parse_pdf

FIX = Path(__file__).parent / "fixtures"
PUBLIC = Path(__file__).resolve().parents[2] / "public"
REPORTS = {3186: "SD", 3878: "ND", 3225: "NE", 3049: "MN", 2850: "IA", 2887: None}

def parsed(slug):
    txt = parse_pdf.pdf_to_text((FIX / f"ams_{slug}_20261026.pdf").read_bytes())
    return parse_pdf.parse_report(txt, slug, "t", REPORTS[slug])

def fresh_db(tmp):
    return db.connect(Path(tmp) / "t.db")

def load(con, slugs=(3186, 3878), date=None, drop=lambda b: False, posted="2026-10-26T14:28:06-05:00"):
    for slug in slugs:
        p = parsed(slug)
        bids = [dict(b, report_date=date or b["report_date"]) for b in p["bids"] if not drop(b)]
        futs = [dict(f, report_date=date or p["report_date"], source_report=f"AMS_{slug}") for f in p["futures"]]
        ingest.upsert(con, bids, futs, "pdf", REPORTS[slug], posted_at=posted, status=p["status"])
    con.commit()

def do_export(con, tmp, today, sample=False):
    out = Path(tmp) / "out"
    export_json.export(con, out, sample=sample, today=datetime.date.fromisoformat(today))
    return (json.loads((out / "latest.json").read_text()), json.loads((out / "meta.json").read_text()),
            json.loads((out / "futures.json").read_text()))

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.con = fresh_db(self.tmp.name)
        os.environ.pop("GRAIN_FUTURES_DISPLAY", None)

    def test_staleness_is_against_today_not_newest_data(self):
        load(self.con)
        latest, meta, _ = do_export(self.con, self.tmp.name, "2026-10-30")
        self.assertTrue(latest and all(r["age_days"] == 4 for r in latest))      # a dead ingest no longer looks "fresh"
        self.assertEqual(meta["export_today"], "2026-10-30")

    def test_rows_expire_after_limit(self):
        load(self.con)
        latest, meta, _ = do_export(self.con, self.tmp.name, "2026-11-10")
        self.assertEqual(latest, [])
        self.assertTrue(any("expired" in d for d in meta["dropped_rows"]))

    def test_dropped_region_does_not_linger(self):
        load(self.con, slugs=(3186,), date="2026-10-26")
        load(self.con, slugs=(3186,), date="2026-10-27", drop=lambda b: b["location"] == "North Central")
        latest, meta, _ = do_export(self.con, self.tmp.name, "2026-10-27")
        self.assertFalse(any(r["location"] == "SD North Central" for r in latest))
        self.assertTrue(any(r["location"] == "SD Southeast" and r["age_days"] == 0 for r in latest))
        self.assertTrue(any("North Central" in d for d in meta["dropped_rows"]))

    def test_grades_and_freight_never_merge(self):
        load(self.con, slugs=(3186, 3878))
        latest, _, _ = do_export(self.con, self.tmp.name, "2026-10-26")
        soy = {(r["grade"], r["freight"]): r["variant"] for r in latest if r["commodity"] == "soybeans"}
        self.assertIn(("US #1 Soybeans", "DLVD-T"), soy); self.assertIn(("US #2 Soybeans", "FOB-T"), soy)
        self.assertNotEqual(soy[("US #1 Soybeans", "DLVD-T")], soy[("US #2 Soybeans", "FOB-T")])
        corn = {r["freight"]: r["variant"] for r in latest if r["commodity"] == "corn"}   # same grade, different freight term
        self.assertEqual(len(set(corn.values())), 2)
        for r in latest:
            self.assertIn(r["freight"], r["variant"]); self.assertIn(r["grade"], r["variant"]); self.assertTrue(r["freight_label"])
        hrs = {r["variant"] for r in latest if r["commodity"] == "spring_wheat"}
        self.assertEqual(len(hrs), 2)                                     # "HRS" (SD) and "Milling HRS" (ND) stay apart

    def test_labels(self):
        self.assertEqual(export_json.freight_label("DLVD-T"), "Delivered, truck (DLVD-T)")
        self.assertEqual(export_json.freight_label("FOB-T"), "FOB, truck (FOB-T)")
        self.assertEqual(export_json.basis_ref("corn", "Dec"), "CBOT Dec futures")
        self.assertEqual(export_json.basis_ref("spring_wheat", "Dec"), "MGE Dec futures")
        self.assertEqual(export_json.basis_ref("winter_wheat", "Dec"), "KCBT Dec futures")
        self.assertEqual(export_json.basis_ref("sunflowers", ""), "")

    def test_precision_only_town_for_sunflowers(self):
        load(self.con, slugs=(3186, 2887))
        latest, _, _ = do_export(self.con, self.tmp.name, "2026-10-26")
        for r in latest:
            self.assertEqual(r["precision"], "town" if r["commodity"] == "sunflowers" else "region", r["location"])

    def test_futures_switch(self):
        load(self.con)
        self.assertEqual(config.futures_display(), "full")                # default
        _, meta, fut = do_export(self.con, self.tmp.name, "2026-10-26")
        self.assertEqual(meta["futures_display"], "full"); self.assertGreater(len(fut), 0)
        with mock.patch.dict(os.environ, {"GRAIN_FUTURES_DISPLAY": "basis_only"}):
            _, meta, fut = do_export(self.con, self.tmp.name, "2026-10-26")
        self.assertEqual(meta["futures_display"], "basis_only"); self.assertEqual(fut, [])   # nothing leaks into futures.json
        with mock.patch.dict(os.environ, {"GRAIN_FUTURES_DISPLAY": "bogus"}):
            with self.assertRaises(ValueError):
                config.futures_display()

    def test_frontend_config_default(self):
        cfg = (PUBLIC / "config.js").read_text()
        self.assertRegex(cfg, r"FUTURES_DISPLAY:\s*'full'")
        self.assertRegex(cfg, r"ALLOW_SAMPLE:\s*false")
        self.assertRegex(cfg, r"GOOGLE_MAPS_API_KEY:\s*''")          # never a committed key
        self.assertIn("TILE_URL", cfg); self.assertRegex(cfg, r"DEV_OSM_TILES_ON_LOCALHOST:\s*true")
        self.assertNotRegex(cfg, r"AIza[0-9A-Za-z_-]{20,}")

    def test_iowa_unplaced_row_is_stored_and_exported(self):
        p = parsed(2850)
        self.assertEqual(len(p["skipped"]), 1)
        self.assertEqual(ingest.store_skipped(self.con, p["skipped"]), 1)
        load(self.con, slugs=(2850,))
        _, meta, _ = do_export(self.con, self.tmp.name, "2026-10-26")
        sk = meta["skipped_rows"]
        self.assertEqual((sk[0]["source_report"], sk[0]["commodity"], sk[0]["section"], sk[0]["bid_high"]), ("AMS_2850", "soybeans", "Mills and Processors", 12.1625))

class RunTests(unittest.TestCase):
    def run_with(self, fail_slug=None):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        def fake_fetch(slug, timeout=60):
            if slug == fail_slug:
                return b"%PDF-1.4 not a real report"
            return (FIX / f"ams_{slug}_20261026.pdf").read_bytes()
        exported = []
        with mock.patch.object(db, "DB_PATH", Path(tmp.name) / "r.db"), mock.patch.object(parse_pdf, "fetch_pdf", fake_fetch), \
             mock.patch.object(parse_pdf, "fetch_posted_at", lambda *a, **k: "2026-10-26T14:00:00-05:00"), \
             mock.patch("ingest.export_json.export", lambda *a, **k: exported.append(1)):
            rc = ingest.run("pdf", None, 0, True)
            con = db.connect(Path(tmp.name) / "r.db")
            runs = con.execute("SELECT ok FROM ingest_runs").fetchall()
            skipped = con.execute("SELECT COUNT(*) FROM skipped_rows").fetchone()[0]
        return rc, exported, [r[0] for r in runs], skipped

    def test_success_exports(self):
        rc, exported, oks, skipped = self.run_with()
        self.assertEqual(rc, 0); self.assertEqual(exported, [1]); self.assertEqual(oks, [1]); self.assertEqual(skipped, 1)

    def test_parse_failure_stops_export(self):
        rc, exported, oks, _ = self.run_with(fail_slug=3878)
        self.assertEqual(rc, 1); self.assertEqual(exported, []); self.assertEqual(oks, [0])

class StaticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.con = fresh_db(self.tmp.name)
        os.environ.pop("GRAIN_FUTURES_DISPLAY", None)

    def test_license_texts_shipped(self):
        self.assertIn("BSD 2-Clause", (PUBLIC / "vendor" / "LICENSE-leaflet.txt").read_text())
        self.assertIn("MIT License", (PUBLIC / "vendor" / "LICENSE-chartjs.txt").read_text())

    def test_service_worker_only_caches_good_responses(self):
        sw = (PUBLIC / "sw.js").read_text()
        self.assertIn("r.ok && r.status === 200", sw)
        self.assertNotRegex(sw, r"fetch\(req\)\.then\(r => \{ const cp")  # old unconditional put

    def test_outside_margin_bids_listed_not_pinned(self):
        load(self.con, slugs=(3878,))
        out = Path(self.tmp.name) / "out"
        export_json.export(self.con, out, today=datetime.date(2026, 10, 27))
        outside = json.loads((out / "outside.json").read_text())
        latest = json.loads((out / "latest.json").read_text())
        names = {o["location"] for o in outside}
        self.assertTrue(any("Northeast" in n for n in names) and any("North Central" in n for n in names), names)
        self.assertTrue(all(300 < o["distance_mi"] <= config.MARGIN_MILES and o["approximate"] for o in outside))
        self.assertTrue(all(o["variant"] and o["freight_label"] for o in outside))
        self.assertFalse({o["location"] for o in outside} & {r["location"] for r in latest})   # never pinned/ranked
        self.assertFalse([r for r in latest if r["distance_mi"] > 300])

    def test_row_count_guard_blocks_export_and_keeps_last_good(self):
        load(self.con, slugs=(3186, 3878, 3225))
        out = Path(self.tmp.name) / "out"
        export_json.export(self.con, out, today=datetime.date(2026, 10, 27))
        good = (out / "latest.json").read_text()
        # next day: layout change drops most rows (only ~25% parse)
        keep = iter(range(10 ** 6))
        load(self.con, slugs=(3186, 3878, 3225), date="2026-10-27", drop=lambda b: next(keep) % 4 != 0)
        with self.assertRaises(export_json.ExportGuardError):
            export_json.export(self.con, out, today=datetime.date(2026, 10, 27))
        self.assertEqual(good, (out / "latest.json").read_text())
        export_json.export(self.con, out, today=datetime.date(2026, 10, 27), accept_row_drop=True)   # explicit override works
        self.assertNotEqual(good, (out / "latest.json").read_text())

    def test_row_guard_fails_the_ingest_run(self):
        out = Path(self.tmp.name) / "data"; out.mkdir()
        (out / "latest.json").write_text(json.dumps([{}] * 1000))
        with mock.patch.object(export_json.export.__globals__["config"], "ROOT", Path(self.tmp.name)), \
             mock.patch.object(ingest.db, "connect", return_value=self.con), \
             mock.patch.object(ingest.parse_pdf, "fetch_pdf", side_effect=lambda slug: (FIX / f"ams_{slug}_20261026.pdf").read_bytes()), \
             mock.patch.object(ingest.parse_pdf, "fetch_posted_at", return_value=None):
            (Path(self.tmp.name) / "public").mkdir(); (Path(self.tmp.name) / "public" / "data").mkdir()
            (Path(self.tmp.name) / "public" / "data" / "latest.json").write_text(json.dumps([{}] * 1000))
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop(config.API_KEY_ENV, None)
                rc = ingest.run("pdf", None, 0, True)
        self.assertEqual(rc, 1)
        self.assertEqual(self.con.execute("SELECT ok FROM ingest_runs ORDER BY id DESC LIMIT 1").fetchone()[0], 0)

    def test_times_carry_central_zone(self):
        load(self.con, slugs=(3186,))
        self.con.execute("INSERT INTO ingest_runs(started_at,finished_at,source,summary,ok) VALUES ('2026-10-27T13:11:00','2026-10-27T13:11:17','pdf','',1)")
        _, meta, _ = do_export(self.con, self.tmp.name, "2026-10-27")
        self.assertTrue(meta["last_ingest_ok_at"].endswith("-05:00"), meta["last_ingest_ok_at"])
        self.assertTrue(meta["generated_at"][-6:] in ("-05:00", "-06:00"))
        self.assertEqual(meta["time_zone"], "America/Chicago")

    def test_skipped_row_carries_variant_for_best_card(self):
        load(self.con, slugs=(2850,))
        ingest.store_skipped(self.con, parsed(2850)["skipped"]); self.con.commit()
        _, meta, _ = do_export(self.con, self.tmp.name, "2026-10-27")
        self.assertEqual(len(meta["skipped_rows"]), 1)
        self.assertIn("US #1 Soybeans", meta["skipped_rows"][0]["variant"])

    def test_wording_manifest_and_sample_not_in_deploy(self):
        man = (PUBLIC / "manifest.webmanifest").read_text()
        self.assertNotRegex(man, r"(?i)end-of-day")
        self.assertIn("2 to 4 pm Central", man)
        root = PUBLIC.parent
        import subprocess
        tracked = subprocess.run(["git", "ls-files", "public/data-sample"], cwd=root, capture_output=True, text=True).stdout
        self.assertEqual(tracked.strip(), "")
        self.assertIn("public/data-sample/", (root / ".gitignore").read_text())
        self.assertIn("data-sample", (root / "build_dist.sh").read_text())

    def test_wording(self):
        for f in ("index.html", "app.js"):
            t = (PUBLIC / f).read_text()
            self.assertNotRegex(t, r"(?i)end-of-day", f)
        html = (PUBLIC / "index.html").read_text()
        for needle in ("2 to 4 pm Central", "voluntary", "Calculated by this app", "straight-line", "Call your elevator to confirm", "CBOT for corn and soybeans"):
            self.assertIn(needle, html)
        self.assertNotRegex((PUBLIC / "app.js").read_text() + html, r"(?i)profit")

if __name__ == "__main__":
    unittest.main()
