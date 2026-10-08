"""Offline contract tests for the read-only Friday Briefs source audit."""
from __future__ import annotations

from contextlib import nullcontext
from datetime import date
from pathlib import Path
import unittest
from unittest.mock import patch

from scripts.weekly_briefs_source_preflight import (
    _valid_friday, collect_report, summarize,
)


def records():
    return [
        {"id": 101, "desk_id": "china",
         "text_english": "A" * 300, "text_original": "原" * 300},
        {"id": 202, "desk_id": "singapore",
         "text_english": None, "text_original": "B" * 400},
        {"id": 303, "desk_id": "china",
         "text_english": None, "text_original": "brief"},
    ]


def trail(row):
    return {"record_id": row["id"], "desk": row["desk_id"]}


def draft():
    return {"source_trail": [trail(r) for r in records()]}


class SourceReadinessTests(unittest.TestCase):
    def test_report_uses_verified_fulltext_and_no_source_body(self):
        chosen = [(records()[0], "A" * 300), (records()[1], "B" * 400)]
        with patch("scripts.weekly_briefs_source_preflight.trail_entry",
                   side_effect=trail):
            result = summarize(
                friday=date(2026, 10, 2),
                desks=["china", "singapore"],
                records=records(), draft=draft(), selected=chosen,
            )
        self.assertEqual(result["total_source_records"], 3)
        self.assertEqual(result["offered_source_candidates"], 3)
        self.assertEqual(result["selected_fulltext_records"], 2)
        self.assertEqual(result["selected_desk_count"], 2)
        self.assertEqual(result["by_desk"]["china"]["usable_fulltext"], 1)
        self.assertEqual(result["by_desk"]["singapore"]["chosen_for_model"], 1)
        self.assertEqual(result["sunday_start"], "2026-09-27")
        self.assertEqual(result["saturday_identity"], "2026-10-03")
        self.assertTrue(result["ready"])
        self.assertFalse(result["approved_or_published"])
        self.assertNotIn("A" * 300, str(result))
        self.assertNotIn("http", str(result))

    def test_missing_second_desk_blocks_readiness_without_guessing(self):
        with patch("scripts.weekly_briefs_source_preflight.trail_entry",
                   side_effect=trail):
            result = summarize(
                friday=date(2026, 10, 2),
                desks=["china", "singapore"],
                records=records(), draft=draft(),
                selected=[(records()[0], "A" * 300)],
            )
        self.assertFalse(result["ready"])
        self.assertEqual(result["selected_desk_count"], 1)
        self.assertEqual(result["status"], "BLOCKED_INSUFFICIENT_DESKS")

    def test_unaudited_or_too_short_records_not_counted_as_fulltext(self):
        items = records()
        tampered = {"record_id": 101, "desk": "other"}
        packet = {"source_trail": [tampered, trail(items[1]), trail(items[2])]}
        with patch("scripts.weekly_briefs_source_preflight.trail_entry",
                   side_effect=trail):
            result = summarize(friday=date(2026, 10, 2),
                               desks=["china", "singapore"], records=items,
                               draft=packet, selected=[])
        self.assertEqual(result["by_desk"]["china"]["usable_fulltext"], 0)
        self.assertEqual(result["by_desk"]["singapore"]["usable_fulltext"], 1)

    def test_friday_format_and_future_guard_before_any_db_access(self):
        for value in ("2026-10-01", "20261002", "invalid"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _valid_friday(value)
        with self.assertRaisesRegex(ValueError, "future"):
            _valid_friday("2099-12-25")

    def test_collect_calls_only_readonly_corpus_and_existing_selector(self):
        items = records()
        packet = draft()
        selected = [(items[0], "A" * 300), (items[1], "B" * 400)]
        module = "scripts.weekly_briefs_source_preflight."
        with patch(module + "live_editorial_desks",
                   return_value=["china", "singapore"]) as desk_loader, \
             patch(module + "read_only",
                   return_value=nullcontext("DB-CONNECTION")) as read, \
             patch(module + "get_articles_for_desks",
                   return_value=items) as load, \
             patch(module + "build_draft",
                   return_value=packet) as build, \
             patch(module + "choose_evidence",
                   return_value=selected) as choose, \
             patch(module + "trail_entry", side_effect=trail):
            result = collect_report("2026-10-02", db="/tmp/mock-readonly.db")
        self.assertTrue(result["ready"])
        desk_loader.assert_called_once()
        read.assert_called_once_with(Path("/tmp/mock-readonly.db"))
        load.assert_called_once_with(
            "2026-09-27", "2026-10-02",
            ["china", "singapore"], conn="DB-CONNECTION",
        )
        build.assert_called_once_with(
            items, desks=["china", "singapore"],
            week_start="2026-09-27", week_ending="2026-10-03",
        )
        choose.assert_called_once_with(
            packet, as_of="2026-10-02", db="/tmp/mock-readonly.db",
        )

    def test_blocked_evidence_gate_yields_no_email_no_model(self):
        items = records()
        module = "scripts.weekly_briefs_source_preflight."
        with patch(module + "live_editorial_desks",
                   return_value=["china", "singapore"]), \
             patch(module + "read_only",
                   return_value=nullcontext(None)), \
             patch(module + "get_articles_for_desks", return_value=items), \
             patch(module + "build_draft", return_value=draft()), \
             patch(module + "choose_evidence", side_effect=ValueError(
                 "fewer than two desks with full-text evidence; not safe to generate a cross-desk Brief"
             )), \
             patch(module + "trail_entry", side_effect=trail):
            report = collect_report("2026-10-02")
        self.assertFalse(report["ready"])
        self.assertEqual(report["selected_fulltext_records"], 0)

    def test_unexpected_integrity_errors_fail_closed(self):
        module = "scripts.weekly_briefs_source_preflight."
        with patch(module + "live_editorial_desks",
                   return_value=["china", "singapore"]), \
             patch(module + "read_only",
                   return_value=nullcontext(None)), \
             patch(module + "get_articles_for_desks", return_value=records()), \
             patch(module + "build_draft", return_value=draft()), \
             patch(module + "choose_evidence",
                   side_effect=ValueError("source trail has changed")):
            with self.assertRaisesRegex(ValueError, "source trail"):
                collect_report("2026-10-02")

    def test_workflow_manual_and_secretless(self):
        yml = (Path(__file__).resolve().parents[1] / ".github" /
               "workflows" / "ipr_briefs_source_readiness.yml"
               ).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", yml)
        self.assertNotIn("schedule:", yml)
        self.assertIn("scripts.weekly_briefs_source_preflight", yml)
        self.assertNotIn("secrets.", yml)
        self.assertNotIn("ANTHROPIC_API_KEY", yml)
        self.assertNotIn("SMTP_SSL", yml)
        self.assertNotIn("contents: write", yml)


if __name__ == "__main__":
    unittest.main()
