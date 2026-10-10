"""C2-C source-selection freeze, native execution, and tamper refusal tests."""
from __future__ import annotations

import tempfile
import unittest

from core.collection.contract import SourceRunResult
from core.evidence_snapshot import EvidenceContractError, canonical_bytes
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)
from storage.evidence_source_plan import FictionalSourcePlan
from tests.custody_fixtures import initialize_application, insert_fictional


class FictionalPlanContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-custody-source-plan-")
        self.addCleanup(tmp.cleanup)
        self.transport = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.transport)
        self.session = RehearsalCustodySession(
            self.coordinator, tmp.name, run_id="fictional-plan-1",
            logical_date="2026-10-10", enabled=True)
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        with self.session.application():
            self.native = db.start_scrape_run()
        self.plan = FictionalSourcePlan(self.session)

    def assert_code(self, code, fn):
        with self.assertRaises(EvidenceContractError) as caught:
            fn()
        self.assertEqual(str(caught.exception), code)

    def collected(self):
        return insert_fictional(self.session.database_path)

    def test_freeze_before_collection_and_resume_from_durable_plan(self):
        result = self.plan.freeze(["fictional_custody"])
        self.assertEqual(result["source_count"], 1)
        self.assertFalse(result["production_selection_authorized"])
        self.assertFalse(result["eligible_for_publication"])
        self.assertFalse(result["already_frozen"])
        self.assertTrue(self.plan.freeze(
            ["fictional_custody"])["already_frozen"])
        self.collected()
        receipt = self.plan.seal_collection()
        self.assertEqual(receipt["source_count"], 1)
        self.assertTrue(self.plan.verify_before_analysis()[
            "analysis_dispatch_eligible_fictional_only"])

    def test_missing_declared_source_never_closes_as_complete(self):
        self.plan.freeze(["fictional_custody", "fictional_second"])
        self.collected()
        self.assert_code("c2_source_ledger_incomplete",
                         self.plan.seal_collection)
        self.assertIsNone(self.coordinator.current()[0])

    def test_explicit_failure_is_complete_not_silent(self):
        self.plan.freeze(["fictional_custody", "fictional_failed"])
        self.collected()
        with self.session.application():
            db.record_source_run_result(self.native, SourceRunResult(
                source_slug="fictional_failed", desk_id="china",
                status="listing_failure"))
        self.assertEqual(self.plan.seal_collection()["source_failure_count"], 1)

    def test_no_retroactive_freeze_after_source_results(self):
        self.collected()
        self.assert_code("c2_source_plan_too_late", lambda:
            self.plan.freeze(["fictional_custody"]))
        self.assert_code("c2_source_plan_missing", self.plan.seal_collection)

    def test_no_retroactive_freeze_after_native_articles(self):
        self.plan.freeze(["fictional_custody"])
        self.collected()
        self.assert_code("c2_source_plan_too_late", lambda:
            self.plan.freeze(["fictional_custody"]))
        self.assertTrue(self.plan.seal_collection()["generation"])

    def test_plan_cannot_be_narrowed_or_changed_by_reordered_retry(self):
        self.plan.freeze(["fictional_custody", "fictional_second"])
        self.assertTrue(self.plan.freeze(
            ["fictional_second", "fictional_custody"])["already_frozen"])
        self.assert_code("c2_source_plan_conflict", lambda:
            self.plan.freeze(["fictional_custody"]))
        self.assertEqual(self.plan.load()["sources"],
                         ["fictional_custody", "fictional_second"])

    def test_plan_missing_refuses_analysis_without_other_evidence(self):
        self.collected()
        self.assert_code("c2_source_plan_missing",
                         self.plan.verify_before_analysis)
        self.assertIsNone(self.coordinator.current()[0])

    def test_lost_write_ack_preserves_intent_without_authorizing_change(self):
        self.transport.fail_next("put_new", after_write=True)
        self.assert_code("synthetic_storage_unavailable", lambda:
            self.plan.freeze(["fictional_custody", "fictional_second"]))
        self.assertEqual(self.plan.load()["sources"],
                         ["fictional_custody", "fictional_second"])
        self.assert_code("c2_source_plan_conflict", lambda:
            self.plan.freeze(["fictional_custody"]))

    def test_tampered_canonical_plan_is_not_trusted(self):
        self.plan.freeze(["fictional_custody"])
        raw = dict(self.plan.load())
        raw["sources"] = []
        self.transport.damage_for_test(
            self.plan.key, canonical_bytes(raw))
        self.assert_code("c2_source_plan_invalid", self.plan.load)
        self.assert_code("c2_source_plan_invalid", self.plan.seal_collection)

    def test_fresh_session_reloads_plan_and_verifies_snapshot(self):
        self.plan.freeze(["fictional_custody"])
        self.collected()
        original = self.plan.seal_collection()
        tmp = tempfile.TemporaryDirectory(prefix="ipr-custody-plan-restart-")
        self.addCleanup(tmp.cleanup)
        restarted = RehearsalCustodySession(
            self.coordinator, tmp.name, run_id=self.session.run_id,
            logical_date=self.session.logical_date, enabled=True)
        restarted.bootstrap()
        replay = FictionalSourcePlan(restarted)
        self.assertEqual(replay.load()["sources"], ["fictional_custody"])
        self.assertEqual(replay.verify_before_analysis()[
            "collected_generation"], original["generation"])

    def test_zero_source_backlog_is_valid_only_when_frozen(self):
        self.plan.freeze([])
        receipt = self.plan.seal_collection()
        self.assertEqual(receipt["source_count"], 0)
        self.assertEqual(receipt["new_article_count"], 0)
        self.assertFalse(receipt["eligible_for_publication"])

    def test_unstarted_or_invalid_list_is_refused(self):
        self.assert_code("c2_source_plan_invalid", lambda:
            self.plan.freeze(None))
        self.assert_code("c2_source_plan_duplicate", lambda:
            self.plan.freeze(["a", "a"]))
        self.assert_code("c2_source_plan_invalid", lambda:
            self.plan.freeze(["a/../../escape"]))
        tmp = tempfile.TemporaryDirectory(prefix="ipr-custody-source-plan-")
        self.addCleanup(tmp.cleanup)
        unstarted = RehearsalCustodySession(
            self.coordinator, tmp.name, enabled=True)
        self.assert_code("custody_startup_required", lambda:
            FictionalSourcePlan(unstarted).freeze([]))


if __name__ == "__main__":
    unittest.main()
