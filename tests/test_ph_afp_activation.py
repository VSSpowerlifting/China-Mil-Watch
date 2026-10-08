"""Synthetic, offline AFP activation preflight invariants only."""
from __future__ import annotations

import copy
import unittest
from scripts import assess_ph_afp_activation as preflight


class OfflineGate(unittest.TestCase):
    def setUp(self):
        self.audit = {
            "immutable_state_commit": "a" * 40,
            "as_of_utc_date": "2026-10-13",
            "window_start": "2026-10-07",
            "window_end": "2026-10-13",
            "successfully_supported_ledger_slots": 7,
            "all_seven_ledger_slots_supported": True,
            "slots": [
                {"date": "2026-10-%02d" % day,
                 "status": "ledger_success_unverified_actions",
                 "run_id": "SYNTHETIC-%d" % day,
                 "inserted": (13 if day == 7 else 5 if day == 8 else 0)}
                for day in range(7, 14)
            ],
        }
        self.reviews = {
            "SYNTHETIC-7": {"total": 13, "decisions": {"verified": 13, "hold": 0, "pending": 0}},
            "SYNTHETIC-8": {"total": 5, "decisions": {"verified": 5, "hold": 0, "pending": 0}},
        }

    def test_fully_supported_still_never_activates(self):
        out = preflight.summarize(self.audit, self.reviews)
        self.assertTrue(out["seven_day_machine_evidence_candidate_for_human_checkpoint"])
        self.assertEqual(out["production_minimum_consecutive_collecting_days"], 30)
        self.assertFalse(out["thirty_day_continuity_assessed"])
        self.assertFalse(out["day_7_human_checkpoint_completed"])
        self.assertFalse(out["day_14_human_checkpoint_completed"])
        self.assertFalse(out["day_30_human_checkpoint_completed"])
        self.assertFalse(out["production_eligible"])
        self.assertFalse(out["weekly_AI_model_eligible"])
        self.assertFalse(out["desk_activated"])
        self.assertEqual(out["database_or_output_writes"], 0)
        self.assertEqual(len(out["unresolved_external_gates"]), 6)
        self.assertIn("C13_thirty_consecutive_collecting_days_and_day_7_14_30_human_checkpoints",
                      out["unresolved_external_gates"])

    def test_before_seventh_day_remains_blocked(self):
        partial = copy.deepcopy(self.audit)
        partial["all_seven_ledger_slots_supported"] = False
        partial["successfully_supported_ledger_slots"] = 2
        for s in partial["slots"][2:]:
            s.update(status="future_not_due", inserted=None, run_id=None)
        out = preflight.summarize(partial, {})
        self.assertFalse(out["seven_slot_ledger_gate"])
        self.assertFalse(out["source_review_packet_gate"])
        self.assertEqual(out["pending_review_runs"], ["SYNTHETIC-7", "SYNTHETIC-8"])

    def test_missing_review_blocks_preflight(self):
        out = preflight.summarize(self.audit, {"SYNTHETIC-7": self.reviews["SYNTHETIC-7"]})
        self.assertFalse(out["source_review_packet_gate"])
        self.assertEqual(out["pending_review_runs"], ["SYNTHETIC-8"])

    def test_hold_blocks_even_complete_packet(self):
        reviews = copy.deepcopy(self.reviews)
        reviews["SYNTHETIC-8"]["decisions"] = {"verified": 4, "hold": 1, "pending": 0}
        out = preflight.summarize(self.audit, reviews)
        self.assertFalse(out["source_review_packet_gate"])
        self.assertEqual(out["held_review_runs"], ["SYNTHETIC-8"])

    def test_mutated_review_counts_refused(self):
        reviews = copy.deepcopy(self.reviews)
        reviews["SYNTHETIC-7"]["total"] = 12
        with self.assertRaisesRegex(preflight.AdmissionPreflightError, "conflicts"):
            preflight.summarize(self.audit, reviews)

    def test_missing_or_inconsistent_review_decisions_block(self):
        for fake in ({}, {"verified": 13, "hold": 0, "pending": 0},
                     {"verified": 13, "hold": 1, "pending": 0}):
            fake_reviews = copy.deepcopy(self.reviews)
            fake_reviews["SYNTHETIC-8"]["decisions"] = fake
            with self.subTest(fake=fake), self.assertRaisesRegex(
                    preflight.AdmissionPreflightError, "decision counts"):
                preflight.summarize(self.audit, fake_reviews)

    def test_manifest_rejects_duplicate_unknown_and_traversal(self):
        base = {"protocol": "ipr_ph_afp_activation_review_manifest_v1",
                "reviews": [{"run_id": "SYNTHETIC-7", "state_commit": "b"*40,
                             "file": "day0.json"}]}
        self.assertEqual(len(preflight.validate_manifest(base, self.audit)), 1)
        for change in ("../../oops.json", "../oops.json", "/tmp/evil.json"):
            bad = copy.deepcopy(base)
            bad["reviews"][0]["file"] = change
            with self.subTest(change=change), self.assertRaises(preflight.AdmissionPreflightError):
                preflight.validate_manifest(bad, self.audit)
        for other in ("SYNTHETIC-9", "SYNTHETIC-17"):
            bad = copy.deepcopy(base)
            bad["reviews"][0]["run_id"] = other
            with self.subTest(other=other), self.assertRaises(preflight.AdmissionPreflightError):
                preflight.validate_manifest(bad, self.audit)
        bad = copy.deepcopy(base)
        bad["reviews"].append(dict(bad["reviews"][0]))
        with self.assertRaises(preflight.AdmissionPreflightError):
            preflight.validate_manifest(bad, self.audit)

    def test_manifest_rejects_forged_source_commit(self):
        raw = {"protocol": "ipr_ph_afp_activation_review_manifest_v1",
               "reviews": [{"run_id": "SYNTHETIC-7", "state_commit": "main", "file": "day0.json"}]}
        with self.assertRaises(preflight.AdmissionPreflightError):
            preflight.validate_manifest(raw, self.audit)

    def test_manifest_rejects_unreviewable_non_success_day(self):
        partial = copy.deepcopy(self.audit)
        partial["slots"][0]["status"] = "invalid_ledger_evidence"
        raw = {"protocol": "ipr_ph_afp_activation_review_manifest_v1",
               "reviews": [{"run_id": "SYNTHETIC-7", "state_commit": "b"*40,
                            "file": "day0.json"}]}
        with self.assertRaises(preflight.AdmissionPreflightError):
            preflight.validate_manifest(raw, partial)


if __name__ == "__main__":
    unittest.main()
