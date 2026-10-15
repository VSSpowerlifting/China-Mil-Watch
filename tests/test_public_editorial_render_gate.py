"""A real published Brief must cite exact government originals to activate desk."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.guard_public_editorial_research import RenderHold, verify_render, validate_editorial_manuscripts
from core.public_editorial_research import load_catalog
from datetime import date
import copy
from tests.test_public_editorial_research import fixture

ROOT = Path(__file__).resolve().parents[1]


class RenderedPermanentResearchContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "briefs").mkdir()
        self.row = fixture()["entries"][0]
        self.src = self.row["source_links"][0]["publisher_url"]

    def build(self, *, cite=True, list_publication=True, status=True):
        body = '<a href="' + self.src + '">Read the ministry original</a>' if cite else "unreferenced"
        (self.root / self.row["ipr_page"]).write_text(
            "<html><main>" + body + "</main></html>", encoding="utf-8")
        source_link = '<a href="' + self.src + '">Original</a>'
        brief_link = ('<a href="' + self.row["ipr_page"] + '">IPR</a>'
                      if list_publication else "")
        heading = ('<section aria-labelledby="ipr-published-research-heading">'
                   if status else '<section>')
        (self.root / "indonesia.html").write_text(
            heading + "not a production source-text archive"
            + brief_link + source_link + "</section>", encoding="utf-8")

    def test_all_published_links_and_original_citations_are_checked(self):
        self.build()
        result = verify_render(self.root, [self.row])
        self.assertEqual(result["approved_ipr_publications"], 1)
        self.assertEqual(result["linked_originals"], 1)
        self.assertFalse(result["private_original_custody_verified_by_this_index"])

    def test_missing_brief_or_omitted_source_never_passes(self):
        self.build()
        (self.root / self.row["ipr_page"]).unlink()
        with self.assertRaises(RenderHold):
            verify_render(self.root, [self.row])
        self.build(cite=False)
        with self.assertRaises(RenderHold):
            verify_render(self.root, [self.row])

    def test_unlisted_article_or_missing_permanent_heading_fails(self):
        self.build(list_publication=False)
        with self.assertRaises(RenderHold):
            verify_render(self.root, [self.row])
        self.build(status=False)
        with self.assertRaises(RenderHold):
            verify_render(self.root, [self.row])

    def test_missing_html_or_accidental_archive_link_fails(self):
        self.build()
        (self.root / "indonesia.html").unlink()
        with self.assertRaises(RenderHold):
            verify_render(self.root, [self.row])
        self.build()
        with (self.root / "indonesia.html").open("a") as f:
            f.write('<a href="archive.html?desk=indonesia">Unapproved corpus</a>')
        with self.assertRaises(RenderHold):
            verify_render(self.root, [self.row])

    def test_real_vietnam_no18_editorial_approval_and_all_originals_are_pinned(self):
        genuine = load_catalog(today=date(2026, 10, 15))
        self.assertEqual(validate_editorial_manuscripts(genuine), 1)
        self.assertEqual(len(genuine[0]["source_links"]), 3)

    def test_forged_editor_or_original_title_cannot_pass_source_approval_gate(self):
        approved = load_catalog(today=date(2026, 10, 15))
        for key, value in (("approved_by", "Fabricated Editor"),
                           ("approved_on", "2026-10-14")):
            altered = copy.deepcopy(approved)
            altered[0][key] = value
            with self.subTest(key=key), self.assertRaises(RenderHold):
                validate_editorial_manuscripts(altered)
        changed = copy.deepcopy(approved)
        changed[0]["source_links"][0]["title_original"] = "Unverified original"
        with self.assertRaises(RenderHold):
            validate_editorial_manuscripts(changed)
        changed = copy.deepcopy(approved)
        changed[0]["source_links"][0]["publisher_date"] = "2026-10-09"
        with self.assertRaises(RenderHold):
            validate_editorial_manuscripts(changed)

    def test_empty_manifest_does_not_invent_a_published_article(self):
        result = verify_render(self.root, [])
        self.assertEqual(result["approved_ipr_publications"], 0)
        self.assertFalse(result["source_bodies_rehosted_by_this_index"])

    def test_site_template_official_links_and_publication_are_separate(self):
        template = (ROOT/"site/preview/templates/desk.html").read_text()
        renderer = (ROOT/"site/preview/generate_preview.py").read_text()
        self.assertIn("published_research | default([])", template)
        self.assertIn("IPR research published — official originals linked", template)
        self.assertIn("paper.source_links", template)
        self.assertIn("rel=\"noopener noreferrer\"", template)
        self.assertNotIn("<img", template.split('{# A permanent publication')[1].split("{# Public Korea")[0])
        self.assertIn("load_editorial_catalog()", renderer)
        self.assertIn("published_research=published_research", renderer)
        self.assertIn("published_research=[]", renderer)
        directory = (ROOT/"site/preview/templates/desks.html").read_text()
        self.assertIn("Research published", directory)
        self.assertIn("Corpus records", directory)
        self.assertIn("editorial_published_desks", directory)
        self.assertIn("editorial_published_desks", renderer)

if __name__ == "__main__":
    unittest.main()
