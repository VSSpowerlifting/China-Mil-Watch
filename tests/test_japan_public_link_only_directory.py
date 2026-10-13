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
