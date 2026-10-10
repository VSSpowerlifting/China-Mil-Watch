"""S2.2a object transport rehearsal: fictional SQLite only, no network or Git."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.evidence_snapshot import (
    EvidenceContractError, capture_backup, canonical_bytes, digest_bytes,
    manifest_for_backup,
)
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore, MAX_SYNTHETIC_BYTES,
)


class ObjectProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-s2-object-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = sqlite3.connect(str(self.root / "fictional.sqlite"))
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE articles(id INTEGER PRIMARY KEY, text_original TEXT)")
        self.db.execute("INSERT INTO articles VALUES(57,'FICTIONAL_NOT_FOR_PUBLICATION')")
        self.db.commit()
        self.fake = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.fake)

    def generation(self, label="one", parent=None, run_id=None, stage="rehearsal"):
        p = self.root / (label + ".sqlite")
        capture_backup(self.db, p)
        m = manifest_for_backup(p, run_id=run_id or ("synthetic-" + label),
                                stage=stage, parent=parent)
        return p, m

    def register(self, label="one", parent=None, run_id=None):
        p, m = self.generation(label, parent, run_id)
        self.coordinator.prepare(p, m)
        return m

    def test_empty_current_until_explicit_advance(self):
        m = self.register()
        self.assertIsNone(self.coordinator.current()[0])
        self.assertEqual(len(m["generation"]), 64)

    def test_commit_and_restore_verifies_fictional_sqlite(self):
        m = self.register()
        self.assertTrue(self.coordinator.advance(m["generation"]))
        dest = self.root / "restored.sqlite"
        output = self.coordinator.restore_to_temp(dest)
        self.assertEqual(output["generation"], m["generation"])
        with sqlite3.connect(str(dest)) as db:
            self.assertEqual(db.execute(
                "SELECT id FROM articles").fetchone()[0], 57)

    def test_wal_insert_is_in_uploaded_snapshot(self):
        self.db.execute("INSERT INTO articles VALUES(92,'COMMITTED_WAL_DATA')")
        self.db.commit()
        m = self.register()
        self.coordinator.advance(m["generation"])
        dest = self.root / "wal.sqlite"
        self.coordinator.restore_to_temp(dest)
        with sqlite3.connect(str(dest)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM articles").fetchone()[0], 2)

    def test_old_generation_restore(self):
        first = self.register()
        self.coordinator.advance(first["generation"])
        self.db.execute("INSERT INTO articles VALUES(90,'FICTIONAL_UPDATE')")
        self.db.commit()
        second = self.register("two", first["generation"])
        self.coordinator.advance(second["generation"], first["generation"])
        out = self.root / "older.sqlite"
        self.coordinator.restore_to_temp(out, first["generation"])
        with sqlite3.connect(str(out)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM articles").fetchone()[0], 1)

    def test_retry_of_identical_immutable_payload_and_pointer(self):
        p, m = self.generation()
        self.coordinator.prepare(p, m)
        self.coordinator.prepare(p, m)
        self.assertTrue(self.coordinator.advance(m["generation"]))
        self.assertFalse(self.coordinator.advance(m["generation"]))

    def test_different_payload_with_same_run_stage_rejected(self):
        p, first = self.generation(run_id="same-run")
        self.coordinator.prepare(p, first)
        self.db.execute("INSERT INTO articles VALUES(61,'DIFFERENT_PAYLOAD')")
        self.db.commit()
        p2, second = self.generation("two", run_id="same-run")
        with self.assertRaisesRegex(EvidenceContractError, "object_readback_mismatch"):
            self.coordinator.prepare(p2, second)
        self.assertIsNone(self.coordinator.current()[0])

    def test_same_run_different_stages_are_allowed(self):
        first = self.register()
        self.coordinator.advance(first["generation"])
        p, next_stage = self.generation("stage", first["generation"],
                                        run_id="synthetic-one", stage="analyzed")
        self.coordinator.prepare(p, next_stage)
        self.assertTrue(self.coordinator.advance(next_stage["generation"],
                                                  first["generation"]))

    def test_two_racing_writers_only_one_wins(self):
        first = self.register()
        self.coordinator.advance(first["generation"])
        a = self.register("two", first["generation"])
        b = self.register("three", first["generation"])
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks = [pool.submit(self.coordinator.advance, m["generation"],
                                 first["generation"]) for m in (a, b)]
            results = []
            for t in tasks:
                try:
                    results.append(("ok", t.result()))
                except EvidenceContractError as exc:
                    results.append(("error", str(exc)))
        self.assertEqual(sorted(x[0] for x in results), ["error", "ok"])
        self.assertIn(results[0][1] if results[0][0] == "error" else results[1][1],
                      ("stale_generation", "concurrent_pointer_update"))
        self.assertIn(self.coordinator.current()[0]["generation"],
                      (a["generation"], b["generation"]))

    def test_first_generation_needs_no_parent(self):
        m = self.register()
        with self.assertRaisesRegex(EvidenceContractError, "stale_generation"):
            self.coordinator.advance(m["generation"], "0" * 64)

    def test_bad_parent_does_not_update_head(self):
        first = self.register()
        self.coordinator.advance(first["generation"])
        other = self.register("two", "0" * 64)
        with self.assertRaisesRegex(EvidenceContractError, "parent_generation_mismatch"):
            self.coordinator.advance(other["generation"], first["generation"])
        self.assertEqual(self.coordinator.current()[0]["generation"], first["generation"])

    def test_failed_immutable_upload_does_not_advance_head(self):
        self.fake.fail_next("put_new")
        p, m = self.generation()
        with self.assertRaisesRegex(EvidenceContractError, "synthetic_storage_unavailable"):
            self.coordinator.prepare(p, m)
        self.assertIsNone(self.coordinator.current()[0])

    def test_failed_upload_can_retry_cleanly(self):
        self.fake.fail_next("put_new")
        p, m = self.generation()
        with self.assertRaises(EvidenceContractError):
            self.coordinator.prepare(p, m)
        self.coordinator.prepare(p, m)
        self.assertTrue(self.coordinator.advance(m["generation"]))

    def test_ack_lost_after_immutable_upload_can_retry(self):
        self.fake.fail_next("put_new", after_write=True)
        p, m = self.generation()
        with self.assertRaisesRegex(EvidenceContractError, "synthetic_storage_unavailable"):
            self.coordinator.prepare(p, m)
        self.coordinator.prepare(p, m)
        self.assertTrue(self.coordinator.advance(m["generation"]))

    def test_object_readback_failure_does_not_register_claim(self):
        self.fake.fail_next("get")
        p, m = self.generation()
        with self.assertRaisesRegex(EvidenceContractError, "synthetic_storage_unavailable"):
            self.coordinator.prepare(p, m)
        self.assertIsNone(self.fake.get("claims/" + m["run_id"] + "/rehearsal.json"))
        self.assertIsNone(self.coordinator.current()[0])

    def test_cas_service_failure_no_pointer(self):
        m = self.register()
        self.fake.fail_next("cas")
        with self.assertRaisesRegex(EvidenceContractError, "synthetic_storage_unavailable"):
            self.coordinator.advance(m["generation"])
        self.assertIsNone(self.coordinator.current()[0])

    def test_cas_ack_lost_after_write_is_safe_on_retry(self):
        m = self.register()
        self.fake.fail_next("cas", after_write=True)
        with self.assertRaisesRegex(EvidenceContractError, "synthetic_storage_unavailable"):
            self.coordinator.advance(m["generation"])
        self.assertFalse(self.coordinator.advance(m["generation"]))
        self.assertEqual(self.coordinator.current()[0]["generation"], m["generation"])

    def test_corrupt_snapshot_prevents_advance(self):
        m = self.register()
        self.fake.damage_for_test(
            "snapshots/" + m["snapshot_sha256"] + ".sqlite", b"CORRUPT")
        with self.assertRaisesRegex(EvidenceContractError, "snapshot_object_corrupt"):
            self.coordinator.advance(m["generation"])
        self.assertIsNone(self.coordinator.current()[0])

    def test_corrupt_manifest_prevents_advance(self):
        m = self.register()
        self.fake.damage_for_test("manifests/" + m["generation"] + ".json",
                                  b'{"fake":true}')
        with self.assertRaises(EvidenceContractError):
            self.coordinator.advance(m["generation"])

    def test_corrupt_run_claim_prevents_advance(self):
        m = self.register()
        self.fake.damage_for_test("claims/" + m["run_id"] + "/rehearsal.json",
                                  b'{"generation":"0"}\n')
        with self.assertRaisesRegex(EvidenceContractError, "run_stage_conflict"):
            self.coordinator.advance(m["generation"])

    def test_corrupt_current_ref_detected(self):
        m = self.register()
        self.coordinator.advance(m["generation"])
        self.fake.damage_for_test(self.coordinator.REF_KEY, b'{"fake":true}')
        with self.assertRaises(EvidenceContractError):
            self.coordinator.current()

    def test_manifest_digest_mismatch_detected(self):
        m = self.register()
        self.coordinator.advance(m["generation"])
        first, _ = self.fake.get(self.coordinator.REF_KEY)
        fake_ref = json.loads(first)
        fake_ref["manifest_sha256"] = "0" * 64
        self.fake.damage_for_test(self.coordinator.REF_KEY, canonical_bytes(fake_ref))
        with self.assertRaisesRegex(EvidenceContractError, "active_manifest_digest_mismatch"):
            self.coordinator.current()

    def test_missing_snapshot_fails_closed(self):
        m = self.register()
        self.fake._objects.pop("snapshots/" + m["snapshot_sha256"] + ".sqlite")
        with self.assertRaisesRegex(EvidenceContractError, "snapshot_missing"):
            self.coordinator.advance(m["generation"])

    def test_ref_revision_detects_stale_pointer(self):
        m = self.register()
        self.assertTrue(self.fake.cas(self.coordinator.REF_KEY, None, b"bogus"))
        self.assertFalse(self.fake.cas(self.coordinator.REF_KEY, None, b"other"))
        with self.assertRaises(EvidenceContractError):
            self.coordinator.advance(m["generation"])

    def test_clean_readback_is_identity_exact(self):
        m = self.register()
        key = "manifests/" + m["generation"] + ".json"
        self.assertEqual(self.fake.get(key)[0], canonical_bytes(m))
        self.assertEqual(digest_bytes(self.fake.get(key)[0]),
                         digest_bytes(canonical_bytes(m)))

    def test_restore_destination_must_be_temporary(self):
        m = self.register()
        self.coordinator.advance(m["generation"])
        with self.assertRaisesRegex(EvidenceContractError,
                                    "restore_destination_not_temporary"):
            self.coordinator.restore_to_temp(Path("/nonexistent/file.db"))

    def test_no_clobber_of_existing_recovery(self):
        m = self.register()
        self.coordinator.advance(m["generation"])
        dest = self.root / "restored.sqlite"
        dest.write_bytes(b"KEEP")
        with self.assertRaisesRegex(EvidenceContractError,
                                    "restore_destination_not_temporary"):
            self.coordinator.restore_to_temp(dest)
        self.assertEqual(dest.read_bytes(), b"KEEP")

    def test_no_original_text_in_fixed_diagnostics_or_manifests(self):
        p, m = self.generation()
        self.coordinator.prepare(p, m)
        body = "FICTIONAL_NOT_FOR_PUBLICATION"
        self.assertNotIn(body, json.dumps(m))
        self.fake.damage_for_test("snapshots/" + m["snapshot_sha256"] + ".sqlite",
                                  b"BREAK")
        with self.assertRaises(EvidenceContractError) as failure:
            self.coordinator.advance(m["generation"])
        self.assertNotIn(body, str(failure.exception))

    def test_snapshots_not_claimed_publicly_eligible(self):
        m = self.register()
        self.coordinator.advance(m["generation"])
        self.assertNotIn("eligible_for_publication", json.dumps(m))
        self.assertNotIn("eligible_for_publication",
                         self.fake.get(self.coordinator.REF_KEY)[0].decode())

    def test_rehearsal_snapshot_limit(self):
        p, m = self.generation()
        m["snapshot_bytes"] = MAX_SYNTHETIC_BYTES + 1
        with self.assertRaises(EvidenceContractError):
            self.coordinator.prepare(p, m)

    def test_transport_has_no_network_credentials(self):
        self.assertFalse(hasattr(self.fake, "access_key"))
        self.assertFalse(hasattr(self.fake, "endpoint"))
        self.assertFalse(hasattr(self.fake, "bucket"))


if __name__ == "__main__":
    unittest.main()
