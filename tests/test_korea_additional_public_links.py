"""Owner-scoped additional Korea official URLs: no original or corpus release."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.korea_reference_gate import KoreaGateHold
from core.korea_public_bibliography import load_public_korea_links
from core import korea_additional_public_links as public
from scripts.preview_korea_fourteen_official_links import validate

ROOT = Path(__file__).resolve().parents[1]


class KoreaAdditionalPublicLinkReleaseTests(unittest.TestCase):
    def test_original_five_unchanged_and_exact_nine_new_canonical(self):
        five = load_public_korea_links()
        nine = public.load_additional_korea_official_links()
        self.assertEqual(len(five), 5)
        self.assertEqual(len(nine), 9)
        self.assertEqual({r["source_identity"] for r in five}.intersection(
            {r["source_identity"] for r in nine}), set())
        self.assertEqual(len(set(x["source_identity"] for x in five + nine)), 14)
        self.assertEqual(
            [r["source_identity"].partition(":")[2] for r in nine],
            list(public.EXPECTED))
        actual, published = validate()
        self.assertEqual(len(published), 5)
        for row in nine:
            ident = row["source_identity"].partition(":")[2]
            self.assertEqual(row["source_url"],
                             "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + ident)
            self.assertEqual(len([x for x in actual if x["news_id"] == ident]), 1)
            self.assertEqual(set(row), {"source_identity", "source_url",
                                        "neutral_label", "editorial_hold"})
            self.assertNotIn("HWPX", json.dumps(row))
            self.assertNotIn("document_capture_sha256", json.dumps(row))
        dispute = [r for r in nine if r["editorial_hold"]]
        self.assertEqual(len(dispute), 1)
        self.assertEqual(dispute[0]["source_identity"], "korea-policy:156785161")
        self.assertIn("unresolved excavation-year discrepancy",
                      dispute[0]["editorial_hold"])

    def test_altered_permissions_scope_and_extra_ids_refused(self):
        raw = json.loads(public.INDEX.read_text())
        for field, val in (
            ("source_ids", raw["source_ids"][:-1]),
            ("source_ids", raw["source_ids"] + ["156799999"]),
            ("source_ids", list(reversed(raw["source_ids"]))),
            ("state_commit", "f" * 40),
            ("release_mode", "full-hwpx-archive"),
            ("existing_five_unchanged", False),
            ("korean_semantic_or_media_rights_approval", True),
            ("production_desk_admission", True),
            ("model_or_email_admission", True),
            ("separate_owner_public_link_approval", False),
            ("owner_scope", "release-entire-MND-source-body"),
            ("body_original", "Korean publisher body pasted"),
        ):
            changed = copy.deepcopy(raw)
            changed[field] = val
            with self.subTest(field=field, value=str(val)[:20]):
                with patch.object(public, "load_json", return_value=changed):
                    with self.assertRaises(KoreaGateHold):
                        public.load_additional_korea_official_links()

    def test_original_register_and_license_notice_cannot_drift(self):
        actual, old = validate()
        altered = copy.deepcopy(actual)
        altered[8]["hwpx_capture_sha256"] = "f" * 64
        with patch.object(public, "held_review", return_value=(altered, old)):
            # The public loader must itself check that all returned IDs
            # agree with the pinned roster and rights-hash gate.
            with self.assertRaises(KoreaGateHold):
                public.load_additional_korea_official_links()

    def test_normal_public_site_has_fourteen_links_zero_documents(self):
        import sys
        sys.path.insert(0, str(ROOT / "site/preview"))
        import generate_preview as gp
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "site"
            report = gp.build(
                dest, "Korea Public Official Links", ROOT / "pla_watch.db",
                snapshot=gp.snapshot_from_corpus(ROOT / "pla_watch.db"),
                site_origin="https://indopacificrecord.org")
            page = (dest / "korea.html").read_text(encoding="utf-8")
            self.assertEqual(report["korea_public_bibliography_entries"], 5)
            self.assertEqual(report["korea_additional_official_link_entries"], 9)
            self.assertEqual(page.count('data-korea-public-link='), 5)
            self.assertEqual(page.count('data-korea-additional-link='), 9)
            self.assertEqual(page.count(
                "https://www.korea.kr/briefing/pressReleaseView.do?newsId="), 14)
            self.assertIn("unresolved excavation-year discrepancy", page)
            self.assertIn("not IPR archived records", page)
            self.assertIn("KOGL Type 1", page)
            self.assertIn("Official-source directory", page)
            self.assertNotIn("noindex, nofollow", page)
            for forbidden in ("body_original", "text_original",
                              "download.do?fileId=", "data-review-status=",
                              "english_description", "HWPX capture SHA",
                              "source_content_sha256"):
                self.assertNotIn(forbidden, page)
            self.assertIn('href="korea.html"',
                          (dest / "desks.html").read_text(encoding="utf-8"))
            self.assertIn("https://indopacificrecord.org/korea.html",
                          (dest / "sitemap.xml").read_text(encoding="utf-8"))

    def test_owner_release_is_narrow_and_pages_is_guarded(self):
        workflow = (ROOT / ".github/workflows/korea_public_bibliography_release.yml").read_text()
        self.assertIn('"research/korea_additional_public_official_links_2026-10-15.json"', workflow)
        self.assertIn("assert len(additional) == 9", workflow)
        self.assertIn("html.count('data-korea-additional-link=') == 9", workflow)
        self.assertIn("scripts.guard_korea_public_output_scope", workflow)
        self.assertIn("git add -A -- output/korea.html output/desk-references.css", workflow)
        self.assertIn("publish_required == 'true'", workflow)
        self.assertIn("sha256sum -c", workflow)
        registry = json.loads((ROOT / "desks/registry.json").read_text())
        korea = next(x for x in registry["desks"] if x["slug"] == "korea")
        self.assertEqual(korea["status"], "shadow")
        self.assertEqual(korea["manifest"], None)
        self.assertIs(korea["has_production_records"], False)
        self.assertIs(korea["public"], True)


if __name__ == "__main__":
    unittest.main()
