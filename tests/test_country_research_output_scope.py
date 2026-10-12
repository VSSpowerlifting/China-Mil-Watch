"""No-network tests for fail-closed country-research output release scope."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.guard_country_research_output_scope import classify_output_changes


class CountryOutputScopeTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="ipr-country-output-")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self._git("init", "-q")
        self._git("config", "user.name", "Test")
        self._git("config", "user.email", "test@example.invalid")
        (self.root / "output").mkdir()
        (self.root / "output/japan.html").write_text("old")
        (self.root / "output/analysis.html").write_text("old")
        (self.root / ".gitignore").write_text("output/ignored-asset.jpg\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "baseline")

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def test_only_approved_japan_change_is_allowed(self):
        (self.root / "output/japan.html").write_text("new")
        changed, unexpected = classify_output_changes(self.root)
        self.assertEqual(changed, {"output/japan.html"})
        self.assertEqual(unexpected, set())

    def test_unrelated_existing_page_fails_closed(self):
        (self.root / "output/japan.html").write_text("new")
        (self.root / "output/analysis.html").write_text("unreviewed")
        changed, unexpected = classify_output_changes(self.root)
        self.assertEqual(changed, {"output/japan.html", "output/analysis.html"})
        self.assertEqual(unexpected, {"output/analysis.html"})

    def test_untracked_and_ignored_media_are_both_rejected(self):
        (self.root / "output/new-image.jpg").write_bytes(b"untracked")
        (self.root / "output/ignored-asset.jpg").write_bytes(b"ignored")
        _, unexpected = classify_output_changes(self.root)
        self.assertEqual(unexpected, {
            "output/new-image.jpg", "output/ignored-asset.jpg"
        })

    def test_staged_unreviewed_page_cannot_hide(self):
        (self.root / "output/analysis.html").write_text("staged")
        self._git("add", "output/analysis.html")
        _, unexpected = classify_output_changes(self.root)
        self.assertEqual(unexpected, {"output/analysis.html"})

    def test_deleted_unreviewed_asset_cannot_hide(self):
        (self.root / "output/analysis.html").unlink()
        _, unexpected = classify_output_changes(self.root)
        self.assertEqual(unexpected, {"output/analysis.html"})

    def test_renaming_unreviewed_page_cannot_hide_old_path(self):
        (self.root / "output/analysis.html").rename(self.root / "output/desks.html")
        changed, unexpected = classify_output_changes(self.root)
        self.assertIn("output/analysis.html", changed)
        self.assertIn("output/analysis.html", unexpected)

    def test_no_deltas_does_not_cause_failed_preview(self):
        self.assertEqual(classify_output_changes(self.root), (set(), set()))


if __name__ == "__main__":
    unittest.main()
