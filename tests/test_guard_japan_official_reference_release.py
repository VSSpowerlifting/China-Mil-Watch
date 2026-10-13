"""Offline regression tests for the generated Japan 13-link release contract."""
import unittest
from pathlib import Path

from scripts.guard_japan_official_reference_release import (
    JCG_LINKS, MOD_LINKS, REQUIRED_TEXT, validate_japan_release_html,
)


def example_html():
    lines = ['<html><body><section>']
    lines.extend("<p>" + phrase + "</p>" for phrase in REQUIRED_TEXT)
    for url in JCG_LINKS + MOD_LINKS:
        lines.append('<a href="' + url
                     + '" rel="noopener noreferrer">Official document</a>')
    lines.append("</section></body></html>")
    return "\n".join(lines)


class JapanOfficialReferenceReleaseTests(unittest.TestCase):
    def test_all_thirteen_exact_reviewed_links_pass(self):
        self.assertEqual(len(JCG_LINKS), 6)
        self.assertEqual(len(MOD_LINKS), 7)
        self.assertIn("https://www.mod.go.jp/j/press/news/2026/09/17a.pdf", MOD_LINKS)
        self.assertIn("https://www.mod.go.jp/j/press/news/2026/09/29d.pdf", MOD_LINKS)
        self.assertNotIn("https://www.mod.go.jp/j/press/news/2026/10/02b.pdf", MOD_LINKS)
        self.assertEqual(validate_japan_release_html(example_html()), [])

    def test_missing_reference_fails_closed(self):
        html = example_html().replace(
            '<a href="' + MOD_LINKS[-1]
            + '" rel="noopener noreferrer">Official document</a>', "")
        self.assertTrue(any(MOD_LINKS[-1] in error for error
                            in validate_japan_release_html(html)))

    def test_duplicates_fail_closed(self):
        extra = '<a href="' + JCG_LINKS[0] + '" rel="noopener noreferrer">Again</a>'
        self.assertTrue(any("found 2" in error for error
                            in validate_japan_release_html(example_html() + extra)))

    def test_unreviewed_mod_pdf_fails_closed(self):
        extra = ('<a href="https://www.mod.go.jp/j/press/news/2026/10/09z.pdf"'
                 ' rel="noopener noreferrer">Unreviewed</a>')
        self.assertTrue(any("Unreviewed" in error for error
                            in validate_japan_release_html(example_html() + extra)))

    def test_outbound_link_protection_is_required(self):
        html = example_html().replace('rel="noopener noreferrer"', 'rel="noopener"', 1)
        self.assertTrue(any("Missing external-link protection" in error
                            for error in validate_japan_release_html(html)))

    def test_shadow_status_qualification_is_required(self):
        html = example_html().replace("All Japan production records remain held", "Ready")
        self.assertTrue(any("qualification" in error
                            for error in validate_japan_release_html(html)))

    def test_image_only_exception_scope_cannot_disappear(self):
        for phrase in ("Visual original review only: no extractable PDF text layer",
                       "No extractable text layer; not eight independent archive originals",
                       "The oversized October 2 original remains intentionally excluded."):
            with self.subTest(phrase=phrase):
                self.assertTrue(any("qualification" in error for error in
                    validate_japan_release_html(example_html().replace(phrase, "REDACTED"))))

    def test_template_cites_two_new_undelivered_originals_and_holds_oversized(self):
        template = (Path(__file__).resolve().parents[1] /
                    "site/preview/templates/desk.html").read_text(encoding="utf-8")
        for url in MOD_LINKS:
            self.assertEqual(template.count('href="' + url + '"'), 1)
        self.assertNotIn('href="https://www.mod.go.jp/j/press/news/2026/10/02b.pdf"', template)
        self.assertIn("Seven independently inspected original Ministry PDFs", template)
        self.assertIn("Five are text-bearing shadow source originals", template)
        self.assertIn("visual original review only", template.lower())
        self.assertIn("not machine-extracted records", template.lower())
        self.assertIn("seven reviewed Japanese PDFs", template)

    def test_no_embedded_shadow_body_or_archive_link(self):
        for marker in ('state/shadow.db', 'text_original',
                       'href="archive.html?desk=japan"'):
            with self.subTest(marker=marker):
                self.assertTrue(any("boundary violated" in error for error
                                    in validate_japan_release_html(example_html() + marker)))


if __name__ == "__main__":
    unittest.main()
