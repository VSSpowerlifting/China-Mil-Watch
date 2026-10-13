"""Output-scope tests for the Phase 3C / No. 17 release."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.guard_briefs_render_scope import (
    REVIEWED_OUTPUT_PATHS, classify_output_changes, is_reviewed_path,
)


class BriefsOutputScopeTests(unittest.TestCase):
    def test_exact_native_and_historical_routes_are_reviewed(self):
        self.assertTrue(is_reviewed_path("output/analysis.html"))
        self.assertTrue(is_reviewed_path("output/briefs/trident-resolve-regional-scale-specific-chinese-tasks.html"))
        self.assertTrue(is_reviewed_path("output/the-pla-watch/posts/2026-08-15.html"))
        self.assertTrue(is_reviewed_path("output/assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg"))
        self.assertEqual(len([p for p in REVIEWED_OUTPUT_PATHS if "/posts/" in p]), 14)

    def test_unrelated_routes_and_media_are_not_implicitly_admitted(self):
        for path in (
            "output/indonesia.html",
            "output/korea.html",
            "output/briefs/unreviewed.html",
            "output/the-pla-watch/media/2026-08-01-veil.jpg",
            "output/assets/editorial/other-photo.jpg",
            "output/briefs/feed.xml",
        ):
            with self.subTest(path=path):
                self.assertFalse(is_reviewed_path(path))

    def test_guard_sees_tracked_and_ignored_untracked_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "output").mkdir()
            (root / ".gitignore").write_text("output/hidden-preview.bin\n", encoding="utf-8")
            (root / "output" / "analysis.html").write_text("old", encoding="utf-8")
            (root / "output" / "indonesia.html").write_text("old", encoding="utf-8")

            def git(*args):
                subprocess.run(
                    ["git", *args], cwd=root, check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )

            git("init", "-q")
            git("config", "user.name", "test")
            git("config", "user.email", "test@example.invalid")
            git("add", "-A")
            git("commit", "-qm", "baseline")
            (root / "output" / "analysis.html").write_text("new", encoding="utf-8")
            (root / "output" / "indonesia.html").write_text("new", encoding="utf-8")
            (root / "output" / "hidden-preview.bin").write_bytes(b"not reviewed")

            changed, unexpected = classify_output_changes(root)
            self.assertEqual(
                changed,
                {
                    "output/analysis.html",
                    "output/indonesia.html",
                    "output/hidden-preview.bin",
                },
            )
            self.assertEqual(
                unexpected,
                {"output/indonesia.html", "output/hidden-preview.bin"},
            )


if __name__ == "__main__":
    unittest.main()
