"""Offline typed Japan/Vietnam metadata-only source HOLD proofs."""
from __future__ import annotations

import copy
import json
import unittest

from core.brief_editorial_evidence import load_editorial_evidence
from core.regional_typed_research_holds import (
    TypedResearchHoldError, audit_typed_holds,
)
from tests.test_regional_weekly_inventory import make, pending, row

SAT = "2026-10-10"


def fixture():
    rows = load_editorial_evidence(SAT, SAT)
    inventory = make(research_rows=rows)
    return inventory, rows


class TypedResearchHoldTests(unittest.TestCase):
    def test_real_first_pilot_six_typed_sources_are_all_held(self):
        inventory, rows = fixture()
        report = audit_typed_holds(inventory, rows)
        self.assertEqual(report["schema"], "ipr-regional-typed-research-holds/1")
        self.assertEqual(sum(report["counts"][x] for x in ("japan", "vietnam")), 6)
        self.assertEqual(report["first_pilot_roster_gaps"], [])
        self.assertTrue(report["all_items_held_for_human_review"])
        self.assertFalse(report["model_input_authorized"])
        self.assertFalse(report["publication_authorized"])
        self.assertFalse(report["editor_email_authorized"])
        self.assertFalse(report["japan_vietnam_production_activated"])
        self.assertTrue(all(x["state"] ==
            "hold_independent_original_version_and_source_use_review"
            for x in report["items"]))
        self.assertEqual(len(report["typed_research_roster_sha256"]), 64)
        self.assertEqual(len({x["id"] for x in report["items"]}), 6)
        serialized = json.dumps(report)
        for x in rows:
            self.assertNotIn(x["source_url"], serialized)
            self.assertNotIn(x["summary"], serialized)
            self.assertNotIn(x["title_original"], serialized)
        self.assertNotIn("SENSITIVE RAW TEXT MUST NOT COPY", serialized)

    def test_shadow_hashes_present_but_never_certify_current_version(self):
        inv, rows = fixture()
        report = audit_typed_holds(inv, rows)
        for x in report["items"]:
            if x["historical_version_pin_structurally_present"]:
                self.assertEqual(len(x["state_commit"]), 40)
                self.assertEqual(len(x["source_content_sha256"]), 64)
                self.assertEqual(x["reason"],
                                 "historical_shadow_pin_present_current_capture_not_attested")
            else:
                self.assertIsNone(x["state_commit"])
                self.assertIsNone(x["source_content_sha256"])
                self.assertEqual(x["reason"],
                                 "publisher_page_immutable_original_missing_requires_review")
            self.assertFalse(x["private_model_input_authorized"])

    def test_inventory_holds_must_match_full_research_packet_exactly(self):
        inv, rows = fixture()
        with self.assertRaisesRegex(TypedResearchHoldError, "different typed"):
            audit_typed_holds(inv, rows[:-1])
        d = copy.deepcopy(rows)
        d[0]["source_url"] = "https://www.mod.go.jp/j/press/news/changed.html"
        with self.assertRaisesRegex(TypedResearchHoldError, "differs"):
            audit_typed_holds(inv, d)
        d = copy.deepcopy(rows)
        d.append(copy.deepcopy(d[0]))
        with self.assertRaises(TypedResearchHoldError):
            audit_typed_holds(inv, d)

    def test_forged_approval_and_production_promotion_fail_closed(self):
        inv, rows = fixture()
        for key, value in (("status", "approved"),
                           ("copy_scope", "public"),
                           ("desk", "china")):
            d = copy.deepcopy(rows)
            d[0][key] = value
            with self.subTest(key=key), self.assertRaises(TypedResearchHoldError):
                audit_typed_holds(inv, d)
        d = copy.deepcopy(inv)
        d["model_input_authorized"] = True
        with self.assertRaises(TypedResearchHoldError):
            audit_typed_holds(d, rows)

    def test_metadata_drift_and_duplicate_publisher_url_fail(self):
        inv, rows = fixture()
        d = copy.deepcopy(rows)
        d[0]["published_date"] = (
            "2026-10-06" if d[0]["published_date"] != "2026-10-06"
            else "2026-10-08")
        with self.assertRaises(TypedResearchHoldError):
            audit_typed_holds(inv, d)
        d = copy.deepcopy(rows)
        d[1]["source_url"] = d[0]["source_url"]
        with self.assertRaises(TypedResearchHoldError):
            audit_typed_holds(inv, d)
        modified = copy.deepcopy(inv)
        modified["production_evidence"][0]["source_url"] = rows[0]["source_url"]
        with self.assertRaisesRegex(TypedResearchHoldError, "duplicates"):
            audit_typed_holds(modified, rows)

    def test_missing_original_or_forged_shadow_digest_rejected(self):
        inv, rows = fixture()
        ix = next(i for i, r in enumerate(rows)
                  if r["source_kind"] == "shadow-extracted-original")
        d = copy.deepcopy(rows)
        d[ix]["source_content_sha256"] = None
        with self.assertRaisesRegex(TypedResearchHoldError, "immutable"):
            audit_typed_holds(inv, d)
        d = copy.deepcopy(rows)
        d[ix]["source_kind"] = "official-publisher-page-reviewed-for-research"
        with self.assertRaisesRegex(TypedResearchHoldError, "cannot claim"):
            audit_typed_holds(inv, d)
        d = copy.deepcopy(rows)
        d[ix]["source_kind"] = "phantom provenance"
        with self.assertRaisesRegex(TypedResearchHoldError, "unknown"):
            audit_typed_holds(inv, d)

    def test_first_pilot_gaps_are_reported_not_auto_approved(self):
        one = pending("JP-W41-01")
        inv = make(research_rows=[one])
        # Full loader would prohibit this intentionally impoverished sample.
        minimal = dict(one, source_name="Japan Ministry of Defense",
                       source_kind="official-publisher-page-reviewed-for-research",
                       state_commit=None, source_content_sha256=None,
                       hash_rule=None, copy_scope="private-model-drafting-only-no-source-body")
        audit = audit_typed_holds(inv, [minimal])
        self.assertIn("first_pilot_missing_japan_research_ids",
                      audit["first_pilot_roster_gaps"])
        self.assertIn("first_pilot_missing_vietnam_research",
                      audit["first_pilot_roster_gaps"])
        self.assertEqual(audit["first_pilot_missing_japan_ids"],
                         ["JP-W41-02", "JP-W41-06"])
        self.assertFalse(audit["model_input_authorized"])

    def test_future_empty_week_does_not_mean_publisher_silence(self):
        inv = make(week_ending="2026-10-17", as_of="2026-10-17",
                   review_day="2026-10-18", marker="2026-10-18",
                   research_rows=[], rows=[
                       row(42, "china", published_date="2026-10-15"),
                       row(47, "singapore", published_date="2026-10-15")])
        result = audit_typed_holds(inv, [])
        self.assertEqual(result["items"], [])
        self.assertEqual(result["first_pilot_roster_gaps"], [])
        self.assertTrue(result["all_items_held_for_human_review"])
        self.assertFalse(result["model_input_authorized"])

    def test_reject_unbounded_research_packet(self):
        inv, rows = fixture()
        many = rows + copy.deepcopy(rows[:3])
        with self.assertRaisesRegex(TypedResearchHoldError, "bounded"):
            audit_typed_holds(inv, many)


if __name__ == "__main__":
    unittest.main()
