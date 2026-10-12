"""Official institution-level navigation on Japan and Vietnam research desks.

An official publisher section is external navigation only; it does not enable
shadow/corpus admission, imply full source retrieval, or approve an article.
"""
import unittest
from urllib.parse import urlsplit

from core.desk_registry import load_registry
from tests.test_desk_rollout_contract import DeskCase


LINKS = {
    "japan": {
        "Ministry of Defense — news feed (Japanese)":
            "https://www.mod.go.jp/j/press/news/",
        "Ministry of Defense — site update feed (Japanese)":
            "https://www.mod.go.jp/j/update/index.html",
    },
    "vietnam": {
        "Viet Nam Government News — defense tag page (English)":
            "https://en.baochinhphu.vn/defense.html",
        "Ministry of Public Security — foreign affairs (Vietnamese)":
            "https://bocongan.gov.vn/chuyen-muc/thong-tin-doi-ngoai-1751367399",
        "Ministry of Industry and Trade — energy (Vietnamese)":
            "https://moit.gov.vn/tin-tuc/phat-trien-nang-luong",
        "Ministry of Industry and Trade — foundational industry (Vietnamese)":
            "https://moit.gov.vn/tin-tuc/phat-trien-cong-nghiep/cong-nghiep-nen-tang",
    },
}
ALLOWED_HOSTS = {
    "www.mod.go.jp", "en.baochinhphu.vn", "bocongan.gov.vn", "moit.gov.vn",
}


class CountryPublisherNavigationTests(DeskCase):
    def test_exact_verified_indices_and_separate_moit_clocks(self):
        for slug, expected in LINKS.items():
            desk = load_registry().get(slug)
            self.assertEqual(desk.status, "shadow")
            self.assertFalse(desk.has_production_records)
            actual = {s["name"]: s["publisher_url"]
                      for s in desk.research["source_families"]
                      if s.get("publisher_url")}
            self.assertEqual(actual, expected)
            for name, url in actual.items():
                with self.subTest(desk=slug, source=name):
                    parts = urlsplit(url)
                    self.assertEqual(parts.scheme, "https")
                    self.assertIn(parts.hostname, ALLOWED_HOSTS)
                    self.assertIsNone(parts.username)
                    self.assertIsNone(parts.password)
                    self.assertFalse(parts.query or parts.fragment)
        vietnam_sources = load_registry().get("vietnam").research["source_families"]
        self.assertEqual(len([s for s in vietnam_sources if "Ministry of Industry and Trade — " in s["name"]]), 2)
        self.assertIn("own isolated source family and reliability clock",
                      next(s["note"] for s in vietnam_sources if "foundational industry" in s["name"]))

    def test_official_index_links_render_only_on_their_own_desks(self):
        for slug, expected in LINKS.items():
            html = self.page(slug + ".html")
            for url in expected.values():
                with self.subTest(desk=slug, url=url):
                    self.assertIn('href="' + url + '" rel="noopener noreferrer"', html)
            self.assertEqual(html.count("Open official publisher index"), len(expected))
            other = "vietnam" if slug == "japan" else "japan"
            for url in LINKS[other].values():
                self.assertNotIn(url, html)
            self.assertNotIn('href="archive.html?desk=' + slug + '"', html)
            self.assertNotIn("data-reference-list", html)
            self.assertNotIn("state/shadow.db", html)
            self.assertNotIn("text_original", html)

    def test_blocked_institutions_not_made_clickable_by_accident(self):
        for slug in ("japan", "vietnam"):
            sources = load_registry().get(slug).research["source_families"]
            for source in sources:
                if ("Not reached" in source["format"]
                        or "challenged" in source["format"]
                        or "disabled source candidate" in source["format"]):
                    with self.subTest(desk=slug, source=source["name"]):
                        self.assertNotIn("publisher_url", source)

    def test_live_desk_and_philippines_counts_are_unaffected(self):
        self.assertEqual(
            sorted(d.slug for d in load_registry() if d.is_collecting),
            ["china", "singapore"])
        philippines = self.page("philippines.html")
        self.assertEqual(philippines.count("Open official publisher index"), 2)
        for slug in LINKS:
            self.assertNotIn(list(LINKS[slug].values())[0], philippines)


if __name__ == "__main__":
    unittest.main()
