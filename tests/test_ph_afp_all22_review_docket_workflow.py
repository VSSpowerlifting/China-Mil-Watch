"""Offline workflow security contract for exact AFP 13+5+4 human review roster."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / ".github/workflows/ph_afp_all22_review_docket.yml"


class All22ReviewDocketWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.content = FLOW.read_text(encoding="utf-8")

    def test_manual_only_read_only_workflow(self):
        self.assertIn("on:\n  pull_request:", self.content)
        self.assertIn("  workflow_dispatch:", self.content)
        self.assertNotIn("\n  schedule:", self.content)
        self.assertNotIn("\n  push:", self.content)
        self.assertIn("permissions:\n  contents: read", self.content)
        self.assertNotIn("contents: write", self.content)
        self.assertNotIn("actions: write", self.content)
        self.assertIn("github.ref == 'refs/heads/main'", self.content)
        self.assertNotIn("git push ", self.content)
        self.assertNotIn("gh workflow run", self.content)

    def test_exact_historical_first_22_commits(self):
        pins = (
            ("492001f34ba6176169b6acc96a237f05592a3395", "37631681338-1"),
            ("c668790ce3be88b08b3300b945bad58589b3a5b1", "37788547061-1"),
            ("4dd40b9655ec53fe4fae829eb12ba21032946b25", "38562843186-1"),
        )
        for sha, run in pins:
            self.assertRegex(sha, r"^[a-f0-9]{40}$")
            self.assertIn("--batch %s:%s" % (sha, run), self.content)
            self.assertIn("git -C \"$repo\" merge-base --is-ancestor", self.content)
        self.assertIn("test \"$(git -C \"$repo\" ls-tree --name-only \"$pin\")\" = state", self.content)
        self.assertIn("docket[\"total_source_records\"]==22", self.content)
        self.assertIn("docket[\"body_unavailable_records\"]==0", self.content)
        self.assertIn("len(docket[\"batches\"])==3", self.content)
        self.assertIn("2026-10-07", self.content)
        self.assertIn("2026-10-08", self.content)
        self.assertIn("2026-10-14", self.content)

    def test_metadata_only_and_unreviewed_human_rights_holds(self):
        self.assertIn("--format json > \"$RUNNER_TEMP/ph-afp-all22-unsigned.json\"", self.content)
        self.assertIn("record[\"review_status\"]==\"not_started\"", self.content)
        self.assertIn("record[\"human_review_authenticated\"] is False", self.content)
        self.assertIn("\"original_api_response_utf8\" not in record", self.content)
        self.assertIn("\"text_original\" not in record", self.content)
        for gate in ("source_bodies_or_raw_api_responses_included",
                     "human_review_completed", "source_reuse_approved",
                     "production_eligible", "weekly_ai_writer_eligible"):
            self.assertIn('docket[flag] is False', self.content)
            self.assertIn(gate, self.content)
        self.assertIn('docket["automated_review_decisions"]==0', self.content)
        self.assertNotIn("production_admission_authorized=True", self.content)
        self.assertNotIn("model_call(", self.content)

    def test_uploads_only_verified_successful_metadata_and_has_no_tracked_outputs(self):
        section = self.content.split("      - name: Retain unsigned metadata docket only")[1]
        self.assertIn("if: success()", section)
        self.assertIn("retention-days: 7", section)
        self.assertIn("path: ${{ runner.temp }}/ph-afp-all22-unsigned.json", section)
        for unsafe in ("state/shadow.db", "state/evidence/payloads",
                       "state/captures", "pla_watch.db", "original_api_response"):
            self.assertNotIn(unsafe, section)
        self.assertIn("test -z \"$(git status --porcelain --untracked-files=all)\"", self.content)
        self.assertIn("persist-credentials: false", self.content)


if __name__ == "__main__":
    unittest.main()
