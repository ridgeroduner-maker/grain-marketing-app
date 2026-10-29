"""The GitHub Pages workflow is a FILE ONLY (never run here). These tests lock its safety properties and exercise the helper gate
(deploy/ci_check.py) and the pinned-download script. No YAML library is used on purpose (stdlib only): checks are text-based."""
import datetime, json, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy"))
import ci_check
WF = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
CODE = "\n".join(re.sub(r"\s+#.*$", "", l) for l in WF.splitlines() if not l.lstrip().startswith("#"))     # comments dropped (no '#' inside any value)
OFFICIAL = {"actions/checkout", "actions/setup-python", "actions/configure-pages", "actions/upload-pages-artifact", "actions/deploy-pages", "actions/cache"}


def job_block(name):
    m = re.search(rf"^  {name}:\n(.*?)(?=^  \w[\w-]*:\n|\Z)", CODE, re.S | re.M)
    assert m, name
    return m.group(1)


class WorkflowFileTests(unittest.TestCase):
    def test_only_official_actions_pinned_to_full_sha(self):
        uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", CODE, re.M)
        self.assertGreaterEqual(len(uses), 6)
        for u in uses:
            name, _, ref = u.partition("@")
            self.assertIn(name, OFFICIAL, u)
            self.assertRegex(ref, r"^[0-9a-f]{40}$", f"{u} must be pinned to a full commit SHA")
        for need in ("configure-pages", "upload-pages-artifact", "deploy-pages"):     # the official Pages actions
            self.assertTrue(any(need in u for u in uses), need)
        self.assertTrue(all(re.search(re.escape(u) + r"\s+# v\d", WF) for u in uses), "each pin needs a '# vX.Y.Z' comment")

    def test_triggers_never_include_build_v1_and_schedule_is_utc_after_4pm_central(self):
        self.assertNotIn("pull_request", CODE)
        on = re.search(r"^on:\n(.*?)(?=^\w)", CODE, re.S | re.M).group(1)
        self.assertIn("workflow_dispatch", on)
        self.assertRegex(on, r"push:\s*\n\s*branches:\s*\[main\]")
        self.assertNotIn("build/v1", on)
        crons = re.findall(r"cron:\s*'([^']+)'", on)
        self.assertEqual(len(crons), 2, "an evening run and a later catch-up run")
        for c in crons:
            minute, hour, *_ = c.split()
            self.assertNotEqual(minute, "0", "avoid the top of the hour (GitHub delays/drops those)")
        h1, h2 = (int(c.split()[1]) for c in crons)
        for h, label in ((h1, "evening"), (h2, "later")):
            for off in (5, 6):                                  # CDT / CST
                local = (h - off) % 24
                self.assertTrue(17 <= local <= 21 or (h == h2 and local >= 20), f"{label} run at {h}:xx UTC = {local}:xx local (UTC-{off}) must be after 4 pm Central")
        self.assertLess((h1 - 6) % 24, (h2 - 6) % 24)           # later run really is later in the evening
        self.assertIn("1-5", crons[0]); self.assertIn("2-6", crons[1])        # second run's UTC date has rolled over

    def test_least_privilege_no_secrets(self):
        self.assertRegex(CODE, r"(?m)^permissions:\n  contents: read\n", "workflow-level default is read-only")
        self.assertNotIn("write-all", CODE)
        self.assertNotIn("secrets.", CODE)
        self.assertNotIn("pull_request_target", CODE)
        build = job_block("build")
        self.assertNotRegex(build, r"\bpermissions:")      # build job inherits contents: read only
        self.assertNotRegex(build, r"(pages|id-token):\s*write")
        dep = job_block("deploy")
        self.assertIn("pages: write", dep); self.assertIn("id-token: write", dep)
        self.assertNotIn("contents: write", CODE)
        self.assertIn("needs: build", dep)
        self.assertRegex(dep, r"environment:\s*\n\s*name: github-pages")
        self.assertIn("persist-credentials: false", build)

    def test_does_not_enable_pages_and_ships_nojekyll(self):
        self.assertNotIn("enablement", CODE)
        self.assertRegex(CODE, r"upload-pages-artifact@[0-9a-f]{40}.*?\n\s+with:\n(?:\s+.*\n)*?\s+include-hidden-files: true", )
        self.assertRegex(CODE, r"path: dist\b")

    def test_failsafe_ordering_and_no_continue_on_error_on_data_steps(self):
        i_ingest = CODE.index("python3 -m ingest.ingest"); i_chk = CODE.index("ci_check.py data")
        i_dist = CODE.index("./build_dist.sh"); i_chkd = CODE.index("ci_check.py dist"); i_up = CODE.index("upload-pages-artifact@")
        self.assertTrue(i_ingest < i_chk < i_dist < i_chkd < i_up)
        self.assertLess(CODE.index("unittest discover"), i_ingest, "tests gate the publish")
        self.assertIn("--source pdf", CODE)                      # keyless path
        for m in re.finditer(r"continue-on-error", CODE):
            before = CODE[:m.start()].rsplit("- name:", 1)[-1]
            self.assertIn("map tiles", before.lower(), "only the optional tile build may continue on error")
        self.assertNotIn("--accept-row-drop\n", CODE)
        self.assertRegex(CODE, r"inputs\.accept_row_drop")        # only a human, via manual dispatch, can accept a row drop
        self.assertNotIn("cache-hit != 'true' ||", CODE)
        self.assertNotRegex(CODE, r"git (push|commit)")           # nothing is written back to the repo

    def test_data_cache_saved_only_by_default_post_step(self):
        self.assertRegex(CODE, r"actions/cache@[0-9a-f]{40}\s*\n\s+with:\n\s+path: data/grain\.db")
        self.assertNotIn("cache/save", CODE)                      # default cache saves only if the job succeeds

    def test_concurrency_does_not_cancel_a_deploy(self):
        self.assertRegex(CODE, r"concurrency:\n  group: pages\n  cancel-in-progress: false")


