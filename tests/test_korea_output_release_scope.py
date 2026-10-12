"""Regression tests for Korea-only GitHub Pages publication scope."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.guard_korea_public_output_scope import (
    KOREA_OUTPUT_PATHS, audit_korea_output,
)


class KoreaOutputScopeTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="ipr-korea-release-")
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self._git("init", "-q")
        self._git("config", "user.name", "Test")
        self._git("config", "user.email", "test@example.invalid")
        (self.root / "output").mkdir()
        (self.root / "output/korea.html").write_text("old Korea")
        (self.root / "output/desk-references.css").write_text("old styles")
        (self.root / "output/analysis.html").write_text("old analysis")
        (self.root / "output/japan.html").write_text("old Japan")
        (self.root / ".gitignore").write_text("output/ignored-media.jpg\n")
        self._git("add", "-A")
        self._git("commit", "-qm", "baseline")

    def _git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root,
                              check=True, capture_output=True)

    def test_exact_two_approved_changes(self):
        (self.root / "output/korea.html").write_text("new Korea")
        (self.root / "output/desk-references.css").write_text("new styles")
        changed, denied = audit_korea_output(self.root)
        self.assertEqual(changed, KOREA_OUTPUT_PATHS)
        self.assertEqual(denied, set())

    def test_unrelated_analysis_and_japan_pages_block(self):
        (self.root / "output/korea.html").write_text("new Korea")
        (self.root / "output/analysis.html").write_text("unreviewed analysis")
        (self.root / "output/japan.html").write_text("unreviewed Japan")
        changed, denied = audit_korea_output(self.root)
        self.assertEqual(denied, {
            "output/analysis.html", "output/japan.html"
        })
        self.assertIn("output/korea.html", changed)

    def test_untracked_catalogue_media_blocks(self):
        media = self.root / "output/assets/catalogue/media/held.jpg"
        media.parent.mkdir(parents=True)
        media.write_bytes(b"not reviewed")
        _, denied = audit_korea_output(self.root)
        self.assertEqual(denied, {"output/assets/catalogue/media/held.jpg"})

    def test_gitignored_media_still_blocks(self):
        (self.root / "output/ignored-media.jpg").write_bytes(b"not approved")
        _, denied = audit_korea_output(self.root)
        self.assertEqual(denied, {"output/ignored-media.jpg"})

    def test_staged_non_korea_file_blocks(self):
        (self.root / "output/analysis.html").write_text("staged analysis")
        self._git("add", "output/analysis.html")
        _, denied = audit_korea_output(self.root)
        self.assertEqual(denied, {"output/analysis.html"})

    def test_unapproved_deletion_and_rename_block(self):
        (self.root / "output/analysis.html").rename(
            self.root / "output/new-analysis.html")
        _, denied = audit_korea_output(self.root)
        self.assertEqual(denied, {
            "output/analysis.html", "output/new-analysis.html"
        })

    def test_deleted_korea_page_blocks(self):
        (self.root / "output/korea.html").unlink()
        _, denied = audit_korea_output(self.root)
        self.assertIn("output/korea.html", denied)

    def test_no_changes_is_safe_noop(self):
        self.assertEqual(audit_korea_output(self.root), (set(), set()))

    def test_workflow_cannot_stage_entire_output(self):
        repo_root = Path(__file__).resolve().parents[1]
        workflow = (repo_root / ".github/workflows/korea_public_bibliography_release.yml").read_text(encoding="utf-8")
        self.assertIn("python -m scripts.guard_korea_public_output_scope", workflow)
        self.assertGreaterEqual(workflow.count(
            "if: steps.korea-output-scope.outputs.publish_required == 'true'"), 3)
        self.assertIn("git add -A -- output/korea.html output/desk-references.css", workflow)
        self.assertNotIn("git add -A -- output/\\n", workflow)
        self.assertIn("python -m unittest tests.test_korea_output_release_scope", workflow)


if __name__ == "__main__":
    unittest.main()
