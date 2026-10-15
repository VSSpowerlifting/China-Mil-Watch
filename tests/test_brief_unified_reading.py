"""All eighteen published Briefs share navigable reading styles without prose edits.

This contract deliberately reads checked-in output. Rendering of source-linked
No. 18, native Nos. 15–17 and historical Nos. 1–14 is covered elsewhere.
"""
from pathlib import Path
import unittest

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
HISTORICAL = (
    "05-09", "05-16", "05-23", "05-30", "06-06", "06-13", "06-20",
    "06-27", "07-04", "07-11", "07-18", "08-01", "08-08", "08-15",
)
NATIVE = (
    "maritime-cooperation-2026",
    "xiangshan-security-frames-defense-ties",
    "trident-resolve-regional-scale-specific-chinese-tasks",
    "what-is-being-built-in-laos",
)
PAGES = tuple(ROOT / "output/the-pla-watch/posts" / ("2026-" + day + ".html")
              for day in HISTORICAL) + tuple(
    ROOT / "output/briefs" / (slug + ".html") for slug in NATIVE)


class UnifiedBriefReadingTests(unittest.TestCase):
    def test_all_eighteen_pages_keep_navigable_editorial_sections(self):
        self.assertEqual(len(PAGES), 18)
        for path in PAGES:
            with self.subTest(page=path.relative_to(ROOT)):
                soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
                self.assertEqual(len(soup.select("h1")), 1)
                self.assertIsNotNone(soup.select_one(".brief-layout"))
                self.assertIsNotNone(soup.select_one(".brief-byline"))
                toc = soup.select_one("nav.brief-toc")
                self.assertIsNotNone(toc)
                targets = [a.get("href", "")[1:] for a in toc.select('a[href^="#"]')]
                self.assertGreaterEqual(len(targets), 3)
                for target in targets:
                    self.assertIsNotNone(soup.find(id=target), (path, target))

    def test_unified_css_is_generated_and_uses_turquoise_not_red(self):
        source = (ROOT / "site/preview/briefs.css").read_bytes()
        output = (ROOT / "output/briefs.css").read_bytes()
        self.assertEqual(output, source)
        css = source.decode("utf-8")
        self.assertIn(".brief-layout>.brief-reading-navigation{position:sticky;", css)
        self.assertIn(".brief-layout:not(.brief-layout--structured) .brief-main>.brief-section[id]:target", css)
        self.assertIn(".brief-reading-finding{border-top:2px solid var(--accent);", css)
        self.assertIn(".brief-signal{border:0;", css)
        self.assertNotIn("var(--crimson)", css)
        self.assertNotIn("var(--crimson-ink)", css)

    def test_historical_routes_and_laos_owner_presentation_remain_distinct(self):
        historic = (ROOT / "output/analysis.html").read_text(encoding="utf-8")
        for day in HISTORICAL:
            with self.subTest(issue=day):
                self.assertIn("/the-pla-watch/posts/2026-" + day + ".html", historic)
        laos = BeautifulSoup((ROOT / "output/briefs/what-is-being-built-in-laos.html")
                             .read_text(encoding="utf-8"), "html.parser")
        self.assertIsNotNone(laos.select_one(".brief-layout--structured"))
        self.assertEqual(len(laos.select("[data-manuscript-paragraph]")), 11)
        self.assertEqual(len(laos.select(".brief-reading-section")), 5)
        for slug in NATIVE[:3]:
            with self.subTest(native=slug):
                page = BeautifulSoup((ROOT / "output/briefs" / (slug + ".html"))
                                     .read_text(encoding="utf-8"), "html.parser")
                self.assertIsNone(page.select_one(".brief-layout--structured"))
                self.assertIsNotNone(page.select_one("#s-development"))


if __name__ == "__main__":
    unittest.main()
