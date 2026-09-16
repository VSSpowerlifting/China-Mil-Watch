"""
Global Times body extraction — offline, against recorded fixtures.

Why this file exists
--------------------
Records 3432, 3946 and 3948 sat in the corpus with empty bodies and re-entered
the analysis queue on every run. Their pages were live and served 359, 3,969
and 2,113 characters of prose. The paper had moved its body markup: prose now
sits in `div.article_content > div.article_right` as bare text nodes separated
by `<br><br>`, and the only `<p>` elements are `class="picture"` captions. The
extractor looked for `<p>` inside `article_content`, found only captions,
correctly refused to treat a caption as a body — and returned nothing. An
extraction defect was therefore recorded as source silence, which C5 of
docs/DESK_STRENGTH_CRITERIA.md names as the inversion never to make.

Repairing that surfaced a second defect. On a flow-markup page the old fallback
swept every bare `<p>` on the page into the body, including the related-article
rail: 2,726 characters of other articles' first lines stored as this article's
body, against a real body of 797. That is worse than an empty body — an empty
body is a gap; this was other reporting attributed to the wrong document.

Fixtures were captured from www.globaltimes.cn on 2026-09-16 with the project
user agent. Nothing here makes a network request.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bs4 import BeautifulSoup                                    # noqa: E402

from scraper.sources.global_times_mil import (                   # noqa: E402
    GlobalTimesMilScraper, _flow_text, _inside_embed,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "global_times_mil"

#: The three records that were stored empty, and the page that was stored full
#: of other articles' text. Minimums are set below the measured value so a
#: harmless copy edit at the source does not fail the build, but far enough
#: above zero that the defect cannot come back unnoticed.
REPAIRED = {
    "flow_1368751_scs_patrols.html": 300,
    "flow_1370052_peace_train_opens.html": 2000,
    "flow_1370061_medical_team.html": 2300,
    "flow_1365233_missile_test.html": 700,
}
CONTROLS = ("control_1365253.html", "control_1365273.html",
            "control_1365291.html", "control_1365316.html")


def soup(name):
    return BeautifulSoup((FIXTURES / name).read_text(encoding="utf-8"), "lxml")


class TestFlowMarkupBodies(unittest.TestCase):
    """The repair: pages whose prose is text nodes and `<br>`."""

    def setUp(self):
        self.scraper = GlobalTimesMilScraper()

    def test_every_repaired_page_now_yields_its_prose(self):
        for name, minimum in REPAIRED.items():
            with self.subTest(page=name):
                text = self.scraper._extract_text(soup(name))
                self.assertGreaterEqual(
                    len(text), minimum,
                    "%s extracted %d characters; it was repaired to carry at "
                    "least %d" % (name, len(text), minimum))

    def test_paragraph_structure_survives_the_br_boundaries(self):
        text = self.scraper._extract_text(
            soup("flow_1370052_peace_train_opens.html"))
        self.assertGreater(len(text.split("\n")), 3,
                           "the body collapsed into a single run-on paragraph")

    def test_no_control_page_regressed(self):
        for name in CONTROLS:
            with self.subTest(page=name):
                self.assertGreater(
                    len(self.scraper._extract_text(soup(name))), 300)

    def test_extraction_is_deterministic(self):
        for name in list(REPAIRED) + list(CONTROLS):
            with self.subTest(page=name):
                self.assertEqual(self.scraper._extract_text(soup(name)),
                                 self.scraper._extract_text(soup(name)))


class TestCaptionsAreNotBodies(unittest.TestCase):
    """An image caption is not a sentence the paper published as its report."""

    def setUp(self):
        self.scraper = GlobalTimesMilScraper()

    def test_a_known_caption_is_absent_from_the_body(self):
        text = self.scraper._extract_text(
            soup("flow_1368751_scs_patrols.html"))
        self.assertNotIn("South China Sea Photo: VCG", text)

    def test_a_media_only_shell_yields_nothing(self):
        shell = ('<html><body><div class="article_content">'
                 '<div class="article_right"><center><img src="a.jpg"/>'
                 '</center><p class="picture">A caption long enough to pass '
                 'every length threshold in this module</p>'
                 '</div></div></body></html>')
        self.assertEqual(
            self.scraper._extract_text(BeautifulSoup(shell, "lxml")), "")

    def test_the_flow_helper_does_not_mutate_the_caller_s_soup(self):
        """`_extract_date` walks the same tree afterwards."""
        page = soup("flow_1370061_medical_team.html")
        before = len(page.find_all("img"))
        self.assertGreater(before, 0, "fixture carries no image to strip")
        _flow_text(page.find("div", class_="article_content"))
        self.assertEqual(len(page.find_all("img")), before,
                         "the shared soup was stripped in place")


class TestRelatedArticlesAreNotBodies(unittest.TestCase):
    """The second defect: other articles' text attributed to this one."""

    def setUp(self):
        self.scraper = GlobalTimesMilScraper()

    def test_teaser_text_is_absent_from_the_body(self):
        text = self.scraper._extract_text(
            soup("flow_1365233_missile_test.html"))
        for teaser in (
            "Children embrace various activities during summer vacation",
            "From the majestic skies above the capital",
        ):
            with self.subTest(teaser=teaser[:40]):
                self.assertNotIn(teaser, text)

    def test_the_body_is_the_article_itself(self):
        text = self.scraper._extract_text(
            soup("flow_1365233_missile_test.html"))
        self.assertTrue(text.startswith("The Chinese People's Liberation Army"))

    def test_the_embed_guard_recognises_a_related_rail(self):
        page = BeautifulSoup(
            '<div class="related_content"><p>inside</p></div>'
            '<div class="article_right"><p>outside</p></div>', "lxml")
        inside, outside = page.find_all("p")
        self.assertTrue(_inside_embed(inside))
        self.assertFalse(_inside_embed(outside))


class TestParagraphMarkupStillWins(unittest.TestCase):
    """Route 1 is unchanged, and still takes precedence."""

    def test_a_paragraph_body_is_extracted_by_the_original_route(self):
        page = ('<html><body><div class="article_content">'
                '<p>' + "A sentence of real reporting. " * 4 + '</p>'
                '<p>' + "A second paragraph of reporting. " * 4 + '</p>'
                '</div></body></html>')
        text = GlobalTimesMilScraper()._extract_text(
            BeautifulSoup(page, "lxml"))
        self.assertEqual(len(text.split("\n")), 2)
        self.assertIn("A sentence of real reporting.", text)

    def test_a_short_caption_paragraph_is_still_excluded(self):
        page = ('<html><body><div class="article_content">'
                '<p class="picture">' + "Caption text. " * 10 + '</p>'
                '<p>' + "Real reporting sentence. " * 4 + '</p>'
                '</div></body></html>')
        text = GlobalTimesMilScraper()._extract_text(
            BeautifulSoup(page, "lxml"))
        self.assertNotIn("Caption text.", text)
        self.assertIn("Real reporting sentence.", text)


if __name__ == "__main__":
    unittest.main()
