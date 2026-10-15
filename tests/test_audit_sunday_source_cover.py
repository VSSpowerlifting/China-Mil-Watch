"""Offline identity-only observer tests; no source bodies, models or email."""
from __future__ import annotations

import contextlib
import json
import unittest
from unittest.mock import patch

from scripts import audit_sunday_source_cover as cover

SATURDAY = "2026-10-10"
LONG_BODY = "SOURCE-BODY-NEVER-LEAVES-OBSERVER " * 12


def row(ident, desk, date, *, analyzed=None, significant=False, body=LONG_BODY):
    return {
        "id": ident, "desk_id": desk, "published_date": date,
        "analyzed_at": analyzed, "is_significant": significant,
        "text_original": body, "text_english": None,
    }


def source_key(x):
    return {"record_id": x["id"], "verified": True}


def fixture():
    # Reconstruct the concrete issue #355 shape, not copied publisher facts.
    # Two recent unscreened Singapore sources outrank the older pivotal item.
    singapore = [
        row(5071, "singapore", "2026-10-10"),
        row(5070, "singapore", "2026-10-10"),
        row(4911, "singapore", "2026-10-05"),
    ]
    china = [
        row(4937, "china", "2026-10-08", analyzed="2026-10-10",
            significant=True),
    ] + [
        row(6000 + x, "china", "2026-10-09", analyzed="2026-10-10",
            significant=True) for x in range(7)
    ]
    rows = singapore + china
    sidecar = {
        "week_start": "2026-10-04",
        "week_ending": SATURDAY,
        "desks": ["singapore", "china"],
        "source_trail": [source_key(x) for x in rows],
    }
    return sidecar, rows


class SourceCoverReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.sidecar, self.rows = fixture()
        self._patches = [
            patch("scripts.audit_sunday_source_cover.read_only",
                  return_value=contextlib.nullcontext(None)),
            patch("scripts.sunday_briefs_auto_writer.read_only",
                  return_value=contextlib.nullcontext(None)),
            patch("scripts.audit_sunday_source_cover.get_articles_for_desks",
                  return_value=self.rows),
            patch("scripts.sunday_briefs_auto_writer.get_articles_for_desks",
                  return_value=self.rows),
            patch("scripts.audit_sunday_source_cover.trail_entry",
                  side_effect=source_key),
            patch("scripts.sunday_briefs_auto_writer.trail_entry",
                  side_effect=source_key),
        ]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def audit(self, required=None):
        return cover.audit(self.sidecar, as_of=SATURDAY, required_ids=(
            required if required is not None else [4911, 4937]),
            db="/does/not/exist.db")

    def test_two_newer_singapore_sources_displace_eligible_priority_id(self):
        result = self.audit()
        self.assertEqual(result["selection_cap_unchanged"], 10)
        self.assertEqual(len(result["default_selected_ids"]), 10)
        self.assertIn(5071, result["default_selected_ids"])
        self.assertIn(5070, result["default_selected_ids"])
        self.assertIn(4937, result["default_selected_ids"])
        self.assertNotIn(4911, result["default_selected_ids"])
        self.assertEqual(
            [(r["record_id"], r["status"]) for r in result["reviewed_anchors"]],
            [(4911, "eligible_but_ranked_out"),
             (4937, "selected_by_default")])
        self.assertFalse(result["all_required_anchors_selected"])
        self.assertFalse(result["theme_override"])
        self.assertFalse(result["model_called"])
        self.assertFalse(result["email_sent"])

    def test_short_source_is_a_hold_not_a_ranking_omission(self):
        self.rows[2]["text_original"] = "short"
        self.assertEqual(
            self.audit()["reviewed_anchors"][0]["status"],
            "stored_body_shorter_than_minimum")

    def test_modified_source_trail_is_not_reported_as_eligible(self):
        self.sidecar["source_trail"][2]["verified"] = False
        self.assertEqual(
            self.audit()["reviewed_anchors"][0]["status"],
            "source_trail_mismatch")

    def test_source_absent_from_exact_trail(self):
        self.sidecar["source_trail"] = [
            x for x in self.sidecar["source_trail"] if x["record_id"] != 4911]
        self.assertEqual(
            self.audit()["reviewed_anchors"][0]["status"],
            "not_in_exact_source_trail")

    def test_absent_id_is_not_invented(self):
        result = self.audit([4911, 9999999])
        self.assertEqual(
            result["reviewed_anchors"][1],
            {"record_id": 9999999, "desk": None,
             "status": "absent_from_reporting_window_or_production",
             "selected_by_default": False})

    def test_invalid_ids_and_future_cutoff_fail_closed(self):
        for ids in ([], [4911, 4911], [True], [0], [-5], ["4911"],
                    list(range(1, 12))):
            with self.subTest(ids=ids), self.assertRaises(cover.SourceCoverageError):
                self.audit(ids)
        with self.assertRaises(cover.SourceCoverageError):
            cover.audit(self.sidecar, as_of="2026-10-15",
                        required_ids=[4911], db="/does/not/exist.db")

    def test_diagnostic_never_serializes_documentary_body_or_source_url(self):
        result = self.audit()
        serialized = json.dumps(result)
        self.assertNotIn("SOURCE-BODY-NEVER", serialized)
        self.assertNotIn("text_original", serialized)
        self.assertNotIn("source_url", serialized)
        self.assertEqual(result["production_or_review_approved"], False)


if __name__ == "__main__":
    unittest.main()
