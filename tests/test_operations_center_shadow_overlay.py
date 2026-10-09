"""Synthetic-only Phase 2 candidate overlay integration and safety contracts."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import operations_center as ops
from scripts import operations_center_shadow_overlay as overlay


class OverlayContracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-ops-overlay-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shadow = self.root / "shadow"
        sources = [
            ("id_kemhan", "id_kemhan_news", "indonesia"),
            ("vietnam_journal", "vn_national_defence_journal_en", "vietnam"),
        ]
        self.families = []
        for folder, slug, desk in sources:
            dest = shadow / folder / "manifest.json"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps({
                "desk": {"desk_id": desk, "active": False,
                         "public_status": "shadow"},
                "sources": [{"slug": slug, "enabled": True}],
            }), encoding="utf-8")
            self.families.append({
                "manifest": "shadow/%s/manifest.json" % folder,
                "declared_source_count": 1,
                "display_name": folder, "desk_id": desk,
                "registry_status": None, "inventory_role": "nonproduction",
                "enabled_in_shadow_manifest": 1,
            })
        self.base = {
            "schema": ops.SCHEMA, "as_of": "2026-10-08",
            "shadow_source_manifests": self.families,
            "daily_marker": {"date": None, "state": "not_observed"},
            "desks": [], "source_health_review_flags": [],
            "limits": ["Unverified source evidence."],
            "publication_authorized": False,
            "shadow_promotion_authorized": False,
            "editor_delivery_authorized": False,
        }
        self.bindings = {
            "schema": overlay.BINDING_SCHEMA,
            "declaration_only": True, "all_runs_attested": False,
            "production_eligible": False, "shadow_promotion_authorized": False,
            "editorial_publication_authorized": False, "writes": 0,
            "manifests_checked": 2, "source_families_checked": 2,
            "sources": [
                {
                    "manifest": "shadow/id_kemhan/manifest.json",
                    "source_slug": "id_kemhan_news",
                    "state_branch": "shadow/indonesia-kemhan",
                    "workflow": ".github/workflows/indonesia_korea_shadow.yml",
                    "cron": "17 17 * * *", "trigger": "scheduled",
                    "run_attested": False, "production_eligible": False,
                    "editorial_authorized": False,
                },
                {
                    "manifest": "shadow/vietnam_journal/manifest.json",
                    "source_slug": "vn_national_defence_journal_en",
                    "state_branch": None, "workflow": None, "cron": None,
                    "trigger": "research_only", "run_attested": False,
                    "production_eligible": False, "editorial_authorized": False,
                },
            ],
        }
        self.slot = {
            "schema": overlay.SLOT_SCHEMA,
            "source_slug": "id_kemhan_news",
            "state_branch": "shadow/indonesia-kemhan",
            "cron_utc": "17:17", "as_of_utc": "2026-10-08T19:00:00Z",
            "counts": {"pending": 0, "candidate_supported": 1,
                       "review_required": 0,
                       "missing_from_supplied_evidence": 0},
            "slots": [{
                "logical_date": "2026-10-07",
                "status": "scheduled_success_new_records_candidate",
                "new_record_count_is_not_publication_completeness": True,
            }],
            "supplied_actions_export_authenticated": False,
            "source_capture_chain_verified_by_this_audit": False,
            "all_historical_scheduled_attempts_exhaustively_observed": False,
            "government_silence_established": False,
            "desk_production_eligible": False,
            "weekly_ai_writer_eligible": False,
            "editor_delivery_authorized": False,
            "automatic_recovery_dispatched": False,
            "writes": 0,
        }

    def report(self, reports=None, bindings=None):
        return overlay.attach(self.base,
                              self.bindings if bindings is None else bindings,
                              [self.slot] if reports is None else reports,
                              root=self.root)

    def test_supplied_evidence_shown_but_never_authenticated(self):
        result = self.report()
        self.assertEqual(result["shadow_evidence_overlay"]["families_with_slot_candidates"], 1)
        self.assertEqual(len(result["shadow_evidence_overlay"]["source_families"]), 2)
        by_slug = {x["source_slug"]: x
                   for x in result["shadow_evidence_overlay"]["source_families"]}
        self.assertEqual(
            by_slug["id_kemhan_news"]["slot_candidate_summary"]["candidate_supported_slots"], 1)
        self.assertEqual(by_slug["vn_national_defence_journal_en"]["slot_evidence_status"],
                         "not_supplied")
        self.assertFalse(result["shadow_evidence_overlay"]["input_origin_authenticated"])
        self.assertFalse(result["shadow_evidence_overlay"]["collection_verified"])
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["editor_delivery_authorized"])

    def test_base_snapshot_not_modified_and_no_state_write(self):
        original = copy.deepcopy(self.base)
        self.report()
        self.assertEqual(original, self.base)
        self.assertEqual(sorted((self.root / "shadow/id_kemhan").iterdir()),
                         [self.root / "shadow/id_kemhan/manifest.json"])

    def test_html_shows_candidate_only_and_missing_separately(self):
        html = ops.render_html(self.report())
        self.assertIn("Shadow collection evidence candidates", html)
        self.assertIn("Operator-supplied, unauthenticated evidence", html)
        self.assertIn("id_kemhan_news", html)
        self.assertIn("not_supplied", html)
        self.assertIn("1 candidate-supported", html)
        self.assertNotIn("Certified live", html)

    def test_empty_reports_do_not_fill_slot_count(self):
        r = self.report(reports=[])
        self.assertEqual(r["shadow_evidence_overlay"]["families_with_slot_candidates"], 0)
        for item in r["shadow_evidence_overlay"]["source_families"]:
            self.assertEqual(item["slot_evidence_status"], "not_supplied")

    def test_wrong_branch_or_wrong_source_refused(self):
        for key, value in (("state_branch", "shadow/korea-policy-briefing"),
                           ("source_slug", "kr_policy_mnd_releases")):
            with self.subTest(key=key):
                s = copy.deepcopy(self.slot)
                s[key] = value
                with self.assertRaises(overlay.OverlayError):
                    self.report(reports=[s])

    def test_wrong_cron_even_on_valid_branch_refused(self):
        s = copy.deepcopy(self.slot)
        s["cron_utc"] = "17:47"
        with self.assertRaisesRegex(overlay.OverlayError, "cron"):
            self.report(reports=[s])

    def test_future_observation_is_not_accepted(self):
        s = copy.deepcopy(self.slot)
        s["as_of_utc"] = "2026-10-09T01:00:00Z"
        with self.assertRaisesRegex(overlay.OverlayError, "future"):
            self.report(reports=[s])

    def test_missing_or_duplicate_family_binding_refused(self):
        b = copy.deepcopy(self.bindings)
        b["sources"].pop()
        with self.assertRaises(overlay.OverlayError):
            self.report(bindings=b)
        b = copy.deepcopy(self.bindings)
        b["sources"].append(copy.deepcopy(b["sources"][0]))
        b["source_families_checked"] = 3
        with self.assertRaises(overlay.OverlayError):
            self.report(bindings=b)

    def test_research_only_family_cannot_receive_fake_slot_report(self):
        s = copy.deepcopy(self.slot)
        s["source_slug"] = "vn_national_defence_journal_en"
        s["state_branch"] = None
        with self.assertRaises(overlay.OverlayError):
            self.report(reports=[s])

    def test_forged_authorization_flags_are_rejected(self):
        patches = [
            {"desk_production_eligible": True},
            {"editor_delivery_authorized": True},
            {"supplied_actions_export_authenticated": True},
            {"government_silence_established": True},
        ]
        for patch in patches:
            with self.subTest(patch=patch):
                s = dict(self.slot, **patch)
                with self.assertRaisesRegex(overlay.OverlayError, "authority"):
                    self.report(reports=[s])

    def test_counts_must_match_candidate_statuses(self):
        s = copy.deepcopy(self.slot)
        s["counts"]["candidate_supported"] = 2
        with self.assertRaisesRegex(overlay.OverlayError, "count/status"):
            self.report(reports=[s])

    def test_duplicate_supplied_slot_source_refused(self):
        with self.assertRaisesRegex(overlay.OverlayError, "duplicate"):
            self.report(reports=[self.slot, copy.deepcopy(self.slot)])

    def test_unknown_slot_status_refused(self):
        s = copy.deepcopy(self.slot)
        s["slots"][0]["status"] = "production_green"
        with self.assertRaisesRegex(overlay.OverlayError, "logical slot"):
            self.report(reports=[s])

    def test_shadow_manifest_identity_drift_refused(self):
        p = self.root / "shadow/id_kemhan/manifest.json"
        document = json.loads(p.read_text(encoding="utf-8"))
        document["sources"].append({"slug": "new_source", "enabled": True})
        p.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(overlay.OverlayError, "source count"):
            self.report()

    def test_real_repository_binding_report_joins_exact_shadow_manifests(self):
        # Before source-binding PR #257 lands this dependency is absent.
        # Once present on main, this becomes a REAL configuration contract,
        # rather than assuming independently invented fixture field names.
        native = ops.ROOT / "scripts/audit_shadow_workflow_bindings.py"
        if not native.is_file():
            self.skipTest("separate binding-audit PR not in checkout yet")
        from scripts import audit_shadow_workflow_bindings as bindings

        production_snapshot = copy.deepcopy(self.base)
        production_snapshot["shadow_source_manifests"] = ops.shadow_inventory(
            ops.SHADOW_ROOT, {})
        native_report = bindings.validate(ops.ROOT)
        joined = overlay.attach(
            production_snapshot, native_report, [], root=ops.ROOT)
        families = joined["shadow_evidence_overlay"]["source_families"]
        self.assertEqual(native_report["source_families_checked"], len(families))
        self.assertEqual(
            len(production_snapshot["shadow_source_manifests"]),
            native_report["manifests_checked"])
        self.assertEqual(
            {f["source_slug"] for f in families},
            {f["source_slug"] for f in native_report["sources"]})
        self.assertEqual(0, joined["shadow_evidence_overlay"]["families_with_slot_candidates"])
        self.assertTrue(all(f["slot_evidence_status"] == "not_supplied"
                            for f in families))
        self.assertFalse(joined["shadow_evidence_overlay"]["collection_verified"])
        self.assertFalse(joined["publication_authorized"])

    def test_snapshot_authorization_is_not_overridden(self):
        self.base["publication_authorized"] = True
        with self.assertRaisesRegex(overlay.OverlayError, "editorial authorization"):
            self.report()


if __name__ == "__main__":
    unittest.main()
