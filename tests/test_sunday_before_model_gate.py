"""Actual Sunday workflow rejects an unready corpus before Claude or email."""
from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_before_model_gate import BeforeModelRefused, gate, main
from tests.test_sunday_corpus_readiness import assess, row

SAT = "2026-10-10"
SUN = "2026-10-11"
ROOT = Path(__file__).resolve().parents[1]


def invoke(day=SUN, cutoff=SAT):
    return gate(week_ending=SAT, as_of=cutoff, review_local_day=day)


class SundayBeforeModelContracts(unittest.TestCase):
    def test_current_sunday_ready_requires_actual_collected_full_text(self):
        report = assess()
        with patch("scripts.sunday_before_model_gate.inspect",
                   return_value=report) as audit:
            result = invoke()
        audit.assert_called_once()
        self.assertEqual(result["pre_model_scope"],
                         "current_sunday_collection_marker_and_corpus_checked")
        self.assertTrue(result["sunday_collection_verified_for_this_execution"])
        self.assertEqual(result["usable_text_records"], 2)
        self.assertEqual(result["production_desks_with_usable_text"],
                         ["china", "singapore"])
        self.assertFalse(result["model_output_reviewed"])
        self.assertFalse(result["external_research_reviewed"])
        self.assertFalse(result["editor_delivery_authorized"])
        self.assertFalse(result["publication_authorized"])
        self.assertNotIn("Official original text", json.dumps(result))

    def test_stale_or_missing_sunday_marker_is_hard_refusal(self):
        for value in ("", "2026-10-08", "2026-10-10"):
            with self.subTest(marker=value), patch(
                "scripts.sunday_before_model_gate.inspect",
                return_value=assess(marker=value)):
                with self.assertRaisesRegex(
                    BeforeModelRefused, "same_sunday_success_marker"):
                    invoke()

    def test_current_sunday_one_usable_desk_does_not_trigger_model(self):
        incomplete = assess(rows=[
            row(1, "china", "2026-10-08"),
            row(2, "singapore", "2026-10-07", chars=40),
        ])
        with patch("scripts.sunday_before_model_gate.inspect",
                   return_value=incomplete):
            with self.assertRaisesRegex(BeforeModelRefused, "fewer_than_two"):
                invoke()

    def test_saturday_provisional_week_refused_before_archive_read(self):
        with patch("scripts.sunday_before_model_gate.inspect") as audit:
            with self.assertRaisesRegex(BeforeModelRefused,
                                        "reporting Saturday has not ended"):
                invoke(day="2026-10-10")
            audit.assert_not_called()

    def test_incomplete_saturday_cutoff_still_refused_on_sunday(self):
        r = assess(as_of="2026-10-09")
        with patch("scripts.sunday_before_model_gate.inspect", return_value=r):
            with self.assertRaisesRegex(BeforeModelRefused,
                                        "reporting_week_not_complete"):
                invoke(cutoff="2026-10-09")

    def test_historical_preview_never_claims_sunday_collection_verified(self):
        old = assess(review_day="2026-10-12", marker="2026-10-12")
        self.assertEqual(old["unmet_gates"],
                         ["same_sunday_success_marker_missing_or_stale"])
        with patch("scripts.sunday_before_model_gate.inspect",
                   return_value=old):
            result = invoke(day="2026-10-12")
        self.assertEqual(result["pre_model_scope"],
                         "historical_snapshot_only_sunday_collection_unattested")
        self.assertFalse(result["sunday_collection_verified_for_this_execution"])
        self.assertEqual(result["usable_text_records"], 2)
        self.assertFalse(result["editor_delivery_authorized"])

    def test_historical_unusable_archive_still_refuses(self):
        old = assess(review_day="2026-10-12", marker="2026-10-12",
                     rows=[row(1, "china", "2026-10-08")])
        with patch("scripts.sunday_before_model_gate.inspect",
                   return_value=old):
            with self.assertRaisesRegex(BeforeModelRefused, "fewer_than_two"):
                invoke(day="2026-10-12")

    def test_source_date_provenance_not_bypassed(self):
        with patch("scripts.sunday_before_model_gate.inspect",
                   side_effect=ValueError("archive/source integrity refused")):
            with self.assertRaisesRegex(ValueError, "integrity refused"):
                invoke()

    def test_metadata_only_cli_and_no_publish_or_send(self):
        with patch("scripts.sunday_before_model_gate.inspect",
                   return_value=assess()):
            with patch("sys.stdout", new_callable=io.StringIO) as stdout:
                result = main([
                    "--week-ending", SAT, "--as-of", SAT,
                    "--review-local-day", SUN,
                ])
        self.assertEqual(result, 0)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["usable_text_records"], 2)
        self.assertFalse(output["publication_authorized"])
        self.assertNotIn("https://", stdout.getvalue())
        self.assertNotIn("Official original text", stdout.getvalue())

    def test_workflow_gate_precedes_research_and_model(self):
        path = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"
        source = path.read_text(encoding="utf-8")
        preflight = source.index(
            "- name: Require real production full-text readiness before model and email")
        refresh = source.index(
            "- name: Audit current Vietnam MPS shadow state")
        model = source.index(
            "- name: Generate source-cited Sunday manuscript")
        self.assertLess(preflight, refresh)
        self.assertLess(preflight, model)
        section = source[preflight:source.index(
            "- name: Verify bounded Japan/Vietnam editorial source packet", preflight)]
        self.assertIn("python -m scripts.sunday_before_model_gate", section)
        for forbidden in ("ANTHROPIC_API_KEY", "IPR_SMTP_APP_PASSWORD",
                          "upload-artifact", "git push", "send_packet"):
            self.assertNotIn(forbidden, section)


if __name__ == "__main__":
    unittest.main()
