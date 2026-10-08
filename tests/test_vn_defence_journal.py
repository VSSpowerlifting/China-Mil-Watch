"""Offline National Defence Journal source-contract tests.

These assert identities, source boundaries, duplicate suppression and review
gates. They do not claim live robots permission or validated body extraction.
"""
import json
import unittest
from pathlib import Path

from core.manifests import load_manifest
from scraper.sources import vn_defence_journal as dj

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "shadow" / "vietnam_journal" / "manifest.json"
ARTICLE_ID = "26936"
MAIN_ARTICLE = (
    "https://tapchiqptd.vn/en/theory-and-practice/"
    "military-technical-academy-proactively-embraces-international-integration-and-elevates-int/"
    "26936.html")
MOBILE_ARTICLE = (
    "https://m.tapchiqptd.vn/en/theory-and-practice/"
    "military-technical-academy-proactively-embraces-international-integration-and-elevates-int-26936.html")


class JournalIdentity(unittest.TestCase):
    def test_same_real_article_on_two_layouts_has_one_identity_and_permalink(self):
        self.assertEqual(dj.canonical_article_url(MOBILE_ARTICLE), MAIN_ARTICLE)
        self.assertEqual(dj.canonical_article_url(MAIN_ARTICLE), MAIN_ARTICLE)
        self.assertEqual(dj.article_identity(MAIN_ARTICLE), "vndj-en:26936")
        self.assertEqual(dj.article_identity(MOBILE_ARTICLE), dj.article_identity(MAIN_ARTICLE))

    def test_other_real_article_matches_both_layouts(self):
        desk = "https://tapchiqptd.vn/en/research-and-discussion/distinctive-features-of-military-art-in-the-tay-ninh-campaign-of-1966/26919.html"
        phone = "https://m.tapchiqptd.vn/en/research-and-discussion/distinctive-features-of-military-art-in-the-tay-ninh-campaign-of-1966-26919.html"
        self.assertEqual(dj.canonical_article_url(phone), desk)
        self.assertEqual(dj.article_identity(phone), "vndj-en:26919")

    def test_wrong_hosts_languages_queries_sections_and_redirects_refused(self):
        bad = [
            "http://tapchiqptd.vn/en/theory-and-practice/test/26936.html",
            "https://evil.example/en/theory-and-practice/test/26936.html",
            "https://tapchiqptd.vn/vi/theory-and-practice/test/26936.html",
            MAIN_ARTICLE + "?from=mobile",
            MAIN_ARTICLE + "#section",
            "https://m.tapchiqptd.vn/en/theory-and-practice/"
            "military-technical-academy-proactively-embraces-international-integration-and-elevates-int/26936.html",
            "https://tapchiqptd.vn/en/default.html",
            "https://tapchiqptd.vn/en/theory-and-practice-56.html",
            "https://tapchiqptd.vn/en/budget/test/26936.html",
            "https://tapchiqptd.vn/en/news/test/%32%36%39%33%36.html",
            "https://tapchiqptd.vn:443/en/news/test/26936.html",
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ValueError):
                dj.canonical_article_url(url)

    def test_homepage_repetitions_do_not_inflate_records(self):
        html = ('<html><body><a href="' + MOBILE_ARTICLE +
                '">Military Technical Academy research</a>'
                '<a href="' + MAIN_ARTICLE +
                '">Military Technical Academy research</a>'
                '<a href="/en/news/">News</a></body></html>')
        rows = dj.discovery_links(html, dj.MOBILE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], MAIN_ARTICLE)
        self.assertEqual(rows[0]["identity"], "vndj-en:26936")

    def test_listing_refuses_empty_and_unapproved_site(self):
        html = '<a href="/en/news">News</a>'
        with self.assertRaisesRegex(ValueError, "no identifiable"):
            dj.discovery_links(html, dj.DESKTOP)
        with self.assertRaisesRegex(ValueError, "unapproved"):
            dj.discovery_links(html, "https://tapchiqptd.vn/en/other.html")

    def test_conflicting_slugs_with_one_numeric_id_are_not_silently_combined(self):
        html = ('<a href="' + MAIN_ARTICLE + '">Original</a>'
                '<a href="https://tapchiqptd.vn/en/theory-and-practice/different-slug/26936.html">'
                'Conflicting</a>')
        with self.assertRaisesRegex(ValueError, "inconsistent permalinks"):
            dj.discovery_links(html, dj.DESKTOP)

    def test_publication_stamps_keep_day_only_and_validate_weekday(self):
        self.assertEqual(dj.stated_date("Wednesday, September 30, 2026, 14:48 (GMT+7)"),
                         "2026-09-30")
        self.assertEqual(dj.stated_date("9/30/2026 2:48:13 PM"), "2026-09-30")
        with self.assertRaisesRegex(ValueError, "weekday"):
            dj.stated_date("Monday, September 30, 2026, 14:48 (GMT+7)")
        with self.assertRaises(ValueError):
            dj.stated_date("October 2026")
        with self.assertRaises(ValueError):
            dj.stated_date("9/31/2026 2:48:13 PM")

    def test_source_manifest_is_disabled_and_one_institution(self):
        cfg = load_manifest(MANIFEST)
        self.assertEqual(cfg.desk.desk_id, "vietnam")
        self.assertEqual(cfg.desk.public_status, "research")
        self.assertEqual(len(cfg.sources), 1)
        src = cfg.sources[0]
        self.assertFalse(src.enabled)
        self.assertEqual(src.slug, dj.SOURCE_SLUG)
        self.assertEqual(src.language_tag, "en")
        self.assertEqual(src.authority_tier, "B")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["sources"][0]["listing_endpoints"],
                         [dj.DESKTOP, dj.MOBILE])
        self.assertEqual(src.institution_id, "vn_national_defence_journal")

    def test_source_not_discoverable_by_production_manifest_glob(self):
        self.assertEqual(MANIFEST.parent.parent.name, "shadow")
        self.assertFalse((ROOT / "desks" / "vietnam" / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
