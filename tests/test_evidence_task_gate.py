"""The C2-E stage runner cannot call a model; it only proves intent ordering."""
from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from core.collection.contract import SourceRunResult
from core.evidence_snapshot import EvidenceContractError, digest_file
from core.manifests import DESKS_DIR
from processing.metadata import normalize_article
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_manifest_policy import FictionalManifestSourcePolicy
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)
from storage.evidence_source_plan import FictionalSourcePlan
from storage.evidence_task_gate import FictionalAnalysisTaskGate
from tests.custody_fixtures import initialize_application

USAGE = {
    "input_tokens": 12, "output_tokens": 9,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
}


class FictionalTaskOrderContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ipr-custody-task-gate-")
        self.addCleanup(temp.cleanup)
        self.store = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.store)
        self.session = RehearsalCustodySession(
            self.coordinator, temp.name, run_id="fictional-c2-task-1",
            logical_date="2026-10-10", enabled=True)
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        with self.session.application():
            self.native = db.start_scrape_run()
        self.policy = FictionalManifestSourcePolicy(
            FictionalSourcePlan(self.session))
        self.gate = FictionalAnalysisTaskGate(self.policy)
        self.digest = digest_file(Path(DESKS_DIR) / "china" / "manifest.json")

    def assert_code(self, code, fn):
        with self.assertRaises(EvidenceContractError) as error:
            fn()
        self.assertEqual(str(error.exception), code)

    def collect(self):
        self.policy.freeze("china", self.digest)
        # db.init_db() seeds pla_daily; reuse the native source row.
        original = normalize_article({
            "source_slug": "pla_daily",
            "url": "https://fixture.invalid/c2task/1",
            "title_original": "Fictional record",
            "text_original": "CUSTODY_SYNTHETIC_BODY_NOT_REAL_EVIDENCE",
            "published_date": "2026-10-10",
        })
        with self.session.application():
            self.aid = db.insert_article(original, self.native)
            self.assertIsNotNone(self.aid)
            for slug in self.policy.load()["sources"]:
                if slug == "pla_daily":
                    result = SourceRunResult(
                        source_slug=slug, desk_id="china", status="ok",
                        references_discovered=1, fetched=1, extracted=1,
                        new_documents=1)
                else:
                    result = SourceRunResult(
                        source_slug=slug, desk_id="china",
                        status="ok_no_publications")
                db.record_source_run_result(self.native, result)
        self.collected = self.policy.seal_collection()
        return self.aid

    def relevance_measured(self, aid):
        self.gate.reserve(aid, "relevance", "fictional-model")
        self.gate.record_fictional_outcome(
            aid, "relevance", state="measured", usage=USAGE)

    def pass_relevance(self, aid):
        with self.session.application():
            db.update_relevance(aid, 0.9, "fictional review", True)

    def translation_measured(self, aid):
        self.gate.reserve(aid, "translation", "fictional-model")
        self.gate.record_fictional_outcome(
            aid, "translation", state="measured", usage=USAGE)

    def test_no_provider_intent_before_collected_durability(self):
        self.policy.freeze("china", self.digest)
        self.assert_code("c2_collection_not_durable", lambda:
            self.gate.reserve(1, "relevance", "fictional-model"))

    def test_measured_usage_does_not_equal_passed_relevance(self):
        aid = self.collect()
        first = self.gate.reserve(aid, "relevance", "fictional-model")
        self.assertFalse(first["provider_call_executed"])
        self.assertFalse(first["eligible_for_publication"])
        self.assertFalse(first["automatic_retry_authorized"])
        self.gate.record_fictional_outcome(
            aid, "relevance", state="measured", usage=USAGE)
        self.assert_code("c2_task_relevance_not_passed", lambda:
            self.gate.reserve(aid, "translation", "fictional-model"))
        self.pass_relevance(aid)
        self.assertEqual(self.gate.reserve(
            aid, "translation", "fictional-model")["state"],
            "reserved_spend_unknown")

    def test_unknown_relevance_charge_blocks_next_task_and_retry(self):
        aid = self.collect()
        self.gate.reserve(aid, "relevance", "fictional-model")
        self.gate.record_fictional_outcome(
            aid, "relevance", state="unknown")
        self.pass_relevance(aid)
        self.assert_code("c2_task_prior_spend_unreconciled", lambda:
            self.gate.reserve(aid, "translation", "fictional-model"))
        self.assert_code("c2_spend_attempt_already_reserved", lambda:
            self.gate.reserve(aid, "relevance", "fictional-model"))

    def test_summary_and_categories_require_measured_translation(self):
        aid = self.collect()
        self.relevance_measured(aid)
        self.pass_relevance(aid)
        self.assert_code("c2_task_prior_spend_unreconciled", lambda:
            self.gate.reserve(aid, "summary", "fictional-model"))
        self.gate.reserve(aid, "translation", "fictional-model")
        self.assert_code("c2_task_prior_spend_unreconciled", lambda:
            self.gate.reserve(aid, "categorization", "fictional-model"))
        self.gate.record_fictional_outcome(
            aid, "translation", state="unknown")
        self.assert_code("c2_task_prior_spend_unreconciled", lambda:
            self.gate.reserve(aid, "summary", "fictional-model"))

    def test_parallel_summary_and_category_each_receive_unique_spend_intent(self):
        aid = self.collect()
        self.relevance_measured(aid)
        self.pass_relevance(aid)
        self.translation_measured(aid)

        def reserve(task):
            # Worker has NO inherited ContextVar. The explicit session plus
            # C2 gate creates fresh, validated native DB binding for each call.
            return self.gate.reserve(aid, task, "fictional-model")

        with ThreadPoolExecutor(max_workers=2) as workers:
            receipts = list(workers.map(
                reserve, ("summary", "categorization")))
        self.assertEqual({x["task"] for x in receipts},
                         {"summary", "categorization"})
        self.assertEqual(len({x["intent_id"] for x in receipts}), 2)
        self.assertTrue(all(x["provider_call_executed"] is False
                            for x in receipts))
        self.assertEqual(self.gate.inspect(
            aid, "summary")["state"], "spend_unknown")
        self.assertEqual(self.gate.inspect(
            aid, "categorization")["state"], "spend_unknown")
        self.assert_code("c2_spend_attempt_already_reserved", lambda:
            self.gate.reserve(aid, "summary", "fictional-model"))

    def test_collection_tamper_blocks_all_subsequent_model_intents(self):
        aid = self.collect()
        with self.session.application(), db.get_conn() as conn:
            conn.execute(
                "UPDATE source_run_results SET status='listing_failure',"
                "is_failure=1 WHERE scrape_run_id=? AND source_slug='pla_daily'",
                (self.native,))
        self.assert_code("c2_working_copy_diverged", lambda:
            self.gate.reserve(aid, "relevance", "fictional-model"))

    def test_real_pipeline_private_execution_still_rejected(self):
        import pipeline
        aid = self.collect()
        with self.session.application():
            self.assert_code("custody_pipeline_not_integrated", lambda:
                pipeline.run(["pla_daily"], date(2026, 10, 10)))
        self.assertEqual(self.gate.inspect(aid, "relevance")["state"],
                         "not_reserved")

    def test_invalid_task_and_unknown_article_fail_closed(self):
        aid = self.collect()
        self.assert_code("c2_task_identity_invalid", lambda:
            self.gate.reserve(aid, "email", "fictional-model"))
        self.assert_code("c2_spend_article_not_dispatchable", lambda:
            self.gate.reserve(999999, "relevance", "fictional-model"))


if __name__ == "__main__":
    unittest.main()
