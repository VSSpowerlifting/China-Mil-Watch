"""Cosmetic-only IPR sitewide render preview must remain read-only and fail-closed."""
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.audit_sitewide_render_preview import COSMETIC_CSS, classify, css_source_parity, inventory


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
        (self.root / "site/preview").mkdir(parents=True)
        for output_path in COSMETIC_CSS:
            (self.root / output_path).write_text("/* before */")
            (self.root / "site/preview" / Path(output_path).name).write_text("/* before */")
        (self.root / "pla_watch.db").write_bytes(b"unchanged-database")
        (self.root / "README.txt").write_text("unchanged")
        (self.root / "output/index.html").write_text(
            '<h1 style="color:red">Reviewed text</h1>'
            '<a href="/source">Citation</a>'
            '<img src="/photo.jpg" alt="Source photograph">')
        git("add", ".")
        git("commit", "-qm", "before")
        self.db_sha = hashlib.sha256(b"unchanged-database").hexdigest()

    def test_tracks_modified_and_untracked_output_without_authorizing(self):
        # A new palette source already committed on main is rendered into output.
        (self.root / "site/preview/styles.css").write_text("/* after */")
        subprocess.run(["git", "add", "site/preview/styles.css"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "Reviewed source change"], cwd=self.root, check=True)
        (self.root / "output/styles.css").write_text("/* after */")
        (self.root / "output/index.html").write_text(
            '<h1 style="color:teal">Reviewed text</h1>'
            '<a href="/source">Citation</a>'
            '<img src="/photo.jpg" alt="Source photograph">')
        result = inventory(self.root, self.db_sha)
        self.assertEqual(result["css_to_review"], 1)
        self.assertEqual(result["html_to_review"], 1)
        self.assertEqual(result["blocked"], [])
        self.assertFalse(result["publish_authorized"])
        self.assertTrue(result["requires_human_output_review"])
        self.assertEqual(result["outside_output"], [])
        self.assertEqual(result["css_source_mismatches"], [])
        self.assertEqual(len(result["css_source_parity"]), len(COSMETIC_CSS))
        self.assertEqual(result["html_content_mismatches"], [])
        self.assertEqual(len(result["html_documentary_fidelity"]), 1)

    def test_noncosmetic_and_outside_changes_are_exposed(self):
        (self.root / "output/other.css").write_text("unexpected")
        (self.root / "README.txt").write_text("unrelated change")
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/other.css", result["blocked"])
        self.assertIn("README.txt", result["outside_output"])


    def test_exact_bytes_are_required_even_for_allowlisted_css(self):
        (self.root / "output/briefs.css").write_text("/* an unexpected override */")
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/briefs.css", result["css_source_mismatches"])
        self.assertNotIn("output/briefs.css", result["blocked"])
        self.assertFalse(next(x for x in result["css_source_parity"]
                              if x["generated"] == "output/briefs.css")["identical"])

    def test_missing_source_stylesheet_fails_parity(self):
        (self.root / "site/preview/home.css").unlink()
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/home.css", result["css_source_mismatches"])
        self.assertIn("site/preview/home.css", result["outside_output"])

    def test_missing_generated_css_fails_parity(self):
        (self.root / "output/relief.css").unlink()
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/relief.css", result["css_source_mismatches"])
        self.assertIn("output/relief.css", result["blocked"])


    def test_prose_or_byline_edits_cannot_ship_as_cosmetic(self):
        page = self.root / "output/index.html"
        page.write_text(page.read_text().replace("Reviewed text", "Altered analysis"))
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/index.html", result["html_content_mismatches"])
        self.assertIn("text", result["html_documentary_fidelity"][0]["changed_fields"])

    def test_citation_url_and_photo_attribution_are_protected(self):
        page = self.root / "output/index.html"
        page.write_text(page.read_text().replace('href="/source"', 'href="/incorrect"')
                        .replace('alt="Source photograph"', 'alt="Different credit"'))
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/index.html", result["html_content_mismatches"])
        self.assertIn("links", result["html_documentary_fidelity"][0]["changed_fields"])
        self.assertIn("media", result["html_documentary_fidelity"][0]["changed_fields"])

    def test_untracked_article_in_allowed_namespace_is_blocked(self):
        (self.root / "output/briefs").mkdir()
        (self.root / "output/briefs/new-unapproved.html").write_text("<p>New brief</p>")
        result = inventory(self.root, self.db_sha)
        self.assertIn("output/briefs/new-unapproved.html",
                      result["html_content_mismatches"])
        self.assertIn("missing-tracked-baseline",
                      next(x["changed_fields"] for x in result["html_documentary_fidelity"]
                           if x["path"] == "output/briefs/new-unapproved.html"))

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
