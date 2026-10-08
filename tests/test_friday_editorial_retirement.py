"""Friday Briefs automation retired; manual explicit-delivery fallback remains."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRIDAY = ROOT / ".github/workflows/weekly_briefs_editorial_handoff.yml"


class FridayAutoSendRetirement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = FRIDAY.read_text(encoding="utf-8")

    def test_no_automated_friday_schedule_or_background_email(self):
        self.assertIn("  workflow_dispatch:", self.source)
        self.assertNotIn("  schedule:", self.source)
        self.assertNotIn("    - cron:", self.source)
        self.assertNotIn("github.event_name == 'schedule'", self.source)
        self.assertIn("if: github.event_name == 'workflow_dispatch'", self.source)

    def test_even_legacy_send_still_needs_two_explicit_actions(self):
        self.assertIn("vars.IPR_EDITOR_DELIVERY_ENABLED == 'true'", self.source)
        self.assertIn("inputs.send_email == true", self.source)
        self.assertIn("github.event_name == 'workflow_dispatch'", self.source)
        self.assertIn("default: false", self.source)
        self.assertIn('if [[ "$SHOULD_SEND" == "true" ]]; then', self.source)
        self.assertIn("args+=(--send)", self.source)

    def test_legacy_preview_and_source_guards_preserved(self):
        self.assertIn("Resolve guarded New York Friday reporting window", self.source)
        self.assertIn("Create read-only Friday-bounded source scaffold", self.source)
        self.assertIn("python -m scripts.weekly_editorial_handoff", self.source)
        self.assertIn("--use-japan-research", self.source)
        self.assertIn("permissions:\n  contents: read", self.source)
        self.assertNotIn("contents: write", self.source)
        self.assertNotIn("git push", self.source)
        self.assertNotIn("actions/upload-artifact", self.source)


if __name__ == "__main__":
    unittest.main()
