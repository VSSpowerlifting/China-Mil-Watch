"""Stable first-seen discovery for three China sources; pure HTML fixtures only.

The source's listing/section order matters under the unchanged daily cap.
A membership set may suppress duplicate URLs but may never determine order.
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

from scraper.sources.china_mil_online import ChinaMilOnlineScraper, _SECTIONS as CM_SECTIONS
from scraper.sources.global_times_mil import GlobalTimesMilScraper
from scraper.sources.mod_china import MODChinaScraper, _SECTIONS as MOD_SECTIONS

TARGET = date(2026, 10, 9)

CM_BASE = "http://eng.chinamil.com.cn"
CM_A = CM_BASE + "/2025xb/H_251454/L_251456/16491701.html"
CM_B = CM_BASE + "/2025xb/H_251454/L_251456/16491702.html"
CM_C = CM_BASE + "/2025xb/V_251452/16491703.html"

MOD_BASE = "http://www.mod.gov.cn"
MOD_A = MOD_BASE + "/gfbw/xwfyr/yzxwfb/16491701.html"
MOD_B = MOD_BASE + "/gfbw/xwfyr/yzxwfb/16491702.html"
MOD_C = MOD_BASE + "/gfbw/xwfyr/fyrthhdjzw/16491703.html"

GT_BASE = "https://www.globaltimes.cn"
GT_A = GT_BASE + "/page/202610/1370001.shtml"
GT_B = GT_BASE + "/page/202610/1370002.shtml"
GT_C = GT_BASE + "/page/202610/1370003.shtml"


def _cm_html(links):
    return "<html>" + "".join(
        '<a href="%s"><div class="title"><h3>Article</h3>'
        '<small class="time">%s</small></div></a>' % (u, d)
        for u, d in links) + "</html>"


def _mod_html(links):
    return "<html>" + "".join(
        '<a href="%s">Official notice'
        '<small class="time hidden-xs">%s</small></a>' % (u, d)
        for u, d in links) + "</html>"


def _gt_html(links):
    return "<html>" + "".join(
        '<section><a href="%s">Military headline</a>'
        '<div class="source_time">By Reporter | %s</div></section>' % (u, d)
        for u, d in links) + "</html>"


CM_PAGES = {
    list(CM_SECTIONS)[0]: _cm_html([
        (CM_A, "2026-10-09 09:00"), (CM_B, "2026-10-09 08:00"),
        (CM_A, "2026-10-09 09:00"), (CM_C, "2026-10-08 08:00"),
    ]),
    list(CM_SECTIONS)[1]: _cm_html([
        (CM_C, "2026-10-09 07:00"), (CM_A, "2026-10-09 09:00"),
    ]),
}

MOD_PAGES = {
    list(MOD_SECTIONS)[0]: _mod_html([
        (MOD_A, "2026-10-09 09:00"), (MOD_B, "2026-10-08 08:00"),
        (MOD_A, "2026-10-09 09:00"),
        (MOD_C, "2026-10-01 08:00"),  # outside seven-day window
    ]),
    list(MOD_SECTIONS)[1]: _mod_html([
        (MOD_C, "2026-10-09 07:00"), (MOD_A, "2026-10-09 09:00"),
    ]),
}


def discover(name):
    if name == "china_mil_online":
        s = ChinaMilOnlineScraper(target_date=TARGET)
        def fetch(url):
            section = url.removeprefix(CM_BASE + "/").removesuffix("/index.html")
            return CM_PAGES.get(section, "<html></html>")
        expected = [CM_A, CM_B, CM_C]
    elif name == "mod_china":
        s = MODChinaScraper(target_date=TARGET)
        def fetch(url):
            section = url.removeprefix(MOD_BASE + "/").removesuffix("/index.html")
            return MOD_PAGES.get(section, "<html></html>")
        expected = [MOD_A, MOD_B, MOD_C]
    elif name == "global_times_mil":
        s = GlobalTimesMilScraper(target_date=TARGET)
        def fetch(url):
            return _gt_html([
                (GT_A, "2026/10/9 09:00:00"),
                (GT_B, "2026/10/9 08:00:00"),
                (GT_A, "2026/10/9 09:00:00"),
                (GT_C, "2026/10/9 07:00:00"),
                (GT_BASE + "/page/202610/1370004.shtml",
                 "2026/10/8 10:00:00"),
                (GT_BASE + "/page/202609/1370005.shtml",
                 "2026/10/9 10:00:00"),
            ])
        expected = [GT_A, GT_B, GT_C]
    else:
        raise AssertionError("Unexpected source name")
    with patch.object(s, "fetch", side_effect=fetch):
        output = s.get_article_urls()
    return output, expected


class FirstSeenSourceOrderContracts(unittest.TestCase):
    SOURCES = ("china_mil_online", "global_times_mil", "mod_china")

    def test_each_source_preserves_first_seen_order_and_deduplicates(self):
        for name in self.SOURCES:
            with self.subTest(source=name):
                urls, expected = discover(name)
                self.assertEqual(urls, expected)
                self.assertEqual(len(urls), len(set(urls)))

    def test_repeated_discovery_is_identical(self):
        for name in self.SOURCES:
            with self.subTest(source=name):
                for _ in range(10):
                    result, expected = discover(name)
                    self.assertEqual(result, expected)

    def test_five_python_hash_seeds_cannot_change_the_result(self):
        root = Path(__file__).resolve().parents[1]
        code = (
            "import json; from tests.test_china_source_discovery_order "
            "import FirstSeenSourceOrderContracts, discover; "
            "print(json.dumps({n: discover(n)[0] "
            "for n in FirstSeenSourceOrderContracts.SOURCES}))"
        )
        expected = {name: discover(name)[1] for name in self.SOURCES}
        for seed in ("0", "1", "42", "137", "999"):
            with self.subTest(seed=seed):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                env["PYTHONPATH"] = str(root)
                proc = subprocess.run(
                    [sys.executable, "-c", code], cwd=str(root),
                    env=env, text=True, capture_output=True,
                    timeout=15, check=True,
                )
                self.assertEqual(json.loads(proc.stdout), expected)

    def test_duplicate_title_canonical_selection_does_not_change(self):
        from processing.dedup import dedup_articles
        for name in self.SOURCES:
            with self.subTest(source=name):
                urls, expected = discover(name)
                docs = [{"url": url, "source_slug": name,
                         "title_original": "%s distinct %d" % (name, i),
                         "text_original": "body %d" % i}
                        for i, url in enumerate(urls)]
                self.assertEqual(
                    [r["url"] for r in dedup_articles(docs)], expected,
                )


if __name__ == "__main__":
    unittest.main()
