"""
PLA Daily: the publication date a run falls back to.

`_extract_date()` reads 发布 from the article page. When the page does not
carry it, the adapter has to choose a date anyway — and it used to choose
`date.today()`, the wall clock.

On an ordinary same-day run the wall clock and the requested date are the same,
which is why that stood unnoticed for a long time. They diverge the moment a
run is given an explicit `--date`, and that is exactly when the fallback
matters. Rehearsing the recovery of 2026-09-18 stamped 7 of its 10 PLA Daily
records `2026-09-19`, the day the recovery happened to execute.

This is not a malformed-page edge case. 81.cn serves multimedia items
(多媒体稿件) from a template with no `artichle-info` div and no 发布 marker
anywhere on the page, so the fallback fires for ordinary production traffic.
Both fixtures here are trimmed recordings of real pages: one of each template.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper.sources import pla_daily                          # noqa: E402
from scraper.sources.pla_daily import PLADailyScraper          # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "pla_daily"
MULTIMEDIA = "multimedia_no_pubdate.html"
ORDINARY = "ordinary_with_pubdate.html"

URL = "http://www.81.cn/fyr/16487250.html"


def fixture(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def scraper(target: date) -> PLADailyScraper:
    return PLADailyScraper(target_date=target)


class ExplodingDate(date):
    """A `date` whose `today()` is a test failure rather than a value."""

    @classmethod
    def today(cls):
        raise AssertionError(
            "_extract_date consulted the wall clock; it must use target_date")


class TheFixturesCarryWhatTheTestsClaim(unittest.TestCase):
    """Guard the evidence, so nothing below can pass vacuously."""

    def test_the_multimedia_page_really_has_no_publication_date(self):
        html = fixture(MULTIMEDIA)
        self.assertNotIn("artichle-info", html)
        self.assertNotIn("发布", html)

    def test_the_ordinary_page_really_has_one(self):
        html = fixture(ORDINARY)
        self.assertIn("artichle-info", html)
        self.assertIn("发布", html)

    def test_the_recording_metadata_agrees(self):
        meta = json.loads((FIX / "fixtures.json").read_text(encoding="utf-8"))
        self.assertFalse(meta[MULTIMEDIA]["has_publication_marker"])
        self.assertTrue(meta[ORDINARY]["has_publication_marker"])


class TheFallbackUsesTheTargetDate(unittest.TestCase):

    def test_multimedia_template_falls_back_to_the_requested_date(self):
        rec = scraper(date(2026, 9, 18)).parse_article(URL, fixture(MULTIMEDIA))
        self.assertEqual(rec["published_date"], "2026-09-18")

    def test_a_different_requested_date_gives_a_different_answer(self):
        # The fallback tracks the request, not a constant.
        for d in ("2026-09-17", "2026-09-18", "2026-01-02"):
            with self.subTest(d):
                rec = scraper(date.fromisoformat(d)).parse_article(
                    URL, fixture(MULTIMEDIA))
                self.assertEqual(rec["published_date"], d)

    def test_absent_date_metadata_does_not_stamp_the_execution_date(self):
        # The defect, stated as a test: a 2026-09-18 recovery must not produce
        # a record dated whenever the recovery happened to run.
        rec = scraper(date(2026, 9, 18)).parse_article(URL, fixture(MULTIMEDIA))
        self.assertNotEqual(rec["published_date"], date.today().isoformat())
        self.assertEqual(rec["published_date"], "2026-09-18")

    def test_malformed_date_metadata_also_falls_back_to_the_target(self):
        html = ("<h1>t</h1><div class='container artichle-info'>"
                "<p>发布：not-a-date</p></div><ul class='row m-t-list'>"
                "<p class='ueditor-text-p_display'>body text</p></ul>")
        rec = scraper(date(2026, 9, 18)).parse_article(URL, html)
        self.assertEqual(rec["published_date"], "2026-09-18")


class AParsedDateStillWins(unittest.TestCase):

    def test_the_ordinary_template_uses_the_pages_own_date(self):
        # Requested date deliberately differs from the page's 发布 date.
        rec = scraper(date(2026, 1, 1)).parse_article(URL, fixture(ORDINARY))
        self.assertEqual(rec["published_date"], "2026-09-18")

    def test_the_parsed_date_wins_for_every_requested_date(self):
        for d in (date(2026, 1, 1), date(2026, 9, 18), date(2030, 12, 31)):
            with self.subTest(d):
                rec = scraper(d).parse_article(URL, fixture(ORDINARY))
                self.assertEqual(rec["published_date"], "2026-09-18")

    def test_the_secondary_marker_branch_still_wins(self):
        # No artichle-info div, but 发布 appears in the page text.
        html = ("<h1>t</h1><p>发布：2026-07-04 08:00:00</p>"
                "<ul class='row m-t-list'>"
                "<p class='ueditor-text-p_display'>body</p></ul>")
        rec = scraper(date(2026, 9, 18)).parse_article(URL, html)
        self.assertEqual(rec["published_date"], "2026-07-04")


class TheWallClockIsNeverConsulted(unittest.TestCase):
    """A timezone roll or a slow run must not change an explicit-date run."""

    def setUp(self):
        self.real = pla_daily.date
        pla_daily.date = ExplodingDate
        self.addCleanup(lambda: setattr(pla_daily, "date", self.real))

    def test_the_fallback_does_not_call_today(self):
        rec = scraper(date(2026, 9, 18)).parse_article(URL, fixture(MULTIMEDIA))
        self.assertEqual(rec["published_date"], "2026-09-18")

    def test_the_parsed_branch_does_not_call_today_either(self):
        rec = scraper(date(2026, 9, 18)).parse_article(URL, fixture(ORDINARY))
        self.assertEqual(rec["published_date"], "2026-09-18")

    def test_repeated_extraction_is_stable(self):
        s = scraper(date(2026, 9, 18))
        first = s.parse_article(URL, fixture(MULTIMEDIA))["published_date"]
        for _ in range(5):
            self.assertEqual(
                s.parse_article(URL, fixture(MULTIMEDIA))["published_date"], first)


class OrdinarySameDayBehaviourIsUnchanged(unittest.TestCase):
    """`BaseScraper` defaults `target_date` to today, so a default-constructed
    run falls back to exactly the value the old code produced."""

    def test_a_default_scraper_targets_today(self):
        self.assertEqual(PLADailyScraper().target_date, date.today())

    def test_the_fallback_on_a_default_scraper_is_todays_date(self):
        rec = PLADailyScraper().parse_article(URL, fixture(MULTIMEDIA))
        self.assertEqual(rec["published_date"], date.today().isoformat())

    def test_an_explicit_today_matches_a_default_scraper(self):
        a = PLADailyScraper().parse_article(URL, fixture(MULTIMEDIA))
        b = scraper(date.today()).parse_article(URL, fixture(MULTIMEDIA))
        self.assertEqual(a["published_date"], b["published_date"])


class IdentityAndExtractionAreUntouched(unittest.TestCase):
    """The change is to one fallback value and nothing else."""

    def test_the_url_passes_through_unchanged(self):
        for name in (MULTIMEDIA, ORDINARY):
            with self.subTest(name):
                rec = scraper(date(2026, 9, 18)).parse_article(URL, fixture(name))
                self.assertEqual(rec["url"], URL)
                self.assertEqual(rec["source_slug"], "pla_daily")

    def test_titles_are_what_the_pages_say(self):
        s = scraper(date(2026, 9, 18))
        self.assertEqual(
            s.parse_article(URL, fixture(MULTIMEDIA))["title_original"],
            "中国海警局新闻发言人就菲船只碰撞我海警艇发表谈话")
        self.assertEqual(
            s.parse_article(URL, fixture(ORDINARY))["title_original"],
            "军营观察丨“观天哨兵”托举战鹰高飞远航")

    def test_body_extraction_is_unaffected_by_the_requested_date(self):
        a = scraper(date(2026, 1, 1)).parse_article(URL, fixture(ORDINARY))
        b = scraper(date(2030, 6, 6)).parse_article(URL, fixture(ORDINARY))
        self.assertEqual(a["text_original"], b["text_original"])
        self.assertGreater(len(a["text_original"]), 1000)

    def test_the_multimedia_body_is_still_short_but_present(self):
        rec = scraper(date(2026, 9, 18)).parse_article(URL, fixture(MULTIMEDIA))
        self.assertTrue(rec["text_original"].strip())

    def test_a_titleless_page_is_still_refused(self):
        self.assertIsNone(
            scraper(date(2026, 9, 18)).parse_article(URL, "<p>no heading</p>"))

    def test_url_recognition_is_unchanged(self):
        self.assertTrue(pla_daily._is_article_url("http://www.81.cn/fyr/16487250.html"))
        self.assertFalse(pla_daily._is_article_url("http://www.81.cn/fyr/index.html"))


if __name__ == "__main__":
    unittest.main()
