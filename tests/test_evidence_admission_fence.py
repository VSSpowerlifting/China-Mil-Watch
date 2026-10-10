"""C2-G synthetic CAS admission test matrix. No real source/model execution."""
from __future__ import annotations

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.collection.contract import SourceRunResult
from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_file,
)
from core.manifests import DESKS_DIR
from processing.metadata import normalize_article
from storage import db
from storage.evidence_admission_fence import FictionalSpendAdmissionFence
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_manifest_policy import FictionalManifestSourcePolicy
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)
from storage.evidence_source_plan import FictionalSourcePlan
from tests.custody_fixtures import initialize_application

USAGE = {
    "input_tokens": 10, "output_tokens": 5,
    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
}


class FictionalCASAdmissionContracts(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ipr-custody-admission-")
        self.addCleanup(temp.cleanup)
        self.store = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.store)
        self.session = RehearsalCustodySession(
            self.coordinator, temp.name, run_id="fictional-admission-1",
            logical_date="2026-10-10", enabled=True)
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        with self.session.application():
            self.native = db.start_scrape_run()
        self.policy = FictionalManifestSourcePolicy(
            FictionalSourcePlan(self.session))
        self.fence = FictionalSpendAdmissionFence(self.policy)
        self.digest = digest_file(Path(DESKS_DIR) / "china" / "manifest.json")

    def assert_code(self, code, fn):
        with self.assertRaises(EvidenceContractError) as caught:
            fn()
        self.assertEqual(str(caught.exception), code)

    def collected(self):
        self.policy.freeze("china", self.digest)
        article = normalize_article({
            "source_slug": "pla_daily",
            "url": "https://fixture.invalid/c2-admission/1",
            "title_original": "Fictional admission rehearsal",
            "text_original": "CUSTODY_FAKE_LOCAL_NO_REAL_SOURCE",
            "published_date": "2026-10-10",
        })
        with self.session.application():
            self.article_id = db.insert_article(article, self.native)
            self.assertIsNotNone(self.article_id)
            for slug in self.policy.load()["sources"]:
                outcome = (SourceRunResult(
                    source_slug=slug, desk_id="china", status="ok",
                    references_discovered=1, fetched=1, extracted=1,
                    new_documents=1)
                    if slug == "pla_daily" else SourceRunResult(
                        source_slug=slug, desk_id="china",
                        status="ok_no_publications"))
                db.record_source_run_result(self.native, outcome)
        return self.policy.seal_collection()

    def test_requires_durable_collection_before_gate_open(self):
        self.policy.freeze("china", self.digest)
        self.assert_code("c2_collection_not_durable", self.fence.open)
        self.assertIsNone(self.store.get(self.fence.key))

    def test_relevance_reservation_then_close_stays_non_authorizing(self):
        self.collected()
        first = self.fence.open()
        self.assertEqual(first["phase"], "open")
        self.assertEqual(first["inflight"], 0)
        self.assertEqual(self.fence.open()["phase"], "open")
        reserved = self.fence.reserve(
            self.article_id, "relevance", "fictional-model")
        self.assertEqual(reserved["state"], "reserved_spend_unknown")
        self.assertFalse(reserved["provider_call_executed"])
        self.assertEqual(self.fence.status()["inflight"], 0)
        closed = self.fence.close()
        self.assertEqual(closed["phase"], "closed")
        self.assertEqual(closed["unknown_charge_attempts"], 1)
        self.assertFalse(closed["analyzed_checkpoint_authorized"])
        self.assertFalse(closed["billing_provider_attested"])
        self.assertFalse(closed["eligible_for_publication"])
        self.assert_code("c2_admission_closed", lambda:
            self.fence.reserve(self.article_id, "translation", "fictional-model"))
        self.assert_code("c2_admission_closed", self.fence.close)
        self.assert_code("c2_admission_closed", self.fence.open)

    def test_active_worker_blocks_close_until_released(self):
        self.collected()
        self.fence.open()
        started = threading.Event()
        release = threading.Event()

        def fixture_worker():
            self.fence._change(increment=1)
            started.set()
            release.wait(10)
            self.fence._change(increment=-1)

        with ThreadPoolExecutor(max_workers=1) as pool:
            done = pool.submit(fixture_worker)
            self.assertTrue(started.wait(10))
            self.assertEqual(self.fence.status()["inflight"], 1)
            self.assert_code("c2_admission_inflight", self.fence.close)
            release.set()
            done.result(timeout=10)
        self.assertEqual(self.fence.status()["inflight"], 0)
        self.assertEqual(self.fence.close()["phase"], "closed")

    def test_lost_registration_ack_leaves_sticky_inflight_blocker(self):
        self.collected()
        self.fence.open()
        self.store.fail_next("cas", after_write=True)
        self.assert_code("synthetic_storage_unavailable", lambda:
            self.fence.reserve(self.article_id, "relevance", "fictional-model"))
        self.assertEqual(self.fence.status()["inflight"], 1)
        self.assert_code("c2_admission_inflight", self.fence.close)
        self.assertEqual(self.fence.gate.inspect(
            self.article_id, "relevance")["state"], "not_reserved")
        self.assertFalse(self.fence.status()["analyzed_checkpoint_authorized"])

    def test_lost_close_ack_still_refuses_new_admissions(self):
        self.collected()
        self.fence.open()
        self.store.fail_next("cas", after_write=True)
        self.assert_code("synthetic_storage_unavailable", self.fence.close)
        self.assertEqual(self.fence.status()["phase"], "closed")
        self.assert_code("c2_admission_closed", lambda:
            self.fence.reserve(self.article_id, "relevance", "fictional-model"))

    def test_parallel_worker_spend_intents_are_separately_registered(self):
        self.collected()
        self.fence.open()
        aid = self.article_id
        self.fence.reserve(aid, "relevance", "fictional-model")
        self.fence.gate.record_fictional_outcome(
            aid, "relevance", state="measured", usage=USAGE)
        with self.session.application():
            db.update_relevance(aid, 0.9, "fictional", True)
        self.fence.reserve(aid, "translation", "fictional-model")
        self.fence.gate.record_fictional_outcome(
            aid, "translation", state="measured", usage=USAGE)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda task: self.fence.reserve(
                    aid, task, "fictional-model"),
                ("summary", "categorization")))
        self.assertEqual(len({x["intent_id"] for x in results}), 2)
        self.assertEqual(self.fence.status()["inflight"], 0)
        closure = self.fence.close()
        self.assertEqual(closure["unknown_charge_attempts"], 2)
        self.assertEqual(closure["measured_fictional_attempts"], 2)
        self.assertFalse(closure["analyzed_checkpoint_authorized"])

    def test_tampered_state_fails_closed(self):
        self.collected()
        self.fence.open()
        current, _ = self.fence._read()
        payload = dict(current, inflight=-1)
        self.store.damage_for_test(self.fence.key, canonical_bytes(payload))
        self.assert_code("c2_admission_state_invalid", self.fence.close)
        self.assert_code("c2_admission_state_invalid", self.fence.status)

    def test_failing_model_task_releases_its_registered_flight(self):
        self.collected()
        self.fence.open()
        self.assert_code("c2_task_identity_invalid", lambda:
            self.fence.reserve(self.article_id, "invalid-task", "fictional-model"))
        self.assertEqual(self.fence.status()["inflight"], 0)
        self.assertFalse(self.fence.close()["analyzed_checkpoint_authorized"])

    def test_invalid_limit_refused(self):
        self.assert_code("c2_admission_capacity_invalid", lambda:
            FictionalSpendAdmissionFence(self.policy, max_inflight=0))


if __name__ == "__main__":
    unittest.main()
