"""Partial publish: when one of the six USDA reports fails, the others are still exported, the failed report is marked unavailable
(none of its bids shown), the run still ends in failure (exit code 3 -> failed partial-check job -> refresh-failure alert), and the
all-or-nothing fail-safe is unchanged without --allow-partial or when every report fails."""
import datetime, json, os, re, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ingest import config, db, export_json, ingest, parse_pdf
from ingest.tests.test_export import FIX, load

WF = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
CODE = "\n".join(re.sub(r"\s+#.*$", "", l) for l in WF.splitlines() if not l.lstrip().startswith("#"))
ALL = [r["slug"] for r in config.REPORTS]


def job_block(name):
    m = re.search(rf"^  {name}:\n(.*?)(?=^  \w[\w-]*:\n|\Z)", CODE, re.S | re.M)
    assert m, name
    return m.group(1)


class RunPartialTests(unittest.TestCase):
    def run_with(self, fail=(), allow_partial=True):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        def fake_fetch(slug, timeout=60):
            return b"%PDF-1.4 not a real report" if slug in fail else (FIX / f"ams_{slug}_20261026.pdf").read_bytes()
        calls = []
        with mock.patch.object(db, "DB_PATH", Path(tmp.name) / "r.db"), mock.patch.object(parse_pdf, "fetch_pdf", fake_fetch), \
             mock.patch.object(parse_pdf, "fetch_posted_at", lambda *a, **k: "2026-10-26T14:00:00-05:00"), \
             mock.patch("ingest.export_json.export", lambda *a, **k: calls.append(k)), \
             mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(config.API_KEY_ENV, None)
            res = ingest.run_detailed("pdf", None, 0, True, allow_partial=allow_partial)
            oks = [r[0] for r in db.connect(Path(tmp.name) / "r.db").execute("SELECT ok FROM ingest_runs")]
        return res, calls, oks

    def test_one_failed_report_still_exports_the_others(self):
        res, calls, oks = self.run_with(fail=(3049,))
        self.assertEqual(res["failures"], 1); self.assertTrue(res["exported"])
        self.assertEqual(list(res["unavailable"]), ["AMS_3049"])
        self.assertEqual(len(calls), 1); self.assertEqual(list(calls[0]["unavailable"]), ["AMS_3049"])
        self.assertEqual(oks, [1])                       # the data was updated (5 of 6 reports)

    def test_without_allow_partial_nothing_is_exported(self):
        res, calls, oks = self.run_with(fail=(3049,), allow_partial=False)
        self.assertEqual(calls, []); self.assertFalse(res["exported"]); self.assertEqual(res["unavailable"], {}); self.assertEqual(oks, [0])
        self.assertEqual(ingest.run.__defaults__[-1], False)          # the old all-or-nothing behaviour is the default

    def test_all_reports_failed_is_still_a_hard_stop(self):
        res, calls, oks = self.run_with(fail=tuple(ALL))
        self.assertEqual(res["failures"], len(ALL)); self.assertEqual(calls, []); self.assertFalse(res["exported"]); self.assertEqual(oks, [0])

    def test_exit_codes(self):
        def code(res):
            with mock.patch.object(ingest, "run_detailed", return_value=res), mock.patch.object(sys, "argv", ["ingest", "--export", "--allow-partial"]):
                with self.assertRaises(SystemExit) as cm:
                    ingest.main()
            return cm.exception.code
        self.assertEqual(code({"failures": 0, "exported": True, "unavailable": {}}), 0)
        self.assertEqual(code({"failures": 1, "exported": True, "unavailable": {"AMS_3049": "x"}}), ingest.EXIT_PARTIAL)
        self.assertEqual(code({"failures": 1, "exported": False, "unavailable": {}}), 1)
        self.assertEqual(ingest.EXIT_PARTIAL, 3)


class ExportUnavailableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.con = db.connect(Path(self.tmp.name) / "t.db")
        os.environ.pop("GRAIN_FUTURES_DISPLAY", None)
        self.out = Path(self.tmp.name) / "out"

    def export(self, **kw):
        export_json.export(self.con, self.out, today=datetime.date(2026, 10, 27), **kw)
        return json.loads((self.out / "latest.json").read_text()), json.loads((self.out / "meta.json").read_text())

    def test_failed_report_rows_are_not_shown_and_market_is_marked_unavailable(self):
        load(self.con, slugs=(3186, 3878, 3225, 3049))
        latest, meta = self.export(unavailable={"AMS_3049": "report 3049: no 'Grain Report for' line"})
        self.assertTrue(latest); self.assertFalse([r for r in latest if r["source_report"] == "AMS_3049"])
        self.assertTrue(any(r["source_report"] == "AMS_3186" for r in latest))
        u = meta["unavailable_reports"]
        self.assertEqual([x["source_report"] for x in u], ["AMS_3049"])
        self.assertEqual(u[0]["label"], "MN (3049)"); self.assertIn("Grain Report", u[0]["reason"]); self.assertEqual(u[0]["last_report_date"], "2026-10-26")
        self.assertNotIn("AMS_3049", meta["report_times"])           # so the page does not call its bids "Nd old" (they are not shown at all)
        self.assertTrue(any("unavailable" in d for d in meta["dropped_rows"]))
        self.assertIn("USDA AMS", meta["credit"])

    def test_normal_export_has_no_unavailable_reports(self):
        load(self.con, slugs=(3186,))
        _, meta = self.export()
        self.assertEqual(meta["unavailable_reports"], [])

    def test_row_guard_compares_only_reports_that_came_in(self):
        load(self.con, slugs=(3186, 3878, 3225))
        latest, _ = self.export()                                   # last good export: all three reports
        n_sd = sum(r["source_report"] == "AMS_3186" for r in latest)
        self.assertLess(len(latest) - n_sd, config.MIN_ROW_RATIO * len(latest))   # dropping SD alone would trip the old guard
        latest2, _ = self.export(unavailable={"AMS_3186": "x"})
        self.assertEqual(len(latest2), len(latest) - n_sd)
        keep = iter(range(10 ** 6))                                 # ...but a real row collapse in the reports that did come in still trips it
        load(self.con, slugs=(3878, 3225), date="2026-10-27", drop=lambda b: next(keep) % 4 != 0)
        before = (self.out / "latest.json").read_text()
        with self.assertRaises(export_json.ExportGuardError):
            self.export(unavailable={"AMS_3186": "x"})
        self.assertEqual(before, (self.out / "latest.json").read_text())


class WorkflowPartialTests(unittest.TestCase):
    def test_ingest_step_allows_partial_and_turns_exit_3_into_an_output(self):
        b = job_block("build")
        self.assertIn("--allow-partial", b)
        self.assertRegex(b, r'if \[ "\$rc" = "3" \]; then\n\s+echo "partial=true" >> "\$GITHUB_OUTPUT"')
        self.assertIn("ingest_partial: ${{ steps.ingest.outputs.partial }}", b)
        self.assertIn('exit "$rc"', b)

    def test_partial_check_fails_the_run_after_deploy_and_feeds_the_alert(self):
        j = job_block("partial-check")
        self.assertIn("needs: [build, deploy]", j)
        self.assertIn("needs.build.outputs.ingest_partial == 'true'", j)
        self.assertIn("permissions: {}", j); self.assertIn("exit 1", j)
        a = job_block("refresh-alert")
        self.assertIn("needs: [build, deploy, partial-check]", a)
        self.assertIn("PARTIAL_RESULT: ${{ needs.partial-check.result }}", a)
        self.assertNotRegex(job_block("deploy"), r"\bif:")          # deploy still runs only on a successful build

    def test_alert_script_reports_a_partial_publish(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "calls"; gh = Path(d) / "gh"
            gh.write_text(f'#!/bin/sh\nprintf "%s" "$*" | tr "\\n" " " >> "{log}"; echo >> "{log}"\n'); gh.chmod(0o755)
            env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", BUILD_RESULT="success", DEPLOY_RESULT="success", PARTIAL_RESULT="failure",
                       INGEST_FAILED="AMS_3049 FAILED: bad", RUN_URL="u", EVENT_NAME="schedule")
            r = subprocess.run(["bash", str(ROOT / "deploy" / "refresh_alert.sh")], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            calls = log.read_text().splitlines()
        self.assertTrue(any(c.startswith("issue create") and "Partial publish" in c and "AMS_3049" in c for c in calls), calls)
        self.assertFalse(any(c.startswith("issue close") for c in calls))


class PageTests(unittest.TestCase):
    def test_page_shows_unavailable_reports(self):
        app = (ROOT / "public" / "app.js").read_text()
        self.assertIn("m.unavailable_reports", app); self.assertIn("Unavailable:", app)


if __name__ == "__main__":
    unittest.main()
