"""Offline synthetic tests: no actual Vietnamese article is reviewed or approved."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core.brief_external_evidence import CHECKS, validate_external_evidence
from scripts.bridge_vietnam_reviewed_brief_citations import (
    CitationBridgeRefused, OUT_SCHEMA, SCHEMA, build, load, main,
)
from tests.test_ipr_briefs import complete, registry

REF = "mps-vi:1000000000"
EXT = "VN-MPS-1000000000"
URL = "https://bocongan.gov.vn/bai-viet/synthetic-review-test-1000000000"
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = registry(live=("china", "singapore"), shadow=("vietnam",))


def sidecar():
    sc = complete()
    sc.update(week_start="2026-10-04", week_ending="2026-10-10")
    sc["opening_note"] += " [External " + REF + "]"
    for row in sc["source_trail"]:
        row["date"] = "2026-10-05"
    return sc


def candidate():
    return {
        "id": EXT,
        "desk": "vietnam",
        "source_name": "Vietnam Ministry of Public Security",
        "source_url": URL,
        "published_date": "2026-10-05",
        "language": "vi",
        "title_original": "Thử nghiệm xác minh nguồn tin bằng dữ liệu giả",
        "source_kind": "shadow-extracted-original",
        "state_commit": "a" * 40,
        "source_content_sha256": "b" * 64,
        "hash_rule": "mps-vi-content-v1",
        "summary": "Synthetic and unapproved summary of a fictitious ministry meeting, "
                   "used only to exercise metadata boundary checks.",
        "caveats": ["A fictional fixture does not prove any ministry action."],
        "topics": ["technology_cooperation"],
        "status": "unapproved-source-linked-editorial-candidate",
        "copy_scope": "private-model-drafting-only-no-source-body",
    }


def packet():
    return {
        "schema": "ipr-private-drafting-evidence/1",
        "week_ending": "2026-10-10",
        "status": "unapproved-source-linked-editorial-candidate",
        "items": [candidate()],
    }


def reviewer_receipt():
    item = candidate()
    return {
        "schema": SCHEMA,
        "week_ending": "2026-10-10",
        "records": [{
            "external_id": EXT,
            "source_identity": REF,
            "source_url": URL,
            "published_date": item["published_date"],
            "original_title": item["title_original"],
            "state_commit": item["state_commit"],
            "source_content_sha256": item["source_content_sha256"],
            "reviewed_by": "Independent fixture reviewer",
            "reviewed_on": "2026-10-08",
            "link_and_summary_use_basis": (
                "Fixture documentation of a narrow source-link and "
                "original-analyst-summary use basis, not an actual permission decision."
            ),
            "original_summary": (
                "This wholly synthetic analysis is written for a structural "
                "test only and makes no assertion about a real ministry report."
            ),
            "checks": {k: True for k in CHECKS},
        }],
    }


class VietnamReviewedCitationBridgeTests(unittest.TestCase):
    def test_exact_review_version_and_real_citation_yield_draft_fragment(self):
        sc = sidecar()
        result = build(sc, packet(), reviewer_receipt(), REGISTRY)
        self.assertEqual(result["schema"], OUT_SCHEMA)
        self.assertFalse(result["publication_approved"])
        self.assertTrue(result["final_brief_approval_required"])
        self.assertFalse(result["source_full_text_copied"])
        self.assertEqual(len(result["external_evidence"]), 1)
        review = result["external_evidence"][0]
        self.assertEqual(review["content_sha256"], candidate()["source_content_sha256"])
        self.assertEqual(review["source_identity"], REF)
        self.assertEqual(review["original_summary"],
                         reviewer_receipt()["records"][0]["original_summary"])
        self.assertEqual(validate_external_evidence(
            dict(sc, external_evidence=result["external_evidence"]),
            REGISTRY), [])
        self.assertEqual(sc["desks"], ["china", "singapore"])
        self.assertNotIn("external_evidence", sc)

    def test_unreviewed_or_uncited_vietnam_must_not_be_published_as_reference(self):
        sc = sidecar()
        sc["opening_note"] = "No external reference in this edit."
        with self.assertRaisesRegex(CitationBridgeRefused, "no bounded"):
            build(sc, packet(), reviewer_receipt(), REGISTRY)
        r = reviewer_receipt()
        r["records"] = []
        with self.assertRaises(CitationBridgeRefused):
            build(sidecar(), packet(), r, REGISTRY)

    def test_version_pin_and_title_mismatch_refuse_review_receipt(self):
        for field, value in (
            ("state_commit", "c" * 40),
            ("source_content_sha256", "d" * 64),
            ("source_url", "https://bocongan.gov.vn/bai-viet/other-1000000000"),
            ("published_date", "2026-10-06"),
            ("original_title", "Different original Vietnamese title"),
            ("external_id", "VN-MPS-2000000000"),
        ):
            r = reviewer_receipt()
            r["records"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                    CitationBridgeRefused, "not bound"):
                build(sidecar(), packet(), r, REGISTRY)

    def test_missing_falsified_or_surplus_human_check_refused(self):
        for mode in ("false", "missing", "extra", "no-reviewer", "no-basis",
                     "too-short-summary", "future-review", "pre-publication"):
            r = reviewer_receipt()
            row = r["records"][0]
            if mode == "false":
                row["checks"]["complete_original_body_reviewed"] = False
            elif mode == "missing":
                del row["checks"]["source_page_opened"]
            elif mode == "extra":
                row["checks"]["license_approved"] = True
            elif mode == "no-reviewer":
                row["reviewed_by"] = ""
            elif mode == "no-basis":
                row["link_and_summary_use_basis"] = "ok"
            elif mode == "too-short-summary":
                row["original_summary"] = "Safe"
            elif mode == "future-review":
                row["reviewed_on"] = "2099-01-01"
            else:
                row["reviewed_on"] = "2026-10-04"
            with self.subTest(mode=mode), self.assertRaises(CitationBridgeRefused):
                build(sidecar(), packet(), r, REGISTRY)

    def test_unaudited_shadow_article_cannot_gain_validated_external_status(self):
        for field, value in (
            ("status", "approved"),
            ("copy_scope", "public-full-text-license"),
            ("hash_rule", "sha256-metadata"),
            ("state_commit", "missing"),
            ("source_url", "https://bocongan.gov.vn.evil.test/bai-viet/x-1000000000"),
            ("desk", "singapore"),
        ):
            p = packet()
            p["items"][0][field] = value
            with self.subTest(field=field), self.assertRaises(CitationBridgeRefused):
                build(sidecar(), p, reviewer_receipt(), REGISTRY)

    def test_cannot_replace_production_source_trail_or_forge_live_vietnam_desk(self):
        for mode in ("vietnam-live", "no-second-trail", "external-already",
                     "published-sidecar", "missing-vietnam-registry"):
            sc = sidecar()
            reg = REGISTRY
            if mode == "vietnam-live":
                sc["desks"].append("vietnam")
            elif mode == "no-second-trail":
                sc["source_trail"] = sc["source_trail"][:1]
            elif mode == "external-already":
                sc["external_evidence"] = [{"source_identity": REF}]
            elif mode == "published-sidecar":
                sc["editorial_status"] = "approved"
            else:
                reg = registry(live=("china", "singapore"))
            with self.subTest(mode=mode), self.assertRaises(CitationBridgeRefused):
                build(sc, packet(), reviewer_receipt(), reg)

    def test_other_country_unrelated_research_preserved_but_not_promoted(self):
        p = packet()
        japan = copy.deepcopy(candidate())
        japan["desk"] = "japan"
        japan["id"] = "JP-W41-01"
        japan["source_name"] = "Japan Ministry of Defense"
        japan["source_url"] = "https://www.mod.go.jp/en/article/synthetic.html"
        p["items"].append(japan)
        result = build(sidecar(), p, reviewer_receipt(), REGISTRY)
        self.assertEqual(len(result["external_evidence"]), 1)
        self.assertEqual(result["external_evidence"][0]["desk"], "vietnam")

    def test_json_file_refuses_duplicate_keys_and_large_unapproved_content(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "unsafe.json"
            p.write_text('{"schema":"a","schema":"b"}', encoding="utf-8")
            with self.assertRaisesRegex(CitationBridgeRefused, "duplicate"):
                load(p)
            p.write_text('{"a":"' + "x" * 1000 + '"}', encoding="utf-8")
            with self.assertRaises(CitationBridgeRefused):
                load(p, max_size=50)

    def test_cli_writes_only_private_fragment_after_all_checks_succeed(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for filename, content in (
                ("draft.json", sidecar()),
                ("sources.json", packet()),
                ("human-review.json", reviewer_receipt()),
            ):
                (base / filename).write_text(
                    json.dumps(content, ensure_ascii=False), encoding="utf-8")
            args = ["--draft-sidecar", str(base / "draft.json"),
                    "--private-research-packet", str(base / "sources.json"),
                    "--human-source-review", str(base / "human-review.json"),
                    "--out", str(base / "review-fragment.json")]
            from unittest.mock import patch
            with patch("scripts.bridge_vietnam_reviewed_brief_citations.load_registry",
                       return_value=REGISTRY):
                self.assertEqual(main(args), 0)
            got = json.loads((base / "review-fragment.json").read_text())
            self.assertFalse(got["publication_approved"])
            self.assertTrue(got["final_brief_approval_required"])
            with self.assertRaises(CitationBridgeRefused):
                main(args)
            self.assertEqual(hashlib.sha256(
                (base / "draft.json").read_bytes()).hexdigest(),
                hashlib.sha256(
                    (base / "draft.json").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
