"""Offline structural guard for manual metadata-only country desk release."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/country_research_render_only_release.yml"


class CountryResearchReleaseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def test_manual_only_for_release_and_exact_main_sha(self):
        text = self.body
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("approved_main_sha:", text)
        self.assertIn("EXPECTED_SHA:", text)
        self.assertIn('test "$ACTUAL_SHA" = "$EXPECTED_SHA"', text)
        self.assertIn("github.ref == 'refs/heads/main'", text)
        self.assertNotIn("\n  push:", text)
        self.assertNotIn("\n  schedule:", text)
        self.assertIn("if: inputs.publish", text)

    def test_never_collects_or_spends_model_tokens(self):
        text = self.body
        for forbidden in (
            "python pipeline.py", "ANTHROPIC_API_KEY", "shadow_collect.py",
            "scripts/shadow_collect", "actions-gh-pages@v2", "state/shadow.db:",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)
        self.assertIn("python site/render.py", text)
        self.assertIn("python scripts/validate_output.py", text)
        self.assertIn("python scripts/verify_db_current.py", text)

    def test_private_source_and_public_record_are_separate(self):
        text = self.body
        self.assertIn('assert row["entries"] == []', text)
        self.assertIn('d["has_production_records"] is False', text)
        self.assertIn('d["manifest"] is None', text)
        self.assertIn('assert "data-reference-list" not in text', text)
        self.assertIn('assert "6 declared" in desk_html', text)

    def test_db_immutability_and_safe_publishing(self):
        text = self.body
        self.assertIn("sha256sum -c", text)
        self.assertIn("git diff --exit-code -- pla_watch.db", text)
        self.assertIn("git add -A -- output/", text)
        self.assertIn("git fetch origin main", text)
        self.assertIn("git push origin HEAD:main", text)
        self.assertIn("cname: indopacificrecord.org", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("group: daily-update", text)


if __name__ == "__main__":
    unittest.main()
