"""Native SQLite custody integration; no publisher evidence or network calls."""
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from core.evidence_snapshot import EvidenceContractError, digest_file
from storage import db
from storage.evidence_custody import RehearsalCustodySession, application_identity
from storage.evidence_object_protocol import EvidenceObjectCoordinator, InMemoryConditionalStore
from tests.custody_fixtures import bind_database, initialize_application, insert_fictional


class CustodyTests(unittest.TestCase):
    def setUp(self):
        self.transport = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.transport)
        self.session = self.new_session("fixture-run-1")
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        self.aid = insert_fictional(self.session.database_path)

    def new_session(self, run_id, enabled=True, coordinator=None):
        temp = tempfile.TemporaryDirectory(prefix="ipr-custody-test-")
        self.addCleanup(temp.cleanup)
        return RehearsalCustodySession(coordinator or self.coordinator, temp.name,
                                      run_id=run_id, enabled=enabled)

    def execute(self, sql, values=()):
        with bind_database(self.session.database_path), db.get_conn() as c:
            c.execute(sql, values)

    def collect(self):
        return self.session.checkpoint("collected")

    def assert_code(self, code, call):
        with self.assertRaises(EvidenceContractError) as caught:
            call()
        self.assertEqual(str(caught.exception), code)

    def test_disabled_by_default(self):
        self.assert_code("custody_disabled", lambda: self.new_session("fake", False))

    def test_invalid_run_identity_redacted(self):
        self.assert_code("custody_run_id_invalid", lambda: self.new_session("PRIVATE_BODY/"))

    def test_repository_root_rejected_before_database_read(self):
        with patch("storage.evidence_custody.sqlite3.connect") as connect:
            self.assert_code("custody_scratch_required", lambda:
                RehearsalCustodySession(self.coordinator, Path(__file__).parents[1],
                                        run_id="fake", enabled=True))
            connect.assert_not_called()

    def test_empty_pointer_is_not_automatic_bootstrap(self):
        other = self.new_session("fake")
        self.assert_code("custody_current_required", other.bootstrap)
        self.assertFalse(other.database_path.exists())

    def test_bootstrap_never_clobbers_database(self):
        before = digest_file(self.session.database_path)
        self.assert_code("custody_bootstrap_target_exists", self.session.bootstrap)
        self.assertEqual(before, digest_file(self.session.database_path))

    def test_startup_store_outage_no_database(self):
        other = self.new_session("fake")
        self.transport.fail_next("get")
        self.assert_code("synthetic_storage_unavailable", other.bootstrap)
        self.assertFalse(other.database_path.exists())

    def test_real_storage_insert_and_verified_restore(self):
        collected = self.collect()
        restored = self.new_session("fixture-run-2")
        restored.bootstrap()
        with bind_database(restored.database_path):
            pending = db.get_articles_unscored()
            self.assertEqual([r["id"] for r in pending], [self.aid])
            self.assertEqual(pending[0]["text_original"], "CUSTODY_PRIVATE_SYNTHETIC_BODY_1")
            self.assert_code("custody_migration_disabled", db.init_db)
        self.assertEqual(self.coordinator.current()[0]["generation"], collected["generation"])

    def test_analysis_can_update_native_rows_and_preserve_originals(self):
        collected = self.collect()
        with bind_database(self.session.database_path):
            db.update_relevance(self.aid, 0.8, "fictional model reasoning", True)
            db.update_analysis(self.aid, "Fictional model title", "Fictional translation",
                               "Fictional summary", False, None, [], "fake-model", "fixture-v1")
        analyzed = self.session.checkpoint("analyzed")
        self.assertEqual(collected["preserved_rows_sha256"], analyzed["preserved_rows_sha256"])
        restored = self.new_session("fixture-run-2")
        restored.bootstrap()
        with bind_database(restored.database_path):
            self.assertEqual(db.get_total_analyzed_count(), 1)
            self.assertEqual(db.get_articles_pending_analysis(), [])

    def test_analysis_requires_collection(self):
        self.assert_code("custody_collection_required", lambda: self.session.checkpoint("analyzed"))

    def test_checkpoint_requires_startup(self):
        self.assert_code("custody_startup_required", lambda: self.new_session("fake").checkpoint("collected"))

    def test_unsupported_stage_redacted(self):
        self.assert_code("custody_stage_invalid", lambda: self.session.checkpoint("PRIVATE_BODY"))

    def test_same_payload_retry_is_idempotent(self):
        first = self.collect()
        second = self.collect()
        self.assertEqual(first["generation"], second["generation"])
        self.assertFalse(second["advanced"])

    def test_conflicting_run_stage_payload_rejected(self):
        first = self.collect()
        insert_fictional(self.session.database_path, 2)
        self.assert_code("object_readback_mismatch", self.collect)
        self.assertEqual(self.coordinator.current()[0]["generation"], first["generation"])

    def test_lost_upload_ack_retry_reconciles(self):
        self.transport.fail_next("put_new", after_write=True)
        self.assert_code("synthetic_storage_unavailable", self.collect)
        self.assertIsNone(self.coordinator.current()[0])
        self.assertTrue(self.collect()["advanced"])

    def test_lost_pointer_ack_retry_reconciles(self):
        self.transport.fail_next("cas", after_write=True)
        self.assert_code("synthetic_storage_unavailable", self.collect)
        first = self.coordinator.current()[0]
        retry = self.collect()
        self.assertEqual(retry["generation"], first["generation"])
        self.assertFalse(retry["advanced"])

    def test_failed_analysis_upload_preserves_collection(self):
        first = self.collect()
        self.execute("UPDATE articles SET relevance_score=0.7 WHERE id=?", (self.aid,))
        self.transport.fail_next("put_new")
        self.assert_code("synthetic_storage_unavailable", lambda: self.session.checkpoint("analyzed"))
        self.assertEqual(self.coordinator.current()[0]["generation"], first["generation"])

    def test_two_writers_with_shared_parent_only_one_advances(self):
        first = self.collect()
        writers = [self.new_session("fixture-run-%d" % n) for n in (2,3)]
        for n, writer in enumerate(writers, 2):
            writer.bootstrap()
            insert_fictional(writer.database_path, n)
        results = []
        barrier = threading.Barrier(2)
        def write(session):
            barrier.wait()
            try:
                results.append(session.checkpoint("collected"))
            except EvidenceContractError as exc:
                results.append(str(exc))
        threads = [threading.Thread(target=write, args=(s,)) for s in writers]
        for t in threads: t.start()
        for t in threads: t.join(10)
        self.assertTrue(all(not t.is_alive() for t in threads))
        self.assertEqual(sum(isinstance(r, dict) for r in results), 1)
        self.assertIn(next(r for r in results if isinstance(r, str)),
                      ("stale_generation", "concurrent_pointer_update"))
        self.assertNotEqual(self.coordinator.current()[0]["generation"], first["generation"])

    def test_same_count_max_id_cannot_hide_record_replacement(self):
        insert_fictional(self.session.database_path, 2)
        self.collect()
        other = self.new_session("fixture-run-2")
        other.bootstrap()
        with other.application():
            db.start_scrape_run()
        with bind_database(other.database_path), db.get_conn() as c:
            c.execute("UPDATE articles SET id=3 WHERE id=1")
        self.assert_code("custody_records_removed", lambda: other.checkpoint("collected"))

    def test_analyzed_stage_rejects_new_record_ids(self):
        self.collect()
        insert_fictional(self.session.database_path, 2)
        self.assert_code("custody_analysis_identity_changed", lambda: self.session.checkpoint("analyzed"))

    def test_changed_original_rejected_even_with_new_correct_hash(self):
        self.collect()
        from processing.metadata import compute_content_hash
        title, body = "Fictional replacement", "PRIVATE_SYNTHETIC_REPLACEMENT"
        self.execute("UPDATE articles SET title_original=?,text_original=?,content_hash=? WHERE id=?",
                     (title, body, compute_content_hash(title, body), self.aid))
        self.assert_code("custody_preserved_record_changed", lambda: self.session.checkpoint("analyzed"))

    def test_missing_or_wrong_content_hash_blocks_checkpoint(self):
        self.execute("UPDATE articles SET content_hash='' WHERE id=?", (self.aid,))
        self.assert_code("custody_source_hash_mismatch", self.collect)
        self.assertIsNone(self.coordinator.current()[0])

    def test_changed_source_identity_blocks_analysis(self):
        self.collect()
        self.execute("UPDATE sources SET base_url='https://other-fixture.invalid/' WHERE slug='fictional_custody'")
        self.assert_code("custody_preserved_record_changed", lambda: self.session.checkpoint("analyzed"))

    def test_missing_desk_identity_blocks(self):
        self.execute("UPDATE sources SET desk_id=NULL WHERE slug='fictional_custody'")
        self.assert_code("custody_source_identity_missing", self.collect)

    def test_unknown_migration_blocks_without_modifying_db(self):
        self.execute("INSERT INTO schema_migrations(version,name,checksum) VALUES('9999','fictional','bad')")
        before = digest_file(self.session.database_path)
        self.assert_code("custody_schema_incompatible", self.collect)
        self.assertEqual(before, digest_file(self.session.database_path))

    def test_changed_schema_blocks_stage(self):
        self.collect()
        self.execute("ALTER TABLE articles ADD COLUMN fictional_new_field TEXT")
        self.assert_code("custody_schema_incompatible", lambda: self.session.checkpoint("analyzed"))

    def test_migration_receipts_cannot_hide_missing_native_columns(self):
        self.execute("ALTER TABLE articles DROP COLUMN summary_english")
        self.assert_code("custody_schema_incompatible", self.collect)
        self.assertIsNone(self.coordinator.current()[0])

    def test_foreign_key_violation_blocks(self):
        c = sqlite3.connect(str(self.session.database_path))
        try:
            c.execute("UPDATE articles SET source_id=999999")
            c.commit()
        finally: c.close()
        self.assert_code("backup_failed", self.collect)

    def test_fixture_marker_missing_blocks_before_snapshot(self):
        self.execute("DROP TABLE ipr_custody_fixture")
        with patch("storage.evidence_custody.capture_backup") as backup:
            self.assert_code("custody_fictional_required", self.collect)
            backup.assert_not_called()

    def test_readonly_snapshot_handles_uri_characters(self):
        self.collect()
        target = self.session.root / "restore?#.sqlite"
        self.session.restore(target)
        self.assertTrue(target.is_file())

    def test_uncommitted_application_data_excluded(self):
        connection = sqlite3.connect(str(self.session.database_path))
        try:
            connection.execute("UPDATE articles SET summary_english='FICTIONAL_UNCOMMITTED'")
            first = self.collect()
            target = self.session.root / "committed.sqlite"
            self.session.restore(target, first["generation"])
            with sqlite3.connect(str(target)) as c:
                self.assertIsNone(c.execute("SELECT summary_english FROM articles").fetchone()[0])
        finally:
            connection.rollback()
            connection.close()

    def test_historical_restore_does_not_advance_pointer(self):
        first = self.collect()
        self.execute("UPDATE articles SET summary_english='Fictional model output'")
        second = self.session.checkpoint("analyzed")
        self.session.restore(self.session.root / "history.sqlite", first["generation"])
        self.assertEqual(self.coordinator.current()[0]["generation"], second["generation"])

    def test_restore_refuses_sidecars_and_existing_targets(self):
        self.collect()
        target = self.session.root / "restore.sqlite"
        Path(str(target) + "-wal").write_bytes(b"fictional sidecar")
        self.assert_code("custody_restore_sidecar_exists", lambda: self.session.restore(target))
        self.assertFalse(target.exists())

    def test_same_run_restarts_from_collected_checkpoint(self):
        first = self.collect()
        restarted = self.new_session(self.session.run_id)
        restarted.bootstrap()
        analyzed = restarted.checkpoint("analyzed")
        self.assertNotEqual(first["generation"], analyzed["generation"])

    def test_finished_run_restart_is_readonly_and_reconciles_ack(self):
        self.collect()
        self.session.checkpoint("analyzed")
        restarted = self.new_session(self.session.run_id)
        self.assertTrue(restarted.bootstrap()["completed"])
        self.assertFalse(restarted.checkpoint("analyzed")["advanced"])
        self.assert_code("custody_run_already_analyzed", lambda: restarted.checkpoint("collected"))
        with restarted.application(), db.get_conn() as c:
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("DELETE FROM articles")

    def test_corrupted_active_snapshot_blocks_bootstrap(self):
        self.collect()
        active, _ = self.coordinator.current()
        manifest, _, _ = self.coordinator._registered(active["generation"])
        self.transport.damage_for_test(self.coordinator._snapshot_key(manifest["snapshot_sha256"]), b"fictional corruption")
        other = self.new_session("fixture-run-2")
        self.assert_code("snapshot_object_corrupt", other.bootstrap)
        self.assertFalse(other.database_path.exists())

    def test_reports_do_not_serialize_originals_or_source_fields(self):
        payload = json.dumps(self.collect(), sort_keys=True)
        for forbidden in ("CUSTODY_PRIVATE", "title_original", "text_original", "fixture.invalid"):
            self.assertNotIn(forbidden, payload)
        self.assertFalse(json.loads(payload)["eligible_for_publication"])

    def test_mutated_binding_cannot_target_file_outside_scratch(self):
        other = self.new_session("fake")
        other._database_path = self.session.root / "other.sqlite"
        with patch("storage.evidence_custody.sqlite3.connect") as connect:
            self.assert_code("custody_database_binding", lambda: other.bootstrap(allow_empty=True))
            connect.assert_not_called()

    def test_hardlinked_working_database_rejected(self):
        import os
        alias = self.session.root / "alias.sqlite"
        os.link(self.session.database_path, alias)
        self.assert_code("custody_database_binding", self.collect)

    def test_removed_source_run_receipt_rejected(self):
        self.collect()
        self.execute("DELETE FROM source_run_results")
        self.assert_code("custody_collection_provenance_changed", lambda: self.session.checkpoint("analyzed"))

    def test_changed_run_start_rejected(self):
        self.collect()
        self.execute("UPDATE scrape_runs SET started_at='fictional replacement'")
        self.assert_code("custody_collection_provenance_changed", lambda: self.session.checkpoint("analyzed"))

    def test_run_analysis_accounting_can_close_normally(self):
        self.collect()
        with bind_database(self.session.database_path):
            db.complete_scrape_run(1, 1, 1, 0, [], status="completed")
        self.assertEqual(self.session.checkpoint("analyzed")["stage"], "analyzed")

    def test_untrusted_manifest_stage_is_rejected_at_bootstrap(self):
        from core.evidence_snapshot import capture_backup, manifest_for_backup
        for stage in ("analyzed", "rehearsal"):
            with self.subTest(stage=stage):
                coordinator = EvidenceObjectCoordinator(InMemoryConditionalStore())
                path = self.session.root / (stage + ".sqlite")
                c = sqlite3.connect(str(self.session.database_path))
                try: capture_backup(c, path)
                finally: c.close()
                manifest = manifest_for_backup(path, run_id="untrusted-fixture", stage=stage)
                coordinator.prepare(path, manifest)
                coordinator.advance(manifest["generation"])
                other = self.new_session("next-fixture", coordinator=coordinator)
                self.assert_code("custody_collection_required" if stage == "analyzed" else "custody_stage_invalid", other.bootstrap)
                self.assertFalse(other.database_path.exists())


if __name__ == "__main__":
    unittest.main()
