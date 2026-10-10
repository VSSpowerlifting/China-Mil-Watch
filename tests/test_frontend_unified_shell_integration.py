"""Merged visual materials must not undo the canonical historical IPR Briefs.

No provider, live collection, database write, or public publishing in this
contract. Compare all fourteen approved sidecar-generated articles byte-for-byte.
"""
import json
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from scripts.historical_brief_render import render_historical_brief
from scripts.rerender_pla_watch import _build_post_context

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "output/the-pla-watch/posts"


class UnifiedHistoricalEnrichment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sides = sorted(
            (json.loads(path.read_text(encoding="utf-8"))
             for path in POSTS.glob("*.json")), key=lambda side: side["date"]
        )

    def test_all_original_editions_preserve_exact_current_renderer_output(self):
        self.assertEqual(len(self.sides), 14)
        for i, side in enumerate(self.sides):
            with self.subTest(date=side["date"]):
                ctx = _build_post_context(side)
                ctx["prev_post"] = self.sides[i - 1] if i else None
                ctx["next_post"] = self.sides[i + 1] if i + 1 < len(self.sides) else None
                output = render_historical_brief(ctx)
                checked_in = (POSTS / (side["date"] + ".html")).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(output, checked_in)

    def test_every_page_is_the_unified_ipr_publication_with_scoped_materials(self):
        for side in self.sides:
            with self.subTest(date=side["date"]):
                page = (POSTS / (side["date"] + ".html")).read_text(encoding="utf-8")
                soup = BeautifulSoup(page, "html.parser")
                self.assertEqual(soup.body.get("data-surface"), "brief")
                self.assertEqual(soup.body.get("data-route"), "analysis.html")
                styles = [link.get("href") for link in soup.select(
                    'link[rel="stylesheet"]'
                )]
                for stylesheet in ("../../fonts.css", "../../styles.css",
                                   "../../enrichment.css", "../../briefs.css"):
                    self.assertIn(stylesheet, styles)
                self.assertEqual(styles.count("../../enrichment.css"), 1)
                self.assertEqual(
                    soup.select_one(".brief-eyebrow").get_text(strip=True),
                    "Indo-Pacific Record Briefs"
                )
                self.assertIn(
                    'aria-label="Indo-Pacific Record home"',
                    str(soup.header),
                )
                self.assertNotIn("The PLA Watch", str(soup.header))
                self.assertNotIn("The PLA Watch", str(soup.footer))
                self.assertEqual(
                    len(soup.select(".historical-provenance")), 1
                )
                self.assertIsNone(soup.select_one(".publication-freshness"))
                self.assertEqual(len(soup.select(".brief-hero")), 1)
                self.assertEqual(len(soup.select("#pw-cite")), 1)

    def test_sidecar_and_publication_identifiers_remain_unchanged(self):
        for side in self.sides:
            with self.subTest(date=side["date"]):
                soup = BeautifulSoup((POSTS / (
                    side["date"] + ".html")).read_text(), "html.parser")
                canonical = soup.select_one('link[rel="canonical"]')
                self.assertEqual(
                    canonical["href"],
                    "https://chinamilwatch.org/the-pla-watch/posts/"
                    + side["date"] + ".html",
                )
                if side.get("pw_veil"):
                    self.assertEqual(
                        len(soup.select("figure.historical-veil")), 1
                    )
                for source in soup.select(".historical-source-list a"):
                    self.assertTrue(source.get("href"))


if __name__ == "__main__":
    unittest.main()
