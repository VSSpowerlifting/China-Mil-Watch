"""Read-only accounting inventory for the disabled native C2 fixture."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.collection.contract import SourceRunResult
from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_file,
)
from core.manifests import DESKS_DIR
from processing.metadata import normalize_article
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_manifest_policy import FictionalManifestSourcePolicy
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)
from storage.evidence_source_plan import FictionalSourcePlan
from storage.evidence_spend_inventory import FictionalSpendRecoveryInventory
from storage.evidence_task_gate import FictionalAnalysisTaskGate
from tests.custody_fixtures import initialize_application

USAGE = {
    "input_tokens": 12, "output_tokens": 8,
    "cache_read_input_tokens": 0,
    "cache_creation_input_tokens": 0,
}


class FictionalRecoveryInventoryContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ipr-custody-recovery-")
        self.addCleanup(temp.cleanup)
        self.store = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.store)
        self.session = RehearsalCustodySession(
            self.coordinator, temp.name, run_id="fictional-inventory-1",
            logical_date="2026-10-10", enabled=True)
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        with self.session.application():
            self.native = db.start_scrape_run()
        self.policy = FictionalManifestSourcePolicy(
            FictionalSourcePlan(self.session))
        self.digest = digest_file(Path(DESKS_DIR) / "china" / "manifest.json")
        self.inventory = FictionalSpendRecoveryInventory(self.policy)
        self.gate = FictionalAnalysisTaskGate(self.policy)

    def assert_code(self, code, fn):
        with self.assertRaises(EvidenceContractError) as captured:
            fn()
        self.assertEqual(str(captured.exception), code)

    def seal(self):
        self.policy.freeze("china", self.digest)
        # db.init_db() seeds pla_daily; reuse the native source row.
        article = normalize_article({
            "source_slug": "pla_daily",
            "url": "https://fixture.invalid/recovery/1",
            "title_original": "Not real",
            "text_original": "CUSTODY_SYNTHETIC_PRIVATE_REHEARSAL",
            "published_date": "2026-10-10",
        })
        with self.session.application():
            aid = db.insert_article(article, self.native)
            self.assertIsNotNone(aid)
            for slug in self.policy.load()["sources"]:
                result = (SourceRunResult(
                    source_slug=slug, desk_id="china", status="ok",
                    references_discovered=1, fetched=1, extracted=1,
                    new_documents=1) if slug == "pla_daily"
                    else SourceRunResult(
                        source_slug=slug, desk_id="china",
                        status="ok_no_publications"))
                db.record_source_run_result(self.native, result)
        self.policy.seal_collection()
        return aid

    def test_missing_collected_checkpoint_refuses_inventory(self):
        self.policy.freeze("china", self.digest)
        self.assert_code("c2_collection_not_durable", self.inventory.audit)

    def test_unreserved_not_a_claim_of_analysis_completion(self):
        aid = self.seal()
        report = self.inventory.audit()
        self.assertEqual(report["article_count"], 1)
        self.assertEqual(report["expected_task_slots"], 4)
        self.assertEqual(report["unreserved_task_slots"], 4)
        self.assertEqual(report["unknown_charge_attempts"], 0)
        self.assertFalse(report["analyzed_checkpoint_authorized"])
        self.assertFalse(report["all_analysis_tasks_complete"])
        self.assertFalse(report["eligible_for_publication"])
        self.assertFalse(report["billing_provider_attested"])
        self.assertEqual(report["reported_fictional_tokens"]["input_tokens"], 0)

    def test_unknown_relevance_exposes_charge_ambiguity_without_text(self):
        aid = self.seal()
        self.gate.reserve(aid, "relevance", "fictional-model")
        report = self.inventory.audit()
        self.assertEqual(report["unknown_charge_attempts"], 1)
        self.assertEqual(report["unreserved_task_slots"], 3)
        self.assertEqual(report["measured_fictional_attempts"], 0)
        self.assert_code("c2_inventory_unknown_charge",
                         self.inventory.require_no_unknown)
        encoded = str(report)
        for private in ("CUSTODY_SYNTHETIC_PRIVATE", "fixture.invalid",
                        "Not real", "pla_daily"):
            self.assertNotIn(private, encoded)
        self.assertFalse(report["automatic_retry_authorized"])

    def test_measured_fictional_tokens_are_aggregated_but_not_attested(self):
        aid = self.seal()
        self.gate.reserve(aid, "relevance", "fictional-model")
        self.gate.record_fictional_outcome(
            aid, "relevance", state="measured", usage=USAGE)
        report = self.inventory.require_no_unknown()
        self.assertEqual(report["measured_fictional_attempts"], 1)
        self.assertEqual(report["unreserved_task_slots"], 3)
        self.assertEqual(report["reported_fictional_tokens"], USAGE)
        self.assertFalse(report["analyzed_checkpoint_authorized"])

    def test_ambiguous_lost_ack_must_not_be_counted_as_zero_spend(self):
        aid = self.seal()
        self.store.fail_next("put_new", after_write=True)
        self.assert_code("synthetic_storage_unavailable", lambda:
            self.gate.reserve(aid, "relevance", "fictional-model"))
        report = self.inventory.audit()
        self.assertEqual(report["unknown_charge_attempts"], 1)
        self.assert_code("c2_inventory_unknown_charge",
                         self.inventory.require_no_unknown)
        self.gate.record_fictional_outcome(
            aid, "relevance", state="measured", usage=USAGE)
        self.assertEqual(
            self.inventory.require_no_unknown()["measured_fictional_attempts"],
            1)

    def test_source_record_tampering_fails_before_scan(self):
        aid = self.seal()
        with self.session.application(), db.get_conn() as conn:
            conn.execute(
                "UPDATE source_run_results "
                "SET status='listing_failure',is_failure=1 "
                "WHERE scrape_run_id=? AND source_slug='pla_daily'",
                (self.native,))
        self.assert_code("c2_working_copy_diverged", self.inventory.audit)

    def test_untrusted_corrupt_fictional_usage_fails_closed(self):
        aid = self.seal()
        self.gate.reserve(aid, "relevance", "fictional-model")
        self.gate.record_fictional_outcome(
            aid, "relevance", state="measured", usage=USAGE)
        _, outcome, intent_id = self.gate.journal._keys(aid, "relevance")
        broken = {
            "schema": "ipr-fictional-analysis-spend/1",
            "kind": "outcome", "intent_id": intent_id,
            "state": "measured",
            "usage": dict(USAGE, output_tokens=-1),
        }
        self.store.damage_for_test(outcome, canonical_bytes(broken))
        self.assert_code("c2_spend_store_invalid", self.inventory.audit)

    def test_oversized_article_universe_is_never_silently_truncated(self):
        aid = self.seal()
        limited = FictionalSpendRecoveryInventory(
            self.policy, max_articles=1)
        with self.session.application(), db.get_conn() as conn:
            conn.execute(
                "INSERT INTO articles (url,content_hash,source_id,"
                "scrape_run_id,title_original,text_original,published_date) "
                "SELECT 'https://fixture.invalid/recovery/2',content_hash,"
                "source_id,scrape_run_id,title_original,text_original,"
                "published_date FROM articles WHERE id=?", (aid,))
        # C1 detects post-collected original record mutation before capacity
        # arithmetic can accidentally describe it as a complete scan.
        self.assert_code("c2_working_copy_diverged", limited.audit)

    def test_invalid_capacity_is_rejected_before_reading_state(self):
        self.assert_code("c2_inventory_limit_invalid", lambda:
            FictionalSpendRecoveryInventory(self.policy, max_articles=0))


if __name__ == "__main__":
    unittest.main()
