"""No-network tests for post-Friday IPR Briefs source reconciliation."""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.weekly_briefs_saturday_audit import (
    collect_report, main, parse_original_packet, parse_saturday, summarize,
)
from scripts.weekly_editorial_handoff import render_packet


SATURDAY = date(2026, 10, 3)
SUNDAY = datetime(2026, 10, 4, 17, 0, tzinfo=timezone.utc)


def sample_rows():
    return [
        {"id": 101, "desk_id": "china", "published_date": "2026-09-30",
         "title_english": "China statement", "excluded": False},
        {"id": 201, "desk_id": "singapore", "published_date": "2026-10-01",
         "title_english": "Singapore statement", "excluded": False},
        {"id": 102, "desk_id": "china", "published_date": "2026-10-03",
         "title_english": "Saturday statement", "excluded": False},
        {"id": 202, "desk_id": "singapore", "published_date": "2026-10-03",
         "title_english": "Saturday screened out", "excluded": True},
    ]


def fake_build(rows, *, desks, week_start, week_ending):
    return {
        "source_trail": [
            {"record_id": r["id"], "desk": r["desk_id"],
             "date": r["published_date"]}
            for r in rows if not r["excluded"]
        ],
    }


def friday_packet():
    sidecar = {
        "editorial_status": "draft",
        "issue_number": None,
        "week_start": "2026-09-27",
        "week_ending": "2026-10-03",
        "desks": ["china", "singapore"],
        "coverage_by_desk": {
            "china": {"records": 1, "by_screening": {"analyzed": 1}},
            "singapore": {"records": 1, "by_screening": {"awaiting_screening": 1}},
        },
        "source_trail": [
            {"record_id": 101, "desk": "china", "date": "2026-09-30",
             "source": "Agency A", "title": "China statement",
             "title_original": "China statement", "lang": "en",
             "url": "https://example.com/a", "screening": "analyzed"},
            {"record_id": 201, "desk": "singapore", "date": "2026-10-01",
             "source": "Agency B", "title": "Singapore statement",
             "title_original": "Singapore statement", "lang": "en",
             "url": "https://example.com/b", "screening": "awaiting_screening"},
        ],
    }
    return render_packet(sidecar, as_of="2026-10-02")


