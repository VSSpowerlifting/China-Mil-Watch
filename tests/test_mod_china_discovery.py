"""
MOD China discovery-window tests.

Regression cover for the second half of the 2026-08-17 defect: discovery kept
a listing link only when the run date appeared verbatim in the link text, so an
item was collectable on exactly one calendar day and never again. MOD routinely
posts an item a day or three after the date it stamps on it, and every such item
was invisible when stamped (not yet published) and ignored afterwards (no longer
today). Discovery now accepts the seven calendar dates ending on target_date.

Offline: listing HTML is a local fixture, `fetch` is stubbed, no network, no
model calls. The database used by the storage-contract test is a temporary
file; the tracked pla_watch.db is never opened.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper.sources.mod_china import (                          # noqa: E402
    _LOOKBACK_DATES, MODChinaScraper, _anchor_publication_date,
    _parse_listing_date, _stamp_node,
)

TARGET = date(2026, 8, 17)
WINDOW_START = date(2026, 8, 11)          # seven calendar dates, inclusive


def listing(*rows) -> str:
    """
    Build a listing page in MOD's real shape.

    Verified against 71 archived listing documents: the headline sits in
    <p class="title"> and the publication stamp in its own
    <small class="time hidden-xs"> element, reading "YYYY-MM-DD HH:MM". Each row
    is (href, title, stamp-text); pass "" for an anchor with an empty stamp.
    """
    links = "".join(
        f'<li><a href="{href}"><h3><p class="title">{title}</p>'
        f'<small class="time hidden-xs">{stamp}</small></h3></a></li>'
        for href, title, stamp in rows
    )
    return f"<html><body><ul>{links}</ul></body></html>"


def flat_listing(*rows) -> str:
    """
    A listing with NO stamp element — headline and stamp flattened into one
    string, the shape the text fallback has to cope with.
    """
    links = "".join(
        f'<li><a href="{href}">{text}</a></li>' for href, text in rows
    )
    return f"<html><body><ul>{links}</ul></body></html>"


class _StubbedScraper(MODChinaScraper):
    """MODChinaScraper with `fetch` replaced by a fixture lookup."""

    def __init__(self, page: str, target_date: date = TARGET) -> None:
        super().__init__(target_date=target_date)
        self._page = page
        self.fetched: list[str] = []

    def fetch(self, url: str, force_refresh: bool = False):
        self.fetched.append(url)
        return self._page


class TestWindowBoundaries(unittest.TestCase):
    """Requirement 4: the window includes its oldest and newest dates."""

    def test_window_is_seven_calendar_dates(self):
        self.assertEqual(_LOOKBACK_DATES, 7)
        self.assertEqual((TARGET - WINDOW_START).days, 6)

    def test_oldest_and_newest_boundary_dates_are_included(self):
        page = listing(
            ("/gfbw/wzll/hj/1.html", "最旧边界", "2026-08-11 09:00"),   # oldest in window
            ("/gfbw/wzll/hj/2.html", "最新边界", "2026-08-17 21:19"),   # newest = target
        )
        urls = _StubbedScraper(page).get_article_urls()
        self.assertIn("http://www.mod.gov.cn/gfbw/wzll/hj/1.html", urls)
        self.assertIn("http://www.mod.gov.cn/gfbw/wzll/hj/2.html", urls)

    def test_the_day_before_the_window_is_excluded(self):
        page = listing(("/gfbw/wzll/hj/3.html", "窗口外", "2026-08-10 23:59"))
        self.assertEqual(_StubbedScraper(page).get_article_urls(), [])

    def test_boundary_moves_with_target_date(self):
        page = listing(("/gfbw/wzll/hj/4.html", "标题", "2026-08-11 00:01"))
        self.assertEqual(len(_StubbedScraper(page, date(2026, 8, 17)).get_article_urls()), 1)
        self.assertEqual(len(_StubbedScraper(page, date(2026, 8, 18)).get_article_urls()), 0)


class TestBackdatedDiscovery(unittest.TestCase):
    """Requirement 5: a three-day-backdated item is discovered."""

    def test_three_day_backdated_item_is_found(self):
        page = listing(("/gfbw/wzll/hj/16474422.html", "暗夜“猎鲨”", "2026-08-14 10:30"))
        urls = _StubbedScraper(page, TARGET).get_article_urls()
        self.assertEqual(urls, ["http://www.mod.gov.cn/gfbw/wzll/hj/16474422.html"])

    def test_the_old_same_day_rule_would_have_missed_it(self):
        """Documents the defect: exact-match discovery finds nothing here."""
        page = listing(("/gfbw/wzll/hj/16474422.html", "暗夜“猎鲨”", "2026-08-14 10:30"))
        self.assertNotIn(TARGET.isoformat(), page)
        self.assertEqual(len(_StubbedScraper(page, TARGET).get_article_urls()), 1)


class TestExclusions(unittest.TestCase):
    """Requirement 6: older, future and malformed dates are excluded."""

    def test_future_dated_item_is_excluded(self):
        page = listing(("/gfbw/wzll/hj/5.html", "未来", "2026-08-18 08:00"))
        self.assertEqual(_StubbedScraper(page).get_article_urls(), [])

    def test_far_older_item_is_excluded(self):
        page = listing(("/gfbw/wzll/hj/6.html", "去年", "2025-08-17 08:00"))
        self.assertEqual(_StubbedScraper(page).get_article_urls(), [])

    def test_malformed_and_absent_dates_are_excluded(self):
        page = listing(
            ("/gfbw/wzll/hj/7.html", "不存在的日期", "2026-13-45 10:00"),
            ("/gfbw/wzll/hj/8.html", "二月三十", "2026-02-30 10:00"),
            ("/gfbw/wzll/hj/9.html", "无日期", ""),
        )
        self.assertEqual(_StubbedScraper(page).get_article_urls(), [])

    def test_parse_listing_date_rejects_impossible_dates(self):
        self.assertIsNone(_parse_listing_date("标题2026-13-45 10:00"))
        self.assertIsNone(_parse_listing_date("标题2026-02-30 10:00"))
        self.assertIsNone(_parse_listing_date("标题"))
        self.assertIsNone(_parse_listing_date(""))
        self.assertEqual(_parse_listing_date("标题2026-08-17 15:00"), date(2026, 8, 17))

    def test_non_article_urls_are_ignored(self):
        page = listing(
            ("/gfbw/wzll/hj/index.html", "栏目页", "2026-08-17 10:00"),
            ("http://www.81.cn/yw_208727/1.html", "站外", "2026-08-17 10:00"),
        )
        self.assertEqual(_StubbedScraper(page).get_article_urls(), [])


class TestTerminalStampContract(unittest.TestCase):
    """
    The publication date comes from the terminal metadata stamp, never from a
    date sitting inside the headline.

    Contract verified against every listing document held locally — 10 archived
    cache dates plus the six sections fetched 2026-08-17; 71 documents, 2,850
    article anchors:

      * 1,980 anchors carry the stamp in its own <small class="time hidden-xs">
        element, and all 1,980 read exactly "YYYY-MM-DD HH:MM";
      * no date-only stamp occurs anywhere in the archive;
      * no anchor has non-whitespace content after its stamp;
      * the other 870 anchors have no stamp element and no terminal stamp in
        their text either, and were already being dropped.

    Two earlier rules failed on this. Taking the FIRST date read
    "回顾2020-01-01演习2026-08-14 15:00" as 2020-01-01. Taking the LAST date
    candidate fixed that one case but not the class of case: "回顾2026-08-14演习"
    and "回顾2026-08-14演习纪要" carry no stamp at all, yet both still returned
    2026-08-14, because a date in the prose was the last candidate present.
    """

    # ── the two cases that motivated this remediation ────────────────────────

    def test_headline_date_with_trailing_prose_and_no_stamp(self):
        self.assertIsNone(_parse_listing_date("回顾2026-08-14演习纪要"))

    def test_headline_date_not_in_the_observed_metadata_form(self):
        self.assertIsNone(_parse_listing_date("回顾2026-08-14演习"))
        self.assertIsNone(_parse_listing_date("回顾2026-08-14"))

    # ── the accepted form ────────────────────────────────────────────────────

    def test_valid_terminal_stamp_is_parsed(self):
        self.assertEqual(_parse_listing_date("标题2026-08-17 15:00"), date(2026, 8, 17))
        self.assertEqual(_parse_listing_date("标题2026-08-17 15:00:30"), date(2026, 8, 17))

    def test_trailing_whitespace_is_allowed(self):
        for tail in (" ", "   ", "\n", " \n\t "):
            with self.subTest(repr(tail)):
                self.assertEqual(_parse_listing_date("标题2026-08-17 15:00" + tail),
                                 date(2026, 8, 17))

    def test_non_whitespace_after_the_stamp_rejects_it(self):
        self.assertIsNone(_parse_listing_date("标题2026-08-17 15:00 后记"))
        self.assertIsNone(_parse_listing_date("标题2026-08-17 15:00."))
        self.assertIsNone(_parse_listing_date("标题2026-08-17 15:00阅读全文"))

    def test_date_only_stamp_is_not_accepted(self):
        """
        Not observed anywhere in the archive, so not supported. Accepting it is
        exactly what let a bare date in a headline pass as metadata.
        """
        self.assertIsNone(_parse_listing_date("标题2026-08-17"))

    # ── stamp wins over the headline ─────────────────────────────────────────

    def test_headline_date_plus_valid_terminal_stamp_uses_the_stamp(self):
        self.assertEqual(_parse_listing_date("回顾2020-01-01演习2026-08-14 15:00"),
                         date(2026, 8, 14))
        self.assertEqual(_parse_listing_date("会议2026-13-45纪要2026-08-14 15:00"),
                         date(2026, 8, 14))

    def test_malformed_terminal_stamp_returns_none_with_no_fallback(self):
        self.assertIsNone(_parse_listing_date("回顾2020-01-01演习2026-13-45 15:00"))
        self.assertIsNone(_parse_listing_date("标题2026-02-30 10:00"))
        self.assertIsNone(_parse_listing_date("标题2026-13-45 10:00"))

    def test_absent_stamp_returns_none(self):
        self.assertIsNone(_parse_listing_date("没有日期的标题"))
        self.assertIsNone(_parse_listing_date(""))

    # ── structural extraction ────────────────────────────────────────────────

    def test_stamp_element_is_preferred_over_the_headline(self):
        """
        The stamp element is metadata by construction. Even a headline that
        itself ends in a well-formed stamp must not displace it.
        """
        page = listing(
            ("/gfbw/wzll/hj/1.html", "会议纪要2020-01-01 09:00", "2026-08-14 15:00"),
        )
        urls = _StubbedScraper(page, TARGET).get_article_urls()
        self.assertEqual(urls, ["http://www.mod.gov.cn/gfbw/wzll/hj/1.html"])

    def test_stamp_element_wins_even_when_it_is_not_last_in_the_anchor(self):
        """
        The discriminating case for structural extraction.

        Here the stamp element comes first and the headline — which itself ends
        in a well-formed stamp — comes last, so the flattened text terminates
        with the WRONG date. Only a parser that reads the element can be right;
        one that always falls back to flattened text returns 2020-01-01 and
        drops the article as out of window.
        """
        page = (
            '<html><body><ul><li>'
            '<a href="/gfbw/wzll/hj/7.html">'
            '<small class="time hidden-xs">2026-08-14 15:00</small>'
            '<p class="title">会议纪要2020-01-01 09:00</p>'
            '</a></li></ul></body></html>'
        )
        sc = _StubbedScraper(page, TARGET)
        self.assertEqual(sc.get_article_urls(),
                         ["http://www.mod.gov.cn/gfbw/wzll/hj/7.html"])

    def test_anchor_publication_date_prefers_the_element_over_the_text(self):
        """Same discrimination, asserted directly on the helper."""
        from bs4 import BeautifulSoup
        anchor = BeautifulSoup(
            '<a href="/gfbw/wzll/hj/8.html">'
            '<small class="time hidden-xs">2026-08-14 15:00</small>'
            '<p class="title">会议纪要2020-01-01 09:00</p></a>', "lxml").find("a")
        self.assertIsNotNone(_stamp_node(anchor))
        self.assertEqual(_anchor_publication_date(anchor), date(2026, 8, 14))
        # the flattened text alone would give the headline's trailing date
        self.assertEqual(_parse_listing_date(anchor.get_text()), date(2020, 1, 1))

    def test_empty_stamp_element_drops_the_link(self):
        page = listing(("/gfbw/wzll/hj/2.html", "回顾2026-08-14演习", ""))
        self.assertEqual(_StubbedScraper(page, TARGET).get_article_urls(), [])

    def test_text_fallback_applies_only_when_no_stamp_element_exists(self):
        page = flat_listing(
            ("/gfbw/wzll/hj/3.html", "标题2026-08-14 15:00"),   # terminal stamp
            ("/gfbw/wzll/hj/4.html", "回顾2026-08-14演习纪要"),  # prose only
        )
        urls = _StubbedScraper(page, TARGET).get_article_urls()
        self.assertEqual(urls, ["http://www.mod.gov.cn/gfbw/wzll/hj/3.html"])

    # ── end to end ───────────────────────────────────────────────────────────

    def test_discovery_follows_the_same_rule_end_to_end(self):
        page = listing(
            # headline carries an out-of-window date; stamp is in-window
            ("/gfbw/wzll/hj/1.html", "回顾2020-01-01演习", "2026-08-14 15:00"),
            # headline carries an in-window date; stamp is out of window
            ("/gfbw/wzll/hj/2.html", "展望2026-08-15部署", "2020-01-01 09:00"),
            # headline carries an in-window date; no stamp at all
            ("/gfbw/wzll/hj/3.html", "回顾2026-08-14演习纪要", ""),
        )
        urls = _StubbedScraper(page, TARGET).get_article_urls()
        self.assertEqual(urls, ["http://www.mod.gov.cn/gfbw/wzll/hj/1.html"])

    def test_stamp_respects_the_window_boundaries(self):
        for stamp, kept in (("2026-08-11 00:00", True),    # oldest boundary
                            ("2026-08-17 23:59", True),    # newest boundary
                            ("2026-08-10 23:59", False),   # day before window
                            ("2026-08-18 00:00", False)):  # future
            page = listing(("/gfbw/wzll/hj/9.html", "回顾2020-01-01演习", stamp))
            with self.subTest(stamp):
                self.assertEqual(
                    bool(_StubbedScraper(page, TARGET).get_article_urls()), kept)


class TestUniquenessAndSections(unittest.TestCase):
    """Requirement 7: a URL repeated across sections appears once."""

    def test_duplicate_links_across_sections_appear_once(self):
        page = listing(("/gfbw/wzll/hj/16479268.html", "跨栏目重复", "2026-08-17 10:00"))
        sc = _StubbedScraper(page)          # same fixture served for every section
        urls = sc.get_article_urls()
        self.assertEqual(len(sc.fetched), 6, "all six configured sections requested")
        self.assertEqual(len(urls), 1, "URL de-duplicated across sections")
        self.assertEqual(len(set(urls)), len(urls))

    def test_repeated_link_within_one_page_appears_once(self):
        page = listing(
            ("/gfbw/wzll/hj/16479268.html", "同页重复", "2026-08-17 10:00"),
            ("/gfbw/wzll/hj/16479268.html", "同页重复", "2026-08-17 10:00"),
        )
        self.assertEqual(len(_StubbedScraper(page).get_article_urls()), 1)


class TestStorageContract(unittest.TestCase):
    """
    Requirement 8: re-running discovery stores nothing extra.

    The window deliberately rediscovers already-known URLs every day. That is
    only safe because dedup is cumulative against the database, so this asserts
    the contract that makes the window affordable rather than assuming it.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT UNIQUE, "
            "content_hash TEXT)"
        )
        conn.commit()
        conn.close()
        self.addCleanup(self.tmp.cleanup)

    def _store(self, articles):
        """Run the real dedup filter, then persist whatever survives."""
        from processing.deduplicator import deduplicate
        import storage.db as sdb
        with mock.patch.object(sdb, "DB_PATH", self.db_path):
            new = deduplicate(articles)
            conn = sqlite3.connect(self.db_path)
            for a in new:
                conn.execute(
                    "INSERT OR IGNORE INTO articles (url, content_hash) VALUES (?, ?)",
                    (a["url"], a["content_hash"]),
                )
            conn.commit()
            conn.close()
        return new

    def _rows(self):
        conn = sqlite3.connect(self.db_path)
        n = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        conn.close()
        return n

    def test_rediscovery_adds_no_rows(self):
        from processing.metadata import normalize_article
        batch = [
            normalize_article({
                "url": f"http://www.mod.gov.cn/gfbw/wzll/hj/{i}.html",
                "source_slug": "mod_china",
                "title_original": f"标题{i}",
                "text_original": f"正文{i}",
                "published_date": "2026-08-17",
            })
            for i in range(3)
        ]
        self.assertEqual(len(self._store(batch)), 3)
        self.assertEqual(self._rows(), 3)

        # Same seven-date window, next day's run: every URL comes back.
        self.assertEqual(len(self._store(batch)), 0, "rediscovered URLs must not re-store")
        self.assertEqual(self._rows(), 3)

    def test_tracked_database_is_never_opened(self):
        self.assertNotEqual(self.db_path, REPO_ROOT / "pla_watch.db")
        self.assertTrue(self.db_path.is_relative_to(Path(self.tmp.name)))


class TestHealthGateUnweakened(unittest.TestCase):
    """
    Requirement 9: the 21-day alarm still fires for a genuinely overdue source.

    This fix must not quiet the only signal that caught the defect.
    """

    def test_overdue_active_source_still_reported(self):
        from core.collection.health import silence_verdict

        class Src:
            silence_threshold_days = 21

        self.assertEqual(silence_verdict(38, Src()), "overdue")
        self.assertEqual(silence_verdict(22, Src()), "overdue")
        self.assertEqual(silence_verdict(21, Src()), "within_cadence")

    def test_mod_china_threshold_is_still_21_days(self):
        import json
        manifest = json.loads(
            (REPO_ROOT / "desks" / "china" / "manifest.json").read_text()
        )
        mod = next(s for s in manifest["sources"] if s["slug"] == "mod_china")
        self.assertEqual(mod["silence_threshold_days"], 21)
        self.assertTrue(mod["enabled"])

    def test_mod_china_is_not_marked_inert(self):
        from scripts.check_source_liveness import KNOWN_INERT
        self.assertNotIn("mod_china", KNOWN_INERT)


if __name__ == "__main__":
    unittest.main()
