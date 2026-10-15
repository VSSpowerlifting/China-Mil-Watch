"""Offline safety tests for owner-specific permanent seven-day desk exception."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PermanentDeskExceptionPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.criteria = (ROOT / "docs/DESK_STRENGTH_CRITERIA.md").read_text()
        cls.record = (ROOT / "docs/PERMANENT_DESK_ACCELERATED_ACTIVATION_2026-10-15.md").read_text()
        cls.registry = {d["slug"]: d for d in
                        json.loads((ROOT / "desks/registry.json").read_text())["desks"]}

    def test_exact_accelerated_source_path_and_remaining_regular_standard(self):
        section = self.criteria.split("### C13 — No promotion on elapsed days alone", 1)[1].split("\n---", 1)[0]
        for phrase in (
            "Thirty consecutive genuine collecting days",
            "normal",
            "at least seven",
            "consecutive successful scheduled logical collecting days",
            "C1–C12",
            "Actions run/attempt/job census",
            "every record selected for",
            "reuse rights",
            "source-state SHA",
            "Day 14 and Day 30",
            "DECISION_LOG.md",
        ):
            self.assertIn(phrase, section)
        self.assertNotIn("automatically when this policy is updated", self.criteria[:self.criteria.index("### C13")])
        self.assertIn("No source, desk status, production database, render,", section)

    def test_exception_is_not_unverified_source_or_rights_approval(self):
        for phrase in (
            "not source-specific publication approval",
            "seven consecutive",
            "cancelled/missing/failed",
            "publisher's robots/access terms",
            "Named substantive human source review",
            "exact original language",
            "Source-specific rights and access decision",
            "owner",
            "DECISION_LOG.md",
            "No status tag",
            "not yet admitted",
            "not a completed release receipt",
        ):
            self.assertIn(phrase, self.record)
        self.assertNotIn("production_eligible=true", self.record)
        self.assertNotIn("bypass robots", self.record)
        self.assertNotIn("ignore copyright", self.record)

    def test_no_country_promoted_by_exception_document(self):
        for name in ("philippines", "indonesia", "korea", "japan", "vietnam"):
            d = self.registry[name]
            self.assertEqual(d["status"], "shadow")
            self.assertFalse(d["has_production_records"])
        for name in ("china", "singapore"):
            self.assertEqual(self.registry[name]["status"], "live")
            self.assertTrue(self.registry[name]["has_production_records"])

    def test_policy_requires_real_postlaunch_day14_and_day30_observation(self):
        for phrase in (
            "after those dates occur",
            "without backdating",
            "material coverage failure",
            "stop admission",
            "never retroactively",
        ):
            self.assertIn(phrase, self.record)


if __name__ == "__main__":
    unittest.main()
