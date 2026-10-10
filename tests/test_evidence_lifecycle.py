"""C2-A fictional native collection barrier: no model, source fetch or deployment."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.collection.contract import SourceRunResult
from core.evidence_snapshot import EvidenceContractError
from processing.metadata import compute_content_hash
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_lifecycle import FictionalCollectionBarrier
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)
from tests.custody_fixtures import initialize_application, insert_fictional


class CollectionBarrierContracts(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="ipr-custody-c2-")
        self.addCleanup(self.scratch.cleanup)
        self.store = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.store)
        self.session = RehearsalCustodySession(
            self.coordinator, self.scratch.name, run_id="fictional-c2-1",
            logical_date="2026-10-10", enabled=True,
        )
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        self.article_id = insert_fictional(self.session.database_path)
        self.barrier = FictionalCollectionBarrier(
            self.session, ["fictional_custody"])

    def assert_code(self, code, fn):
        with self.assertRaises(EvidenceContractError) as caught:
            fn()
        self.assertEqual(str(caught.exception), code)

    def update(self, sql, args=()):
        with self.session.application(), db.get_conn() as connection:
            connection.execute(sql, args)

    def add_receipt(self, slug, status):
        with self.session.application():
            native = db.start_scrape_run()
            db.record_source_run_result(native, SourceRunResult(
                source_slug=slug, desk_id="china", status=status,
            ))

    def test_collected_receipt_is_durable_and_redacted(self):
        receipt = self.barrier.seal_collection()
        self.assertEqual(receipt["stage"], "collected")
        self.assertEqual(receipt["source_count"], 1)
        self.assertEqual(receipt["new_article_count"], 1)
        self.assertEqual(receipt["source_failure_count"], 0)
        self.assertFalse(receipt["eligible_for_publication"])
        self.assertFalse(receipt["paid_dispatch_executed"])
        self.assertTrue(receipt["source_ledger_sha256"])
        serialized = json.dumps(receipt)
        for unsafe in ("CUSTODY_PRIVATE", "fixture.invalid", "text_original"):
            self.assertNotIn(unsafe, serialized)
        current, _ = self.coordinator.current()
        self.assertEqual(current["generation"], receipt["generation"])

    def test_no_model_dispatch_before_collected_checkpoint(self):
        self.assert_code("c2_collection_not_durable",
                         self.barrier.verify_before_analysis)
        self.assertIsNone(self.coordinator.current()[0])

    def test_missing_source_receipt_blocks_checkpoint(self):
        other = FictionalCollectionBarrier(
            self.session, ["fictional_custody", "fictional_second"])
        self.assert_code("c2_source_ledger_incomplete", other.seal_collection)
        self.assertIsNone(self.coordinator.current()[0])

    def test_failed_source_outcome_is_preserved_not_silence(self):
        self.add_receipt("fictional_outage", "listing_failure")
        barrier = FictionalCollectionBarrier(
            self.session, ["fictional_custody", "fictional_outage"])
        report = barrier.seal_collection()
        self.assertEqual(report["source_count"], 2)
        self.assertEqual(report["source_failure_count"], 1)
        self.assertTrue(barrier.verify_before_analysis()[
            "analysis_dispatch_eligible_fictional_only"])

    def test_known_empty_outcome_is_not_failure(self):
        self.add_receipt("fictional_empty", "ok_no_publications")
        barrier = FictionalCollectionBarrier(
            self.session, ["fictional_custody", "fictional_empty"])
        self.assertEqual(barrier.seal_collection()["source_failure_count"], 0)

    def test_invalid_status_and_flag_cannot_be_sealed(self):
        self.update("UPDATE source_run_results SET status='unknown_status'")
        self.assert_code("c2_source_status_invalid", self.barrier.seal_collection)
        self.update("UPDATE source_run_results "
                    "SET status='listing_failure',is_failure=0")
        self.assert_code("c2_source_status_invalid", self.barrier.seal_collection)

    def test_invalid_counters_cannot_be_sealed(self):
        self.update("UPDATE source_run_results SET new_documents=-1")
        self.assert_code("c2_source_counters_invalid", self.barrier.seal_collection)

    def test_unattributed_extra_native_row_blocks(self):
        # An article attributed to the same run but a different source must
        # not pass by simply omitting that source from expected_sources.
        with self.session.application(), db.get_conn() as connection:
            connection.execute(
                "INSERT INTO sources(slug,display_name,base_url,language,desk_id)"
                "VALUES('fictional_other','Other fixture',"
                "'https://fixture.invalid/other','en','china')")
            native = db.start_scrape_run()
            other_id = connection.execute(
                "SELECT id FROM sources WHERE slug='fictional_other'"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO articles("
                "url,content_hash,source_id,scrape_run_id,"
                "title_original,text_original,published_date) "
                "VALUES(?,?,?,?,?,?,?)",
                ("https://fixture.invalid/other/1",
                 compute_content_hash("Other", "Fictional text"),
                 other_id, native, "Other", "Fictional text", "2026-10-10"),
            )
        self.assert_code("c2_collection_attribution_invalid",
                         self.barrier.seal_collection)

    def test_mutated_source_receipt_after_seal_blocks_paid_gate(self):
        self.barrier.seal_collection()
        self.update(
            "UPDATE source_run_results SET status='ok_all_duplicates'")
        self.assert_code("c2_working_copy_diverged",
                         self.barrier.verify_before_analysis)

    def test_changed_original_after_seal_blocks_paid_gate(self):
        self.barrier.seal_collection()
        title, original = "Changed fictional title", "changed fictional body"
        self.update(
            "UPDATE articles SET title_original=?,text_original=?,"
            "content_hash=? WHERE id=?",
            (title, original, compute_content_hash(title, original),
             self.article_id),
        )
        self.assert_code("c2_working_copy_diverged",
                         self.barrier.verify_before_analysis)

    def test_analysis_changes_allowed_and_second_generation_durable(self):
        first = self.barrier.seal_collection()
        with self.session.application():
            db.update_relevance(
                self.article_id, 0.8, "fictional relevance", True)
            db.update_analysis(
                self.article_id, "Fictional title", "Fictional translation",
                "Fictional summary", False, None, [],
                "fixture-model", "fixture-v1",
            )
        self.assertTrue(self.barrier.verify_before_analysis()[
            "analysis_dispatch_eligible_fictional_only"])
        second = self.barrier.seal_analysis()
        self.assertEqual(second["collected_generation"], first["generation"])
        self.assertNotEqual(second["analyzed_generation"], first["generation"])
        self.assertFalse(second["usage_receipt_durable"])
        self.assert_code("c2_collection_not_durable",
                         self.barrier.verify_before_analysis)

    def test_lost_checkpoint_ack_requires_explicit_restart(self):
        self.store.fail_next("cas", after_write=True)
        self.assert_code("synthetic_storage_unavailable",
                         self.barrier.seal_collection)
        self.assert_code("c2_checkpoint_not_acknowledged",
                         self.barrier.verify_before_analysis)
        scratch = tempfile.TemporaryDirectory(prefix="ipr-custody-c2-restart-")
        self.addCleanup(scratch.cleanup)
        resumed = RehearsalCustodySession(
            self.coordinator, scratch.name, run_id=self.session.run_id,
            logical_date=self.session.logical_date, enabled=True)
        resumed.bootstrap()
        recovered = FictionalCollectionBarrier(resumed, ["fictional_custody"])
        self.assertTrue(recovered.verify_before_analysis()[
            "analysis_dispatch_eligible_fictional_only"])

    def test_duplicate_or_missing_expected_sources_refused(self):
        self.assert_code("c2_duplicate_source_request", lambda:
            FictionalCollectionBarrier(
                self.session, ["fictional_custody", "fictional_custody"]))
        self.assert_code("c2_expected_sources_invalid", lambda:
            FictionalCollectionBarrier(self.session, []))

    def test_actual_private_pipeline_still_refuses_execution(self):
        import pipeline
        with self.session.application():
            self.assert_code("custody_pipeline_not_integrated", lambda:
                pipeline.run(["fictional_custody"], date(2026, 10, 10)))
        self.assertIsNone(self.coordinator.current()[0])


if __name__ == "__main__":
    unittest.main()
