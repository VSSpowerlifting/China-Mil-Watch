"""No-network contract for Indonesia exact 31-original review handoff."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/indonesia_pinned_reference_review_queue.yml"
PIN = "0595c6677be24f8f0f33aecb28eec0050e36e8f9"


class ExactIndonesiaReviewQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKFLOW.read_text(encoding="utf-8")

    def test_public_status_and_human_decisions_remain_unapproved(self):
        src = self.source
        self.assertIn("permissions:\n  contents: read", src)
        self.assertNotIn("contents: write", src)
        self.assertNotIn("actions: write", src)
        self.assertNotIn("\n  schedule:", src)
        self.assertNotIn("\n  push:", src)
        self.assertNotIn("git push ", src)
        self.assertIn('assert not data["independent_human_review_completed"]', src)
        self.assertIn('assert not data["source_reuse_approved"]', src)
        self.assertIn('assert not data["public_corpus_admitted"]', src)
        self.assertIn('assert row["independent_human_review_complete"] is False', src)
        self.assertIn('assert row["publisher_body_reuse_authorized"] is False', src)
        self.assertIn('assert row["eligible_for_public_corpus"] is False', src)

    def test_historical_exact_commit_is_not_replaced_by_current_head(self):
        src = self.source
        self.assertIn("pin=" + PIN, src)
        self.assertIn('merge-base --is-ancestor "$pin" "$sha"', src)
        self.assertIn('cat-file -e "$pin^{commit}"', src)
        self.assertIn('echo "INDONESIA_STATE_SHA=$pin"', src)
        self.assertIn('--state-commit "$INDONESIA_STATE_SHA"', src)
        self.assertIn('data["state_commit"] == "' + PIN + '"', src)
        self.assertIn('data["stored_originals"] == 31', src)
        self.assertNotIn("--depth=1", src)

    def test_no_source_capture_or_production_content_in_artifact(self):
        src = self.source
        self.assertIn("indonesia-review-queue/", src)
        self.assertIn("review_queue.json", src)
        self.assertIn("review_queue.csv", (ROOT/"scripts/prepare_indonesia_reference_review_queue.py").read_text())
        self.assertIn("retention-days: 14", src)
        self.assertNotIn("state/shadow.db", src)
        self.assertNotIn("state/evidence/payloads", src)
        self.assertIn("sha256sum -c", src)
        self.assertIn("git diff --exit-code -- pla_watch.db output/ shadow/", src)


if __name__ == "__main__":
    unittest.main()
