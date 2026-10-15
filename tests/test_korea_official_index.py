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
DAPA_INDEX = INDEX.replace("repCode=A00005", "repCode=B00008")


class KoreaOfficialIndexContracts(unittest.TestCase):
    def test_exact_ministry_filtered_official_index(self):
        korea = load_registry().get("korea")
        self.assertTrue(korea.public)
        self.assertEqual(korea.status, "shadow")
        self.assertIsNone(korea.manifest_path)
        self.assertFalse(korea.has_production_records)
        sources = korea.research["source_families"]
        self.assertEqual(len(sources), 2)
        source, dapa = sources
        self.assertEqual(source["publisher_url"], INDEX)
        self.assertEqual(dapa["publisher_url"], DAPA_INDEX)
        self.assertIn("research only", dapa["name"])
        self.assertIn("no DAPA shadow collection", dapa["format"])
        self.assertIn("unapproved", dapa["note"])
        parsed = urlsplit(INDEX)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path),
                         ("https", "www.korea.kr",
                          "/briefing/pressReleaseList.do"))
        self.assertEqual(parse_qs(parsed.query),
                         {"pWiseMinistry": ["ministryNews"],
                          "repCode": ["A00005"], "repCodeType": ["정부부처"]})
        self.assertEqual(parse_qs(urlsplit(DAPA_INDEX).query)["repCode"], ["B00008"])
        self.assertNotEqual(DAPA_INDEX, INDEX)
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
            self.assertIn('href="' + escape(DAPA_INDEX, quote=True) +
                          '" rel="noopener noreferrer">Open official publisher index', page)
            self.assertEqual(page.count("Open official publisher index"), 2)
            self.assertIn('<nav class="korea-publisher-shortcuts"', page)
            self.assertIn('id="korea-publisher-shortcuts-title"', page)
            self.assertIn("Research-only source family; no DAPA records admitted", page)
            # Both indexes are next to the frozen bibliography, never buried
            # behind the bottom source inventory or counted as sixth records.
            self.assertLess(page.index("korea-publisher-shortcuts-title"),
                            page.index('data-korea-public-link='))
            self.assertEqual(page.count('data-korea-public-link='), 5)
            # Two formerly unreviewed MND IDs now have explicitly approved
            # link-only status, while the DAPA/unselected items stay excluded.
            self.assertEqual(page.count('data-korea-additional-link='), 9)
            for approved_id in ("156784787", "156784873"):
                self.assertIn(
                    'data-korea-additional-link="korea-policy:' + approved_id + '"',
                    page)
            # A subsequently captured, hash-verified official link may be
            # admitted under the separate standing metadata-only policy;
            # a merely unreviewed fixed-directory entry may not appear.
            from core.korea_official_live_links import load_live_korea_official_links
            from core.korea_public_bibliography import load_public_korea_links
            from core.korea_additional_public_links import load_additional_korea_official_links
            fixed = {x["source_identity"] for x in (
                load_public_korea_links() + load_additional_korea_official_links())}
            auto_ids = {x["source_identity"].partition(":")[2] for x in
                        load_live_korea_official_links(ROOT / "pla_watch.db", exclude=fixed)}
            for unapproved_id in ("156784618", "156784625"):
                if unapproved_id not in auto_ids:
                    self.assertNotIn(unapproved_id, page)
            for forbidden in ("body_original", "download.do?fileId=",
                              "english_description", "data-review-status="):
                self.assertNotIn(forbidden, page)
            self.assertIn("not IPR archived records", page)
            self.assertNotIn("download.do?fileId=", page)


if __name__ == "__main__":
    unittest.main()
