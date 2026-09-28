"""
Singapore's scheduled production window.

A scheduled run used to hand every adapter the same single-day window. The
Singapore adapter discovers strictly by the window it is given, so a release
was collectable on its slug date and never again. Compared against the shadow
corpus on 2026-09-28, production had lost three releases in its first week:

  * `22sep26-nr` and `22sep26-speech` -- the 2026-09-22 run's Singapore
    collection crashed, and the 2026-09-23 run looked only at 2026-09-23;
  * `23sep26-mq` -- first listed by the sitemap two days after its slug date.

Each loss is modelled below with synthetic fixtures. Everything is offline:
fake HTTP, temporary databases, no tracked-database access and no corpus
figures.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pipeline                                                    # noqa: E402
from core.collection.contract import CollectionWindow              # noqa: E402
from core.registry import SourceRegistry                           # noqa: E402
from scraper.sources import sg_mindef as sg                        # noqa: E402
from tests.test_singapore_scheduled_production import (            # noqa: E402
    DbBackedCase, FakeSession, sg_adapter)

RELEASES = "https://www.mindef.gov.sg/news-and-events/latest-releases/"
NR_22 = RELEASES + "22sep26-nr/"
SPEECH_22 = RELEASES + "22sep26-speech/"
NR_23 = RELEASES + "23sep26-nr/"
MQ_23 = RELEASES + "23sep26-mq/"
NR_25 = RELEASES + "25sep26-nr/"
HELD_16 = RELEASES + "16sep26-speech/"


def sitemap(*urls) -> str:
    rows = "".join("<url><loc>%s</loc><lastmod>2026-09-25</lastmod></url>\n"
                   % u for u in urls)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset>\n%s</urlset>\n'
            % rows)


def discovered(urls, target: date, window=None):
    adapter = sg_adapter(FakeSession(sitemap_text=sitemap(*urls)))
    window = window or pipeline.production_window(adapter, target)
    result = adapter.discover(window)
    return {ref.url for ref in result.references}


class TestTheProductionWindow(unittest.TestCase):

    def test_singapore_is_handed_seven_slug_dates(self):
        window = pipeline.production_window(sg_adapter(), date(2026, 9, 29))
        self.assertEqual(window.target_date, date(2026, 9, 29))
        self.assertEqual(window.lookback_days, 6)

    def test_the_seventh_date_is_in_and_the_eighth_is_out(self):
        window = pipeline.production_window(sg_adapter(), date(2026, 9, 29))
        chosen = sg.select_window([(MQ_23, None), (NR_22, None)], window, 40)
        self.assertEqual([url for _, url, _ in chosen], [MQ_23])

    def test_every_china_source_is_still_handed_a_single_day(self):
        """China's collection path must not move: its legacy scrapers keep
        their own windows internally and are handed exactly what they were."""
        registry = SourceRegistry()
        china = registry.slugs_for_desk("china")
        self.assertTrue(china)
        for slug in china:
            with self.subTest(slug=slug):
                window = pipeline.production_window(
                    registry.get_adapter(slug), date(2026, 9, 29))
                self.assertEqual(window, CollectionWindow(date(2026, 9, 29)))


class TestTheObservedLossesAreCollected(unittest.TestCase):

    def test_a_day_whose_run_failed_is_collected_by_the_next_run(self):
        """22sep26-nr / 22sep26-speech: the 09-22 run collected nothing for
        Singapore, and the 09-23 run must still reach 09-22."""
        urls = (NR_22, SPEECH_22, NR_23)
        target = date(2026, 9, 23)
        self.assertEqual(discovered(urls, target), set(urls))
        # The single-day window that lost them, for contrast.
        self.assertEqual(
            discovered(urls, target, window=CollectionWindow(target)), {NR_23})

    def test_a_release_listed_after_its_slug_date_is_collected(self):
        """23sep26-mq: absent from the 09-23 sitemap, first listed by 09-25."""
        self.assertEqual(discovered((NR_23,), date(2026, 9, 23)), {NR_23})
        later = discovered((NR_23, MQ_23, NR_25), date(2026, 9, 25))
        self.assertIn(MQ_23, later)

    def test_governed_holds_stay_out_of_the_wider_window(self):
        found = discovered((HELD_16, NR_22), date(2026, 9, 22))
        self.assertEqual(found, {NR_22})


class TestRediscoveredReleasesDoNotBlockNewOnes(DbBackedCase):
    """
    A seven-date window re-fetches releases already stored. They must be
    dropped before the all-or-nothing insert, including one whose body has
    changed since it was stored, so they can never roll back a new release.
    """

    def test_a_stored_release_with_a_changed_body_beside_a_new_release(self):
        from processing.deduplicator import deduplicate
        from processing.relevance import keyword_filter

        stored = self.sg_article(NR_22, title="Stored release",
                                 text="Original body. " * 40,
                                 published="2026-09-22")
        self.sdb.insert_article(stored, scrape_run_id=1)

        edited = self.sg_article(NR_22, title="Stored release",
                                 text="Edited body. " * 40,
                                 published="2026-09-22")
        new = self.sg_article(NR_23, title="New release",
                              published="2026-09-23")
        self.assertNotEqual(edited["content_hash"], stored["content_hash"])

        fresh = deduplicate([edited, new])
        self.assertEqual([a["url"] for a in fresh], [NR_23])

        # Whether the keyword screen passes or rejects it, a new release is
        # stored either way; only a rollback would keep it out.
        passed, rejected = keyword_filter(fresh)
        _, failed = pipeline._store_atomic_batches(passed, rejected, run_id=2)

        self.assertEqual(failed, set())
        rows = {r["url"]: r for r in self.article_rows()}
        self.assertEqual(set(rows), {NR_22, NR_23})
        self.assertEqual(rows[NR_22]["content_hash"], stored["content_hash"])


if __name__ == "__main__":
    unittest.main()
