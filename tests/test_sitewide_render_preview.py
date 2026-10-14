"""Cosmetic-only IPR sitewide render preview must remain read-only and fail-closed."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.audit_sitewide_render_preview import COSMETIC_CSS, classify, inventory


class SitewideRenderPreview(unittest.TestCase):
    def test_expected_css_is_review_only(self):
        for path in COSMETIC_CSS:
            with self.subTest(path=path):
                self.assertEqual(classify(path), "css-review")

    def test_public_html_requires_manual_review(self):
        for path in (
            "output/index.html", "output/analysis.html",
            "output/briefs/what-is-being-built-in-laos.html",
            "output/record/124.html",
            "output/the-pla-watch/posts/2026-08-15.html",
        ):
            with self.subTest(path=path):
                self.assertEqual(classify(path), "html-manual-review")

    def test_canonical_assets_feeds_and_unreviewed_routes_are_blocked(self):
        for path in (
            "output/the-pla-watch/posts/2026-08-15.json",
            "output/briefs/feed.xml", "output/sitemap.xml",
            "output/data/articles.json", "output/assets/flags/japan.svg",
            "output/assets/editorial/derivatives/photo.jpg",
            "output/briefs/media/image.webp", "output/another.css",
            "output/record/one/two.html", "output/record/123.json",
            "scripts/site/render.py", "output/CNAME", "output/robots.txt",
        ):
            with self.subTest(path=path):
                self.assertEqual(classify(path), "blocked-noncosmetic")

    def test_no_substring_bypass(self):
        for path in ("output/styles.css.bak", "output/x/styles.css",
                     "output/briefs/piece.html.bak", "output/index.html/evil"):
            self.assertEqual(classify(path), "blocked-noncosmetic")


class RenderPreviewGitIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

        def git(*args):
            return subprocess.run(["git", *args], cwd=self.root, check=True,
                                  capture_output=True, text=True)
        git("init", "-q")
        git("config", "user.name", "Review QA")
        git("config", "user.email", "qa@example.test")
        (self.root / "output").mkdir()
        (self.root / "output/styles.css").write_text("/* before */")
        (self.root / "pla_watch.db").write_bytes(b"unchanged-database")
        (self.root / "README.txt").write_text("unchanged")
        git("add", ".")
        git("commit", "-qm", "before")
        self.db_sha = hashlib.sha256(b"unchanged-database").hexdigest()

    def test_tracks_modified_and_untracked_output_without_authorizing(self):
        (self.root / "output/styles.css").write_text("/* after */")
        (self.root / "output/index.html").write_text("<h1>Review me</h1>")
        result = inventory(self.root, self.db_sha)
        self.assertEqual(result["css_to_review"], 1)
        self.assertEqual(result["html_to_review"], 1)
        self.assertEqual(result["blocked"], [])
        self.assertFalse(result["publish_authorized"])
        self.assertTrue(result["requires_human_output_review"])
        self.assertEqual(result["outside_output"], [])

    def test_noncosmetic_and_outside_changes_are_exposed(self):
        (self.root / "output/other.css").write_text("unexpected")
        (self.root / "README.txt").write_text("unrelated change")
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/other.css", result["blocked"])
        self.assertIn("README.txt", result["outside_output"])

    def test_database_mutation_or_sidecar_fails_closed(self):
        (self.root / "pla_watch.db").write_bytes(b"mutated")
        with self.assertRaises(RuntimeError):
            inventory(self.root, self.db_sha)
        (self.root / "pla_watch.db").write_bytes(b"unchanged-database")
        (self.root / "pla_watch.db-wal").write_bytes(b"unexpected")
        with self.assertRaises(RuntimeError):
            inventory(self.root, self.db_sha)

    def test_deleted_tracked_stylesheet_is_blocked(self):
        (self.root / "output/styles.css").unlink()
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/styles.css", result["blocked"])

    def test_generated_symlink_is_blocked(self):
        (self.root / "output/styles.css").unlink()
        (self.root / "output/styles.css").symlink_to(self.root / "README.txt")
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/styles.css", result["blocked"])


if __name__ == "__main__":
    unittest.main()
