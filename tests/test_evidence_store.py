"""S2.1: synthetic CAS, recovery and failure-safety tests; no production data."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.evidence_snapshot import (
    EvidenceContractError, capture_backup, digest_file, manifest_for_backup,
)
from storage.evidence_store import LocalEvidenceStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ipr-s2-fixtures-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dbpath = self.root / "source.sqlite"
        self.db = sqlite3.connect(str(self.dbpath))
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE articles(id INTEGER PRIMARY KEY, text_original TEXT)")
        self.db.execute("INSERT INTO articles VALUES(42, 'FICTIONAL_PRIVATE_BODY_10001')")
        self.db.commit()
        self.store_path = self.root / "ipr-s2-private-store"
        self.store_path.mkdir()
        self.store = LocalEvidenceStore(self.store_path)

    def generation(self, n=1, parent=None):
        path = self.root / ("snapshot%d.sqlite" % n)
        capture_backup(self.db, path)
        manifest = manifest_for_backup(path, run_id="synthetic-run-%d" % n,
                                       stage="rehearsal", parent=parent)
        return path, manifest

    def upload(self, path, manifest):
        self.store.put_snapshot(path, manifest)
        self.store.put_manifest(manifest)

    def test_commit_and_recover(self):
        path, m = self.generation()
        self.upload(path, m)
        self.assertTrue(self.store.advance(m["generation"]))
        restored = self.root / "restored.sqlite"
        self.assertEqual(self.store.recover(restored)["generation"], m["generation"])
        self.assertEqual(digest_file(restored), digest_file(path))
        con = sqlite3.connect(str(restored))
        try:
            self.assertEqual(con.execute("SELECT id FROM articles").fetchone()[0], 42)
        finally:
            con.close()

    def test_current_absent_until_explicit_commit(self):
        path, m = self.generation()
        self.upload(path, m)
        self.assertIsNone(self.store.current())
        with self.assertRaisesRegex(EvidenceContractError, "no_current_generation"):
            self.store.recover(self.root / "restore.sqlite")

    def test_retry_is_idempotent(self):
        path, m = self.generation()
        self.upload(path, m)
        self.assertTrue(self.store.advance(m["generation"]))
        self.upload(path, m)
        self.assertFalse(self.store.advance(m["generation"]))

    def test_second_writer_with_stale_parent_fails(self):
        p1, m1 = self.generation()
        self.upload(p1, m1)
        self.store.advance(m1["generation"])
        p2, m2 = self.generation(2, parent=m1["generation"])
        p3, m3 = self.generation(3, parent=m1["generation"])
        self.upload(p2, m2)
        self.upload(p3, m3)
        self.store.advance(m2["generation"], m1["generation"])
        with self.assertRaisesRegex(EvidenceContractError, "stale_generation"):
            self.store.advance(m3["generation"], m1["generation"])
        self.assertEqual(self.store.current()["generation"], m2["generation"])

    def test_parent_must_match_manifest(self):
        p, m = self.generation(1)
        self.upload(p, m)
        self.store.advance(m["generation"])
        later, m2 = self.generation(2, parent="0" * 64)
        self.upload(later, m2)
        with self.assertRaisesRegex(EvidenceContractError, "parent_generation_mismatch"):
            self.store.advance(m2["generation"], m["generation"])

    def test_orphan_upload_never_active(self):
        p, m = self.generation(1)
        self.upload(p, m)
        self.assertIsNone(self.store.current())

    def test_cannot_reference_missing_manifest(self):
        with self.assertRaisesRegex(EvidenceContractError, "manifest_missing"):
            self.store.advance("0" * 64)

    def test_recover_older_generation(self):
        p1, m1 = self.generation(1)
        self.upload(p1, m1)
        self.store.advance(m1["generation"])
        self.db.execute("INSERT INTO articles VALUES(67, 'FICTIONAL_BODY_2')")
        self.db.commit()
        p2, m2 = self.generation(2, m1["generation"])
        self.upload(p2, m2)
        self.store.advance(m2["generation"], m1["generation"])
        past = self.root / "older.sqlite"
        self.store.recover(past, generation=m1["generation"])
        con = sqlite3.connect(str(past))
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM articles").fetchone()[0], 1)
        finally:
            con.close()

    def test_corrupt_snapshot_blocks_pointer(self):
        p, m = self.generation()
        self.upload(p, m)
        self.store.snapshot_path(m["snapshot_sha256"]).write_bytes(b"CORRUPTED")
        with self.assertRaises(EvidenceContractError):
            self.store.advance(m["generation"])
        self.assertIsNone(self.store.current())

    def test_corrupt_snapshot_blocks_recovery(self):
        p, m = self.generation()
        self.upload(p, m)
        self.store.advance(m["generation"])
        self.store.snapshot_path(m["snapshot_sha256"]).write_bytes(b"BROKEN")
        with self.assertRaises(EvidenceContractError):
            self.store.recover(self.root / "recovered.sqlite")
        self.assertFalse((self.root / "recovered.sqlite").exists())

    def test_manifest_tampering_rejected(self):
        p, m = self.generation()
        self.upload(p, m)
        mp = self.store.manifest_path(m["generation"])
        data = json.loads(mp.read_text())
        data["article_count"] = 100
        mp.write_text(json.dumps(data))
        with self.assertRaises(EvidenceContractError):
            self.store.advance(m["generation"])

    def test_ref_tampering_rejected(self):
        p, m = self.generation()
        self.upload(p, m)
        self.store.advance(m["generation"])
        ref = self.store_path / "refs" / "current.json"
        data = json.loads(ref.read_text())
        data["manifest_sha256"] = "0" * 64
        ref.write_text(json.dumps(data))
        with self.assertRaisesRegex(EvidenceContractError, "active_manifest_digest_mismatch"):
            self.store.recover(self.root / "recovered.sqlite")

    def test_existing_restore_target_not_overwritten(self):
        p, m = self.generation()
        self.upload(p, m)
        self.store.advance(m["generation"])
        target = self.root / "existing.sqlite"
        target.write_bytes(b"do not overwrite")
        with self.assertRaisesRegex(EvidenceContractError, "restore_target_invalid"):
            self.store.recover(target)
        self.assertEqual(target.read_bytes(), b"do not overwrite")

    def test_unapproved_storage_path_rejected(self):
        unsafe = self.root / "not-an-authorized-store"
        unsafe.mkdir()
        with self.assertRaisesRegex(EvidenceContractError, "unsafe_store_root"):
            LocalEvidenceStore(unsafe)

    def test_symlink_store_rejected(self):
        alias = self.root / "ipr-s2-symlink"
        try:
            alias.symlink_to(self.store_path, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(EvidenceContractError, "unsafe_store_root"):
            LocalEvidenceStore(alias)

    def test_symlink_manifest_rejected(self):
        p, m = self.generation()
        self.upload(p, m)
        mp = self.store.manifest_path(m["generation"])
        mp.unlink()
        mp.symlink_to(p)
        with self.assertRaisesRegex(EvidenceContractError, "manifest_missing"):
            self.store.advance(m["generation"])

    def test_no_private_body_in_custody_report(self):
        p, m = self.generation()
        self.upload(p, m)
        self.store.advance(m["generation"])
        result = self.store.recover(self.root / "restore.sqlite")
        self.assertNotIn("FICTIONAL_PRIVATE_BODY_10001", json.dumps(result))

    def test_no_publication_implicit_in_manifest(self):
        p, m = self.generation()
        self.upload(p, m)
        self.assertIsNone(self.store.current())
        self.assertNotIn("eligible_for_publication", json.dumps(m))

    def test_conflicting_payload_same_run_and_stage_rejected(self):
        p1, m1 = self.generation(1)
        self.upload(p1, m1)
        self.db.execute("INSERT INTO articles VALUES(43,'DIFFERENT_FAKE_EVIDENCE')")
        self.db.commit()
        p2 = self.root / "repeated-run.sqlite"
        capture_backup(self.db, p2)
        m2 = manifest_for_backup(p2, run_id="synthetic-run-1", stage="rehearsal")
        self.store.put_snapshot(p2, m2)
        with self.assertRaisesRegex(EvidenceContractError, "run_stage_conflict"):
            self.store.put_manifest(m2)
        self.assertIsNone(self.store.current())

    def test_two_stages_for_same_run_allowed(self):
        p1, m1 = self.generation(1)
        self.upload(p1, m1)
        p2 = self.root / "analysis-stage.sqlite"
        capture_backup(self.db, p2)
        m2 = manifest_for_backup(p2, run_id="synthetic-run-1", stage="analyzed",
                                 parent=m1["generation"])
        self.upload(p2, m2)
        self.store.advance(m1["generation"])
        self.assertTrue(self.store.advance(m2["generation"], m1["generation"]))


if __name__ == "__main__":
    unittest.main()
