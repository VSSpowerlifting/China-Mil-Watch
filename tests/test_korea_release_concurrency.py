"""Korea activation must not disappear behind U.S./daily queue coalescing."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/korea_verified_official_link_production.yml"


class KoreaMetadataSchedulerIsolation(unittest.TestCase):
    def test_korea_pending_slot_is_separate_from_other_desk_runs(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: korea-verified-official-link-production", content)
        self.assertNotIn("group: daily-update", content)
        self.assertIn("cancel-in-progress: false", content)
        self.assertIn("cron: '37 20 * * *'", content)
        self.assertIn("workflow_dispatch:", content)

    def test_independent_queue_still_fails_closed_on_stale_shared_db(self):
        content = WORKFLOW.read_text(encoding="utf-8")
        required = (
            "git rev-parse origin/main",
            "korea-prod-main-before",
            "git fetch origin main",
            "git push origin HEAD:main",
            "git push origin HEAD:gh-pages",
            "git rev-parse origin/gh-pages",
            "korea-prod-source-before",
            "current_source",
            "sha256sum -c",
            "git add -- pla_watch.db output/korea.html",
            "test -z \"$(git status --porcelain --untracked-files=all)\"",
        )
        for protection in required:
            with self.subTest(protection=protection):
                self.assertIn(protection, content)
        self.assertNotIn("peaceiris/actions-gh-pages", content)
        self.assertNotIn("git push --force", content)


if __name__ == "__main__":
    unittest.main()
