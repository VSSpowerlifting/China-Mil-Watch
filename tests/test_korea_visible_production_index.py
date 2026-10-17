"""Korea live production status cannot be hidden by frozen bibliography overlap.

All source/rights and reviewed-editorial publication registries remain
independently governed. This test only observes existing production metadata.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

from core.korea_official_live_links import load_live_korea_official_links
from core.korea_public_bibliography import load_public_korea_links
from core.korea_additional_public_links import load_additional_korea_official_links
from core.korea_published_originals import read_release_index
from core.korea_english_publication import public_registry

ROOT = Path(__file__).resolve().parents[1]


class KoreaLiveMetadataCountTests(unittest.TestCase):
    def test_real_production_counts_beyond_previously_curated_links(self):
        sys.path.insert(0, str(ROOT / "site" / "preview"))
        import generate_preview as preview
        db = ROOT / "pla_watch.db"
        all_admitted = load_live_korea_official_links(db)
        self.assertGreater(len(all_admitted), 0,
                           "verified MND production metadata cannot silently disappear")
        bibliography = load_public_korea_links() + load_additional_korea_official_links()
        frozen = {r["source_identity"] for r in bibliography}
        newly_listed = [r for r in all_admitted
                        if r["source_identity"] not in frozen]
        originals = read_release_index()
        reviewed = public_registry()

        with tempfile.TemporaryDirectory(prefix="ipr-korea-status-") as tmp:
            out = Path(tmp) / "site"
            preview.build(out, "Indo-Pacific Record", db,
                          snapshot=preview.snapshot_from_corpus(db),
                          site_origin="https://indopacificrecord.org")
            html = (out / "korea.html").read_text(encoding="utf-8")
            self.assertIn(
                'data-korea-production-admitted-count="%d"' % len(all_admitted),
                html)
            self.assertIn("MND official-source production live", html)
            self.assertIn(
                "contains %d separately admitted official-link metadata records"
                % len(all_admitted), html)
            self.assertIn(
                "links to %d licensed Korean original-text releases" % len(originals),
                html)
            self.assertIn(
                "%d editor-approved English translation" % len(reviewed),
                html)
            self.assertEqual(
                html.count('data-korea-auto-official-link='), len(newly_listed))
            self.assertIn('data-korea-production-lanes', html)
            self.assertIn('Live MND official-link metadata</dt><dd>%d</dd>'
                          % len(all_admitted), html)
            self.assertIn('Published Korean originals</dt><dd>%d</dd>'
                          % len(originals), html)
            self.assertIn('Reviewed English translations and analyses</dt><dd>%d</dd>'
                          % len(reviewed), html)
            self.assertIn('Article-corpus records</dt><dd>Not admitted', html)
            self.assertIn('DAPA production source</dt><dd>Not qualified', html)
            self.assertNotIn(
                'This desk has no admitted records in the public IPR corpus.', html)
            self.assertEqual(html.count('data-korea-public-link='), 5)
            self.assertEqual(html.count('data-korea-additional-link='), 9)
            for source in newly_listed:
                self.assertIn(
                    'data-korea-auto-official-link="%s"' % source["source_identity"],
                    html)
            for source in all_admitted:
                expected = int(source["source_identity"] not in frozen)
                self.assertEqual(html.count(
                    'data-korea-auto-official-link="%s"' % source["source_identity"]
                ), expected)
            self.assertIn("DAPA remains research-only", html)
            self.assertNotIn("original-source archive remains restricted", html)
            self.assertNotIn("text_original", html)
            self.assertNotIn("summary_english", html)
            self.assertFalse((ROOT / "pla_watch.db-wal").exists())
            self.assertFalse((ROOT / "pla_watch.db-shm").exists())

    def test_actual_writer_runs_on_status_template_changes_but_stays_scoped(self):
        path = ROOT / ".github/workflows/korea_verified_official_link_production.yml"
        flow = path.read_text(encoding="utf-8")
        self.assertIn("- site/preview/generate_preview.py", flow)
        self.assertIn("- site/preview/templates/desk.html", flow)
        self.assertIn("git add -- pla_watch.db output/korea.html", flow)
        self.assertIn("cp ../output/korea.html korea.html", flow)
        self.assertIn("cmp ../output/korea.html korea.html", flow)


if __name__ == "__main__":
    unittest.main()
