"""Source-free contracts for Philippines AFP and Vietnam checkpoint intake."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.compose_country_desk_checkpoint import (
    CheckpointRefused, philippines, vietnam, read_report, SCHEMA,
)

AFP_SHA = "a" * 40
VN_SHA = {"vn_mps_foreign_affairs_vi": "1" * 40,
          "vn_moit_energy_vi": "2" * 40,
          "vn_moit_foundational_industry_vi": "3" * 40}
BRANCH = {"vn_mps_foreign_affairs_vi": "shadow/vietnam-mps-foreign-affairs",
          "vn_moit_energy_vi": "shadow/vietnam-moit-energy",
          "vn_moit_foundational_industry_vi": "shadow/vietnam-moit-foundational-industry"}


def afp_inputs(n=7, reviewed=True):
    from datetime import date, timedelta
    start = date(2026, 10, 7)
    slots, runs = [], []
    for i in range(7):
        d = (start + timedelta(days=i)).isoformat()
        supported = i < n
        rid = "%d-1" % (7000 + i) if supported else None
        slots.append({"date": d, "run_id": rid,
                      "collection_status": ("ledger_success_unverified_actions"
                                            if supported else "future_not_due"),
                      "review_status": ("packet_checks_passed_identity_not_authenticated"
                                        if supported and reviewed else
                                        "human_source_review_packet_missing"
                                        if supported else "collection_evidence_unavailable")})
        runs.append({"date": d, "run_id": rid,
                     "status": ("actions_success_matches_ledger" if supported
                                else "not_eligible_for_actions_match")})
    preflight = {
        "protocol": "ipr_ph_afp_admission_preflight_v1",
        "desk": "philippines_afp_shadow_only",
        "state_commit": AFP_SHA,
        "as_of_utc_date": "2026-10-13" if n == 7 else "2026-10-11",
        "audit_window": ["2026-10-07", "2026-10-13"],
        "slots": slots,
        "ledger_slots_supported": n,
        "seven_slot_ledger_gate": n == 7,
        "source_review_packet_gate": reviewed and n == 7,
        "pending_review_runs": ([] if reviewed else
                                [s["run_id"] for s in slots if s["run_id"]]),
        "held_review_runs": [],
        "production_eligible": False,
        "weekly_AI_model_eligible": False,
        "desk_activated": False,
        "thirty_day_continuity_assessed": False,
        "day_7_human_checkpoint_completed": False,
        "day_14_human_checkpoint_completed": False,
        "day_30_human_checkpoint_completed": False,
    }
    actions = {
        "protocol": "ipr_ph_afp_actions_positive_match_v1",
        "desk": "ph-afp", "state_commit": AFP_SHA,
        "as_of_utc_date": preflight["as_of_utc_date"],
        "window_start": "2026-10-07", "window_end": "2026-10-13",
        "slots": runs, "matched_scheduled_successes": n,
        "all_seven_positive_runs_matched": n == 7,
        "other_scheduled_runs_in_export": [],
        "export_query_scope_independently_authenticated": False,
        "historical_failed_and_rerun_attempts_exhaustively_audited": False,
        "github_metadata_signed_or_authenticated_by_script": False,
        "human_reviews_or_reuse_rights_approved": False,
        "production_eligible": False, "weekly_ai_writer_eligible": False,
    }
    return preflight, actions


def vietnam_inputs():
    sources = []
    for slug, commit in VN_SHA.items():
        sources.append({
            "source_slug": slug, "state_branch": BRANCH[slug],
            "state_commit": commit, "as_of": "2026-10-14",
            "checkpoint": "day-07", "latest_run_id": "999-1",
            "checkpoint_reached": True,
            "anomaly_count": 0,
            "missing_collecting_days_count": 0,
            "uncovered_date_count": 0,
            "consecutive_collecting_days_count": 8,
            "human_signoff_complete": False,
            "production_promotion_authorized": False,
        })
    rollup = {
        "schema": "ipr-vietnam-three-source-checkpoint-rollup/1",
        "desk_id": "vietnam", "checkpoint": "day-07", "as_of": "2026-10-14",
        "source_count": 3, "all_three_review_packets_integrity_checked": True,
        "all_three_machine_checkpoints_reached": True,
        "latest_published_run_attempts_aligned": True,
        "sources": sources, "machine_warnings": [],
        "human_signoff_complete": False,
        "rights_to_publicly_republish_established": False,
        "production_promotion_authorized": False, "desk_qualified": False,
    }
    reconciler = {
        "schema": "ipr-vn-ministry-attempt-reconciliation/1",
        "review_window": {"from": "2026-10-07", "through": "2026-10-14"},
        "latest_run_by_source": dict.fromkeys(VN_SHA, "999-1"), "warnings": [],
        "github_attempt_inventory_independently_proven_exhaustive": False,
        "failed_attempt_artifacts_independently_verified": False,
        "all_scheduled_slots_proven_complete": False,
        "day_7_human_signoff_complete": False,
        "desk_qualified": False, "production_promotion_authorized": False,
        "source_rights_expanded": False,
    }
    bridge = {
        "schema": "ipr-vietnam-github-reconciler-bridge/1",
        "source": "real_GitHub_REST_read_only_bounded_window",
        "review_window": reconciler["review_window"],
        "state_head_shas": VN_SHA.copy(),
        "source_anomaly_counts": dict.fromkeys(VN_SHA, 0),
        "reconciler": reconciler,
        "status": "reconciled_bounded_metadata_not_human_approved",
        "independent_git_history_fully_verified": False,
        "complete_failed_attempt_artifact_review": False,
        "owner_signed_checkpoint": False,
        "source_use_rights_approved": False,
        "production_or_publication_authorized": False,
    }
    return rollup, bridge


class CheckpointIntakeContracts(unittest.TestCase):
    def test_afp_matching_seven_slot_candidate_is_never_approval(self):
        report = philippines(*afp_inputs())
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["machine_status"], "candidate_for_human_checkpoint")
        self.assertEqual(report["machine_evidence"]["verified_ledger_slots"], 7)
        self.assertEqual(report["machine_evidence"]["positive_Actions_matches"], 7)
        for field in ("human_checkpoint_authenticated", "complete_Actions_history_authenticated",
                      "production_eligible", "source_reuse_rights_approved",
                      "weekly_model_eligible", "desk_activated", "deployment_authorized"):
            self.assertIs(report[field], False, field)

    def test_afp_five_successful_scheduled_days_does_not_qualify(self):
        r = philippines(*afp_inputs(n=5, reviewed=False))
        self.assertEqual(r["machine_status"], "machine_evidence_incomplete_or_held")
        self.assertIn("AFP_checkpoint_window_not_elapsed", r["machine_holds"])
        self.assertEqual(r["machine_evidence"]["verified_ledger_slots"], 5)

    def test_afp_unverified_actions_slot_never_counts_as_matching(self):
        p, a = afp_inputs()
        a["slots"][4]["status"] = "actions_unverified"
        a["matched_scheduled_successes"] = 6
        a["all_seven_positive_runs_matched"] = False
        r = philippines(p, a)
        self.assertEqual(r["machine_status"], "machine_evidence_incomplete_or_held")
        self.assertIn("unverified_AFP_Actions_slot_2026-10-11", r["machine_holds"])

    def test_afp_extra_scheduled_run_requires_review(self):
        p, a = afp_inputs()
        a["other_scheduled_runs_in_export"] = [{"id": 9999}]
        r = philippines(p, a)
        self.assertIn("AFP_unreconciled_scheduled_Actions_events", r["machine_holds"])

    def test_afp_mixed_commit_or_shifted_date_refused(self):
        p, a = afp_inputs()
        a["state_commit"] = "f" * 40
        with self.assertRaisesRegex(CheckpointRefused, "commit mismatch"):
            philippines(p, a)
        p, a = afp_inputs()
        a["slots"][0]["date"] = "2026-10-08"
        with self.assertRaisesRegex(CheckpointRefused, "slot date"):
            philippines(p, a)

    def test_afp_forged_production_approval_refused(self):
        p, a = afp_inputs()
        p["production_eligible"] = True
        with self.assertRaisesRegex(CheckpointRefused, "unsafe or unknown"):
            philippines(p, a)

    def test_afp_forged_green_totals_refused(self):
        p, a = afp_inputs(n=5, reviewed=False)
        a["all_seven_positive_runs_matched"] = True
        with self.assertRaisesRegex(CheckpointRefused, "summary counts"):
            philippines(p, a)

    def test_vietnam_three_matching_source_packets_still_need_review(self):
        r = vietnam(*vietnam_inputs())
        self.assertEqual(r["machine_status"], "candidate_for_human_checkpoint")
        self.assertEqual(len(r["machine_evidence"]["sources"]), 3)
        self.assertIs(r["source_reuse_rights_approved"], False)
        self.assertIs(r["C13_satisfied"], False)
        self.assertIs(r["public_records_admitted"], False)

    def test_moit_source_anomaly_preserved_and_held(self):
        p, a = vietnam_inputs()
        slug = "vn_moit_energy_vi"
        a["source_anomaly_counts"][slug] = 4
        a["status"] = "needs_review"
        for row in p["sources"]:
            if row["source_slug"] == slug:
                row["anomaly_count"] = 4
        p["machine_warnings"] = [{"source_slug": slug, "kind": "unresolved_machine_anomaly"}]
        r = vietnam(p, a)
        self.assertIn(slug + "_source_anomalies_require_disposition", r["machine_holds"])
        self.assertEqual(r["machine_status"], "machine_evidence_incomplete_or_held")

    def test_formal_packet_omitting_moit_source_warning_is_refused(self):
        p, a = vietnam_inputs()
        slug = "vn_moit_foundational_industry_vi"
        a["source_anomaly_counts"][slug] = 5
        a["status"] = "needs_review"
        with self.assertRaisesRegex(CheckpointRefused, "omitted a committed source anomaly"):
            vietnam(p, a)

    def test_cross_branch_stale_pin_and_mismatched_latest_run_refused(self):
        p, a = vietnam_inputs()
        a["state_head_shas"]["vn_mps_foreign_affairs_vi"] = "f" * 40
        with self.assertRaisesRegex(CheckpointRefused, "pin mismatch"):
            vietnam(p, a)
        p, a = vietnam_inputs()
        a["reconciler"]["latest_run_by_source"]["vn_mps_foreign_affairs_vi"] = "998-1"
        with self.assertRaisesRegex(CheckpointRefused, "pin mismatch"):
            vietnam(p, a)

    def test_vietnam_future_checkpoint_and_missing_day_remain_held(self):
        p, a = vietnam_inputs()
        p["checkpoint"] = "day-14"
        for s in p["sources"]:
            s["checkpoint"] = "day-14"
            s["checkpoint_reached"] = False
        p["all_three_machine_checkpoints_reached"] = False
        r = vietnam(p, a)
        self.assertIn("Vietnam_checkpoint_earliest_scheduled_day_not_due", r["machine_holds"])
        self.assertEqual(r["machine_status"], "machine_evidence_incomplete_or_held")

    def test_vietnam_rights_forgery_refused(self):
        p, a = vietnam_inputs()
        a["source_use_rights_approved"] = True
        with self.assertRaisesRegex(CheckpointRefused, "unsafe or unknown"):
            vietnam(p, a)

    def test_vietnam_mixed_calendar_or_omitted_source_refused(self):
        p, a = vietnam_inputs()
        a["review_window"]["through"] = "2026-10-15"
        with self.assertRaisesRegex(CheckpointRefused, "audit must end"):
            vietnam(p, a)
        p, a = vietnam_inputs()
        p["sources"] = p["sources"][:2]
        with self.assertRaisesRegex(CheckpointRefused, "source identities"):
            vietnam(p, a)

    def test_duplicate_json_keys_and_symlink_input_refused(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            malformed = base / "dupe.json"
            malformed.write_text('{"schema":"one","schema":"two"}')
            with self.assertRaisesRegex(CheckpointRefused, "duplicate JSON field"):
                read_report(malformed)
            valid = base / "valid.json"
            valid.write_text(json.dumps({"schema": "one"}))
            link = base / "alias.json"
            link.symlink_to(valid)
            with self.assertRaisesRegex(CheckpointRefused, "regular local file"):
                read_report(link)


if __name__ == "__main__":
    unittest.main()
