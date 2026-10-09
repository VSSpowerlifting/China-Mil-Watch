"""Offline Operations Center contracts: no publication or invented shadow health."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.desk_registry import load_registry
from scripts import operations_center as ops
from scripts.source_health_report import build_report


class OperationsCenterContracts(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(prefix="ipr-ops-test-")
        self.addCleanup(self.root.cleanup)
        self.temp = Path(self.root.name)
        self.shadow = self.temp / "shadow"
        self.shadow.mkdir()
        self.marker = self.temp / "daily.txt"
        self.registry = load_registry()
        self.as_of = date(2026, 10, 8)

    def report(self):
        rows = []
        for desk in self.registry:
            if not desk.is_collecting:
                continue
            for src in desk.sources:
                rows.append({
                    "source_slug": src.slug, "desk_id": desk.slug,
                    "articles_total": 4, "last_article_date": "2026-10-07",
                    "last_successful_collection_at": "2026-10-08 13:00:00",
                    "silence_verdict": "within_cadence",
                    "config_health": "ok",
                    "latest_run_result": {"status": "ok", "is_failure": 0},
                })
        return {"sources": rows, "per_source_history_available": True,
                "generated_at": "2026-10-08 15:00:00"}

    def make_shadow(self, directory="test_shadow", desk="philippines",
                    source_slug="ph_afp_test", title="Philippines source pilot"):
        loc = self.shadow / directory
        loc.mkdir()
        (loc / "manifest.json").write_text(json.dumps({
            "desk": {"desk_id": desk, "display_name": title},
            "sources": [{"slug": source_slug, "enabled": True}],
        }), encoding="utf-8")
        return loc / "manifest.json"

    def snapshot(self, report=None):
        return ops.assemble(
            self.registry, report if report is not None else self.report(),
            self.shadow, self.marker, self.as_of)

    def test_production_counts_come_from_source_report(self):
        result = self.snapshot()
        for desk in result["desks"]:
            if desk["is_production"]:
                self.assertEqual(4 * desk["declared_sources"],
                                 desk["production_source_articles"])
                self.assertTrue(desk["source_health_observed"])
            else:
                self.assertIsNone(desk["production_source_articles"])
                self.assertEqual([], desk["production_sources"])
                self.assertEqual("not_observed", desk["shadow_health"])
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["editor_delivery_authorized"])

    def test_shadow_enabled_flag_cannot_become_live_evidence(self):
        self.make_shadow()
        item = self.snapshot()["shadow_source_manifests"][0]
        self.assertEqual(1, item["enabled_in_shadow_manifest"])
        self.assertIsNone(item["collected_records"])
        self.assertIsNone(item["observed_run_date"])
        self.assertFalse(item["eligible_for_production"])
        self.assertFalse(item["live_collection_verified"])
        self.assertFalse(item["source_rights_verified"])
        self.assertIsNone(item["registry_status"])
        self.assertEqual("not_in_public_registry", item["registry_binding"])

    def test_historical_shadow_manifest_is_not_an_active_shadow_claim(self):
        self.make_shadow(desk="singapore")
        item = self.snapshot()["shadow_source_manifests"][0]
        self.assertEqual("historical_shadow_manifest", item["inventory_role"])
        self.assertFalse(item["live_collection_verified"])

    def test_undocumented_source_is_not_silently_dropped(self):
        report = self.report()
        report["sources"].append(dict(report["sources"][0], source_slug="phantom"))
        with self.assertRaisesRegex(ops.SnapshotError, "mismatch"):
            self.snapshot(report)

    def test_missing_production_source_fails_closed(self):
        report = self.report()
        report["sources"].pop()
        with self.assertRaisesRegex(ops.SnapshotError, "mismatch"):
            self.snapshot(report)

    def test_wrong_desk_source_fails_closed(self):
        report = self.report()
        report["sources"][0]["desk_id"] = "japan"
        with self.assertRaisesRegex(ops.SnapshotError, "wrong desk"):
            self.snapshot(report)

    def test_malformed_shadow_configuration_fails_closed(self):
        path = self.make_shadow()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["sources"][0].pop("enabled")
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ops.SnapshotError, "enabled"):
            self.snapshot()

    def test_malicious_manifest_name_is_escaped_in_local_html(self):
        self.make_shadow(title="<script>alert('oops')</script>")
        html = ops.render_html(self.snapshot())
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script src=", html)
        self.assertIn("No live shadow Actions", html)

    def test_observed_marker_does_not_certify_ci_health(self):
        self.marker.write_text("2026-10-07\n", encoding="utf-8")
        item = self.snapshot()["daily_marker"]
        self.assertEqual("marker_observed", item["state"])
        self.assertEqual(1, item["age_days"])
        self.assertIn("not checked", item["meaning"])

    def test_missing_marker_is_unknown_not_failure_or_success(self):
        self.assertEqual("not_observed",
                         self.snapshot()["daily_marker"]["state"])

    def test_future_marker_rejected(self):
        self.marker.write_text("2026-10-09", encoding="utf-8")
        with self.assertRaisesRegex(ops.SnapshotError, "future"):
            self.snapshot()

    def test_unsafe_output_destinations_refused(self):
        with self.assertRaises(ops.SnapshotError):
            ops.safe_destination(ops.ROOT / "output" / "operations.html")
        with self.assertRaises(ops.SnapshotError):
            ops.safe_destination(ops.ROOT / "pla_watch.db")
        with self.assertRaisesRegex(ops.SnapshotError, "inside the repository"):
            ops.safe_destination(ops.ROOT / ".github" / "workflows" / "new_report.yml")
        with self.assertRaisesRegex(ops.SnapshotError, "inside the repository"):
            ops.safe_destination(ops.ROOT / "new_report.html")
        self.assertEqual(self.temp / "fresh.json",
                         ops.safe_destination(self.temp / "fresh.json"))
        existing = self.temp / "exists.html"
        existing.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(ops.SnapshotError, "overwrite"):
            ops.safe_destination(existing)
        self.assertEqual("preserve", existing.read_text(encoding="utf-8"))

    def test_recent_article_does_not_hide_failed_source_attempt(self):
        report = self.report()
        report["sources"][0]["latest_run_result"] = {
            "status": "retrieval_error", "is_failure": 1,
        }
        snap = self.snapshot(report)
        self.assertTrue(snap["desks"][0]["production_sources"][0]["latest_run_failed"])
        self.assertIn("latest_source_collection_failed",
                      snap["source_health_review_flags"][0]["reasons"])
        self.assertFalse(snap["publication_authorized"])

    def test_unknown_source_run_history_is_not_a_success_claim(self):
        report = self.report()
        report["sources"][0]["latest_run_result"] = None
        snap = self.snapshot(report)
        self.assertIsNone(snap["desks"][0]["production_sources"][0]["latest_run_failed"])
        self.assertEqual([], snap["source_health_review_flags"])

    def test_invalid_source_failure_evidence_refused(self):
        report = self.report()
        report["sources"][0]["latest_run_result"] = {"status": "ok"}
        with self.assertRaisesRegex(ops.SnapshotError, "failure evidence"):
            self.snapshot(report)

    def test_html_displays_review_reasons_not_just_count(self):
        report = self.report()
        report["sources"][0]["latest_run_result"] = {
            "status": "retrieval_error", "is_failure": 1,
        }
        report["sources"][0]["silence_verdict"] = "overdue"
        report["sources"][0]["config_health"] = "unusable"
        snap = self.snapshot(report)
        self.assertEqual(3, len(snap["source_health_review_flags"][0]["reasons"]))
        html = ops.render_html(snap)
        self.assertIn("Source review flags", html)
        self.assertIn("Latest source collection failed", html)
        self.assertIn("Publication silence overdue", html)
        self.assertIn("Adapter configuration requires review", html)
        self.assertIn(snap["source_health_review_flags"][0]["source_slug"], html)
        self.assertIn("Empty does not certify complete coverage", html)
        self.assertFalse(snap["publication_authorized"])

    def test_html_does_not_confuse_unknown_run_with_success(self):
        report = self.report()
        report["sources"][0]["latest_run_result"] = None
        snap = self.snapshot(report)
        html = ops.render_html(snap)
        self.assertEqual([], snap["source_health_review_flags"])
        self.assertIn("Source runs not observed", html)
        self.assertIn("Unknown is not a successful collection", html)
        source = snap["desks"][0]["production_sources"][0]["name"]
        self.assertIn(source.replace("&", "&amp;"), html)
        self.assertFalse(snap["editor_delivery_authorized"])

    def test_source_flag_does_not_promote_desk(self):
        report = self.report()
        report["sources"][0]["silence_verdict"] = "overdue"
        snap = self.snapshot(report)
        self.assertEqual(1, len(snap["source_health_review_flags"]))
        self.assertFalse(snap["shadow_promotion_authorized"])
        self.assertFalse(snap["publication_authorized"])


class TrackedDatabaseReadOnlySmoke(unittest.TestCase):
    def test_production_health_can_be_read_without_sidecars(self):
        db = ops.ROOT / "pla_watch.db"
        if not db.is_file():
            self.skipTest("tracked database not available")
        before = db.stat().st_mtime_ns
        report = build_report(db)
        slugs = {x["source_slug"] for x in report["sources"]}
        expected = {s.slug for d in load_registry() if d.is_collecting
                    for s in d.sources}
        self.assertEqual(expected, slugs)
        self.assertEqual(before, db.stat().st_mtime_ns)
        self.assertFalse((ops.ROOT / "pla_watch.db-wal").exists())
        self.assertFalse((ops.ROOT / "pla_watch.db-shm").exists())


if __name__ == "__main__":
    unittest.main()
