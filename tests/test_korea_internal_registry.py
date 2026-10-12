"""Korea is operational in research, not publicly promoted or configured."""
import tempfile
import unittest
from pathlib import Path

from core.desk_registry import load_registry
from core.reviewed_source_links import load_public_desk_references
from core.brief_contract import eligible_desks


class KoreaInternalRegistry(unittest.TestCase):
    def test_internal_korea_entry_is_unambiguous(self):
        reg = load_registry()
        entry = reg.get("korea")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.slug, "korea")
        self.assertEqual(entry.route, "korea.html")
        self.assertEqual(entry.status, "shadow")
        self.assertFalse(entry.public)
        self.assertFalse(entry.is_collecting)
        self.assertFalse(entry.has_production_records)
        self.assertFalse(entry.may_show_record_count)
        self.assertIsNone(entry.manifest_path)
        self.assertEqual(entry.configured_source_count, 0)
        self.assertEqual(entry.enabled_source_count, 0)
        self.assertEqual(len(entry.research["source_families"]), 1)
        self.assertIn("Policy Briefing", entry.scope)
        self.assertNotIn("korea", [x.slug for x in reg.public_entries])
        self.assertNotIn("korea", eligible_desks(reg))
        self.assertEqual(load_public_desk_references("korea"), [])
        self.assertFalse((Path(__file__).resolve().parents[1] /
                          "desks/korea/manifest.json").exists())

    def test_public_build_does_not_create_korea_page_or_route(self):
        import sys
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "site/preview"))
        import generate_preview as gp
        db = root / "pla_watch.db"
        if not db.is_file():
            self.skipTest("tracked production snapshot unavailable")
        with tempfile.TemporaryDirectory(prefix="korea-nonpublic-registry-") as tmp:
            site = Path(tmp) / "preview"
            gp.build(site, "Korea Private Registry Fixture", db,
                     snapshot=gp.snapshot_from_corpus(db))
            self.assertFalse((site / "korea.html").exists())
            listing = (site / "desks.html").read_text(encoding="utf-8")
            self.assertNotIn('href="korea.html"', listing)
            for published in ("china.html", "singapore.html", "japan.html",
                              "philippines.html", "vietnam.html"):
                self.assertTrue((site / published).is_file(), published)


if __name__ == "__main__":
    unittest.main()
