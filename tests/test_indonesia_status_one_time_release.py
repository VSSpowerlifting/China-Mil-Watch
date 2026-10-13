"""Retired Indonesia status-only release remains a read-only site contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github/workflows/indonesia_public_status_release_once.yml"


class IndonesiaOneTimePublicationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WF.read_text(encoding="utf-8")

    def test_retired_one_time_release_cannot_publish_full_site(self):
        src = self.source
        self.assertIn("on:\n  pull_request:\n", src)
        self.assertIn("site/preview/templates/desk.html", src)
        self.assertIn("indonesia-status-readonly-", src)
        self.assertIn("cancel-in-progress: false", src)
        self.assertNotIn("  push:\n", src)
        self.assertNotIn("  publish:\n", src)
        for forbidden in (
            "contents: write", "github_token:", "publish_dir:",
            "publish_branch:", "git push origin", "git add -A -- output/",
            "startsWith(github.event.head_commit.message",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)

    def test_pull_request_contract_has_no_write_credentials(self):
        src = self.source
        self.assertIn("permissions:\n  contents: read", src)
        self.assertIn("if: github.event_name == 'pull_request'", src)
        self.assertIn("persist-credentials: false", src)
        self.assertNotIn("persist-credentials: true", src)
        self.assertIn("actions/checkout@v4", src)

    def test_render_checks_twelve_bibliographic_links_without_corpus(self):
        src = self.source
        for required in (
            "python site/render.py", "python scripts/validate_output.py",
            "output/indonesia.html", "output/desks.html",
            "No individual source references have completed",
            "Twelve external ministry news links",
            "data-reference-list", "state/shadow.db",
            "text_original", "body_original",
            "sha256sum -c",
            "assert len(links) == 12",
        ):
            with self.subTest(required=required):
                self.assertIn(required, src)
        for forbidden in (
            "scripts/shadow_collect", "python pipeline.py",
            "ANTHROPIC_API_KEY", "source_rights_approved: true",
            "python scripts/publish_shadow_review",
            'Four external ministry news links',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
