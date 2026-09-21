"""
PLA Daily body extraction across both article templates.

The defect (found 2026-09-20 while verifying the 2026-09-18/19 recovery
manifest). `_extract_text` looked for the content container as
`<ul class="row m-t-list">`. The ordinary article template is exactly that.
The multimedia template — the same one whose missing 发布 marker produced the
target-date defect — uses `<div class=" m-t-list">`, so every multimedia page
skipped the class-scoped paragraph path entirely and fell through to a
page-wide fallback that keeps only `<p>` longer than 30 characters.

A photo item's entire text is one short sentence plus a caption. Both are
under 30 characters. So `http://www.81.cn/bz_208549/16487441.html` — a page
carrying a real sentence and a real photo credit — extracted to the empty
string and would have been stored as a metadata-only shell claiming the
document had no usable text. The one paragraph on the page long enough to
survive the fallback is the copyright block, which is excluded by keyword; a
fix that reached that instead would look like success.

The repair is the container lookup, and nothing else. In particular the
paragraph join is left alone: the ordinary template's extracted text must come
out byte-identical, because it is what every stored PLA Daily body was built
from.

Offline: every page here is a recorded fixture. No network, no model calls.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper.sources.pla_daily import PLADailyScraper        # noqa: E402

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "pla_daily"
MULTIMEDIA_SHORT = "multimedia_short_paragraphs.html"
MULTIMEDIA_LONG = "multimedia_no_pubdate.html"
ORDINARY = "ordinary_with_pubdate.html"

COPYRIGHT_MARKER = "版权"        # 版权
EDITOR_MARKER = "责任编辑"   # 责任编辑


def scraper(target=date(2026, 9, 18)) -> PLADailyScraper:
    return PLADailyScraper(target_date=target)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def soup_for(name: str):
    return scraper().parse(fixture(name))


def old_extract_text(s: PLADailyScraper, soup) -> str:
    """The pre-fix implementation, verbatim except for the container lookup
    it is being compared against. Used to prove the ordinary template's
    output did not move."""
    content_ul = soup.find("ul", class_=lambda c: c and "m-t-list" in c)
    if content_ul:
        paras = content_ul.find_all("p", class_=lambda c: c and "ueditor" in c)
        if paras:
            return "\n".join(p.get_text(strip=True) for p in paras)
        text = content_ul.get_text(separator="\n", strip=True)
        if len(text) > 50:
            return text
    paragraphs = [
        p.get_text(strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(strip=True)) > 30
        and COPYRIGHT_MARKER not in p.get_text()
        and EDITOR_MARKER not in p.get_text()
    ]
    return "\n".join(paragraphs)


class TheMultimediaTemplateKeepsItsProse(unittest.TestCase):

    def setUp(self):
        self.s = scraper()
        self.soup = soup_for(MULTIMEDIA_SHORT)

    def test_the_fixture_still_reproduces_the_shape_that_broke(self):
        """If the recording stops matching the defect, the test is theatre."""
        self.assertIsNone(
            self.soup.find("ul", class_=lambda c: c and "m-t-list" in c),
            "the fixture no longer lacks a ul.m-t-list",
        )
        self.assertIsNotNone(
            self.soup.find("div", class_=lambda c: c and "m-t-list" in c)
        )
        prose = [
            p.get_text(strip=True) for p in self.soup.find_all("p")
            if p.get_text(strip=True)
            and COPYRIGHT_MARKER not in p.get_text()
        ]
        self.assertTrue(prose)
        self.assertTrue(
            all(len(p) <= 30 for p in prose),
            "every real paragraph must be under the fallback's 30-char floor, "
            "or this page would have survived the defect by accident",
        )

    def test_the_old_implementation_returned_nothing(self):
        self.assertEqual("", old_extract_text(self.s, self.soup))

    def test_the_body_is_no_longer_empty(self):
        self.assertNotEqual("", self.s._extract_text(self.soup).strip())

    def test_the_lede_sentence_is_present(self):
        meta = json.loads(
            (FIXTURES / "body_fixtures.json").read_text(encoding="utf-8")
        )[MULTIMEDIA_SHORT]
        text = self.s._extract_text(self.soup)
        self.assertIn("东部战区空军", text)   # 东部战区空军
        self.assertGreaterEqual(
            len(text.replace("\n", "")),
            meta["prose_paragraph_chars"] + meta["caption_paragraph_chars"],
        )

    def test_the_photo_caption_is_present(self):
        """The ordinary template already keeps captions; both must agree."""
        self.assertIn("图为", self.s._extract_text(self.soup))  # 图为

    def test_boilerplate_never_enters_the_body(self):
        text = self.s._extract_text(self.soup)
        self.assertNotIn(COPYRIGHT_MARKER, text)
        self.assertNotIn("Copyright", text)
        self.assertNotIn(EDITOR_MARKER, text)

    def test_title_and_date_are_untouched_by_this_change(self):
        self.assertEqual(
            "东部战区空军某部开展"
            "业务强化训练",
            self.s._extract_title(self.soup),
        )
        # No 发布 marker on this template: the date is the run's target date,
        # which is the 2026-09-20 target-date repair, not this one.
        self.assertEqual("2026-09-18", self.s._extract_date(self.soup))


class TheOrdinaryTemplateDidNotMove(unittest.TestCase):

    def test_extraction_is_byte_identical_to_the_old_implementation(self):
        s = scraper()
        soup = soup_for(ORDINARY)
        self.assertEqual(old_extract_text(s, soup), s._extract_text(soup))

    def test_it_still_uses_the_ul_container(self):
        soup = soup_for(ORDINARY)
        self.assertIsNotNone(
            soup.find("ul", class_=lambda c: c and "m-t-list" in c)
        )

    def test_a_long_paragraph_multimedia_page_did_not_move_either(self):
        """This page survived the defect because its one paragraph is long.
        The repair must not change what it already extracted correctly."""
        s = scraper()
        soup = soup_for(MULTIMEDIA_LONG)
        self.assertEqual(old_extract_text(s, soup), s._extract_text(soup))


class TheContainerLookupIsTolerantButNotGreedy(unittest.TestCase):

    def test_both_tag_shapes_resolve_to_a_container(self):
        for name in (ORDINARY, MULTIMEDIA_SHORT, MULTIMEDIA_LONG):
            with self.subTest(fixture=name):
                soup = soup_for(name)
                self.assertIsNotNone(
                    soup.find(["ul", "div"],
                              class_=lambda c: c and "m-t-list" in c),
                    "%s resolved no content container" % name,
                )

    def test_an_unrelated_container_class_is_not_matched(self):
        s = scraper()
        soup = s.parse(
            '<html><body><div class="m-t-listing-sidebar">'
            '<p class="ueditor-text-p_display">sidebar junk</p></div>'
            '<p class="ueditor-text-p_display">%s</p></body></html>'
            % ("x" * 40)
        )
        # 'm-t-list' is a substring of 'm-t-listing-sidebar', so the class
        # match is by token, not by substring.
        from scraper.sources.pla_daily import _is_content_container
        self.assertIsNone(
            soup.find(["ul", "div"], class_=_is_content_container),
            "a class merely CONTAINING the token was selected as the body",
        )
        self.assertNotIn("sidebar junk", s._extract_text(soup))

    def test_a_page_with_no_container_still_uses_the_page_wide_fallback(self):
        s = scraper()
        body = "测" * 60
        soup = s.parse(
            "<html><body><h2>t</h2><p>%s</p></body></html>" % body
        )
        self.assertEqual(body, s._extract_text(soup))

    def test_a_page_with_genuinely_no_prose_still_extracts_nothing(self):
        """An empty body remains a possible, honest answer."""
        s = scraper()
        soup = s.parse(
            '<html><body><h2>t</h2><div class="m-t-list">'
            '<p class="ueditor-paragraph-img"><img src="a.jpg"/></p>'
            "</div></body></html>"
        )
        self.assertEqual("", s._extract_text(soup).strip())


class TheRecoveredDocumentParsesEndToEnd(unittest.TestCase):

    def test_parse_article_returns_a_usable_document(self):
        s = scraper()
        meta = json.loads(
            (FIXTURES / "body_fixtures.json").read_text(encoding="utf-8")
        )[MULTIMEDIA_SHORT]
        art = s.parse_article(meta["url"], fixture(MULTIMEDIA_SHORT))
        self.assertIsNotNone(art)
        self.assertEqual(meta["url"], art["url"])
        self.assertEqual("pla_daily", art["source_slug"])
        self.assertEqual("2026-09-18", art["published_date"])
        self.assertTrue(art["title_original"])
        self.assertTrue(
            art["text_original"].strip(),
            "the document that exposed the defect must now carry text",
        )


if __name__ == "__main__":
    unittest.main()
