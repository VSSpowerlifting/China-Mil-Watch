"""Source-use and workflow boundaries for AFP Oct 14 human review."""
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/ph_afp_oct14_review_docket.yml"
PIN = "4dd40b9655ec53fe4fae829eb12ba21032946b25"
RUN = "38562843186-1"


class AFPOct14DocketWorkflowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.script = WORKFLOW.read_text(encoding="utf-8")

    def test_exact_pinned_successful_day_and_run(self):
        s = self.script
        self.assertIn("pin=" + PIN, s)
        self.assertIn("--batch " + PIN + ":" + RUN, s)
        self.assertIn('git -C "$repo" merge-base --is-ancestor "$pin" HEAD', s)
        self.assertIn('test "$(git -C "$repo" rev-parse HEAD)" = "$pin"', s)
        self.assertIn("shadow/ph-afp", s)

    def test_read_only_no_silent_promotion(self):
        s = self.script
        self.assertNotRegex(s, r"(?m)^\s*schedule:")
        self.assertIn("permissions:\n  contents: read", s)
        self.assertNotIn("contents: write", s)
        self.assertIn("github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'", s)
        self.assertIn("persist-credentials: false", s)
        for forbidden in ("git push", "ANTHROPIC_API_KEY", "SMTP_",
                          "shadow_collect", "promote_shadow_records",
                          "run_briefs", "git commit"):
            self.assertNotIn(forbidden, s)

    def test_unsigned_four_originals_never_auto_approved(self):
        s = self.script
        self.assertIn("--format json >", s)
        self.assertIn('d["total_source_records"] == 4', s)
        self.assertIn('d["body_unavailable_records"] == 0', s)
        self.assertIn('d["automated_review_decisions"] == 0', s)
        self.assertIn('batch["target_date"] == "2026-10-14"', s)
        self.assertIn('batch["run_id"] == "' + RUN + '"', s)
        self.assertIn('len({r["source_identity"] for r in batch["records"]}) == 4', s)
        for key in ("source_bodies_or_raw_api_responses_included",
                    "human_review_completed", "source_reuse_approved",
                    "production_eligible", "weekly_ai_writer_eligible"):
            self.assertIn('"' + key + '"', s)
        self.assertIn('r["review_status"] == "not_started"', s)
        self.assertIn('r["human_review_authenticated"] is False', s)

    def test_only_metadata_report_uploaded(self):
        s = self.script
        self.assertEqual(s.count("actions/upload-artifact@v4"), 1)
        self.assertIn("path: ${{ runner.temp }}/afp-oct14-unsigned-review.json", s)
        self.assertIn("if-no-files-found: error", s)
        self.assertIn("retention-days: 7", s)
        for prohibited in ("path: state/", "path: output/", "path: pla_watch.db"):
            self.assertNotIn(prohibited, s)


if __name__ == "__main__":
    unittest.main()
