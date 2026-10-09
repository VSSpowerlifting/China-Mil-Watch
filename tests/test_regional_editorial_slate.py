"""Offline checks for the proposed private regional intelligence slate."""
from __future__ import annotations

import copy
import unittest

from core.regional_editorial_slate import (
    SCHEMA, SlateError, heuristic_score, validate_slate,
)


def source(ident, desk, *, lane="production_record", role="new_week"):
    return {
        "id": ident, "desk": desk, "lane": lane,
        "scope": ("production_evidence" if lane == "production_record"
                  else "private_drafting_candidate"),
        "source_url": "https://example.gov/" + str(ident),
        "published_date": "2026-10-08" if role == "new_week" else "2026-09-28",
        "role": role, "topic_suggestions": ["maritime-security"],
    }


def theme(slug, ids, **scores):
    values = {
        "strategic_significance": 4,
        "evidence_strength": 4,
        "analytical_novelty": 3,
        "cross_desk_connection": 1,
        "timeliness": 5,
    }
    values.update(scores)
    return {
        "slug": slug,
        "thesis": "One documented development has substantial regional implications",
        "why_now": "New official reporting falls inside the reporting week",
        "source_ids": ids,
        "counterevidence": "No independent confirmation of broader causality",
        "limitations": "Source accounts do not prove institutional coordination",
        "topic_threads": ["maritime-security"],
        "scores": values,
    }


def example():
    return {
        "schema": SCHEMA, "week_start": "2026-10-04",
        "week_ending": "2026-10-10",
        "coverage": [
            {"desk": "china", "state": "reviewable",
             "reason": "In-week text and citations independently checked"},
            {"desk": "singapore", "state": "no_qualifying_evidence",
             "reason": "No eligible in-week records observed"},
            {"desk": "japan", "state": "collector_unavailable",
             "reason": "Collector rights status has not been resolved"},
        ],
        "evidence": [source(42, "china")],
        "candidates": [theme("security-cooperation", [42])],
        "provisional_lead": "security-cooperation",
        "lead_rationale": "Grounded evidence beats weak cross-desk coincidence",
    }


class RegionalSlateTests(unittest.TestCase):
    def test_one_desk_lead_while_other_desks_are_unavailable(self):
        slate = example()
        self.assertIs(validate_slate(
            slate, expected_desks=["china", "singapore", "japan"]), slate)
        self.assertEqual(heuristic_score(slate["candidates"][0]["scores"]), 3.55)

    def test_three_theme_competition_does_not_force_high_score_to_win(self):
        doc = example()
        doc["coverage"][1]["state"] = "reviewable"
        doc["coverage"][1]["reason"] = "In-week source verified"
        doc["coverage"][2]["state"] = "reviewable"
        doc["coverage"][2]["reason"] = "Private research candidate checked"
        doc["evidence"].extend([
            source(47, "singapore"),
            source("JP-W41-01", "japan", lane="private_research"),
            source(18, "china", role="historical_context"),
        ])
        doc["candidates"] = [
            theme("regional-partnerships", [47, "JP-W41-01"]),
            theme("single-country-change", [42],
                  strategic_significance=5, cross_desk_connection=0),
            theme("historical-continuity", [18, 42, 47]),
        ]
        doc["provisional_lead"] = "single-country-change"
        self.assertIs(validate_slate(doc), doc)

    def test_abstention_from_weak_or_absent_evidence(self):
        doc = example()
        for row in doc["coverage"]:
            row["state"] = "awaiting_validation"
            row["reason"] = "No eligible source can yet be attested"
        doc["evidence"] = []
        doc["candidates"] = []
        doc["provisional_lead"] = None
        doc["lead_rationale"] = "Abstain rather than invent a significance thesis"
        validate_slate(doc)
        doc["provisional_lead"] = "invented"
        with self.assertRaises(SlateError):
            validate_slate(doc)

    def test_registry_and_status_fail_closed(self):
        doc = example()
        with self.assertRaises(SlateError):
            validate_slate(doc, expected_desks=["china"])
        doc = example()
        doc["coverage"][0]["state"] = "awaiting_validation"
        with self.assertRaises(SlateError):
            validate_slate(doc)
        doc = example()
        doc["coverage"][2]["reason"] = "Institutional silence proves no activity"
        with self.assertRaises(SlateError):
            validate_slate(doc)

    def test_reject_forged_numeric_shadow_id_and_public_scope(self):
        doc = example()
        doc["evidence"][0]["lane"] = "private_research"
        doc["evidence"][0]["scope"] = "private_drafting_candidate"
        with self.assertRaises(SlateError):
            validate_slate(doc)
        doc = example()
        doc["evidence"][0]["lane"] = "private_research"
        doc["evidence"][0]["id"] = "JP-W41-01"
        doc["candidates"][0]["source_ids"] = ["JP-W41-01"]
        with self.assertRaises(SlateError):
            validate_slate(doc)
        doc["evidence"][0]["scope"] = "private_drafting_candidate"
        validate_slate(doc)

    def test_unverified_external_evidence_cannot_be_candidate_source(self):
        doc = example()
        doc["evidence"].append(
            source("JP-W41-01", "japan", lane="private_research"))
        with self.assertRaises(SlateError):
            validate_slate(doc)

    def test_reject_duplicate_or_missing_cited_ids(self):
        doc = example()
        doc["evidence"].append(copy.deepcopy(doc["evidence"][0]))
        with self.assertRaises(SlateError):
            validate_slate(doc)
        doc = example()
        doc["candidates"][0]["source_ids"] = [999]
        with self.assertRaises(SlateError):
            validate_slate(doc)

    def test_reject_wrong_week_and_context_only_theme(self):
        doc = example()
        doc["week_start"] = "2026-10-05"
        with self.assertRaises(SlateError):
            validate_slate(doc)
        doc = example()
        doc["evidence"].append(source(44, "china", role="historical_context"))
        doc["candidates"][0]["source_ids"] = [44]
        with self.assertRaises(SlateError):
            validate_slate(doc)

    def test_invalid_score_and_extra_body_refused(self):
        doc = example()
        doc["candidates"][0]["scores"]["timeliness"] = True
        with self.assertRaises(SlateError):
            validate_slate(doc)
        doc = example()
        doc["evidence"][0]["article_body"] = "Not permitted in slate"
        with self.assertRaises(SlateError):
            validate_slate(doc)

    def test_no_mandatory_multi_desk_and_no_auto_publication(self):
        doc = example()
        doc["candidates"][0]["scores"]["cross_desk_connection"] = 0
        doc["approved_for_publication"] = True
        with self.assertRaises(SlateError):
            validate_slate(doc)
        del doc["approved_for_publication"]
        self.assertIs(validate_slate(doc), doc)


if __name__ == "__main__":
    unittest.main()
