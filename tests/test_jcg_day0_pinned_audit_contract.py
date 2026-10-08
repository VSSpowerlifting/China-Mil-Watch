"""No approval, state mutation or source text in JCG Day 0 CI review."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / ".github/workflows/jcg_day0_pinned_audit.yml"
SHA = "81558026117067cbcf54bd7a7859a2d9db168a0c"


class DayZeroAuditContracts(unittest.TestCase):
    def setUp(self):
        self.source = AUDIT.read_text(encoding="utf-8")

    def test_pinned_exact_original_commit_and_reporting_day(self):
        self.assertEqual(self.source.count(
            "--state-commit " + SHA), 2)
        self.assertIn("--as-of 2026-10-08", self.source)
        self.assertIn("--desk japan_jcg", self.source)
        self.assertIn("--state-repo", self.source)
        self.assertIn("--branch shadow/japan-jcg", self.source)
        self.assertIn("merge-base --is-ancestor", self.source)
        self.assertIn('report["records"] == 3', self.source)
        self.assertIn('report["ledgers"] == 1', self.source)
        self.assertIn('report["findings"] == []', self.source)
        self.assertIn('report["missing_successful_days"] == []', self.source)

    def test_read_only_trigger_not_scheduled_or_owner_approval(self):
        self.assertIn("  pull_request:", self.source)
        self.assertNotIn("  workflow_dispatch:", self.source)
        self.assertNotIn("  schedule:", self.source)
        self.assertIn("permissions:\n  contents: read", self.source)
        self.assertNotIn("contents: write", self.source)
        self.assertIn("persist-credentials: false", self.source)
        self.assertNotIn("git push", self.source)
        self.assertNotIn("git commit", self.source)
        self.assertNotIn("create-or-update", self.source)
        self.assertNotIn("IPR_EDITOR", self.source)
        self.assertNotIn("--send", self.source)
        self.assertIn('receipt["human_review_completed"] is False', self.source)
        self.assertIn('receipt["promotion_authorized"] is False', self.source)
        self.assertIn('receipt["editorial_release_authorized"] is False', self.source)

    def test_artifacts_are_metadata_not_original_text_or_captures(self):
        self.assertIn("scripts.review_desk_shadow", self.source)
        self.assertIn("scripts/japan_jcg_pinned_review_receipt.py", self.source)
        area = self.source.split("path: |", 1)[-1].split(
            "retention-days:", 1)[0]
        self.assertIn("receipt.json", area)
        self.assertIn("formal/report.json", area)
        self.assertIn("formal/report.md", area)
        for forbidden in ("records.jsonl", "shadow.db", ".bin", "captures/"):
            self.assertNotIn(forbidden, area)
        self.assertIn("human_holds", self.source)

    def test_no_manifest_or_corpus_activation(self):
        self.assertFalse((ROOT / "desks/japan/manifest.json").exists())
        self.assertNotIn("scrape", self.source)
        self.assertNotIn("shadow_collect_desk", self.source)
        self.assertNotIn("weekly_editorial_handoff", self.source)


if __name__ == "__main__":
    unittest.main()
