"""Unified local Operations Center: truthful evidence joins and no publication."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core.desk_registry import load_registry
from scripts import audit_daily_run_receipts as daily
from scripts import audit_shadow_workflow_bindings as bindings
from scripts import operations_center as ops
from scripts import operations_center_unified as unified
from tests.test_daily_run_receipts import (complete, guard_only, cancelled,
                                           envelope)


class UnifiedOperationsContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-unified-ops-")
        self.addCleanup(tmp.cleanup)
        self.temp = Path(tmp.name)
        self.shadow_root = self.temp / "shadow"
        self.shadow_root.mkdir()
        self.marker = self.temp / "absent-marker.txt"
        self.registry = load_registry()
        self.day = date(2026, 10, 9)

    def report(self):
        sources = []
        for desk in self.registry:
            if desk.is_collecting:
                for source in desk.sources:
                    sources.append({
                        "desk_id": desk.slug, "source_slug": source.slug,
                        "articles_total": 6, "last_article_date": "2026-10-08",
                        "last_successful_collection_at": "2026-10-08 19:00:00",
                        "silence_verdict": "within_cadence",
                        "config_health": "ok",
                        "latest_run_result": {"status": "ok", "is_failure": 0},
                    })
        return {"sources": sources,
                "per_source_history_available": True,
                "generated_at": "2026-10-09 01:00:00"}

    def base(self):
        return ops.assemble(self.registry, self.report(),
                            self.shadow_root, self.marker, self.day)

    def build(self, *, receipts=None, shadow_bindings=False):
        if shadow_bindings:
            return unified.build_unified(
                self.registry, self.report(), ops.SHADOW_ROOT,
                self.marker, self.day, bindings.validate(unified.ROOT),
                receipt=receipts, root=unified.ROOT)
        return unified.build_unified(
            self.registry, self.report(), self.shadow_root,
            self.marker, self.day, None, receipt=receipts)

    def test_raw_daily_receipt_is_classified_and_not_authenticated(self):
        result = self.build(receipts=envelope([complete(), guard_only()]))
        d = result["daily_actions_evidence"]
        self.assertEqual(unified.SCHEMA, d["schema"])
        self.assertEqual(2, d["supplied_attempt_count"])
        self.assertEqual(
            [r["status"] for r in d["attempts"]],
            ["collection_validation_deploy_candidate",
             "green_scheduling_guard_skip_candidate"])
        self.assertFalse(d["input_origin_authenticated"])
        self.assertFalse(d["collector_work_certified"])
        self.assertFalse(d["complete_run_history_established"])
        self.assertFalse(d["current_analysis_queue_verified"])
        self.assertFalse(d["publication_authorized"])
        self.assertFalse(d["source_promotion_authorized"])
        self.assertFalse(d["editor_delivery_authorized"])
        self.assertFalse(d["publisher_silence_established"])
        self.assertEqual(d["writes"], 0)

    def test_green_guard_skip_cannot_double_count_collection(self):
        d = self.build(receipts=envelope([complete(), guard_only()]))[
            "daily_actions_evidence"]
        self.assertEqual(1, len(d["historical_backlog_snapshots"]))
        self.assertEqual(266, d["historical_backlog_snapshots"][0][
            "backlog_after_cap"])
        self.assertEqual(46, d["historical_backlog_snapshots"][0][
            "new_articles_stored"])
        self.assertEqual(
            d["created_new_york_day_counts"]["2026-10-08"][
                "green_scheduling_guard_skip_candidate"], 1)

    def test_cancelled_unknown_execution_stays_unknown(self):
        d = self.build(receipts=envelope([cancelled()]))[
            "daily_actions_evidence"]
        self.assertEqual("cancelled_execution_extent_unknown",
                         d["attempts"][0]["status"])
        self.assertEqual([], d["historical_backlog_snapshots"])
        self.assertFalse(d["complete_run_history_established"])

    def test_empty_daily_evidence_never_infers_silence(self):
        d = self.build(receipts=envelope([]))["daily_actions_evidence"]
        self.assertEqual(0, d["supplied_attempt_count"])
        self.assertEqual([], d["attempts"])
        self.assertFalse(d["publisher_silence_established"])
        self.assertFalse(d["collector_work_certified"])
        self.assertIn("No observations",
                      ops.render_html(self.build(receipts=envelope([]))))

    def test_no_daily_input_preserves_phase_one_html(self):
        self.assertEqual(
            ops.render_html(self.base()),
            ops.render_html(self.build()))
        self.assertNotIn("daily_actions_evidence", self.build())

    def test_base_snapshot_is_unchanged_by_join(self):
        base = self.base()
        old = copy.deepcopy(base)
        unified.attach_daily(base, envelope([complete()]))
        self.assertEqual(old, base)

    def test_existing_desk_health_unmodified_by_daily_receipts(self):
        before = self.build()
        after = self.build(receipts=envelope([complete(), guard_only()]))
        for key in ("desks", "daily_marker", "source_health_review_flags",
                    "shadow_source_manifests", "production_report_generated_at"):
            self.assertEqual(before[key], after[key])
        self.assertFalse(after["publication_authorized"])
        self.assertFalse(after["shadow_promotion_authorized"])
        self.assertFalse(after["editor_delivery_authorized"])

    def test_refuses_payload_that_claims_publication_authority(self):
        bad = self.base()
        bad["publication_authorized"] = True
        with self.assertRaisesRegex(unified.UnifiedError, "authorizations"):
            unified.attach_daily(bad, envelope([complete()]))

    def test_refuses_duplicate_daily_overlay(self):
        added = self.build(receipts=envelope([complete()]))
        with self.assertRaisesRegex(unified.UnifiedError, "duplicate"):
            unified.attach_daily(added, envelope([complete()]))

    def test_refuses_future_attempt_relative_to_display_date(self):
        before = self.base()
        before["as_of"] = "2026-10-07"
        with self.assertRaisesRegex(unified.UnifiedError, "display date"):
            unified.attach_daily(before, envelope([complete()]))

    def test_rejects_invalid_or_precomputed_daily_report(self):
        for payload in (
            {"schema": daily.OUT_SCHEMA, "attempts": []},
            {"schema": daily.SCHEMA, "as_of_utc": "2026-10-09T03:00:00Z",
             "runs": [{"publication_authorized": True}]},
            {"schema": daily.SCHEMA, "as_of_utc": "2026-10-09T03:00:00Z",
             "runs": "not an array"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises((daily.ReceiptError, unified.UnifiedError)):
                    unified.attach_daily(self.base(), payload)

    def test_live_manifest_binding_is_joined_not_assumed_authenticated(self):
        # Integration with the actual production repository manifests + audit.
        result = self.build(shadow_bindings=True)
        sh = result["shadow_evidence_overlay"]
        expected = bindings.validate(unified.ROOT)
        self.assertEqual(expected["source_families_checked"],
                         len(sh["source_families"]))
        self.assertEqual(expected["manifests_checked"],
                         len(result["shadow_source_manifests"]))
        self.assertTrue(all(not row["collection_verified"]
                            for row in sh["source_families"]))
        self.assertEqual(0, sh["families_with_slot_candidates"])
        self.assertFalse(sh["input_origin_authenticated"])

    def test_both_overlay_types_coexist_without_changing_authority(self):
        result = self.build(receipts=envelope([cancelled()]),
                            shadow_bindings=True)
        self.assertIn("shadow_evidence_overlay", result)
        self.assertIn("daily_actions_evidence", result)
        self.assertFalse(result["shadow_evidence_overlay"][
            "editor_delivery_authorized"])
        self.assertFalse(result["daily_actions_evidence"][
            "editor_delivery_authorized"])
        self.assertFalse(result["publication_authorized"])
        html = ops.render_html(result)
        self.assertIn("Shadow collection evidence candidates", html)
        self.assertIn("Daily Actions evidence candidates", html)
        self.assertIn("cancelled_execution_extent_unknown", html)
        self.assertIn("Source review flags", html)

    def test_html_escapes_supplied_source_text(self):
        result = self.build(receipts=envelope([cancelled()]))
        result["daily_actions_evidence"]["attempts"][0][
            "status"] = "<img src=x onerror=alert(1)>"
        html = ops.render_html(result)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertNotIn("<img src=x onerror=alert(1)>", html)

    def test_daily_evidence_not_rendered_as_live_status(self):
        html = ops.render_html(
            self.build(receipts=envelope([complete(), guard_only()])))
        for warning in ("Operator-supplied receipts, NOT authenticated",
                        "not live queue size",
                        "green_scheduling_guard_skip_candidate",
                        "collection_validation_deploy_candidate"):
            self.assertIn(warning, html)
        self.assertNotIn("Collection verified", html)

    def test_slot_candidates_require_source_bindings(self):
        with self.assertRaisesRegex(unified.UnifiedError, "require source bindings"):
            unified.build_unified(
                self.registry, self.report(), self.shadow_root, self.marker,
                self.day, None, slot_reports=[{"bogus": 1}])

    def test_cli_generates_two_new_local_files_without_repo_writes(self):
        receipt = self.temp / "evidence.json"
        receipt.write_text(json.dumps(envelope([cancelled()])), encoding="utf-8")
        output = self.temp / "report.json"
        html = self.temp / "report.html"
        with patch.object(unified, "build_report", return_value=self.report()):
            rc = unified.main([
                "--as-of", "2026-10-09",
                "--daily-receipts", str(receipt),
                "--json", str(output),
                "--html", str(html),
            ])
        self.assertEqual(0, rc)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertIn("shadow_evidence_overlay", data)
        self.assertEqual(1, data["daily_actions_evidence"]["supplied_attempt_count"])
        self.assertIn("Daily Actions evidence candidates",
                      html.read_text(encoding="utf-8"))
        self.assertEqual(json.dumps(envelope([cancelled()])),
                         receipt.read_text(encoding="utf-8"))

    def test_cli_refuses_overwriting_existing_report(self):
        html = self.temp / "existing.html"
        html.write_text("KEEP", encoding="utf-8")
        output = self.temp / "new.json"
        with self.assertRaises(SystemExit):
            unified.main(["--json", str(output), "--html", str(html)])
        self.assertEqual(html.read_text(encoding="utf-8"), "KEEP")
        self.assertFalse(output.exists())

    def test_cli_refuses_target_inside_repository(self):
        with self.assertRaises(SystemExit):
            unified.main(["--json", str(unified.ROOT / "output/unsafe.json"),
                          "--html", str(self.temp / "out.html")])


if __name__ == "__main__":
    unittest.main()
