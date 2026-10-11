"""No-network tests: an unsigned worksheet NEVER constitutes source approval."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from core.brief_external_evidence import CHECKS
from scripts.bridge_vietnam_reviewed_brief_citations import (
    CitationBridgeRefused, build as validated_bridge,
)
from scripts.prepare_vietnam_unsigned_citation_review import (
    build_unsigned, main,
)
from tests.test_vietnam_reviewed_brief_citations import (
    REGISTRY, candidate, packet, sidecar,
)


class VietnamUnsignedCitedSourceTests(unittest.TestCase):
    def test_one_citation_generates_unapproved_pinned_source_only(self):
        item = candidate()
        original = packet()
        draft = sidecar()
        result = build_unsigned(draft, original)
        self.assertEqual(result["schema"], "vietnam-reviewed-brief-citation-receipt/1")
        self.assertEqual(len(result["records"]), 1)
        row = result["records"][0]
        self.assertEqual(row["external_id"], item["id"])
        self.assertEqual(row["source_url"], item["source_url"])
        self.assertEqual(row["source_content_sha256"],
                         item["source_content_sha256"])
        self.assertEqual(row["state_commit"], item["state_commit"])
        self.assertEqual(set(row["checks"]), CHECKS)
        self.assertTrue(all(v is False for v in row["checks"].values()))
        for name in ("reviewed_by", "reviewed_on", "original_summary",
                     "link_and_summary_use_basis"):
            self.assertIsNone(row[name])
        self.assertNotIn("summary", row)
        self.assertNotIn("article_body", row)
        with self.assertRaises(CitationBridgeRefused):
            validated_bridge(draft, original, result, REGISTRY)

    def test_three_candidates_select_only_the_draft_cited_subset(self):
        original = packet()
        draft = sidecar()
        others = []
        for digit in ("1000000001", "1000000002"):
            another = copy.deepcopy(candidate())
            another["id"] = "VN-MPS-" + digit
            another["source_url"] = (
                "https://bocongan.gov.vn/bai-viet/synthetic-review-" + digit)
            another["state_commit"] = digit[0] * 40
            another["source_content_sha256"] = digit[0] * 64
            original["items"].append(another)
            others.append(another)
        draft["opening_note"] += " [External mps-vi:1000000002]"
        review = build_unsigned(draft, original)
        self.assertEqual([x["source_identity"] for x in review["records"]],
                         ["mps-vi:1000000000", "mps-vi:1000000002"])
        self.assertNotIn("mps-vi:1000000001",
                         {x["source_identity"] for x in review["records"]})
        self.assertTrue(all(all(v is False for v in x["checks"].values())
                            for x in review["records"]))

    def test_bogus_draft_identity_and_fake_source_approval_refuse(self):
        original = packet()
        draft = sidecar()
        draft["opening_note"] += " [External mps-vi:1000000099]"
        with self.assertRaisesRegex(CitationBridgeRefused, "unknown"):
            build_unsigned(draft, original)
        cases = (
            ("status", "approved-for-publication"),
            ("copy_scope", "public-body-reuse"),
            ("source_content_sha256", "missing"),
            ("state_commit", None),
            ("source_url", "https://bocongan.gov.vn.evil.test/bai-viet/x-1000000000"),
            ("source_kind", "unverified-translation"),
        )
        for key, value in cases:
            fake = packet()
            fake["items"][0][key] = value
            with self.subTest(key=key), self.assertRaises(CitationBridgeRefused):
                build_unsigned(sidecar(), fake)

    def test_repeated_external_citations_cannot_flood_reviewer_queue(self):
        draft = sidecar()
        draft["opening_note"] += " [External mps-vi:1000000000]" * 9
        with self.assertRaisesRegex(CitationBridgeRefused, "excessively repeated"):
            build_unsigned(draft, packet())

    def test_wrong_week_published_or_numbered_draft_refused(self):
        for field, value in (
            ("editorial_status", "approved"),
            ("issue_number", 17),
            ("week_ending", "2026-10-09"),
            ("week_start", "2026-10-03"),
        ):
            draft = sidecar()
            draft[field] = value
            with self.subTest(field=field), self.assertRaises(CitationBridgeRefused):
                build_unsigned(draft, packet())

    def test_private_cli_never_overwrites_and_has_no_false_signoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            draft, research, out = (
                work / "draft.json", work / "research.json", work / "review.json")
            draft.write_text(json.dumps(sidecar()), encoding="utf-8")
            research.write_text(json.dumps(packet()), encoding="utf-8")
            flags = ["--draft-sidecar", str(draft), "--private-research-packet",
                     str(research), "--out", str(out)]
            self.assertEqual(main(flags), 0)
            row = json.loads(out.read_text())["records"][0]
            self.assertIsNone(row["reviewed_by"])
            self.assertTrue(all(x is False for x in row["checks"].values()))
            old = out.read_bytes()
            with self.assertRaises(CitationBridgeRefused):
                main(flags)
            self.assertEqual(out.read_bytes(), old)

    def test_no_model_network_smtp_production_or_approvals(self):
        root = Path(__file__).resolve().parents[1]
        script = (root / "scripts/prepare_vietnam_unsigned_citation_review.py"
                  ).read_text(encoding="utf-8")
        for forbidden in ("anthropic", "requests", "httpx", "smtplib",
                          "import sqlite3", "git push", "send_packet(", "approve("):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
