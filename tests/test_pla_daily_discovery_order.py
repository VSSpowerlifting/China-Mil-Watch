"""PLA Daily discovery order is an observed input, not a hash-table accident.

Offline, synthetic listing pages only. No external requests or DB mutation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from scraper.sources.pla_daily import PLADailyScraper, _SECTIONS

TARGET = date(2026, 10, 9)
BASE = "http://www.81.cn"

A = BASE + "/yw_208727/16491701.html"
B = BASE + "/yw_208727/16491702.html"
C = BASE + "/jw_208551/16491703.html"
D = BASE + "/zq_208553/16491704.html"

FIXTURE_PAGES = {
    "yw_208727": (
        "<html><body>"
        '<a href="/yw_208727/16491701.html">2026-10-09 08:00 A</a>'
        '<a href="/yw_208727/16491702.html">2026-10-09 07:00 B</a>'
        '<a href="/yw_208727/16491701.html">2026-10-09 08:00 A again</a>'
        '<a href="/yw_208727/16491705.html">2026-10-08 08:00 old</a>'
        '<a href="/yw_208727/index.html">2026-10-09 index</a>'
        "</body></html>"
    ),
    "jw_208551": (
        "<html><body>"
        '<a href="/jw_208551/16491703.html">2026-10-09 06:00 C</a>'
        '<a href="/yw_208727/16491701.html">2026-10-09 08:00 repost</a>'
        "</body></html>"
    ),
    "zq_208553": (
        "<html><body>"
        '<a href="/zq_208553/16491704.html">2026-10-09 05:00 D</a>'
        "</body></html>"
    ),
}


def discover():
    scraper = PLADailyScraper(target_date=TARGET)
    seen_listings = []

    def offline_fetch(url):
        seen_listings.append(url)
        section = url.split("/")[-2]
        return FIXTURE_PAGES.get(section, "<html><body></body></html>")

    with patch.object(scraper, "fetch", side_effect=offline_fetch):
        result = scraper.get_article_urls()
    return result, seen_listings


class FirstSeenDiscoveryOrderContracts(unittest.TestCase):

    def test_preserves_section_and_dom_order_and_removes_duplicates(self):
        result, visited = discover()
        self.assertEqual(result, [A, B, C, D])
        self.assertEqual(len(result), len(set(result)))
        self.assertEqual(len(visited), len(_SECTIONS))
        self.assertEqual([x.split("/")[-2] for x in visited],
                         list(_SECTIONS.keys()))

    def test_repeated_offline_discovery_preserves_same_order(self):
        for _ in range(12):
            self.assertEqual(discover()[0], [A, B, C, D])

    def test_order_stable_across_hash_seeds_and_processes(self):
        """Old list(seen) could permute the four values between processes."""
        root = Path(__file__).resolve().parents[1]
        code = (
            "import json; "
            "from tests.test_pla_daily_discovery_order import discover; "
            "print(json.dumps(discover()[0]))"
        )
        for seed in ("0", "1", "42", "137", "999"):
            with self.subTest(seed=seed):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                env["PYTHONPATH"] = str(root)
                result = subprocess.run(
                    [sys.executable, "-c", code],
                    cwd=str(root), env=env,
                    capture_output=True, text=True, timeout=10,
                    check=True,
                )
                self.assertEqual(json.loads(result.stdout), [A, B, C, D])

    def test_pipeline_receives_order_without_mutating_it(self):
        from processing.dedup import dedup_articles
        articles = [
            {"url": u, "source_slug": "pla_daily",
             "title_original": "Test unique title " + str(i),
             "text_original": "body for " + str(i)}
            for i, u in enumerate(discover()[0])
        ]
        result = dedup_articles(articles)
        self.assertEqual([x["url"] for x in result], [A, B, C, D])

    def test_no_network_or_analyzer_required(self):
        self.assertEqual(discover()[0], [A, B, C, D])


if __name__ == "__main__":
    unittest.main()