class SaturdayAuditTests(unittest.TestCase):
    def test_new_york_local_cutoff_requires_complete_saturday(self):
        with self.assertRaisesRegex(ValueError, "incomplete Saturday"):
            parse_saturday(
                "2026-10-03",
                now=datetime(2026, 10, 4, 2, 0, tzinfo=timezone.utc),
            )
        self.assertEqual(parse_saturday("2026-10-03", now=SUNDAY), SATURDAY)
        for value in ("20261003", "2026-10-02", "not-a-date"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_saturday(value, now=SUNDAY)
        with self.assertRaisesRegex(ValueError, "timezone"):
            parse_saturday("2026-10-03", now=datetime(2026, 10, 4, 12, 0))

    def test_saturday_candidates_are_bounded_to_current_stored_state(self):
        rows = sample_rows()
        fridays = [r for r in rows if r["published_date"] < "2026-10-03"]
        saturdays = [r for r in rows if r["published_date"] == "2026-10-03"]
        result = summarize(
            saturday=SATURDAY, desks=["china", "singapore"],
            friday_rows=fridays, saturday_rows=saturdays,
            friday_draft=fake_build(fridays, desks=[], week_start="", week_ending=""),
            full_draft=fake_build(rows, desks=[], week_start="", week_ending=""),
        )
        self.assertEqual(result["saturday_stored_records"], 2)
        self.assertEqual(result["saturday_offered_candidates"], 1)
        self.assertTrue(result["saturday_records_require_editorial_review"])
        self.assertEqual(result["by_desk"]["china"]["saturday_candidates"], 1)
        self.assertEqual(result["by_desk"]["singapore"]["saturday_stored"], 1)
        self.assertEqual(result["by_desk"]["singapore"]["saturday_candidates"], 0)
        self.assertFalse(result["approval_or_publication_authorized"])
        self.assertNotIn("https://", str(result))
        self.assertNotIn("Saturday statement", str(result))

    def test_unchanged_packet_has_no_friday_candidate_drift(self):
        rows = sample_rows()
        fridays = [r for r in rows if r["published_date"] < "2026-10-03"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "friday.txt"
            path.write_text(friday_packet(), encoding="utf-8")
            original = parse_original_packet(path, saturday=SATURDAY)
        result = summarize(
            saturday=SATURDAY, desks=["china", "singapore"],
            friday_rows=fridays,
            saturday_rows=[r for r in rows if r["published_date"] == "2026-10-03"],
            friday_draft=fake_build(fridays, desks=[], week_start="", week_ending=""),
            full_draft=fake_build(rows, desks=[], week_start="", week_ending=""),
            original=original,
        )
        self.assertFalse(
            result["friday_packet_comparison"]["needs_friday_reconciliation"]
        )
        self.assertEqual(result["friday_packet_comparison"]["original_friday_candidates"], 2)

    def test_friday_candidate_drift_is_review_flag_not_auto_published(self):
        rows = sample_rows()
        fridays = [r for r in rows if r["published_date"] < "2026-10-03"]
        baseline = {"records": {101: "china", 999: "china"}}
        result = summarize(
            saturday=SATURDAY, desks=["china", "singapore"],
            friday_rows=fridays, saturday_rows=[],
            friday_draft=fake_build(fridays, desks=[], week_start="", week_ending=""),
            full_draft=fake_build(fridays, desks=[], week_start="", week_ending=""),
            original=baseline,
        )
        changes = result["friday_packet_comparison"]
        self.assertEqual(changes["new_candidate_ids_since_packet"], 1)
        self.assertEqual(changes["missing_or_no_longer_offered_ids"], 1)
        self.assertTrue(changes["needs_friday_reconciliation"])
        self.assertFalse(result["approval_or_publication_authorized"])

    def test_packet_date_and_source_appendix_tampering_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "orig.txt"
            for text in (
                friday_packet().replace("Packet: IPR-2026-10-03",
                                        "Packet: IPR-2026-10-10"),
                friday_packet().replace("AS-OF CUT-OFF: 2026-10-02",
                                        "AS-OF CUT-OFF: 2026-10-03"),
                friday_packet().replace("Record 101 | china | 2026-09-30",
                                        "Record 101 | china | 2026-10-03"),
                friday_packet().replace("Record 201 | singapore | 2026-10-01",
                                        "Record 101 | singapore | 2026-10-01"),
            ):
                with self.subTest(text=text[:70]):
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        parse_original_packet(path, saturday=SATURDAY)

    def test_collect_queries_only_week_once_and_never_networks(self):
        module = "scripts.weekly_briefs_saturday_audit."
        rows = sample_rows()
        with patch(module + "live_editorial_desks",
                   return_value=["china", "singapore"]) as desk_loader, \
             patch(module + "read_only",
                   return_value=contextlib.nullcontext("READ-ONLY")) as ro, \
             patch(module + "get_articles_for_desks", return_value=rows) as get, \
             patch(module + "build_draft", side_effect=fake_build) as build:
            result = collect_report("2026-10-03", db="/tmp/mock.db", now=SUNDAY)
        self.assertEqual(result["saturday_offered_candidates"], 1)
        desk_loader.assert_called_once()
        ro.assert_called_once_with(Path("/tmp/mock.db"))
        get.assert_called_once_with(
            "2026-09-27", "2026-10-03",
            ["china", "singapore"], conn="READ-ONLY",
        )
        self.assertEqual(build.call_count, 2)
        self.assertEqual(build.call_args_list[0].args[0][0]["id"], 101)

    def test_cli_emits_aggregate_only_and_read_only(self):
        with patch("scripts.weekly_briefs_saturday_audit.collect_report",
                   return_value={
                       "saturday_stored_records": 1,
                       "saturday_offered_candidates": 1,
                       "approval_or_publication_authorized": False,
                   }):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(main(["--saturday", "2026-10-03"]), 0)
            self.assertIn("Unapproved source audit only", stdout.getvalue())
            self.assertNotIn("example.com", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
