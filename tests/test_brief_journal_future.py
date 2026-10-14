"""Future Briefs inherit the permanent article system without publication."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from bs4 import BeautifulSoup

from core import brief_collection as bc, brief_cover as bcv
from core.brief_presentation import validate_presentation, presentation_html_errors
from core.brief_source_linked import manuscript_html_errors, validate_source_linked
from core.desk_registry import load_registry
from tests import brief_journal_fixtures as fixtures


class FutureJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="ipr-journal-future-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.out = Path(cls.temporary.name) / "site"
        cls.routes = fixtures.build_private_fixtures(cls.out)
        cls.pages = {route: BeautifulSoup((cls.out / route).read_text(), "html.parser")
                     for route in cls.routes}

    def page(self, slug):
        return self.pages[bc.brief_route(slug)]

    def test_five_variants_use_same_actual_stylesheet_and_navigation(self):
        self.assertEqual(len(self.routes), 5)
        self.assertEqual((self.out / "briefs.css").read_bytes(),
                         (fixtures.ROOT / "site/preview/briefs.css").read_bytes())
        for route, page in self.pages.items():
            with self.subTest(route=route):
                self.assertEqual(len(page.select('link[rel="stylesheet"][href="../briefs.css"]')), 1)
                self.assertIsNotNone(page.select_one("main.brief-page"))
                navigation = page.select_one("details.brief-reading-navigation")
                self.assertIsNotNone(navigation)
                self.assertIsNotNone(navigation.select_one('nav[aria-label="In this brief"]'))
                # Every section link has exactly one real target. This protects
                # future optional anatomy and the source-linked presentation.
                for link in navigation.select('a[href^="#"]'):
                    self.assertEqual(len(page.select('[id="%s"]' % link["href"][1:])), 1)
                self.assertIsNotNone(page.select_one('meta[name="robots"][content*="noindex"]'))
                self.assertIsNotNone(page.select_one(".brief-fixture"))
                for css in page.select('link[rel="stylesheet"]'):
                    if not css["href"].startswith("http"):
                        self.assertTrue((self.out / route).parent.joinpath(css["href"]).is_file())
        self.assertFalse((self.out / "sitemap.xml").exists())

    def test_granted_photo_keeps_exact_pixels_and_provenance(self):
        page = self.page(fixtures.PHOTO_SLUG)
        figure = page.select_one('[data-article-media="photograph"]')
        self.assertIsNotNone(figure)
        self.assertIsNone(page.select_one('[data-article-media="plate"]'))
        image = figure.select_one("img")
        emitted = (self.out / "briefs" / image["src"]).resolve()
        source = fixtures.ROOT / image["src"].replace("../", "site/", 1)
        self.assertEqual(emitted.read_bytes(), source.read_bytes())
        self.assertIn("Photo:", figure.get_text())
        self.assertIn("Cropped and resized by IPR", figure.get_text())
        self.assertTrue(figure.select("figcaption a[href^='https://']"))

    def test_no_photo_uses_labelled_artwork_and_short_omits_optional_extras(self):
        page = self.page("fixture-journal-no-photograph")
        self.assertIsNone(page.select_one('[data-article-media="photograph"]'))
        plate = page.select_one('[data-article-media="plate"]')
        self.assertIsNotNone(plate)
        self.assertIn("Editorial plate", plate.get_text())
        short = self.page("fixture-journal-short")
        for selector in ("#s-term", ".brief-signal", "#s-external", "#reading-finding", "#reading-evidence", '[aria-label="Research contributor"]'):
            self.assertIsNone(short.select_one(selector), selector)
        self.assertIsNotNone(short.select_one("#s-development"))
        self.assertIsNotNone(short.select_one("#s-sources"))

    def test_long_cross_desk_body_is_not_truncated(self):
        page = self.page("fixture-journal-long-cross-desk")
        original = fixtures.fixture_records()["fixture-journal-long-cross-desk"]
        self.assertEqual(page.select_one("h1").get_text(strip=True), original["title"])
        self.assertGreater(len(page.select("#s-stood-out p")), 12)
        for claim in original["cross_desk_claims"]:
            for paragraph in bc.paragraphs(claim["claim"]):
                self.assertIn(paragraph, page.select_one("#s-compare").get_text())

    def test_source_linked_draft_is_unnumbered_and_exact_manuscript_is_preserved(self):
        page = self.page(fixtures.SOURCE_SLUG)
        article = fixtures.fixture_records()[fixtures.SOURCE_SLUG]
        html = str(page)
        self.assertIsNone(article["issue_number"])
        self.assertNotIn("approval", article)
        self.assertIsNone(page.select_one(".ed-no"))
        self.assertIn("unapproved, unnumbered and unpublished", page.get_text())
        self.assertEqual(manuscript_html_errors(article, html), [])
        manifest = fixtures.reviewed_presentation(article)
        self.assertEqual(presentation_html_errors(manifest, html), [])
        self.assertIsNone(page.select_one('[data-article-media="photograph"]'))
        self.assertIsNone(page.select_one('[data-article-media="plate"]'))
        self.assertIsNotNone(page.select_one("#s-publishers"))
        self.assertIsNotNone(page.select_one("#reading-finding"))
        self.assertEqual(len(page.select("[data-manuscript-paragraph]")), len(article["body_paragraphs"]))

    def test_changed_presentation_approval_or_manuscript_fails_real_contract(self):
        article = fixtures.fixture_records()[fixtures.SOURCE_SLUG]
        approved = fixtures.reviewed_presentation(article)
        self.assertEqual(validate_presentation(approved, article, slug=fixtures.SOURCE_SLUG), [])
        for field, value in (("fingerprint", "0" * 64), ("checks", {})):
            changed = copy.deepcopy(approved)
            changed["approval"][field] = value
            self.assertTrue(validate_presentation(changed, article, slug=fixtures.SOURCE_SLUG))
        changed = copy.deepcopy(article)
        changed["body_paragraphs"][0][0]["text"] += " Synthetic unreviewed addition."
        self.assertTrue(any("binding is stale" in e for e in validate_presentation(approved, changed, slug=fixtures.SOURCE_SLUG)))
        real = json.loads((fixtures.ROOT / "briefs/what-is-being-built-in-laos.json").read_text())
        self.assertEqual(validate_source_linked(real, release=True), [])
        real["body_paragraphs"][0][0]["text"] += " Synthetic unreviewed addition."
        self.assertTrue(any("exact-version" in e for e in validate_source_linked(real, release=True)))

    def test_changed_media_digest_is_refused_by_real_cover_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = fixtures.stage_cover(root)
            self.assertIsNotNone(bcv.brief_cover(fixtures.PHOTO_SLUG, root, manifest=[entry]))
            image = root / bcv.EDITORIAL_ROOT / entry["derivatives"][0]["file"]
            image.write_bytes(b"private test tampering")
            self.assertIsNone(bcv.brief_cover(fixtures.PHOTO_SLUG, root, manifest=[entry]))

    def test_fixture_publication_and_export_safety_gates_remain_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            briefs = Path(directory)
            records = fixtures.fixture_records()
            (briefs / (fixtures.PHOTO_SLUG + ".json")).write_text(json.dumps(records[fixtures.PHOTO_SLUG]))
            with self.assertRaisesRegex(bc.CollectionError, "synthetic"):
                bc.load_collection([], load_registry(), briefs_dir=briefs)
            # Source-linked manuscripts have no synthetic shortcut: their
            # actual draft status remains withheld by the ordinary loader.
            (briefs / (fixtures.SOURCE_SLUG + ".json")).write_text(json.dumps(records[fixtures.SOURCE_SLUG]))
            private = bc.load_collection([], load_registry(), briefs_dir=briefs, allow_synthetic=True)
            self.assertIn(fixtures.SOURCE_SLUG, private.withheld)
            self.assertNotIn(fixtures.SOURCE_SLUG, private.sidecars)
            with self.assertRaisesRegex(SystemExit, "synthetic|origin"):
                fixtures.gp.build(briefs / "rejected-site", fixtures.gp.PUBLIC_TITLE,
                                  fixtures.ROOT / "pla_watch.db", briefs_dir=briefs,
                                  allow_synthetic_briefs=True,
                                  site_origin=fixtures.gp.LIVE_BASE)
            self.assertFalse((briefs / "rejected-site").exists())
            for destination in (fixtures.ROOT, fixtures.ROOT.parent,
                                fixtures.ROOT / "output",
                                fixtures.ROOT / "briefs/private-fixture",
                                fixtures.ROOT / "docs/private-fixture"):
                with self.subTest(destination=destination):
                    existed = destination.exists()
                    with self.assertRaisesRegex(ValueError, "fixture"):
                        fixtures.build_private_fixtures(destination)
                    self.assertEqual(destination.exists(), existed)
