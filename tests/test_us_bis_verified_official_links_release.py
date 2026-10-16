"""BIS Pages release is source-triggered, typed, scoped and never PR activated.

Source-free integration contracts. Live scheduled-run evidence is NOT simulated
by CI and must independently pass the production run before admission.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/us_bis_verified_official_links_release.yml"

class VerifiedBISPublicationContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf = WORKFLOW.read_text(encoding="utf-8")

    def test_only_genuine_source_run_may_activate_production_job(self):
        self.assertIn("workflow_run:",self.wf)
        self.assertIn("BIS Official Homepage Press Metadata — Scheduled Shadow",self.wf)
        self.assertIn("github.event.workflow_run.event == 'schedule'",self.wf)
        self.assertIn("github.event.workflow_run.conclusion == 'success'",self.wf)
        self.assertIn("github.event.workflow_run.head_branch == 'main'",self.wf)
        self.assertIn("github.event_name == 'workflow_run'",self.wf)
        self.assertNotIn("\n  workflow_dispatch:",self.wf)
        self.assertNotIn("\n  push:",self.wf)
        self.assertNotIn("\n  schedule:",self.wf)
        self.assertIn("if: github.event_name == 'pull_request'",self.wf)

    def test_authentic_run_and_git_receipt_checked_before_database_write(self):
        self.assertIn('gh api "repos/$GITHUB_REPOSITORY/actions/runs/$BIS_RUN_ID"',self.wf)
        self.assertIn("git/ref/heads/shadow/us-bis-homepage",self.wf)
        self.assertIn("python -m scripts.attest_us_bis_scheduled_receipt",self.wf)
        self.assertIn("python -m scripts.admit_us_bis_scheduled_metadata",self.wf)
        self.assertLess(
            self.wf.index("python -m scripts.attest_us_bis_scheduled_receipt"),
            self.wf.index("python -m scripts.admit_us_bis_scheduled_metadata"))
        self.assertIn("--authenticated-run-json",self.wf)
        self.assertIn("--expected-remote-head",self.wf)
        self.assertIn("--standing-official-url-date-issuer-approval",self.wf)
        self.assertNotIn("collect_us_bis_homepage_metadata \\",self.wf)
        self.assertNotIn("shadow/us-treasury-press",self.wf)

    def test_only_us_desk_and_live_sqlite_published(self):
        self.assertIn("group: daily-update",self.wf)
        self.assertIn("git add -- pla_watch.db output/us-indopacific.html",self.wf)
        self.assertIn("cp ../output/us-indopacific.html us-indopacific.html",self.wf)
        self.assertIn("test \"$changed\" = \"us-indopacific.html\"",self.wf)
        self.assertIn("git push origin HEAD:refs/heads/gh-pages",self.wf)
        self.assertIn("source-free-release-contracts:",self.wf)
        self.assertIn("genuine-scheduled-source-only:",self.wf)
        self.assertNotIn("deploy_output_only",self.wf)
        self.assertNotIn("git add -A",self.wf)
        self.assertNotIn("git add output/",self.wf)

    def test_preserves_pacom_uscc_treasury_and_unrelated_sqlite_counts(self):
        self.assertIn("bis-other-tables.json",self.wf)
        self.assertIn("if not r[0].startswith(\"bis_\")",self.wf)
        for key in ("data-us-bis-official-link","data-us-pacom-link",
                    "data-uscc-official-link","data-us-treasury-official-link"):
            self.assertIn(key,self.wf)
        self.assertIn("load_public_links",self.wf)
        self.assertIn("PACOM remains access-blocked",self.wf)
        self.assertIn("DVIDS paused",self.wf)
        self.assertIn("sha256sum output/us-indopacific.html",self.wf)

    def test_source_branch_and_main_locks_precede_both_pushes(self):
        self.assertIn("bis-source-before.sha",self.wf)
        self.assertIn("bis-main-before.sha",self.wf)
        self.assertLess(
            self.wf.index('latest="$(gh api'),
            self.wf.index("git push origin HEAD:refs/heads/main"))
        self.assertLess(
            self.wf.index("git fetch --quiet origin main"),
            self.wf.index("git push origin HEAD:refs/heads/main"))
        self.assertIn("git fetch --quiet origin gh-pages",self.wf)
        self.assertIn("test \"$(git rev-parse origin/gh-pages)\" = \"$before\"",self.wf)

    def test_site_renderer_only_reads_authenticated_bis(self):
        generator=(ROOT/"site/preview/generate_preview.py").read_text(encoding="utf-8")
        template=(ROOT/"site/preview/templates/desk.html").read_text(encoding="utf-8")
        self.assertIn("from core.us_bis_authenticated_metadata import load_public_links as load_bis_live_links",generator)
        self.assertIn("us_bis_authenticated_links=bis_links",generator)
        self.assertIn("if desk.slug == 'us-indopacific' and us_bis_authenticated_links",template)
        self.assertIn("data-us-bis-official-link",template)
        self.assertIn("not the agency's full publication history",template)

if __name__=="__main__":
    unittest.main()
