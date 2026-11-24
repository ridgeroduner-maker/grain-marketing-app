"""Locks the safety properties of the pull-request test workflow (.github/workflows/tests.yml). Text checks, stdlib only."""
import re, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
WF = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
CODE = "\n".join(re.sub(r"\s+#.*$", "", l) for l in WF.splitlines() if not l.lstrip().startswith("#"))
OFFICIAL = {"actions/checkout", "actions/setup-python", "actions/setup-node"}


class TestsWorkflow(unittest.TestCase):
    def test_runs_on_pull_request_only_never_target(self):
        on = re.search(r"^on:\n(.*?)(?=^\w)", CODE, re.S | re.M).group(1)
        self.assertRegex(on, r"(?m)^  pull_request:")
        self.assertNotIn("pull_request_target", CODE)
        self.assertNotIn("push:", on)
        self.assertNotIn("schedule", on)

    def test_read_only_no_secrets_no_deploy(self):
        self.assertRegex(CODE, r"(?m)^permissions:\n  contents: read\n")
        self.assertEqual(len(re.findall(r"(?m)^\s*permissions:", CODE)), 1, "no job may widen permissions")
        self.assertNotRegex(CODE, r":\s*write")
        self.assertNotIn("secrets.", CODE)
        self.assertNotIn("github.token", CODE)
        for bad in ("deploy-pages", "upload-pages-artifact", "git push", "git commit"):
            self.assertNotIn(bad, CODE)
        self.assertIn("persist-credentials: false", CODE)

    def test_actions_official_and_pinned(self):
        uses = re.findall(r"^\s*(?:-\s*)?uses:\s*(\S+)", CODE, re.M)
        self.assertEqual(len(uses), 3)
        for u in uses:
            name, _, ref = u.partition("@")
            self.assertIn(name, OFFICIAL, u)
            self.assertRegex(ref, r"^[0-9a-f]{40}$", u)
            self.assertRegex(WF, re.escape(u) + r"\s+# v\d")

    def test_runs_every_suite(self):
        self.assertIn("python3 -m unittest discover -s ingest/tests", CODE)
        for t in sorted((ROOT / "public").glob("*.test.js")):
            self.assertIn(f"node public/{t.name}", CODE, f"{t.name} must run on pull requests")


if __name__ == "__main__":
    unittest.main()
