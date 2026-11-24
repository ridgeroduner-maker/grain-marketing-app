"""Refresh-failure alert (pages.yml job refresh-alert + deploy/refresh_alert.sh). The script is run against a fake `gh` that only
records its arguments, so nothing touches GitHub."""
import os, re, subprocess, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
WF = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
CODE = "\n".join(re.sub(r"\s+#.*$", "", l) for l in WF.splitlines() if not l.lstrip().startswith("#"))
SCRIPT = ROOT / "deploy" / "refresh_alert.sh"


def job_block(name):
    m = re.search(rf"^  {name}:\n(.*?)(?=^  \w[\w-]*:\n|\Z)", CODE, re.S | re.M)
    assert m, name
    return m.group(1)


class AlertJobTests(unittest.TestCase):
    def test_issues_write_only_in_the_alert_job(self):
        self.assertEqual(CODE.count("issues: write"), 1)
        job = job_block("refresh-alert")
        self.assertIn("issues: write", job)
        self.assertNotRegex(job, r"(contents|pages|id-token|pull-requests|actions):\s*write")
        self.assertNotIn("issues", job_block("build")); self.assertNotIn("issues", job_block("deploy"))
        self.assertRegex(CODE, r"(?m)^permissions:\n  contents: read\n")     # workflow default unchanged

    def test_runs_after_build_and_deploy_on_main_and_uses_builtin_token(self):
        job = job_block("refresh-alert")
        self.assertIn("needs: [build, deploy]", job)
        self.assertIn("!cancelled()", job); self.assertIn("github.ref == 'refs/heads/main'", job)
        self.assertIn("GH_TOKEN: ${{ github.token }}", job)
        self.assertNotIn("secrets.", CODE)
        self.assertIn("bash deploy/refresh_alert.sh", job)
        self.assertNotIn("continue-on-error", job)

    def test_deploy_still_needs_a_successful_build(self):
        dep = job_block("deploy")
        self.assertIn("needs: build", dep); self.assertNotRegex(dep, r"\bif:")   # fail-safe: a failed build never deploys
        self.assertIn("id: ingest", job_block("build"))
        self.assertIn("exit \"$rc\"", job_block("build"))                         # ingest failure still fails the step
        self.assertIn("rc=${PIPESTATUS[0]}", job_block("build"))


class AlertScriptTests(unittest.TestCase):
    def run_script(self, build, deploy, open_issues="", failed=""):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "calls"
            gh = Path(d) / "gh"
            gh.write_text("#!/bin/sh\n"
                          f'printf "%s" "$*" | tr "\\n" " " >> "{log}"; echo >> "{log}"\n'
                          f'if [ "$1 $2" = "issue list" ]; then printf "%s" "{open_issues}"; fi\n')
            gh.chmod(0o755)
            env = dict(os.environ, PATH=f"{d}:{os.environ['PATH']}", BUILD_RESULT=build, DEPLOY_RESULT=deploy,
                       INGEST_FAILED=failed, RUN_URL="https://example.invalid/run/1", EVENT_NAME="schedule")
            r = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            return log.read_text().splitlines() if log.exists() else []

    def test_failure_with_no_open_issue_creates_one_with_the_label(self):
        calls = self.run_script("failure", "skipped", failed="AMS_3049 FAILED: report 3049: no 'Grain Report for' line")
        self.assertTrue(any(c.startswith("issue list --label refresh-failure --state open") for c in calls))
        create = [c for c in calls if c.startswith("issue create")]
        self.assertEqual(len(create), 1)
        self.assertIn("--label refresh-failure", create[0]); self.assertIn("AMS_3049 FAILED", create[0])
        self.assertIn("last good data", create[0]); self.assertIn("https://example.invalid/run/1", create[0])
        self.assertFalse(any(c.startswith(("issue comment", "issue close")) for c in calls))

    def test_failure_with_an_open_issue_comments_instead(self):
        calls = self.run_script("failure", "skipped", open_issues="12\n")
        self.assertTrue(any(c.startswith("issue comment 12 ") for c in calls))
        self.assertFalse(any(c.startswith(("issue create", "label create", "issue close")) for c in calls))

    def test_deploy_failure_also_alerts(self):
        calls = self.run_script("success", "failure")
        self.assertTrue(any(c.startswith("issue create") and "publishing to GitHub Pages failed" in c for c in calls))

    def test_success_closes_every_open_alert(self):
        calls = self.run_script("success", "success", open_issues="12\n15\n")
        self.assertTrue(any(c.startswith("issue close 12 ") for c in calls)); self.assertTrue(any(c.startswith("issue close 15 ") for c in calls))
        self.assertFalse(any(c.startswith(("issue create", "issue comment")) for c in calls))

    def test_success_with_nothing_open_does_nothing(self):
        calls = self.run_script("success", "success")
        self.assertEqual([c for c in calls if not c.startswith("issue list")], [])

    def test_cancelled_or_skipped_changes_nothing(self):
        calls = self.run_script("cancelled", "skipped", open_issues="12\n")
        self.assertEqual([c for c in calls if not c.startswith("issue list")], [])


if __name__ == "__main__":
    unittest.main()
