"""Public Korea bibliography is deliberately not a live source or corpus."""
import tempfile
import unittest
from pathlib import Path

from core.desk_registry import load_registry
from core.reviewed_source_links import load_public_desk_references
from core.korea_public_bibliography import load_public_korea_links
from core.brief_contract import eligible_desks


class KoreaInternalRegistry(unittest.TestCase):
    def test_public_bibliography_is_not_a_production_collector(self):
        reg = load_registry()
        k = reg.get("korea")
        self.assertIsNotNone(k)
        self.assertEqual(k.route, "korea.html")
        self.assertTrue(k.public)
        self.assertEqual(k.status, "shadow")
        self.assertFalse(k.is_collecting)
        self.assertFalse(k.has_production_records)
        self.assertFalse(k.may_show_record_count)
        self.assertIsNone(k.manifest_path)
        self.assertEqual(k.configured_source_count, 0)
        self.assertEqual(k.enabled_source_count, 0)
        self.assertIn("korea", [x.slug for x in reg.public_entries])
        self.assertNotIn("korea", eligible_desks(reg))
        self.assertEqual(load_public_desk_references("korea"), [])
        self.assertEqual(len(load_public_korea_links()), 5)
        self.assertFalse((Path(__file__).resolve().parents[1] /
                          "desks/korea/manifest.json").exists())

    def test_actual_public_site_includes_five_links_and_no_archive_record(self):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "site/preview"))
        import generate_preview as gp
        db = root / "pla_watch.db"
        if not db.exists():
            self.skipTest("tracked original corpus fixture missing")
        with tempfile.TemporaryDirectory(prefix="ipr-korea-public-directory-") as tmp:
            dest = Path(tmp) / "site"
            gp.build(dest, "Korea Public Link Test", db,
                     snapshot=gp.snapshot_from_corpus(db),
                     site_origin="https://indopacificrecord.org")
            page = (dest / "korea.html").read_text(encoding="utf-8")
            directory = (dest / "desks.html").read_text(encoding="utf-8")
            sitemap = (dest / "sitemap.xml").read_text(encoding="utf-8")
            self.assertIn('href="korea.html"', directory)
            self.assertIn("https://indopacificrecord.org/korea.html", sitemap)
            self.assertEqual(page.count("data-korea-public-link="), 5)
            self.assertIn("not IPR archived records", page)
            self.assertIn("Original titles are presented in Korean", page)
            self.assertNotIn("noindex, nofollow", page)
            for forbidden in ("text_original", "body_original",
                              "download.do?fileId=", "data-review-status=",
                              "english_description"):
                self.assertNotIn(forbidden, page)
            for route in ("china.html", "singapore.html", "japan.html",
                          "philippines.html", "vietnam.html"):
                self.assertTrue((dest / route).is_file(), route)


if __name__ == "__main__":
    unittest.main()
