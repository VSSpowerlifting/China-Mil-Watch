"""S2.1: synthetic SQLite integrity and WAL-consistent snapshot tests."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
import threading
from unittest.mock import patch
from pathlib import Path

from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, capture_backup, digest_file,
    inspect_database, manifest_for_backup, parse_manifest, parse_ref,
    validate_manifest, verify_snapshot,
)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-s2-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "fictional.sqlite"
        self.conn = sqlite3.connect(str(self.source))
        self.addCleanup(self.conn.close)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript("""
            CREATE TABLE publishers(id INTEGER PRIMARY KEY);
            CREATE TABLE articles(id INTEGER PRIMARY KEY,
                publisher_id INTEGER REFERENCES publishers(id),
                source_text TEXT NOT NULL);
            INSERT INTO publishers VALUES(1);
            INSERT INTO articles VALUES(42, 1, 'SYNTHETIC_SECRET_DATA_9855');
        """)
        self.conn.commit()

    def make(self, stage="collected", parent=None, run_id="fake-run-001"):
        path = self.root / (stage + str(len(list(self.root.glob("copy*.sqlite")))) + ".sqlite")
        capture_backup(self.conn, path)
        return path, manifest_for_backup(path, run_id=run_id, stage=stage, parent=parent)

    def test_capture_is_wal_consistent(self):
        self.conn.execute("INSERT INTO articles VALUES(89,1,'WAL_CAPTURED_0123')")
        self.conn.commit()
        self.assertTrue((self.root / "fictional.sqlite-wal").exists())
        path, manifest = self.make()
        with sqlite3.connect(str(path)) as db:
            self.assertEqual(db.execute("SELECT id FROM articles ORDER BY id").fetchall(),
                             [(42,), (89,)])
        self.assertEqual(manifest["article_count"], 2)
        self.assertEqual(manifest["max_article_id"], 89)
        self.assertFalse(Path(str(path) + "-wal").exists())
        self.assertFalse(Path(str(path) + "-shm").exists())

    def test_caller_transaction_rejected_before_destination_and_not_committed(self):
        self.conn.execute("INSERT INTO articles VALUES(99,1,'FICTIONAL_UNCOMMITTED')")
        path = self.root / "refused.sqlite"
        with self.assertRaisesRegex(EvidenceContractError, "^backup_source_transaction$"):
            capture_backup(self.conn, path)
        self.assertTrue(self.conn.in_transaction)
        self.assertFalse(path.exists())
        self.conn.rollback()

    def test_deadline_progress_refusal_removes_exclusive_artifact(self):
        path = self.root / "deadline.sqlite"
        with patch("core.evidence_snapshot.time.monotonic", side_effect=[1.0, 3.0]):
            with self.assertRaisesRegex(EvidenceContractError, "^backup_timeout$"):
                capture_backup(self.conn, path, timeout_seconds=1)
        self.assertFalse(path.exists())
        self.assertEqual(self.conn.execute("SELECT count(*) FROM articles").fetchone()[0], 1)

    def test_concurrent_wal_writer_and_truncate_have_no_torn_snapshot(self):
        started = threading.Event()
        errors = []
        def writer():
            c = sqlite3.connect(str(self.source))
            try:
                started.set()
                for n in range(20):
                    c.executemany("INSERT INTO articles VALUES(?,1,'FICTIONAL_PAIR')",
                                  [(200 + n * 2,), (201 + n * 2,)])
                    c.commit()
                    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                c.close()
        worker = threading.Thread(target=writer); worker.start(); started.wait(5)
        for n in range(5):
            path = self.root / ("concurrent-%d.sqlite" % n)
            capture_backup(self.conn, path)
            with sqlite3.connect(str(path)) as c:
                ids = [r[0] for r in c.execute("SELECT id FROM articles ORDER BY id")]
            self.assertIn(42, ids)
            self.assertEqual((len(ids) - 1) % 2, 0)
            self.assertEqual(ids[1:], list(range(200, 200 + len(ids) - 1)))
        worker.join(10)
        self.assertFalse(worker.is_alive()); self.assertEqual(errors, [])

    def test_uncommitted_writes_not_in_capture(self):
        self.conn.execute("INSERT INTO articles VALUES(100,1,'UNCOMMITTED_FAKE')")
        other = sqlite3.connect(str(self.source))
        try:
            p = self.root / "uncommitted.sqlite"
            capture_backup(other, p)
            with sqlite3.connect(str(p)) as snap:
                self.assertEqual(snap.execute("SELECT count(*) FROM articles").fetchone()[0], 1)
        finally:
            other.close()
            self.conn.rollback()

    def test_original_database_and_wal_not_changed_by_capture(self):
        # SQLite shared-memory -shm is mutable coordination state.
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.glob("fictional.sqlite*")
                  if not p.name.endswith("-shm")}
        self.make()
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.glob("fictional.sqlite*")
                 if not p.name.endswith("-shm")}
        self.assertEqual(before, after)

    def test_deterministic_manifest(self):
        p, first = self.make()
        p2 = self.root / "copy-two.sqlite"
        capture_backup(self.conn, p2)
        second = manifest_for_backup(p2, run_id="fake-run-001", stage="collected")
        self.assertEqual(first, second)
        self.assertEqual(digest_file(p), digest_file(p2))

    def test_parent_and_stage_are_distinct(self):
        _, first = self.make()
        p2 = self.root / "stage-two.sqlite"
        capture_backup(self.conn, p2)
        second = manifest_for_backup(p2, run_id="fake-run-002", stage="analyzed",
                                     parent=first["generation"])
        self.assertNotEqual(first["generation"], second["generation"])
        self.assertEqual(second["parent"], first["generation"])

    def test_backup_integrity(self):
        _, m = self.make()
        self.assertEqual(m["sqlite_user_version"], 0)
        self.assertEqual(m["article_count"], 1)

    def test_corrupted_capture_rejected(self):
        path, m = self.make()
        path.write_bytes(path.read_bytes() + b"tampering")
        with self.assertRaisesRegex(EvidenceContractError, "snapshot_digest_mismatch"):
            verify_snapshot(path, m)

    def test_manifest_generation_tamper_rejected(self):
        _, m = self.make()
        m["max_article_id"] = 43
        with self.assertRaisesRegex(EvidenceContractError, "generation_mismatch"):
            validate_manifest(m)

    def test_manifest_field_injection_rejected(self):
        _, m = self.make()
        m["source_text"] = "SYNTHETIC_SECRET_DATA_9855"
        with self.assertRaisesRegex(EvidenceContractError, "manifest_fields"):
            validate_manifest(m)

    def test_invalid_parent_rejected(self):
        p, _ = self.make()
        with self.assertRaisesRegex(EvidenceContractError, "parent_format"):
            manifest_for_backup(p, run_id="fake-run-002", stage="collected", parent="bad")

    def test_invalid_run_id_rejected_without_echo(self):
        p, _ = self.make()
        with self.assertRaises(EvidenceContractError) as cm:
            manifest_for_backup(p, run_id="SYNTHETIC_SECRET_DATA_9855/", stage="collected")
        self.assertNotIn("SYNTHETIC_SECRET_DATA_9855", str(cm.exception))

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(EvidenceContractError, "manifest_parse_invalid"):
            parse_manifest(b'{"schema":"a","schema":"b"}')
        with self.assertRaisesRegex(EvidenceContractError, "ref_parse_invalid"):
            parse_ref(b'{"schema":"a","schema":"b"}')

    def test_missing_articles_table_blocks(self):
        empty = sqlite3.connect(":memory:")
        try:
            with self.assertRaisesRegex(EvidenceContractError, "articles_id_missing"):
                inspect_database(empty)
        finally:
            empty.close()

    def test_zero_articles_id_rejected(self):
        self.conn.execute("INSERT INTO articles VALUES(0,1,'FAKE')")
        self.conn.commit()
        p = self.root / "invalid.sqlite"
        with self.assertRaisesRegex(EvidenceContractError, "backup_failed"):
            capture_backup(self.conn, p)
        self.assertFalse(p.exists())

    def test_missing_parent_dir_rejected(self):
        with self.assertRaisesRegex(EvidenceContractError, "backup_parent_invalid"):
            capture_backup(self.conn, self.root / "absent" / "file.sqlite")

    def test_never_overwrite_destination(self):
        p, _ = self.make()
        before = digest_file(p)
        with self.assertRaisesRegex(EvidenceContractError, "backup_target_exists"):
            capture_backup(self.conn, p)
        self.assertEqual(digest_file(p), before)

    def test_no_prose_in_manifest(self):
        _, m = self.make()
        for secret in ("SYNTHETIC_SECRET_DATA_9855", "source_text"):
            self.assertNotIn(secret, canonical_bytes(m).decode())

    def test_empty_corpus_allowed(self):
        self.conn.execute("DELETE FROM articles")
        self.conn.commit()
        _, m = self.make()
        self.assertEqual(m["article_count"], 0)
        self.assertEqual(m["max_article_id"], 0)

    def test_frozen_snapshot_verification_never_creates_sidecars(self):
        path, manifest = self.make()
        verify_snapshot(path, manifest)
        self.assertFalse(Path(str(path) + "-wal").exists())
        self.assertFalse(Path(str(path) + "-shm").exists())

    def test_snapshot_with_sidecars_is_not_treated_as_immutable(self):
        path, manifest = self.make()
        Path(str(path) + "-wal").write_bytes(b"fictional sidecar")
        with self.assertRaisesRegex(EvidenceContractError, "snapshot_not_standalone"):
            verify_snapshot(path, manifest)
        with self.assertRaisesRegex(EvidenceContractError, "snapshot_not_standalone"):
            manifest_for_backup(path, run_id="fake-run", stage="collected")


if __name__ == "__main__":
    unittest.main()