class HelperScriptTests(unittest.TestCase):
    def test_install_pmtiles_is_pinned_and_verifies_checksum(self):
        s = (ROOT / "deploy" / "install_pmtiles.sh").read_text()
        self.assertRegex(s, r'VERSION="\d+\.\d+\.\d+"')
        self.assertRegex(s, r'SHA256="[0-9a-f]{64}"')
        self.assertIn("sha256sum -c", s)
        self.assertIn("releases/download/v${VERSION}", s)
        self.assertNotIn("latest", s.replace("# ", ""))
        self.assertTrue((ROOT / "deploy" / "install_pmtiles.sh").stat().st_mode & 0o100)
        self.assertIn("deploy/install_pmtiles.sh", WF)
        self.assertIn('PMTILES_BIN="$RUNNER_TEMP/bin/pmtiles" ./build_tiles.sh', WF)
        self.assertIn("PMTILES_BIN", (ROOT / "build_tiles.sh").read_text())

    def test_install_pmtiles_refuses_a_bad_checksum_before_installing(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "bin"; fake.mkdir()
            (fake / "curl").write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do [ \"$1\" = -o ] && out=$2; shift; done\necho not-a-real-archive > \"$out\"\n")
            (fake / "curl").chmod(0o755)
            env = {"PATH": f"{fake}:/usr/bin:/bin"}
            if subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip() != "x86_64":
                self.skipTest("script is Linux x86_64 only")
            r = subprocess.run(["bash", str(ROOT / "deploy" / "install_pmtiles.sh"), str(Path(d) / "out")], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 1); self.assertIn("checksum mismatch", r.stdout + r.stderr)
            self.assertFalse((Path(d) / "out" / "pmtiles").exists())

    def test_audit_script_is_read_only(self):
        s = (ROOT / "deploy" / "audit_repo.sh").read_text()
        code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
        for forbidden in ("git push", "git commit", "git remote", "gh repo", "gh api", "curl ", "rm -", "git filter"):
            self.assertNotIn(forbidden, code)


def row(**kw):
    r = dict(commodity="corn", location="Sioux Falls, SD", variant="", bid_low=4.1, bid_high=4.2, unit="$/Bu", report_date="2026-10-28",
             source_report="AMS_3186", basis_low=-30, basis_high=-20, basis_low_month="Dec", basis_high_month="Dec", basis_ref_low="x",
             basis_ref_high="x", distance_mi=10)
    r.update(kw); return r


class CiCheckTests(unittest.TestCase):
    TODAY = datetime.date(2026, 10, 29)

    def make(self, rows=None, meta=None, n=40):
        d = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, d, True)
        (d / "latest.json").write_text(json.dumps(rows if rows is not None else [row() for _ in range(n)]))
        m = {"latest_report_date": "2026-10-28", "last_ingest_ok_at": "2026-10-28T18:00:00-05:00", "sample": False}; m.update(meta or {})
        (d / "meta.json").write_text(json.dumps(m))
        for n_ in ("history.json", "futures.json", "outside.json"): (d / n_).write_text("[]")
        return d

    def test_good_data_passes(self):
        self.assertEqual(ci_check.check_data(self.make(), today=self.TODAY), [])

    def test_the_committed_export_passes(self):
        self.assertEqual(ci_check.check_data(ROOT / "public" / "data", today=datetime.date.fromisoformat(
            json.loads((ROOT / "public" / "data" / "meta.json").read_text())["latest_report_date"])), [])

    def test_failures(self):
        cases = {
            "too few rows": self.make(n=5),
            "sample data": self.make(meta={"sample": True}),
            "stale": self.make(meta={"latest_report_date": "2026-10-10"}),
            "future date": self.make(meta={"latest_report_date": "2026-11-30"}),
            "no date": self.make(meta={"latest_report_date": None}),
            "never ingested": self.make(meta={"last_ingest_ok_at": ""}),
            "missing key": self.make(rows=[{k: v for k, v in row().items() if k != "basis_high_month"} for _ in range(40)]),
            "bad range": self.make(rows=[row(bid_low=5, bid_high=4) for _ in range(40)]),
        }
        for why, d in cases.items():
            with self.subTest(why): self.assertTrue(ci_check.check_data(d, today=self.TODAY), why)

    def test_unreadable_data_fails(self):
        d = self.make(); (d / "latest.json").write_text("{not json")
        self.assertTrue(ci_check.check_data(d, today=self.TODAY))
        self.assertTrue(ci_check.check_data(Path(tempfile.mkdtemp()), today=self.TODAY))

    def test_cli_exit_codes(self):
        d = self.make(n=2)
        r = subprocess.run([sys.executable, str(ROOT / "deploy" / "ci_check.py"), "data", "--data-dir", str(d)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1); self.assertIn("last published site stays", r.stderr)

    def test_dist_check_on_a_real_build_and_on_leaks(self):
        dist = ROOT / "dist"; existed = dist.exists()
        if existed: self.skipTest("dist/ exists locally; not touching it")
        self.addCleanup(shutil.rmtree, dist, True)
        subprocess.run(["bash", str(ROOT / "build_dist.sh")], cwd=ROOT, check=True, capture_output=True)
        self.assertEqual(ci_check.check_dist(dist, ROOT / "public" / "data"), [])
        (dist / "x.test.js").write_text("1"); (dist / "data-sample").mkdir(); (dist / ".nojekyll").unlink()
        probs = " ".join(ci_check.check_dist(dist, ROOT / "public" / "data"))
        for s in ("*.test.js", "data-sample", ".nojekyll"): self.assertIn(s, probs)


if __name__ == "__main__":
    unittest.main()
