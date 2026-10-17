"""Real public site Korea official metadata and deny-by-default release scope."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.korea_reference_gate import KoreaGateHold, load_candidates
from core.korea_public_bibliography import load_public_korea_links, INDEX

ROOT = Path(__file__).resolve().parents[1]


class KoreaPublicMetadataContracts(unittest.TestCase):
    def test_exact_five_allowlisted_original_titles_urls_and_dates(self):
        original = {r["source_identity"]: r for r in load_candidates()}
        links = load_public_korea_links()
        self.assertEqual(len(links), 5)
        self.assertEqual(len({r["source_url"] for r in links}), 5)
        for link in links:
            src = original[link["source_identity"]]
            self.assertEqual(set(link), {"source_identity", "source_url",
                                        "title_original", "published_date",
                                        "document_distribution_date"})
            for key in link:
                self.assertEqual(link[key], src[key])
            self.assertTrue(link["source_url"].startswith(
                "https://www.korea.kr/briefing/pressReleaseView.do?newsId="))
            for forbidden in ("text_original", "document_capture_sha256",
                              "content_sha256", "english_description",
                              "rights", "human_korean_review"):
                self.assertNotIn(forbidden, link)
        missile = next(x for x in links if x["source_identity"].endswith("156784297"))
        self.assertEqual(missile["document_distribution_date"], "2026-10-04")
        self.assertEqual(missile["published_date"], "2026-10-06")

    def test_manifest_cannot_expand_or_import_bodies(self):
        manifest = json.loads(INDEX.read_text(encoding="utf-8"))
        for change in (
            {"source_ids": manifest["source_ids"] + ["999999999"]},
            {"source_ids": []},
            {"state_commit": "a"*40},
            {"release_mode": "full-source-archive"},
            {"body_original": "private source body"},
        ):
            item = dict(manifest, **change)
            with tempfile.TemporaryDirectory() as tmp:
                file = Path(tmp) / "korea.json"
                file.write_text(json.dumps(item), encoding="utf-8")
                with self.assertRaises(KoreaGateHold):
                    load_public_korea_links(file)

    def test_source_metadata_cannot_shift_silently(self):
        from core import korea_public_bibliography as pub
        originals = load_candidates()
        changed = json.loads(json.dumps(originals))
        changed[0]["source_identity"] = "korea-policy:fake"
        with patch.object(pub, "load_candidates", return_value=changed):
            with self.assertRaises(KoreaGateHold):
                load_public_korea_links()

    def test_desk_renderer_links_but_never_copies_korean_bodies(self):
        import sys
        sys.path.insert(0, str(ROOT / "site/preview"))
        import generate_preview as gp
        with tempfile.TemporaryDirectory(prefix="ipr-korea-public-") as tmp:
            target = Path(tmp) / "site"
            result = gp.build(target, "Indo-Pacific Record", ROOT / "pla_watch.db",
                              snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
                              site_origin="https://indopacificrecord.org")
            page = (target / "korea.html").read_text(encoding="utf-8")
            self.assertEqual(result["korea_public_bibliography_entries"], 5)
            self.assertEqual(page.count('data-korea-public-link='), 5)
            self.assertIn('lang="ko"', page)
            self.assertIn("KOGL Type 1", page)
            self.assertIn("https://www.korea.kr/guide/copyRight.do", page)
            self.assertIn("Original titles are presented in Korean", page)
            self.assertIn("not IPR archived records", page)
            self.assertNotIn("noindex, nofollow", page)
            for forbidden in ("body_original", "text_original",
                              "download.do?fileId=", "data-review-status=",
                              "english_description", "korea_private_structural_refs"):
                self.assertNotIn(forbidden, page)
            desks_html = (target / "desks.html").read_text(encoding="utf-8")
            self.assertIn('href="korea.html"', desks_html)
            self.assertIn("Shadow evaluation — not in corpus", desks_html)
            self.assertNotIn("Shadow evaluation — not public", desks_html)
            self.assertIn("approved official-source links", desks_html)
            self.assertIn("Ministry of National Defense — official references", page)
            sitemap = (target / "sitemap.xml").read_text(encoding="utf-8")
            self.assertIn("https://indopacificrecord.org/korea.html", sitemap)


if __name__ == "__main__":
    unittest.main()
