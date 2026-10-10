"""S2.3a: fictional only, fail-closed Daily checkpoint/recovery simulation."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.evidence_checkpoint_rehearsal import (
    FAKE_TOKEN, REPORT_SCHEMA, checkpoint_fictional,
    recovery_decision_fictional, restore_fictional,
)
from core.evidence_snapshot import (
    EvidenceContractError, capture_backup, manifest_for_backup,
)
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)


class CheckpointRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-s2-recovery-tests-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "invented.sqlite"
        self.db = sqlite3.connect(str(self.path))
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE ipr_s2_fictional_gate (marker TEXT PRIMARY KEY);
            INSERT INTO ipr_s2_fictional_gate VALUES
                ('IPR_S2_SYNTHETIC_FIXTURE_ONLY_20261010');
            CREATE TABLE articles (id INTEGER PRIMARY KEY, text_original TEXT);
            INSERT INTO articles VALUES (11, 'NEVER_EXPOSE_FICTIONAL_PROSE_1188');
        """)
        self.db.commit()
        self.fake = InMemoryConditionalStore()
        self.store = EvidenceObjectCoordinator(self.fake)

    def checkpoint(self, stage="collected", parent=None, run_id="fictional-run-one"):
        return checkpoint_fictional(self.db, self.store, run_id=run_id,
                                    stage=stage, parent=parent)

    def test_no_current_requires_fake_collection(self):
        state = recovery_decision_fictional(self.store)
        self.assertEqual(state["next_rehearsal_step"], "fictional_initial_collection")
        self.assertIsNone(state["generation"])
        self.assertFalse(state["eligible_for_publication"])

    def test_collection_is_durable_before_any_analysis(self):
        collected = self.checkpoint()
        self.assertTrue(collected["advanced"])
        status = recovery_decision_fictional(self.store)
        self.assertEqual(status["generation"], collected["generation"])
        self.assertEqual(status["next_rehearsal_step"], "fictional_resume_analysis")
        dest = self.root / "recovered-before-analysis.sqlite"
        self.assertTrue(restore_fictional(self.store, dest)["restored"])
        with sqlite3.connect(str(dest)) as con:
            self.assertEqual(con.execute(
                "SELECT text_original FROM articles").fetchone()[0],
                "NEVER_EXPOSE_FICTIONAL_PROSE_1188")

    def test_completed_analysis_is_not_publish_authorization(self):
        collected = self.checkpoint()
        self.db.execute("INSERT INTO articles VALUES (27, 'FAKE_ANALYSIS_DATA')")
        self.db.commit()
        analyzed = self.checkpoint("analyzed", collected["generation"])
        self.assertTrue(analyzed["advanced"])
        status = recovery_decision_fictional(self.store)
        self.assertEqual(status["stage"], "analyzed")
        self.assertEqual(status["next_rehearsal_step"],
                         "fictional_private_validation")
        self.assertFalse(status["eligible_for_publication"])

    def test_analysis_failure_leaves_collected_generation_recoverable(self):
        collected = self.checkpoint()
        self.db.execute("INSERT INTO articles VALUES (27,'SHOULD_NOT_BE_DURABLE')")
        # Uncommitted changes are not a valid checkpoint source.
        with self.assertRaisesRegex(EvidenceContractError,
                                    "uncommitted_fixture_changes"):
            self.checkpoint("analyzed", collected["generation"])
        self.db.rollback()
        self.assertEqual(self.store.current()[0]["generation"],
                         collected["generation"])
        self.assertEqual(recovery_decision_fictional(self.store)
                         ["next_rehearsal_step"], "fictional_resume_analysis")

    def test_new_run_can_follow_failed_analysis_collection(self):
        first = self.checkpoint()
        self.db.execute("INSERT INTO articles VALUES (99,'NEXT_DAY_FAKE_CAPTURE')")
        self.db.commit()
        follow = self.checkpoint("collected", first["generation"],
                                 "fictional-run-two")
        self.assertEqual(recovery_decision_fictional(self.store)["generation"],
                         follow["generation"])
        past = self.root / "prior-day.sqlite"
        restore_fictional(self.store, past, first["generation"])
        with sqlite3.connect(str(past)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM articles").fetchone()[0], 1)

    def test_new_run_requires_distinct_identity(self):
        first = self.checkpoint()
        with self.assertRaisesRegex(EvidenceContractError,
                                    "new_collection_run_required"):
            self.checkpoint("collected", first["generation"])

    def test_analysis_requires_matching_run_and_parent_stage(self):
        first = self.checkpoint()
        with self.assertRaisesRegex(EvidenceContractError,
                                    "analysis_parent_mismatch"):
            self.checkpoint("analyzed", first["generation"],
                            "fictional-run-other")
        self.checkpoint("analyzed", first["generation"])
        with self.assertRaisesRegex(EvidenceContractError,
                                    "analysis_parent_mismatch"):
            self.checkpoint("analyzed",
                            self.store.current()[0]["generation"])

    def test_analysis_cannot_start_without_collection(self):
        with self.assertRaisesRegex(EvidenceContractError,
                                    "analysis_requires_collected_parent"):
            self.checkpoint("analyzed")

    def test_stage_rehearsal_cannot_be_checkpointed(self):
        with self.assertRaisesRegex(EvidenceContractError,
                                    "unsupported_checkpoint_stage"):
            self.checkpoint("rehearsal")

    def test_unmarked_realistic_sqlite_rejected_without_storage_write(self):
        ordinary = sqlite3.connect(":memory:")
        try:
            ordinary.execute("CREATE TABLE articles(id INTEGER PRIMARY KEY)")
            ordinary.commit()
            with self.assertRaisesRegex(EvidenceContractError,
                                        "fictional_fixture_required"):
                checkpoint_fictional(ordinary, self.store,
                                     run_id="fake", stage="collected")
            self.assertIsNone(self.store.current()[0])
        finally:
            ordinary.close()

    def test_wrong_fictional_gate_rejected(self):
        self.db.execute("UPDATE ipr_s2_fictional_gate SET marker='NOPE'")
        self.db.commit()
        with self.assertRaisesRegex(EvidenceContractError,
                                    "fictional_fixture_required"):
            self.checkpoint()

    def test_provider_failure_before_pointer_leaves_no_active_generation(self):
        self.fake.fail_next("put_new")
        with self.assertRaisesRegex(EvidenceContractError,
                                    "synthetic_storage_unavailable"):
            self.checkpoint()
        self.assertIsNone(self.store.current()[0])
        self.assertTrue(self.checkpoint()["advanced"])

    def test_collection_cas_failure_keeps_recoverable_previous_state(self):
        first = self.checkpoint()
        self.db.execute("INSERT INTO articles VALUES (12,'FAKE_NEXT_BATCH')")
        self.db.commit()
        self.fake.fail_next("cas")
        with self.assertRaisesRegex(EvidenceContractError,
                                    "synthetic_storage_unavailable"):
            self.checkpoint("collected", first["generation"], "fictional-run-two")
        self.assertEqual(self.store.current()[0]["generation"],
                         first["generation"])
        self.assertTrue(self.checkpoint("collected", first["generation"],
                                        "fictional-run-two")["advanced"])

    def test_lost_pointer_ack_can_be_replayed_idempotently(self):
        self.fake.fail_next("cas", after_write=True)
        with self.assertRaisesRegex(EvidenceContractError,
                                    "synthetic_storage_unavailable"):
            self.checkpoint()
        originally_active = self.store.current()[0]["generation"]
        repeat = self.checkpoint()
        self.assertFalse(repeat["advanced"])
        self.assertEqual(repeat["generation"], originally_active)

    def test_stale_writer_cannot_discard_new_collection(self):
        first = self.checkpoint()
        self.db.execute("INSERT INTO articles VALUES(13,'FAKE_NEXT_DAY')")
        self.db.commit()
        second = self.checkpoint("collected", first["generation"],
                                 "fictional-run-two")
        with self.assertRaisesRegex(EvidenceContractError, "stale_generation"):
            self.checkpoint("collected", first["generation"],
                            "fictional-run-three")
        self.assertEqual(self.store.current()[0]["generation"],
                         second["generation"])

    def test_competing_payload_with_same_run_identity_rejected(self):
        initial = self.checkpoint()
        self.db.execute("INSERT INTO articles VALUES (13,'CONFLICTED_FAKE')")
        self.db.commit()
        with self.assertRaisesRegex(EvidenceContractError,
                                    "object_readback_mismatch"):
            self.checkpoint()
        self.assertEqual(self.store.current()[0]["generation"],
                         initial["generation"])

    def test_read_outage_blocks_decision_and_remains_retryable(self):
        self.checkpoint()
        self.fake.fail_next("get")
        with self.assertRaisesRegex(EvidenceContractError,
                                    "synthetic_storage_unavailable"):
            recovery_decision_fictional(self.store)
        self.assertEqual(recovery_decision_fictional(self.store)["stage"],
                         "collected")

    def test_corrupt_evidence_blocks_recovery_decision(self):
        first = self.checkpoint()
        key = "manifests/" + first["generation"] + ".json"
        self.fake.damage_for_test(key, b"{broken")
        with self.assertRaises(EvidenceContractError):
            recovery_decision_fictional(self.store)

    def test_restore_rejects_fake_wrong_gate_and_cleans_target(self):
        other = sqlite3.connect(":memory:")
        try:
            other.execute("CREATE TABLE articles(id INTEGER PRIMARY KEY)")
            other.execute("INSERT INTO articles VALUES(50)")
            other.commit()
            fake_path = self.root / "fake-but-ungated.sqlite"
            capture_backup(other, fake_path)
            m = manifest_for_backup(fake_path, run_id="made-up",
                                    stage="rehearsal")
            self.store.prepare(fake_path, m)
            target = self.root / "should-not-survive.sqlite"
            with self.assertRaisesRegex(EvidenceContractError,
                                        "restored_fixture_invalid"):
                restore_fictional(self.store, target, m["generation"])
            self.assertFalse(target.exists())
        finally:
            other.close()

    def test_outputs_have_no_protected_fictional_prose(self):
        first = self.checkpoint()
        report = [first, recovery_decision_fictional(self.store)]
        restored = self.root / "redaction.sqlite"
        report.append(restore_fictional(self.store, restored))
        serialized = json.dumps(report)
        self.assertNotIn("NEVER_EXPOSE_FICTIONAL_PROSE_1188", serialized)
        self.assertNotIn(FAKE_TOKEN, serialized)
        self.assertTrue(all(x["eligible_for_publication"] is False
                            for x in report))

    def test_existing_restore_target_not_overwritten(self):
        first = self.checkpoint()
        target = self.root / "protected-existing.sqlite"
        target.write_bytes(b"KEEP")
        with self.assertRaises(EvidenceContractError):
            restore_fictional(self.store, target, first["generation"])
        self.assertEqual(target.read_bytes(), b"KEEP")


if __name__ == "__main__":
    unittest.main()
