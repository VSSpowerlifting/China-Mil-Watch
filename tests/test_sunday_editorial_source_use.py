"""Sunday private source-use receipt says what entered the model vs article.

All tests are offline; no source fetch, Anthropic call, SMTP, publication or
production database writes. Section citation counts are model-output metadata,
not factual or translation verification.
"""
from __future__ import annotations

import copy
import unittest

from core.brief_editorial_source_use import (
    SourceUseError, format_private_source_use, summarize_source_use,
)
from core.brief_editorial_evidence import load_editorial_evidence
from scripts.sunday_editorial_handoff import render_packet
from scripts.validate_editorial_return import ReturnValidationError, validate_return
from tests.test_briefs_editorial_evidence import SAT, manuscript, scaffold

PROD = [
    {"record_id": 1, "desk": "china"},
    {"record_id": 2, "desk": "singapore"},
]


class PrivateSourceUseReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.research = load_editorial_evidence(SAT, SAT)

    def test_exact_source_citations_not_just_all_research_offered(self):
        report = summarize_source_use(manuscript(), PROD, self.research)
        self.assertEqual(report["schema"], "ipr-private-manuscript-source-use/1")
        self.assertEqual(report["research_by_desk"]["japan"]["offered"],
                         sum(x["desk"] == "japan" for x in self.research))
        self.assertEqual(report["research_by_desk"]["japan"]["cited"], 1)
        self.assertEqual(report["research_by_desk"]["vietnam"]["offered"],
                         sum(x["desk"] == "vietnam" for x in self.research))
        self.assertEqual(report["research_by_desk"]["vietnam"]["cited"], 1)
        self.assertEqual(len(report["research_used"]), 2)
        self.assertEqual({r["id"] for r in report["research_used"]},
                         {"JP-W41-01", "VN-MPS-1791199100"})
        self.assertEqual(
            report["research_by_desk"]["japan"]["unused_source_ids"],
            sorted(x["id"] for x in self.research
                   if x["desk"] == "japan" and x["id"] != "JP-W41-01"))
        vn_cited = next(item for item in report["research_used"]
                        if item["id"] == "VN-MPS-1791199100")
        self.assertEqual(vn_cited["sections"], ["why_it_matters"])
        self.assertTrue(report["external_research_is_not_production"])
        for marker in ("source_accuracy_or_rights_verified",
                       "claim_level_support_verified",
                       "coherent_theme_human_approved",
                       "editorial_or_publication_approval"):
            self.assertIs(report[marker], False)
        self.assertNotIn("source_url", repr(report))
        self.assertNotIn("summary", repr(report))
        self.assertNotIn("JP-W41-06 original", repr(report))

    def test_no_forced_inclusion_of_unrelated_japan_vietnam_research(self):
        m = manuscript()
        for field in m["supplemental_citations"]:
            m["supplemental_citations"][field] = []
        m["citations"]["cross_desk_comparison"] = [1, 2]
        m["citations"]["why_it_matters"] = [1]
        report = summarize_source_use(m, PROD, self.research)
        self.assertEqual(report["research_used"], [])
        self.assertEqual(report["research_by_desk"]["japan"]["cited"], 0)
        self.assertEqual(report["research_by_desk"]["vietnam"]["cited"], 0)
        lines = "\n".join(format_private_source_use(m, PROD, self.research))
        self.assertEqual(lines.count("NOT INCORPORATED:"), 2)
        self.assertIn("production sources only", lines)
        self.assertNotIn("Vietnam contributed to", lines)

    def test_private_manuscript_has_single_source_receipt_in_immutable_appendix(self):
        original = render_packet(scaffold(), manuscript=manuscript(),
                                 as_of=SAT, research_evidence=self.research)
        self.assertEqual(original.count(
            "=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ==="), 1)
        self.assertLess(original.index("=== SOURCE APPENDIX — DO NOT EDIT ==="),
                        original.index("=== MANUSCRIPT SOURCE USE"))
        self.assertIn(
            "japan: {} offered; 1 cited".format(
                sum(x["desk"] == "japan" for x in self.research)), original)
        self.assertIn(
            "vietnam: {} offered; 1 cited".format(
                sum(x["desk"] == "vietnam" for x in self.research)), original)
        self.assertIn("Uncited research IDs: JP-W41-02, JP-W41-06", original)
        changed_prose = original.replace(
            "Official statements around a concrete development",
            "Documentary accounts of official security cooperation", 1)
        self.assertIsInstance(validate_return(original, changed_prose), dict)
        with self.assertRaises(ReturnValidationError):
            validate_return(original, original.replace(
                "japan: 3 offered; 1 cited", "japan: 3 offered; 3 cited", 1))

    def test_no_model_manuscript_does_not_pretend_sources_were_used(self):
        worksheet = render_packet(scaffold(), manuscript=None, as_of=SAT,
                                  research_evidence=self.research)
        self.assertNotIn("=== MANUSCRIPT SOURCE USE", worksheet)
        self.assertIn("=== SOURCE APPENDIX — DO NOT EDIT ===", worksheet)

    def test_invalid_unoffered_or_numeric_pseudo_external_citations_refused(self):
        for wrong in ("JP-NONEXISTENT", "123"):
            m = copy.deepcopy(manuscript())
            m["supplemental_citations"]["why_it_matters"] = [wrong]
            with self.subTest(wrong=wrong), self.assertRaises(SourceUseError):
                summarize_source_use(m, PROD, self.research)
        m = copy.deepcopy(manuscript())
        m["citations"]["why_it_matters"] = [999]
        with self.assertRaises(SourceUseError):
            summarize_source_use(m, PROD, self.research)

    def test_unapproved_research_cannot_be_mislabeled_as_approved(self):
        research = copy.deepcopy(self.research)
        research[0]["status"] = "human-approved"
        with self.assertRaises(SourceUseError):
            summarize_source_use(manuscript(), PROD, research)

    def test_duplicate_research_or_production_id_blocks_receipt(self):
        with self.assertRaises(SourceUseError):
            summarize_source_use(manuscript(), PROD + PROD[:1], self.research)
        with self.assertRaises(SourceUseError):
            summarize_source_use(manuscript(), PROD, list(self.research) + [self.research[0]])

    def test_sections_are_deduplicated_and_only_actual_citation_fields_counted(self):
        m = manuscript()
        m["supplemental_citations"]["development"] = ["JP-W41-01"]
        report = summarize_source_use(m, PROD, self.research)
        cited = next(x for x in report["research_used"] if x["id"] == "JP-W41-01")
        self.assertEqual(cited["sections"], ["cross_desk_comparison", "development"])
        self.assertEqual(len(set(cited["sections"])), len(cited["sections"]))


if __name__ == "__main__":
    unittest.main()
