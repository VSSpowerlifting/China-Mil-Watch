"""Offline contract for the real, read-only Vietnam Day-7 original proof.

This file never opens publisher URLs, source state, or production databases.
The workflow's real Git/capture-integrity step runs separately on a PR.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/vietnam_day7_exact_original_proof.yml"


class Day7RealOriginalProofContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_exact_review_cutoff_and_all_three_source_commits(self):
        for required in (
            "--checkpoint day-07 --as-of 2026-10-14",
            "vn_mps_foreign_affairs_vi|shadow/vietnam-mps-foreign-affairs|cb607582eda7bd8760663540c33de2f73da411ff",
            "vn_moit_energy_vi|shadow/vietnam-moit-energy|5d25d68ee5bd3d1e8e5c7759db880a30d172491a",
            "vn_moit_foundational_industry_vi|shadow/vietnam-moit-foundational-industry|75035550a2f9db4f7a1cac57925141961b390d60",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.workflow)

    def test_provenance_bound_to_literal_immutable_commits(self):
        for required in (
            'cat-file -e "$pinned^{commit}"',
            'merge-base --is-ancestor "$pinned" HEAD',
            '--state-commit "$pinned"',
            'test "$(git -C "$root/$folder-state" ls-tree --name-only HEAD)" = state',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.workflow)
        self.assertNotIn("--state-commit HEAD", self.workflow)

    def test_executes_real_capture_integrity_and_three_packet_rollup(self):
        self.assertIn("python -m scripts.review_vietnam_ministry_state", self.workflow)
        self.assertIn("python -m scripts.vietnam_ministry_checkpoint_rollup", self.workflow)
        self.assertIn("all_three_review_packets_integrity_checked", self.workflow)
        self.assertIn("all_three_machine_checkpoints_reached", self.workflow)
        self.assertIn("MOIT robots warnings lost", self.workflow)

    def test_cannot_report_machine_pass_as_rights_or_human_approval(self):
        for required in (
            '"human_original_language_review_authenticated": False',
            '"failed_attempt_artifact_census_authenticated": False',
            '"source_rights_approved": False',
            '"production_admission_authorized": False',
            '"weekly_ai_or_editor_email_authorized": False',
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.workflow)

    def test_late_utc_finish_is_not_a_missing_scheduled_logical_slot(self):
        for evidence in (
            '"missing_collecting_days"] == ["2026-10-12"]',
            '"target_date_source"] == "schedule-slot"',
            '"run_id": "38328331888-1"',
            '"target_date": "2026-10-12"',
            '"finished_utc_date": "2026-10-13"',
            '"eight_scheduled_logical_dates_present_per_source": True',
            '"missing_scheduled_logical_dates": []',
            '"legacy_utc_completion_day_gap": ["2026-10-12"]',
            '"thirty_consecutive_collecting_days_qualified": False',
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, self.workflow)

    def test_no_originals_ever_uploaded_and_private_output_removed(self):
        self.assertIn('path: ${{ runner.temp }}/vn-day7-machine-summary.json', self.workflow)
        self.assertIn('rm -rf "$root"', self.workflow)
        self.assertIn('test ! -e "$root"', self.workflow)
        self.assertIn('if: success()', self.workflow)
        self.assertNotIn('path: ${{ runner.temp }}/vn-day7-real-proof', self.workflow)
        self.assertNotIn('path: ${{ runner.temp }}/vn-day7-real-proof/', self.workflow)

    def test_no_automatic_dispatch_and_no_privileged_write_permission(self):
        self.assertIn("pull_request:", self.workflow)
        self.assertNotIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("  schedule:", self.workflow)
        self.assertIn("  contents: read", self.workflow)
        self.assertNotIn("contents: write", self.workflow)
        self.assertNotIn("persist-credentials: true", self.workflow)
        self.assertNotIn("git push ", self.workflow)
        self.assertNotIn("gh-pages", self.workflow)

    def test_exact_public_receipt_is_an_allowlist_not_source_prose(self):
        self.assertIn('"protocol": "ipr-vietnam-day7-three-source-originals-machine-only/1"', self.workflow)
        self.assertIn('"machine_packet_sha256":', self.workflow)
        self.assertIn('"source_slug":', self.workflow)
        self.assertIn('"records_checked":', self.workflow)
        self.assertNotIn('"text_original":', self.workflow)
        self.assertNotIn('"corpus_evidence":', self.workflow)


if __name__ == "__main__":
    unittest.main()
