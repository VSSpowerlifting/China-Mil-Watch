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
        "Japan Coast Guard — English press releases":
            "https://www.kaiho.mlit.go.jp/e/topics_archive/index.html",
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
    "www.mod.go.jp", "www.kaiho.mlit.go.jp", "en.baochinhphu.vn",
    "bocongan.gov.vn", "moit.gov.vn",
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
                      next(s["note"] for s in vietnam_sources if s["name"] == "Ministry of Industry and Trade — foundational industry (Vietnamese)"))

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

    def test_jcg_manual_day_zero_is_distinct_from_mod_source_and_rights(self):
        desk = load_registry().get("japan")
        jcg = next(s for s in desk.research["source_families"]
                   if s["name"] == "Japan Coast Guard — English press releases")
        self.assertIn("manual October 8 Day 0", jcg["note"])
        self.assertIn("repository gate was observed unset or unavailable on October 12", jcg["note"])
        self.assertIn("No JCG daily qualification", jcg["note"])
        self.assertIn("per-version rights review", jcg["note"])
        self.assertIn("distinct collection clocks", desk.limits[-1])
        self.assertIn("30 scheduled MOD collection slots", desk.limits[-1])
        self.assertIn("8 of 142 news-feed items (6 percent) were PDF-format candidates",
                      desk.limits[1])
        self.assertNotIn("carried full text", desk.limits[1])
        self.assertIn("some PDF-published originals yield extractable text",
                      desk.status_explanation)

        self.assertIn("five text-bearing originals and 158 unretrieved URLs",
                      desk.research["volume_caveat"])
        self.assertIn("PDF source completeness and qualification remain unresolved",
                      desk.research["blockers"][1][0])
        self.assertIn("30 verified scheduled MOD collection slots",
                      desk.research["blockers"][1][1])
        self.assertIn("repository gate was observed unset or unavailable",
                      self.page("japan.html"))
        self.assertIn("30 scheduled MOD collection slots",
                      self.page("japan.html"))
        self.assertEqual(desk.status, "shadow")
        self.assertFalse(desk.has_production_records)
        self.assertNotIn("data-reference-list", self.page("japan.html"))

    def test_japan_link_only_six_originals_render_with_source_gates(self):
        """Check generated, publishable HTML, not just template literals."""
        from html.parser import HTMLParser

        class OfficialArticleLinks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.targets = []
            def handle_starttag(self, tag, attrs):
                if tag != "a":
                    return
                values = dict(attrs)
                url = values.get("href", "")
                if url.startswith("https://www.kaiho.mlit.go.jp/e/topics_archive/article"):
                    self.targets.append((url, values.get("rel", "")))

        html = self.page("japan.html")
        parser = OfficialArticleLinks()
        parser.feed(html)
        identifiers = ("9399", "9424", "9436", "9453", "9455", "9465")
        self.assertEqual(
            [url for url, _ in parser.targets],
            ["https://www.kaiho.mlit.go.jp/e/topics_archive/article"
             + ident + ".html" for ident in identifiers],
        )
        self.assertTrue(all("noopener" in rel and "noreferrer" in rel
                            for _, rel in parser.targets))
        for phrase in (
            "external official-source links only",
            "not archived IPR records",
            "rights-approved by IPR",
            "All Japan production records remain held",
            "repository gate was observed unset or unavailable",
            "October 8 shadow capture is HTML text only",
            "Post-Day-0 source candidate; not a qualifying collecting day",
        ):
            self.assertIn(phrase, html)
        self.assertIn("https://www.kaiho.mlit.go.jp/questions/post-1.html", html)
        self.assertNotIn('href="archive.html?desk=japan"', html)
        self.assertNotIn("data-reference-list", html)
        self.assertNotIn("text_original", html)
        for slug in ("vietnam", "philippines", "indonesia", "korea"):
            other_html = self.page(slug + ".html")
            for ident in identifiers:
                self.assertNotIn("e/topics_archive/article" + ident + ".html",
                                 other_html)

    def test_japan_five_mod_original_pdfs_render_only_on_japan(self):
        """Verify page output, not merely template source or a collector row."""
        from html.parser import HTMLParser

        class OfficialPDFLinks(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
            def handle_starttag(self, tag, attrs):
                if tag != "a":
                    return
                a = dict(attrs)
                url = a.get("href", "")
                if url.startswith("https://www.mod.go.jp/j/press/news/2026/") and url.endswith(".pdf"):
                    self.links.append((url, a.get("rel", "")))

        html = self.page("japan.html")
        parser = OfficialPDFLinks()
        parser.feed(html)
        expected = (
            "08/27b.pdf",
            "08/28a.pdf",
            "08/28b.pdf",
            "08/28f.pdf",
            "10/05b.pdf",
        )
        prefix = "https://www.mod.go.jp/j/press/news/2026/"
        self.assertEqual([url for url, _ in parser.links],
                         [prefix + suffix for suffix in expected])
        self.assertTrue(all("noopener" in rel and "noreferrer" in rel
                            for _, rel in parser.links))
        for phrase in (
            "Five official Japan Ministry of Defense PDF links",
            "not production IPR records",
            "conflicting with the later October 5 original",
            "not proof the activity occurred",
            "archived-text extraction parity",
            "no production or model use is authorized",
            "repository gate was observed unset or unavailable",
        ):
            self.assertIn(phrase, html)
        for forbidden in ('href="archive.html?desk=japan"', "data-reference-list",
                          "state/shadow.db", "text_original", "body_original"):
            self.assertNotIn(forbidden, html)
        for slug in ("vietnam", "philippines", "indonesia", "korea"):
            other = self.page(slug + ".html")
            for suffix in expected:
                self.assertNotIn(prefix + suffix, other)

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
