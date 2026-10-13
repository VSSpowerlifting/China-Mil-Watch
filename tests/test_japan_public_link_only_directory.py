"""Public Japan bibliography is bounded outbound navigation, never admission."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "site/preview/templates/desk.html"
EXPECTED = {
    "9399": "September 7, 2026",
    "9424": "September 18, 2026",
    "9436": "September 29, 2026",
    "9453": "October 6, 2026",
    "9455": "October 6, 2026",
    "9465": "October 9, 2026",
}


class JapanPublicLinkOnlyDirectory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = TEMPLATE.read_text(encoding="utf-8")
        start = text.index("{% if desk.slug == 'japan' %}")
        end = text.index("{% endif %}", start)
        cls.section = text[start:end]
        cls.text = text

    def test_frozen_six_canonical_publisher_links_only(self):
        urls = re.findall(r'href="(https://www\.kaiho\.mlit\.go\.jp/e/topics_archive/article(\d+)\.html)"',
                          self.section)
        self.assertEqual(len(urls), 6)
        self.assertEqual({key for _, key in urls}, set(EXPECTED))
        self.assertEqual(len({url for url, _ in urls}), 6)
        for date in EXPECTED.values():
            self.assertIn(date, self.section)
        self.assertIn('aria-label="Six official Japan Coast Guard publication links"',
                      self.section)
        self.assertIn("rel=\"noopener noreferrer\"", self.section)

    def test_separate_public_body_and_pdf_rights_hold(self):
        s = self.section
        for warning in (
            "external official-source links only",
            "not archived IPR records",
            "PDF provides additional factual detail",
            "not reproduced or",
            "rights-approved by IPR",
            "source-version",
            "All Japan production records remain held",
            "not a qualifying collecting day",
        ):
            self.assertIn(warning, s)
        for forbidden in (
            "shadow/japan-jcg", "state/shadow.db", "text_original",
            "body_original", "archive.html?desk=japan",
            "data-reference-list", "https://www.kaiho.mlit.go.jp/e/topics_archive/upload/",
        ):
            self.assertNotIn(forbidden, s)

    def test_exact_five_mod_original_pdf_links_are_not_archive_admissions(self):
        expected = (
            "https://www.mod.go.jp/j/press/news/2026/08/27b.pdf",
            "https://www.mod.go.jp/j/press/news/2026/08/28a.pdf",
            "https://www.mod.go.jp/j/press/news/2026/08/28b.pdf",
            "https://www.mod.go.jp/j/press/news/2026/08/28f.pdf",
            "https://www.mod.go.jp/j/press/news/2026/10/05b.pdf",
        )
        pdf_links = re.findall(
            r'href="(https://www\\.mod\\.go\\.jp/j/press/news/2026/(?:08|10)/\\d{2}[a-z]\\.pdf)"',
            self.section,
        )
        self.assertEqual(pdf_links, list(expected))
        self.assertEqual(len(set(pdf_links)), 5)
        self.assertIn('aria-label="Five official Japan Ministry of Defense PDF links"',
                      self.section)
        for qualifier in (
            "22",
            "not production IPR records",
            "Six photographs and their rights are not retained or cleared",
            "conflicting with the later October 5 original",
            "no official erratum verified",
            "not proof the activity occurred",
            "not reproduced here",
            "archived-text extraction parity",
            "current PDF byte identity",
            "no production or model use is authorized",
        ):
            self.assertIn(qualifier, self.section)
        self.assertIn("https://www.mod.go.jp/j/info/contents.html", self.section)
        for forbidden in ("state/shadow.db", "text_original", "body_original",
                          "archive.html?desk=japan", "data-reference-list"):
            self.assertNotIn(forbidden, self.section)

    def test_japan_css_only_addition_other_desks_not_modified(self):
        self.assertIn(
            "'vietnam', 'philippines', 'korea', 'indonesia', 'japan'",
            self.text,
        )
        self.assertIn("desk.slug == 'japan'", self.section)
        self.assertIn('href="https://www.kaiho.mlit.go.jp/questions/post-1.html"', self.section)
        self.assertIn("reproduce", self.section)


if __name__ == "__main__":
    unittest.main()
