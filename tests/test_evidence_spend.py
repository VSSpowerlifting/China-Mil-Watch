"""Fictional C2 write-ahead spend accounting: no provider/model invocation."""
from __future__ import annotations

import tempfile
import threading
import unittest

from core.evidence_snapshot import EvidenceContractError
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_lifecycle import FictionalCollectionBarrier
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)
from storage.evidence_spend import FictionalSpendIntentJournal
from tests.custody_fixtures import initialize_application, insert_fictional


USAGE = {
    "input_tokens": 17, "output_tokens": 23,
    "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0,
}


class SpendIntentContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-custody-spend-")
        self.addCleanup(self.temp.cleanup)
        self.transport = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.transport)
        self.session = RehearsalCustodySession(
            self.coordinator, self.temp.name,
            run_id="fictional-spend-run", logical_date="2026-10-10",
            enabled=True,
        )
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        self.aid = insert_fictional(self.session.database_path)
        self.barrier = FictionalCollectionBarrier(
            self.session, ["fictional_custody"])
        self.journal = FictionalSpendIntentJournal(self.barrier)

    def assert_code(self, code, callback):
        with self.assertRaises(EvidenceContractError) as got:
            callback()
        self.assertEqual(str(got.exception), code)

    def collect(self):
        return self.barrier.seal_collection()

    def test_uncollected_source_cannot_authorize_any_spend(self):
        self.assert_code("c2_collection_not_durable", lambda:
            self.journal.reserve(self.aid, "relevance", "fake-model"))
        self.assertEqual(self.journal.inspect(self.aid, "relevance")["state"],
                         "not_reserved")

    def test_reserved_intent_reports_unknown_charge_until_measured(self):
        self.collect()
        started = self.journal.reserve(self.aid, "relevance", "fake-model")
        self.assertEqual(started["state"], "reserved_spend_unknown")
        self.assertFalse(started["provider_call_executed"])
        assert_unknown = self.journal.inspect(self.aid, "relevance")
        self.assertEqual(assert_unknown["state"], "spend_unknown")
        self.assertIsNone(assert_unknown["usage"])
        self.assertFalse(assert_unknown["automatic_retry_authorized"])
        final = self.journal.record_outcome(
            self.aid, "relevance", state="measured", usage=USAGE)
        self.assertEqual(final["state"], "measured_usage")
        self.assertEqual(final["usage"], USAGE)
        self.assertFalse(final["automatic_retry_authorized"])
        self.assert_code("c2_spend_attempt_already_reserved", lambda:
            self.journal.reserve(self.aid, "relevance", "other-model"))

    def test_unknown_outcome_is_not_reported_as_zero(self):
        self.collect()
        self.journal.reserve(self.aid, "translation", "fake-model")
        report = self.journal.record_outcome(
            self.aid, "translation", state="unknown")
        self.assertEqual(report["state"], "spend_unknown")
        self.assertIsNone(report["usage"])
        self.assert_code("c2_spend_attempt_already_reserved", lambda:
            self.journal.reserve(self.aid, "translation", "fake-model"))

    def test_outcome_requires_durable_intent(self):
        self.collect()
        self.assert_code("c2_spend_intent_missing", lambda:
            self.journal.record_outcome(
                self.aid, "summary", state="measured", usage=USAGE))

    def test_conflicting_accounting_cannot_replace_usage(self):
        self.collect()
        self.journal.reserve(self.aid, "categorization", "fake-model")
        self.journal.record_outcome(
            self.aid, "categorization", state="measured", usage=USAGE)
        self.assertEqual(self.journal.record_outcome(
            self.aid, "categorization", state="measured", usage=USAGE)[
                "state"], "measured_usage")
        changed = dict(USAGE, input_tokens=999)
        self.assert_code("c2_spend_write_conflict", lambda:
            self.journal.record_outcome(
                self.aid, "categorization", state="measured", usage=changed))

    def test_lost_intent_ack_blocks_second_provider_call(self):
        self.collect()
        self.transport.fail_next("put_new", after_write=True)
        self.assert_code("synthetic_storage_unavailable", lambda:
            self.journal.reserve(self.aid, "relevance", "fake-model"))
        self.assertEqual(self.journal.inspect(self.aid, "relevance")["state"],
                         "spend_unknown")
        self.assert_code("c2_spend_attempt_already_reserved", lambda:
            self.journal.reserve(self.aid, "relevance", "fake-model"))

    def test_lost_usage_ack_can_be_reconciled_without_recharge(self):
        self.collect()
        self.journal.reserve(self.aid, "relevance", "fake-model")
        self.transport.fail_next("put_new", after_write=True)
        self.assert_code("synthetic_storage_unavailable", lambda:
            self.journal.record_outcome(
                self.aid, "relevance", state="measured", usage=USAGE))
        self.assertEqual(self.journal.inspect(self.aid, "relevance")["state"],
                         "measured_usage")
        self.assertEqual(self.journal.record_outcome(
            self.aid, "relevance", state="measured", usage=USAGE)["usage"],
                         USAGE)

    def test_unknown_article_and_blank_body_fail_closed(self):
        self.collect()
        self.assert_code("c2_spend_article_not_dispatchable", lambda:
            self.journal.reserve(99999, "summary", "fake-model"))
        from processing.metadata import compute_content_hash
        with self.session.application(), db.get_conn() as conn:
            conn.execute(
                "UPDATE articles SET text_original='',content_hash=? WHERE id=?",
                (compute_content_hash("Fictional fixture title 1", ""),
                 self.aid))
        self.assert_code("c2_working_copy_diverged", lambda:
            self.journal.reserve(self.aid, "relevance", "fake-model"))

    def test_bad_model_task_and_usage_cannot_be_persisted(self):
        self.collect()
        self.assert_code("c2_spend_model_invalid", lambda:
            self.journal.reserve(self.aid, "relevance", "secret\nfake"))
        self.assert_code("c2_spend_identity_invalid", lambda:
            self.journal.reserve(self.aid, "bad task", "fake-model"))
        self.journal.reserve(self.aid, "relevance", "fake-model")
        self.assert_code("c2_spend_usage_invalid", lambda:
            self.journal.record_outcome(self.aid, "relevance",
                                        state="measured", usage={
                "input_tokens": -1, "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0}))
        self.assertEqual(self.journal.inspect(self.aid, "relevance")["state"],
                         "spend_unknown")

    def test_corrupted_measured_usage_cannot_be_reported_as_verified(self):
        from core.evidence_snapshot import canonical_bytes
        self.collect()
        self.journal.reserve(self.aid, "relevance", "fake-model")
        self.journal.record_outcome(
            self.aid, "relevance", state="measured", usage=USAGE)
        _, key, token = self.journal._keys(self.aid, "relevance")
        tampered = {
            "schema": "ipr-fictional-analysis-spend/1",
            "kind": "outcome", "intent_id": token,
            "state": "measured", "usage": dict(USAGE, input_tokens=-17),
        }
        self.transport.damage_for_test(key, canonical_bytes(tampered))
        self.assert_code("c2_spend_store_invalid", lambda:
            self.journal.inspect(self.aid, "relevance"))

    def test_unknown_usage_cannot_carry_fake_measurement(self):
        from core.evidence_snapshot import canonical_bytes
        self.collect()
        self.journal.reserve(self.aid, "relevance", "fake-model")
        self.journal.record_outcome(
            self.aid, "relevance", state="unknown")
        _, key, token = self.journal._keys(self.aid, "relevance")
        tampered = {
            "schema": "ipr-fictional-analysis-spend/1",
            "kind": "outcome", "intent_id": token,
            "state": "unknown", "usage": dict(USAGE),
        }
        self.transport.damage_for_test(key, canonical_bytes(tampered))
        self.assert_code("c2_spend_store_invalid", lambda:
            self.journal.inspect(self.aid, "relevance"))

    def test_modified_intent_identity_is_not_trusted_after_restart(self):
        from core.evidence_snapshot import canonical_bytes
        self.collect()
        self.journal.reserve(self.aid, "relevance", "fake-model")
        key, _, _ = self.journal._keys(self.aid, "relevance")
        tampered = {
            "schema": "ipr-fictional-analysis-spend/1", "kind": "intent",
            "execution_id": self.session.run_id, "article_id": self.aid,
            "task": "relevance", "model": "fake-model",
            "collected_generation": "0" * 64, "ledger_sha256": "-1",
        }
        self.transport.damage_for_test(key, canonical_bytes(tampered))
        self.assert_code("c2_spend_store_invalid", lambda:
            self.journal.inspect(self.aid, "relevance"))

    def test_one_reservation_wins_under_threaded_race(self):
        self.collect()
        results = []
        start = threading.Barrier(2)

        def invoke():
            start.wait()
            try:
                results.append(self.journal.reserve(
                    self.aid, "relevance", "fake-model")["state"])
            except EvidenceContractError as exc:
                results.append(str(exc))

        workers = [threading.Thread(target=invoke) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(15)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(sorted(results), [
            "c2_spend_attempt_already_reserved", "reserved_spend_unknown"
        ])
        self.assertFalse(self.journal.inspect(
            self.aid, "relevance")["automatic_retry_authorized"])


if __name__ == "__main__":
    unittest.main()
