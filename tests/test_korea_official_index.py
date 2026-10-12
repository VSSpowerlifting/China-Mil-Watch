"""Korea public source index is a navigation link, never archive admission."""
import sys
import tempfile
import unittest
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from core.desk_registry import load_registry
from core.korea_public_bibliography import load_public_korea_links

ROOT = Path(__file__).resolve().parents[1]
INDEX = ("https://www.korea.kr/briefing/pressReleaseList.do?"
         "pWiseMinistry=ministryNews&repCode=A00005&"
         "repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98")


class KoreaOfficialIndexContracts(unittest.TestCase):
    def test_exact_ministry_filtered_official_index(self):
        korea = load_registry().get("korea")
        self.assertTrue(korea.public)
        self.assertEqual(korea.status, "shadow")
        self.assertIsNone(korea.manifest_path)
        self.assertFalse(korea.has_production_records)
        self.assertEqual(len(korea.research["source_families"]), 1)
        source = korea.research["source_families"][0]
        self.assertEqual(source["publisher_url"], INDEX)
        parsed = urlsplit(INDEX)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ("https", "www.korea.kr",
                          "/briefing/pressReleaseList.do"))
        self.assertEqual(parse_qs(parsed.query),
                         {"pWiseMinistry": ["ministryNews"],
                          "repCode": ["A00005"], "repCodeType": ["정부부처"]})
        self.assertEqual(len(load_public_korea_links()), 5)

    def test_index_renders_as_outbound_navigation_not_sixth_record(self):
        sys.path.insert(0, str(ROOT / "site/preview"))
        import generate_preview as preview
        with tempfile.TemporaryDirectory(prefix="ipr-korea-publisher-index-") as tmp:
            site = Path(tmp) / "site"
            preview.build(site, "Indo-Pacific Record", ROOT / "pla_watch.db",
                          snapshot=preview.snapshot_from_corpus(ROOT / "pla_watch.db"),
                          site_origin="https://indopacificrecord.org")
            page = (site / "korea.html").read_text(encoding="utf-8")
            self.assertIn('href="' + escape(INDEX, quote=True) +
                          '" rel="noopener noreferrer">Open official publisher index', page)
            self.assertEqual(page.count("data-korea-public-link="), 5)
            self.assertNotIn("156784787", page)  # next unadmitted publisher release
            self.assertIn("not IPR archived records", page)
            self.assertNotIn("download.do?fileId=", page)


if __name__ == "__main__":
    unittest.main()
