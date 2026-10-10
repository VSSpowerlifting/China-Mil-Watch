"""Persistent fictional recovery, process CAS and >live-size streaming fixtures."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest.mock import patch

from core.evidence_snapshot import (EvidenceContractError, capture_backup,
                                    digest_file, manifest_for_backup)
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_streaming import FictionalFileStore, StreamingEvidenceCoordinator
from tests.custody_fixtures import initialize_application, insert_fictional


class PersistentCustodyTests(unittest.TestCase):
    def setUp(self):
        self.store_root = self.temp()
        self.store = FictionalFileStore(self.store_root, enabled=True)
        self.coordinator = StreamingEvidenceCoordinator(self.store)
        self.session = self.new_session()
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        insert_fictional(self.session.database_path)

    def temp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-custody-persistent-")
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def new_session(self, run_id=None, coordinator=None):
        return RehearsalCustodySession(coordinator or self.coordinator, self.temp(),
                                      run_id=run_id, enabled=True)

    def assert_code(self, code, call):
        with self.assertRaisesRegex(EvidenceContractError, "^" + code + "$"):
            call()

    def test_reopen_transport_and_restore_actual_native_queues(self):
        first = self.session.checkpoint("collected")
        with self.session.application():
            db.update_relevance(1, 0.8, "Fictional relevance", True)
        analyzed = self.session.checkpoint("analyzed")
        fresh = StreamingEvidenceCoordinator(FictionalFileStore(self.store_root, enabled=True))
        other = self.new_session(coordinator=fresh)
        self.assertEqual(other.bootstrap()["generation"], analyzed["generation"])
        with other.application():
            self.assertEqual([r["id"] for r in db.get_articles_pending_analysis()], [1])
        historical = other.root / "historical.sqlite"
        other.restore(historical, first["generation"])
        self.assertEqual(fresh.current()[0]["generation"], analyzed["generation"])

    def test_two_executions_restore_same_native_id_without_claim_collision(self):
        self.session.checkpoint("collected")
        writers = [self.new_session(), self.new_session()]
        ids = []
        for n, writer in enumerate(writers, 2):
            writer.bootstrap()
            with writer.application():
                ids.append(db.start_scrape_run())
            insert_fictional(writer.database_path, n)
        self.assertEqual(ids, [2, 2])
        self.assertNotEqual(writers[0].run_id, writers[1].run_id)
        writers[0].checkpoint("collected")
        self.assert_code("stale_generation", lambda: writers[1].checkpoint("collected"))
        for writer in writers:
            self.assertEqual(self.coordinator.claimed_generation(writer.run_id, "collected")["run_id"],
                             writer.run_id)

    def test_descriptor_survives_recreation_and_rejects_new_identity(self):
        restarted = RehearsalCustodySession(self.coordinator, self.session.root, enabled=True)
        self.assertEqual(restarted.run_id, self.session.run_id)
        self.assert_code("custody_execution_conflict", lambda: RehearsalCustodySession(
            self.coordinator, self.session.root, enabled=True, run_id="different"))

    def test_fresh_process_restores_generation_and_native_rows(self):
        receipt = self.session.checkpoint("collected")
        root = self.temp()
        code = ("import sys,json; from storage.evidence_streaming import FictionalFileStore,StreamingEvidenceCoordinator; "
                "from storage.evidence_custody import RehearsalCustodySession; from storage import db; "
                "s=RehearsalCustodySession(StreamingEvidenceCoordinator(FictionalFileStore(sys.argv[1],enabled=True)),"
                "sys.argv[2],enabled=True); r=s.bootstrap(); "
                "print(json.dumps({'generation':r['generation'],'restored':r['restored']}))")
        result = subprocess.run([sys.executable, "-c", code, str(self.store_root), str(root)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"generation": receipt["generation"], "restored": True})
        with sqlite3.connect(str(root / "working.sqlite")) as c:
            self.assertEqual(c.execute("SELECT id FROM articles").fetchall(), [(1,)])

    def test_prepared_collection_recovery_after_crash_before_pointer(self):
        with patch.object(self.store, "cas", side_effect=EvidenceContractError("custody_store_unavailable")):
            self.assert_code("custody_store_unavailable", lambda: self.session.checkpoint("collected"))
        current, _ = self.coordinator.current()
        self.assertIsNone(current)
        fresh = self.new_session(self.session.run_id)
        self.assert_code("custody_current_required", fresh.bootstrap)
        receipt = fresh.bootstrap(recover_stage="collected")
        self.assertTrue(receipt["restored"])
        self.assertEqual(receipt["run_id"], self.session.run_id)

    def test_analyzed_lost_ack_restarts_readonly_without_repeating_work(self):
        self.session.checkpoint("collected")
        original = self.store.cas
        def lost_ack(*args):
            original(*args)
            raise EvidenceContractError("custody_store_unavailable")
        with patch.object(self.store, "cas", side_effect=lost_ack):
            self.assert_code("custody_store_unavailable", lambda: self.session.checkpoint("analyzed"))
        fresh = self.new_session(self.session.run_id)
        self.assertTrue(fresh.bootstrap()["completed"])
        self.assertFalse(fresh.checkpoint("analyzed")["advanced"])
        with fresh.application():
            self.assert_code("custody_read_only", lambda: db.insert_articles_atomic([], [], 1))

    def test_prepared_analyzed_recovery_and_stale_prepared_refusal(self):
        self.session.checkpoint("collected")
        with patch.object(self.store, "cas", side_effect=EvidenceContractError("custody_store_unavailable")):
            self.assert_code("custody_store_unavailable", lambda: self.session.checkpoint("analyzed"))
        fresh = self.new_session(self.session.run_id)
        self.assertTrue(fresh.bootstrap(recover_stage="analyzed")["completed"])
        next_run = self.new_session(); next_run.bootstrap()
        insert_fictional(next_run.database_path, 2); next_run.checkpoint("collected")
        stale = self.new_session(self.session.run_id)
        self.assert_code("stale_generation", lambda: stale.bootstrap(recover_stage="analyzed"))
        self.assertFalse(stale.database_path.exists())

    def test_initialized_missing_pointer_never_creates_fallback(self):
        self.session.checkpoint("collected")
        self.store._path(self.coordinator.REF_KEY).unlink()
        other = self.new_session()
        self.assert_code("custody_initialized_pointer_missing", lambda: other.bootstrap(allow_empty=True))
        self.assertFalse(other.database_path.exists())

    def test_corrupt_snapshot_and_pointer_fail_before_runtime_binding(self):
        receipt = self.session.checkpoint("collected")
        manifest = self.coordinator.inspect_generation(receipt["generation"])
        path = self.store._path(self.coordinator._snapshot_key(manifest["snapshot_sha256"]))
        with path.open("r+b") as stream:
            stream.seek(40); stream.write(b"FICTIONAL_CORRUPTION")
        other = self.new_session()
        self.assert_code("snapshot_digest_mismatch", other.bootstrap)
        self.assertFalse(other.database_path.exists())
        obj = self.store.get(self.coordinator.REF_KEY)
        self.store.cas(self.coordinator.REF_KEY, obj[1], b"{}")
        self.assert_code("ref_fields", other.bootstrap)

    def test_capacity_failure_keeps_verified_parent_current(self):
        receipt = self.session.checkpoint("collected")
        self.store.capacity = 1
        self.assert_code("custody_object_capacity", lambda: self.session.checkpoint("analyzed"))
        self.store.capacity = 256 * 1024 * 1024
        self.assertEqual(self.coordinator.current()[0]["generation"], receipt["generation"])

    def test_interrupted_immutable_write_leaves_parent_restorable(self):
        receipt = self.session.checkpoint("collected")
        original_link = os.link
        def interrupt_store_link(source, destination, **kwargs):
            if Path(destination).parent == self.store_root:
                raise OSError("fictional upload interruption")
            return original_link(source, destination, **kwargs)
        with patch("storage.evidence_streaming.os.link", side_effect=interrupt_store_link):
            self.assert_code("custody_store_unavailable", lambda: self.session.checkpoint("analyzed"))
        self.assertEqual(self.coordinator.current()[0]["generation"], receipt["generation"])
        self.assertFalse(list(self.store_root.glob(".object-stage-*")))
        self.session.restore(self.session.root / "prior.sqlite", receipt["generation"])

    def test_store_outage_cannot_consult_valid_public_default(self):
        receipt = self.session.checkpoint("collected")
        public = self.session.root / "fictional-public.sqlite"
        self.session.restore(public, receipt["generation"])
        before = digest_file(public)
        other = self.new_session()
        with patch.object(db, "DB_PATH", public), \
                patch.object(self.store, "get", side_effect=EvidenceContractError("custody_store_unavailable")), \
                patch("storage.evidence_custody.sqlite3.connect") as connect:
            self.assert_code("custody_store_unavailable", other.bootstrap)
            connect.assert_not_called()
        self.assertFalse(other.database_path.exists())
        self.assertEqual(digest_file(public), before)

    def test_atomic_batch_and_context_nesting_share_authority(self):
        from processing.metadata import normalize_article
        with self.session.application():
            native = db.start_scrape_run()
            article = normalize_article({"source_slug": "fictional_custody",
                       "url": "https://fixture.invalid/atomic", "title_original": "Fictional",
                       "text_original": "FICTIONAL_ATOMIC_BODY", "published_date": "2026-10-10"})
            inserted = db.insert_articles_atomic([article], [], native)
            self.assertEqual(len(inserted), 1)
            with self.session.application(read_only=True):
                self.assert_code("custody_read_only", lambda: db.insert_articles_atomic([article], [], native))
            self.assertEqual(len(db.get_articles_unscored()), 2)
        self.assertIsNone(db.current_database_context())

    def test_private_dry_run_never_initializes_or_calls_collectors(self):
        import pipeline
        with self.session.application(), patch.object(db, "init_db") as init, \
                patch.object(pipeline.CACHE_DIR.__class__, "mkdir") as mkdir:
            pipeline.run([], __import__("datetime").date(2026, 10, 10), dry_run=True)
            init.assert_not_called(); mkdir.assert_not_called()
            self.assert_code("custody_pipeline_not_integrated", lambda:
                pipeline.run([], __import__("datetime").date(2026, 10, 10)))
        self.session.database_path.unlink()
        self.assert_code("custody_working_database_missing", lambda:
            self.session.application().__enter__())
        self.assertFalse(self.session.database_path.exists())

    def test_incompatible_runtime_refuses_migration_without_parent_mutation(self):
        first = self.session.checkpoint("collected")
        with self.session.application(), db.get_conn() as c:
            c.execute("DELETE FROM schema_migrations")
        self.assert_code("custody_schema_incompatible", lambda: self.session.application().__enter__())
        other = self.new_session(); other.bootstrap()
        self.assertEqual(self.coordinator.current()[0]["generation"], first["generation"])

    def test_native_health_verifier_reads_selected_restored_database(self):
        from scripts.verify_db_current import check
        self.session.checkpoint("collected")
        other = self.new_session(); other.bootstrap()
        with other.application(read_only=True), db.get_conn() as c:
            self.assertEqual(check(c), [])
            self.assertEqual(c.execute("SELECT id FROM articles").fetchall()[0][0], 1)

    def test_new_collection_cannot_attribute_append_to_historical_run(self):
        receipt = self.session.checkpoint("collected")
        other = self.new_session(); other.bootstrap()
        insert_fictional(other.database_path, 2)
        with other.application(), db.get_conn() as c:
            c.execute("UPDATE articles SET scrape_run_id=1 WHERE id=2")
        self.assert_code("custody_collection_run_mismatch", lambda: other.checkpoint("collected"))
        self.assertEqual(self.coordinator.current()[0]["generation"], receipt["generation"])

    def test_large_native_snapshot_streaming_memory_and_restart(self):
        # ~55 MiB of fictional rows, beyond the reviewed 47,398,912-byte corpus.
        from processing.metadata import compute_content_hash
        body = "FICTIONAL_CAPACITY_" + "x" * 32768
        content_hash = compute_content_hash("Fictional capacity", body)
        with self.session.application(), db.get_conn() as c:
            source = c.execute("SELECT id FROM sources WHERE slug='fictional_custody'").fetchone()[0]
            c.executemany("INSERT INTO articles(url,content_hash,source_id,scrape_run_id,title_original,"
                          "text_original,published_date) VALUES(?,?,?,1,?,?,?)",
                          (("https://fixture.invalid/capacity/%d" % n, content_hash, source,
                            "Fictional capacity", body, "2026-10-10") for n in range(1700)))
        tracemalloc.start()
        try:
            collected = self.session.checkpoint("collected")
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        manifest = self.coordinator.inspect_generation(collected["generation"])
        self.assertGreater(manifest["snapshot_bytes"], 47_398_912)
        self.assertLess(peak, 12 * 1024 * 1024)
        other = self.new_session(); other.bootstrap()
        with other.application(), db.get_conn() as c:
            self.assertEqual(c.execute("SELECT count(*) FROM articles").fetchone()[0], 1701)
        print("Fictional capacity receipt: bytes=%d, Python checkpoint peak=%d" %
              (manifest["snapshot_bytes"], peak))


class FileTransportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-custody-transport-")
        self.addCleanup(tmp.cleanup); self.root = Path(tmp.name)
        self.store = FictionalFileStore(self.root, enabled=True)

    def test_process_cas_only_one_winner_and_revision_survives_restart(self):
        key = StreamingEvidenceCoordinator.REF_KEY
        self.assertTrue(self.store.cas(key, None, b"initial"))
        revision = self.store.get(key)[1]
        code = ("import sys; from storage.evidence_streaming import FictionalFileStore; "
                "s=FictionalFileStore(sys.argv[1],enabled=True); "
                "print(s.cas('refs/current.json',sys.argv[2],sys.argv[3].encode()))")
        workers = [subprocess.Popen([sys.executable, "-c", code, str(self.root), revision, str(n)],
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for n in range(2)]
        outputs = [w.communicate(timeout=15) for w in workers]
        self.assertTrue(all(w.returncode == 0 for w in workers), outputs)
        self.assertEqual(sorted(o[0].strip() for o in outputs), ["False", "True"])
        fresh = FictionalFileStore(self.root, enabled=True)
        self.assertNotEqual(fresh.get(key)[1], revision)
        self.assertTrue(fresh.cas(key, fresh.get(key)[1], b"initial"))
        self.assertFalse(fresh.cas(key, revision, b"stale"))

    def test_interrupted_replace_preserves_pointer_and_redacts_error(self):
        key = StreamingEvidenceCoordinator.REF_KEY
        self.store.cas(key, None, b"prior")
        prior = self.store.get(key)
        with patch("storage.evidence_streaming.os.replace", side_effect=OSError("FICTIONAL_PRIVATE_BODY")):
            with self.assertRaisesRegex(EvidenceContractError, "^custody_store_unavailable$"):
                self.store.cas(key, prior[1], b"candidate")
        self.assertEqual(self.store.get(key), prior)
        self.assertFalse(list(self.root.glob(".object-stage-*")))

    def test_lost_directory_sync_ack_is_reconciled_from_persistent_pointer(self):
        key = StreamingEvidenceCoordinator.REF_KEY
        self.store.cas(key, None, b"prior")
        revision = self.store.get(key)[1]
        with patch("storage.evidence_streaming.sync_directory", side_effect=OSError("fictional fault")):
            with self.assertRaises(EvidenceContractError):
                self.store.cas(key, revision, b"candidate")
        self.assertEqual(FictionalFileStore(self.root, enabled=True).get(key)[0], b"candidate")

    def test_immutable_collision_capacity_and_unsafe_paths(self):
        self.assertTrue(self.store.put_new("manifest", b"first"))
        self.assertFalse(self.store.put_new("manifest", b"different"))
        self.assertEqual(self.store.get("manifest")[0], b"first")
        with self.assertRaisesRegex(EvidenceContractError, "custody_metadata_capacity"):
            self.store.put_new("large", b"x" * 65537)
        path = self.store._path("link")
        path.symlink_to(self.root / "missing")
        with self.assertRaisesRegex(EvidenceContractError, "custody_object_unsafe"):
            self.store.get("link")
        with self.assertRaisesRegex(EvidenceContractError, "custody_disabled"):
            FictionalFileStore(self.root)


if __name__ == "__main__":
    unittest.main()
