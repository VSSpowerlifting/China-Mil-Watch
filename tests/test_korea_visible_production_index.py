"""Korea public launch visibility: report admitted records, not only new URLs.

A real production source may overlap a pre-existing manually reviewed link.
Suppressing duplicate URLs must never hide a successful SQLite admission.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from core.korea_official_live_links import load_live_korea_official_links
from core.korea_public_bibliography import load_public_korea_links
from core.korea_additional_public_links import load_additional_korea_official_links

ROOT = Path(__file__).resolve().parents[1]


class KoreaVisibleProductionIndex(unittest.TestCase):
    def test_real_production_sqlite_count_is_visible_without_duplicate_urls(self):
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as preview
        db = ROOT / "pla_watch.db"
        all_admitted = load_live_korea_official_links(db)
        self.assertGreater(len(all_admitted), 0,
                           "the verified Oct 15 Korea production admission vanished")
        frozen = {x["source_identity"] for x in (
            load_public_korea_links() + load_additional_korea_official_links())}
        newly_visible = [x for x in all_admitted
                         if x["source_identity"] not in frozen]
        with tempfile.TemporaryDirectory(prefix="ipr-korea-visible-live-") as folder:
            site = Path(folder) / "site"
            preview.build(site, "Indo-Pacific Record", db,
                          snapshot=preview.snapshot_from_corpus(db),
                          site_origin="https://indopacificrecord.org")
            html = (site / "korea.html").read_text(encoding="utf-8")
            self.assertIn(
                'data-korea-production-admitted-count="%d"' % len(all_admitted),
                html)
            self.assertIn("Verified MND official-link feed live", html)
            self.assertIn("live production database", html)
            self.assertEqual(html.count("data-korea-auto-official-link="),
                             len(newly_visible))
            self.assertEqual(html.count("data-korea-public-link="), 5)
            self.assertEqual(html.count("data-korea-additional-link="), 9)
            for row in newly_visible:
                self.assertIn(
                    'data-korea-auto-official-link="%s"' %
                    row["source_identity"], html)
            for source in all_admitted:
                self.assertEqual(
                    html.count('data-korea-auto-official-link="%s"' %
                               source["source_identity"]), int(
                        source["source_identity"] not in frozen))
            self.assertIn("not publication of the original Korean text", html)
            self.assertNotIn("text_original", html)
            self.assertNotIn("summary_english", html)
            self.assertFalse((ROOT / "pla_watch.db-wal").exists())
            self.assertFalse((ROOT / "pla_watch.db-shm").exists())

    def test_korea_workflow_republishes_only_its_page_on_template_change(self):
        flow = (ROOT / ".github/workflows/korea_verified_official_link_production.yml").read_text()
        self.assertIn("- site/preview/generate_preview.py", flow)
        self.assertIn("- site/preview/templates/desk.html", flow)
        self.assertIn("git add -- pla_watch.db output/korea.html", flow)
        self.assertIn("cp ../output/korea.html korea.html", flow)
        self.assertIn("cmp ../output/korea.html korea.html", flow)


if __name__ == "__main__":
    unittest.main()
