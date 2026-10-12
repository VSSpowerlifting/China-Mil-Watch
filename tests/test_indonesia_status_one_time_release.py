"""Single-use public Indonesia status release cannot become a source promotion."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/indonesia_public_status_release_once.yml"


class IndonesiaOneTimePublicationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WF.read_text(encoding="utf-8")

    def test_merge_trigger_is_one_specific_owner_accepted_message(self):
        src = self.source
        self.assertIn("branches:", src)
        self.assertIn("- main", src)
        self.assertIn("startsWith(github.event.head_commit.message, 'Launch Indonesia public research-status page (PR #424)')", src)
        self.assertIn("github.ref == 'refs/heads/main'", src)
        self.assertIn("cancel-in-progress: false", src)
        self.assertIn("group: daily-update", src)

    def test_read_only_pr_and_write_scoped_push(self):
        src = self.source
        self.assertIn("permissions:\n  contents: read", src)
        self.assertIn("  publish:\n", src)
        self.assertIn("      contents: write", src)
        self.assertIn("if: github.event_name == 'pull_request'", src)
        self.assertIn("ref: main", src)
        self.assertIn("test \"$(git rev-parse origin/main)\" = \"$(git rev-parse HEAD)\"", src)

    def test_actual_site_build_and_publication_hold(self):
        src = self.source
        for required in (
            "python site/render.py", "python scripts/validate_output.py",
            "output/indonesia.html", "desks/registry.json", 'item["status"] == "shadow"',
            "No individual source references have completed",
            "data-reference-list", "state/shadow.db",
            "text_original", "body_original",
            "github_token:", "publish_dir: ./output",
            "publish_branch: gh-pages", "cname: indopacificrecord.org",
            "git add -A -- output/", "sha256sum -c",
        ):
            with self.subTest(required=required):
                self.assertIn(required, src)
        for forbidden in (
            "scripts/shadow_collect", "python pipeline.py",
            "ANTHROPIC_API_KEY", "source_rights_approved: true",
            "git add -A -- .", "python scripts/publish_shadow_review",
        ):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
