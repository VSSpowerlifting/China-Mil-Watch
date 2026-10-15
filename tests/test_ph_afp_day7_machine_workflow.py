"""Offline security boundary for manual AFP Day-7 machine review.

No GitHub Actions requests, no source network, no database, SMTP or model calls.
This checks the actual workflow contract in addition to the source-audit and
positive Actions matching tests that workflow itself executes.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / ".github/workflows/ph_afp_day7_machine_receipt_manual.yml"


class ManualAFPMachineGateTests(unittest.TestCase):
    def setUp(self):
        self.flow = PATH.read_text(encoding="utf-8")

    def test_manual_only_no_schedule_or_push_and_read_only_permissions(self):
        self.assertIn("on:\n  workflow_dispatch:", self.flow)
        for unsupported in ("\n  schedule:", "\n  push:", "\n  pull_request:"):
            self.assertNotIn(unsupported, self.flow)
        self.assertIn("permissions:\n  contents: read\n  actions: read", self.flow)
        self.assertIn("if: github.ref == 'refs/heads/main'", self.flow)
        self.assertNotIn("contents: write", self.flow)
        self.assertNotIn("actions: write", self.flow)
        self.assertNotIn("git push origin", self.flow)
        self.assertNotIn("gh workflow run", self.flow)

    def test_pins_exact_state_before_both_audits(self):
        self.assertIn("git clone --quiet --single-branch --branch shadow/ph-afp", self.flow)
        self.assertIn("rev-parse HEAD", self.flow)
        self.assertIn("--state-commit \"$sha\"", self.flow)
        self.assertIn("python -m scripts.audit_ph_afp_seven_day", self.flow)
        self.assertIn("python -m scripts.audit_ph_afp_actions_provenance", self.flow)
        self.assertIn("--start-date 2026-10-07", self.flow)
        self.assertIn("tests.test_ph_afp_seven_day tests.test_ph_afp_actions_provenance", self.flow)

    def test_actions_census_not_filtered_to_successes_or_schedule_and_raw_not_uploaded(self):
        self.assertIn("gh api --paginate --slurp -X GET", self.flow)
        self.assertIn("created=2026-10-07..$REVIEW_CUTOFF&per_page=100", self.flow)
        self.assertNotIn("event=schedule&", self.flow)
        self.assertNotIn("status=success", self.flow)
        self.assertIn('rm "$RUNNER_TEMP/afp-runs-input.json"', self.flow)
        paths = self.flow.split("name: Retain only metadata-only private reviewer receipts")[1]
        self.assertIn("/afp-review/ledger.json", paths)
        self.assertIn("/afp-review/actions.json", paths)
        self.assertNotIn("/ph-afp-state/state/", paths)
        self.assertNotIn("/afp-runs-input.json", paths)

    def test_machine_verdict_remains_unapproved_after_seven_positive_runs(self):
        self.assertIn("positive_seven_slots_machine_only", self.flow)
        self.assertIn("'all_failed_attempts_verified':False", self.flow)
        self.assertIn("'human_source_reviews_completed':False", self.flow)
        self.assertIn("'source_rights_approved':False", self.flow)
        self.assertIn("'production_admission_authorized':False", self.flow)
        self.assertIn("'weekly_ai_writer_authorized':False", self.flow)
        self.assertIn("'editor_email_or_publication_authorized':False", self.flow)
        self.assertIn("'production_writes':0", self.flow)


if __name__ == "__main__":
    unittest.main()
