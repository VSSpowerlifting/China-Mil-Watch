"""No-network tests for regional Sunday operator diagnostic receipts."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.regional_sunday_operator_readiness import (
    OperatorReadinessError, _sha256, summarize,
)
from scripts.regional_sunday_operator_readiness import _private_write, main
from tests.test_regional_weekly_inventory import make, pending, row


class RegionalSundayOperatorTests(unittest.TestCase):
    def test_complete_week_is_only_machine_corpus_gate_not_editor_release(self):
        report = summarize(make())
        self.assertEqual(report["machine_corpus_gate"],
                         "passed_machine_only_not_model_or_email_approval")
        self.assertTrue(report["full_reporting_week_cutoff_reached"])
        self.assertEqual(report["production_record_pointers"], 2)
        self.assertEqual(report["blocking_corpus_gates"], [])
        self.assertEqual({x["desk"] for x in report["desk_coverage"]
                          if x["reviewable_count"]}, {"china", "singapore"})
        for key in ("model_called", "model_input_authorized",
                    "editor_email_authorized", "publication_authorized",
                    "official_publisher_silence_inferred",
                    "changes_production_archive"):
            self.assertIs(report[key], False)
        self.assertIn("separate_owner_SHA256_review_required",
                      report["editorial_review_stages"]["exact_attachment_editor_release"])
        self.assertIn("Human-review",
                      report["operator_next_actions"][0])

    def test_friday_has_incomplete_week_and_marker_not_due(self):
        report = summarize(make(
            as_of="2026-10-09", review_day="2026-10-09", marker=""))
        self.assertEqual(report["machine_corpus_gate"],
                         "hold_before_model_and_editor_delivery")
        self.assertIn("reporting_week_not_complete", report["blocking_corpus_gates"])
        self.assertIn("sunday_production_update_not_due",
                      report["blocking_corpus_gates"])
        self.assertFalse(report["full_reporting_week_cutoff_reached"])
        self.assertFalse(report["sunday_or_later_review_day_reached"])
        self.assertFalse(report["model_input_authorized"])
        self.assertTrue(any("Saturday" in x for x in report["operator_next_actions"]))

    def test_complete_archive_but_no_sunday_marker_stays_held(self):
        report = summarize(make(marker=""))
        self.assertEqual(report["blocking_corpus_gates"],
                         ["same_sunday_success_marker_missing_or_stale"])
        self.assertTrue(report["sunday_or_later_review_day_reached"])
        self.assertFalse(report["editor_email_authorized"])

    def test_a_production_desk_without_evidence_is_not_official_silence(self):
        result = summarize(make(rows=[row(42, "china")]))
        self.assertIn("fewer_than_two_desks_with_usable_source_text",
                      result["blocking_corpus_gates"])
        self.assertEqual(next(x for x in result["desk_coverage"]
                              if x["desk"] == "singapore")["evidence_state"],
                         "no_qualifying_evidence")
        self.assertFalse(result["official_publisher_silence_inferred"])

    def test_research_pending_and_screened_production_reasons_are_counts_only(self):
        inventory = make(
            rows=[row(42, "china"), row(47, "singapore"),
                  row(99, "china", passed_relevance=0),
                  row(88, "china", text_original="short")],
            research_rows=[pending()])
        out = summarize(inventory)
        self.assertEqual(out["held_reason_counts"],
                         {"insufficient_stored_full_text": 1,
                          "screened_not_selected": 1})
        self.assertEqual(out["pending_private_research_by_desk"], {"japan": 1})
        self.assertTrue(any("HOLD" in x for x in out["operator_next_actions"]))
        serial = json.dumps(out)
        self.assertNotIn("https://", serial)
        self.assertNotIn("source_url", serial)
        self.assertNotIn("text_original", serial)
        self.assertNotIn("SENSITIVE RAW TEXT", serial)
        self.assertNotIn("Original reported wording", serial)
        self.assertNotIn("A first party", serial)

    def test_source_metadata_tampering_and_false_approvals_fail_closed(self):
        original = make()
        variants = [
            lambda x: x["production_evidence"][0].update(source_url="https://evil.example/42"),
            lambda x: x["held_production_records"].append(
                {"record_id": 999, "desk": "china", "reason": "new"}),
            lambda x: x["coverage"][0].update(reviewable=9),
            lambda x: x.update(source_metadata_digest_sha256="0" * 64),
            lambda x: x.update(model_input_authorized=True),
            lambda x: x.update(editor_email_authorized=True),
            lambda x: x.update(publication_authorized=True),
        ]
        for fn in variants:
            changed = copy.deepcopy(original)
            fn(changed)
            with self.subTest(fn=fn), self.assertRaises(OperatorReadinessError):
                summarize(changed)

    def test_even_resigned_snapshot_cannot_claim_false_machine_readiness(self):
        changed = make(as_of="2026-10-09",
                       review_day="2026-10-09", marker="")
        changed["production_preflight"] = (
            "candidate_for_no_send_model_preview_not_approved")
        changed["unmet_production_gates"] = []
        with self.assertRaisesRegex(OperatorReadinessError, "before Sunday"):
            summarize(changed)

    def test_mismatched_held_desk_count_cannot_hide_in_valid_digest(self):
        changed = make(rows=[row(42, "china"), row(47, "singapore"),
                             row(71, "china", text_original="short")])
        changed["coverage"][0]["held"] = 0
        changed["coverage"][0]["stored"] = 1
        changed["source_metadata_digest_sha256"] = _sha256({
            "evidence": changed["production_evidence"],
            "held": changed["held_production_records"],
            "pending": changed["pending_private_research"],
            "coverage": changed["coverage"],
        })
        with self.assertRaisesRegex(OperatorReadinessError, "totals"):
            summarize(changed)

    def test_private_json_file_is_exclusive_mode_0600_and_not_repo(self):
        report = summarize(make())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "operator.json"
            _private_write(path, report)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())["schema"],
                             "ipr-regional-sunday-operator-readiness/1")
            with self.assertRaises(ValueError):
                _private_write(path, report)
        repo = Path(__file__).resolve().parents[1]
        with self.assertRaises(ValueError):
            _private_write(repo / "UNCREATED_SUNDAY_OPERATOR.json", report)

    def test_failed_json_serialization_removes_partial_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "operator.json"
            with self.assertRaises(TypeError):
                _private_write(output, {"object": object()})
            self.assertFalse(output.exists())

    def test_failed_fdopen_closes_raw_descriptor_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "operator.json"
            raw_open, raw_close = os.open, os.close
            opened = []

            def record_open(*args, **kwargs):
                fd = raw_open(*args, **kwargs)
                opened.append(fd)
                return fd

            with patch("scripts.regional_sunday_operator_readiness.os.open",
                       side_effect=record_open), patch(
                    "scripts.regional_sunday_operator_readiness.os.fdopen",
                    side_effect=OSError("simulated fdopen failure")), patch(
                    "scripts.regional_sunday_operator_readiness.os.close",
                    wraps=raw_close) as close:
                with self.assertRaisesRegex(OSError, "simulated fdopen failure"):
                    _private_write(output, {"private": True})
            self.assertFalse(output.exists())
            self.assertEqual(len(opened), 1)
            close.assert_called_once_with(opened[0])

    def test_unrelated_replacement_survives_failed_report_write(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "operator.json"
            independent = Path(folder) / "unrelated-document.txt"
            independent.write_text("UNRELATED", encoding="utf-8")
            raw_close = os.close

            def swap_then_fail(fd, *args, **kwargs):
                output.unlink()
                os.link(independent, output)
                raise OSError("simulated replacement")

            with patch("scripts.regional_sunday_operator_readiness.os.fdopen",
                       side_effect=swap_then_fail), patch(
                    "scripts.regional_sunday_operator_readiness.os.close",
                    wraps=raw_close):
                with self.assertRaisesRegex(OSError, "simulated replacement"):
                    _private_write(output, {"private": True})
            self.assertEqual(output.read_text(encoding="utf-8"), "UNRELATED")
            self.assertEqual(independent.read_text(encoding="utf-8"), "UNRELATED")

    def test_existing_dangling_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "operator.json"
            victim = Path(folder) / "must-not-create.json"
            output.symlink_to(victim)
            with self.assertRaises(ValueError):
                _private_write(output, {"private": True})
            self.assertTrue(output.is_symlink())
            self.assertFalse(victim.exists())

    def test_symlink_swap_during_resolution_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "operator.json"
            victim = Path(folder) / "must-not-create.json"
            original_resolve = Path.resolve

            def swap(path_obj, *args, **kwargs):
                if path_obj == output:
                    output.symlink_to(victim)
                return original_resolve(path_obj, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True, side_effect=swap):
                with self.assertRaises(ValueError):
                    _private_write(output, {"private": True})
            self.assertTrue(output.is_symlink())
            self.assertFalse(victim.exists())

    def test_cli_does_not_invoke_model_or_dylan_email(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "operator.json"
            args = ["--week-ending", "2026-10-10", "--as-of", "2026-10-09",
                    "--review-local-day", "2026-10-09", "--out", str(out)]
            with patch("scripts.regional_sunday_operator_readiness.inspect",
                       return_value=make(as_of="2026-10-09",
                                         review_day="2026-10-09", marker="")), patch(
                       "scripts.sunday_editorial_handoff.send_packet") as send, patch(
                       "scripts.sunday_briefs_auto_writer.compose") as model:
                self.assertEqual(main(args), 0)
                send.assert_not_called()
                model.assert_not_called()
            report = json.loads(out.read_text())
            self.assertEqual(report["machine_corpus_gate"],
                             "hold_before_model_and_editor_delivery")


if __name__ == "__main__":
    unittest.main()
