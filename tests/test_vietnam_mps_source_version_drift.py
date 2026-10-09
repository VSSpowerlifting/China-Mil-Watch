"""Offline exact-version MPS historical/current comparison, never rights grant."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.vietnam_mps_source_version_drift import (
    OCT5, OCT7, VietnamRowDriftError, compare_mps_versions,
)
from scripts.vietnam_mps_source_version_drift import (
    main as cli_main, new_private_report,
)
from tests.test_regional_typed_research_holds import fixture
from tests.test_regional_typed_machine_receipts import queue_at, seal


def scenario():
    _inventory, all_sources = fixture()
    old5 = queue_at(OCT5, ("mps-vi:1791199100", "mps-vi:1791199677"))
    old7 = queue_at(OCT7, ("mps-vi:1791366010",))
    current = queue_at(OCT7, (
        "mps-vi:1791199100", "mps-vi:1791199677", "mps-vi:1791366010"))
    return all_sources, [old5, old7], current


class MPSHistoricalCurrentDriftTests(unittest.TestCase):
    def test_real_week_research_catalog_all_three_exact_source_versions(self):
        rows, history, latest = scenario()
        report = compare_mps_versions(rows, history, latest)
        self.assertEqual(report["schema"],
                         "ipr-vietnam-mps-historical-current-shadow-version-drift/1")
        self.assertEqual(report["historical_state_commits"], sorted([OCT5, OCT7]))
        self.assertEqual(report["compared_sources"], 3)
        self.assertEqual(report["comparison_counts"],
                         {"same_shadow_source_version_and_metadata": 3})
        self.assertEqual({x["typed_id"] for x in report["items"]}, {
            "VN-MPS-1791199100", "VN-MPS-1791199677",
            "VN-MPS-1791366010"})
        self.assertTrue(all(x["changed_fields"] == [] for x in report["items"]))
        for item in report["items"]:
            for field in ("eligible_for_regional_model", "publication_authorized",
                          "editor_email_authorized", "human_vietnamese_original_compared",
                          "current_publisher_body_independently_checked",
                          "reuse_rights_reviewed"):
                self.assertIs(item[field], False)
        for key in ("model_input_authorized", "dylan_editor_email_authorized",
                    "publication_authorized", "human_source_review_completed",
                    "source_reuse_rights_reviewed"):
            self.assertIs(report[key], False)
        output = json.dumps(report, ensure_ascii=False)
        for row in rows:
            self.assertNotIn(row["source_url"], output)
            self.assertNotIn(row["summary"], output)
            self.assertNotIn(row["title_original"], output)

    def test_changed_newer_source_digest_is_a_hold_not_an_approval(self):
        rows, history, latest = scenario()
        current = copy.deepcopy(latest)
        victim = next(x for x in current["records"] if x["source_identity"] ==
                      "mps-vi:1791199100")
        victim["content_sha256"] = "0" * 64
        current = seal(current)
        report = compare_mps_versions(rows, history, current)
        item = next(x for x in report["items"]
                    if x["typed_id"] == "VN-MPS-1791199100")
        self.assertEqual(item["version_comparison"],
                         "newer_shadow_source_changed_or_held")
        self.assertIn("content_sha256", item["changed_fields"])
        self.assertFalse(item["eligible_for_regional_model"])

    def test_changed_url_date_title_and_capture_are_visible_field_names_only(self):
        rows, history, latest = scenario()
        current = copy.deepcopy(latest)
        victim = current["records"][0]
        victim["canonical_url"] = "https://bocongan.gov.vn/bai-viet/changed-1791199100"
        victim["published_date"] = "2026-10-08"
        victim["title_original"] = "New title"
        victim["first_capture_sha256"] = "f" * 64
        report = compare_mps_versions(rows, history, seal(current))
        chosen = next(x for x in report["items"]
                      if x["typed_id"] == victim["source_identity"].replace(
                          "mps-vi:", "VN-MPS-"))
        self.assertEqual(chosen["version_comparison"],
                         "newer_shadow_source_changed_or_held")
        for field in ("canonical_url", "published_date",
                      "title_original", "first_capture_sha256"):
            self.assertIn(field, chosen["changed_fields"])
        self.assertNotIn(victim["canonical_url"], json.dumps(report))

    def test_missing_from_newer_archived_state_does_not_mean_ministry_silence(self):
        rows, history, latest = scenario()
        current = copy.deepcopy(latest)
        current["records"] = [x for x in current["records"]
                              if x["source_identity"] != "mps-vi:1791366010"]
        current["record_count"] = 2
        report = compare_mps_versions(rows, history, seal(current))
        latest_record = next(x for x in report["items"]
                             if x["typed_id"] == "VN-MPS-1791366010")
        self.assertEqual(latest_record["version_comparison"],
                         "source_missing_from_newer_shadow_not_publisher_silence")
        self.assertFalse(report["live_official_publisher_silence_inferred"])

    def test_wrong_or_duplicate_historical_commits_never_attest_two_epochs(self):
        rows, history, latest = scenario()
        for bad in ([history[0], history[0]], [history[0]]):
            with self.assertRaises(VietnamRowDriftError):
                compare_mps_versions(rows, bad, latest)
        forged = copy.deepcopy(history[0])
        forged["state_commit"] = "0" * 40
        with self.assertRaisesRegex(VietnamRowDriftError, "commit"):
            compare_mps_versions(rows, [seal(forged), history[1]], latest)

    def test_missing_or_changed_historical_source_is_a_failure(self):
        rows, history, latest = scenario()
        old = copy.deepcopy(history)
        old[0]["records"] = old[0]["records"][:-1]
        old[0]["record_count"] = 1
        with self.assertRaisesRegex(VietnamRowDriftError, "queue source"):
            compare_mps_versions(rows, [seal(old[0]), old[1]], latest)
        old = copy.deepcopy(history)
        old[0]["records"][0]["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(VietnamRowDriftError, "historical"):
            compare_mps_versions(rows, [seal(old[0]), old[1]], latest)

    def test_changed_human_use_flags_refused_even_if_queue_is_rehashed(self):
        rows, history, latest = scenario()
        for key in ("human_source_reviewed", "reuse_rights_reviewed",
                    "production_publication_authorized"):
            broken = copy.deepcopy(latest)
            broken["records"][0][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(
                    VietnamRowDriftError, "approval"):
                compare_mps_versions(rows, history, seal(broken))

    def test_altered_queue_digest_and_duplicate_ids_refused(self):
        rows, history, latest = scenario()
        altered = copy.deepcopy(latest)
        altered["records"][0]["published_date"] = "2026-10-09"
        with self.assertRaisesRegex(VietnamRowDriftError, "self-check"):
            compare_mps_versions(rows, history, altered)
        altered = copy.deepcopy(latest)
        altered["records"].append(copy.deepcopy(altered["records"][0]))
        altered["record_count"] = len(altered["records"])
        with self.assertRaisesRegex(VietnamRowDriftError, "duplicate"):
            compare_mps_versions(rows, history, seal(altered))

    def test_unreviewed_research_scope_and_source_pins_refused(self):
        rows, history, latest = scenario()
        for field, value in (
            ("state_commit", "0" * 40),
            ("copy_scope", "public"),
            ("language", "en"),
            ("source_content_sha256", "0" * 64),
            ("source_kind", "publisher-text-copied"),
            ("status", "production_record"),
        ):
            broken = copy.deepcopy(rows)
            victim = next(x for x in broken if x.get("id") == "VN-MPS-1791199100")
            victim[field] = value
            with self.subTest(field=field), self.assertRaises(
                    VietnamRowDriftError):
                compare_mps_versions(broken, history, latest)

    def test_non_mps_sources_cannot_replace_a_required_article(self):
        rows, history, latest = scenario()
        altered = [x for x in rows if x.get("id") != "VN-MPS-1791199100"]
        with self.assertRaisesRegex(VietnamRowDriftError, "three MPS"):
            compare_mps_versions(altered, history, latest)

    def test_private_output_is_exclusive_and_never_in_repo(self):
        rows, history, latest = scenario()
        receipt = compare_mps_versions(rows, history, latest)
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "comparison.json"
            new_private_report(dest, receipt)
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(dest.read_text())["compared_sources"], 3)
            with self.assertRaisesRegex(ValueError, "overwrite"):
                new_private_report(dest, receipt)
        with self.assertRaises(ValueError):
            new_private_report(
                Path(__file__).resolve().parents[1] / "NO_WRITE_VIETNAM_DRIFT.json",
                receipt)

    def test_failed_encoding_cleans_partial_private_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            with self.assertRaises(TypeError):
                new_private_report(output, {"invalid": object()})
            self.assertFalse(output.exists())

    def test_failed_fdopen_closes_descriptor_and_removes_owned_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            raw_open, raw_close = os.open, os.close
            opened = []

            def count_open(*args, **kwargs):
                fd = raw_open(*args, **kwargs)
                opened.append(fd)
                return fd

            with patch("scripts.vietnam_mps_source_version_drift.os.open",
                       side_effect=count_open), patch(
                    "scripts.vietnam_mps_source_version_drift.os.fdopen",
                    side_effect=OSError("synthetic fdopen error")), patch(
                    "scripts.vietnam_mps_source_version_drift.os.close",
                    wraps=raw_close) as close:
                with self.assertRaisesRegex(OSError, "synthetic fdopen error"):
                    new_private_report(output, {"private": True})
            self.assertEqual(len(opened), 1)
            close.assert_called_once_with(opened[0])
            self.assertFalse(output.exists())

    def test_replacement_file_survives_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            other = Path(folder) / "unrelated.txt"
            other.write_text("KEEP", encoding="utf-8")
            raw_close = os.close

            def swap_and_fail(fd, *args, **kwargs):
                output.unlink()
                os.link(other, output)
                raise OSError("synthetic path swap")

            with patch("scripts.vietnam_mps_source_version_drift.os.fdopen",
                       side_effect=swap_and_fail), patch(
                    "scripts.vietnam_mps_source_version_drift.os.close",
                    wraps=raw_close):
                with self.assertRaisesRegex(OSError, "synthetic path swap"):
                    new_private_report(output, {"private": True})
            self.assertEqual(output.read_text(encoding="utf-8"), "KEEP")
            self.assertEqual(other.read_text(encoding="utf-8"), "KEEP")

    def test_existing_dangling_symlink_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            victim = Path(folder) / "untouched.json"
            output.symlink_to(victim)
            with self.assertRaises(ValueError):
                new_private_report(output, {"private": True})
            self.assertTrue(output.is_symlink())
            self.assertFalse(victim.exists())

    def test_symlink_substitution_during_resolve_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            victim = Path(folder) / "untouched.json"
            orig_resolve = Path.resolve

            def replace_at_resolve(candidate, *args, **kwargs):
                if candidate == output:
                    output.symlink_to(victim)
                return orig_resolve(candidate, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True,
                              side_effect=replace_at_resolve):
                with self.assertRaises(ValueError):
                    new_private_report(output, {"private": True})
            self.assertTrue(output.is_symlink())
            self.assertFalse(victim.exists())

    def test_cli_mocks_only_external_queue_files_and_never_calls_smtp(self):
        rows, history, latest = scenario()
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "receipt.json"
            args = ["--historical-queue", "/private/oct5.json",
                    "--historical-queue", "/private/oct7.json",
                    "--current-queue", "/private/current.json",
                    "--out", str(dest)]
            with patch("scripts.vietnam_mps_source_version_drift.load_editorial_evidence",
                       return_value=rows), patch(
                       "scripts.vietnam_mps_source_version_drift.load_verified_json",
                       side_effect=[history[0], history[1], latest]), patch(
                       "scripts.sunday_editorial_handoff.send_packet") as send:
                self.assertEqual(cli_main(args), 0)
                send.assert_not_called()
            self.assertEqual(json.loads(dest.read_text())["compared_sources"], 3)


if __name__ == "__main__":
    unittest.main()
