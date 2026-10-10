"""C2-D: validate hash-pinned native desk source inventory, fictional only."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.collection.contract import SourceRunResult
from core.evidence_snapshot import (
    EvidenceContractError, canonical_bytes, digest_bytes, digest_file,
)
from core.manifests import DESKS_DIR
from storage import db
from storage.evidence_custody import RehearsalCustodySession
from storage.evidence_manifest_policy import FictionalManifestSourcePolicy
from storage.evidence_object_protocol import (
    EvidenceObjectCoordinator, InMemoryConditionalStore,
)
from storage.evidence_source_plan import FictionalSourcePlan
from tests.custody_fixtures import initialize_application


class ManifestSelectionContracts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ipr-custody-manifest-")
        self.addCleanup(tmp.cleanup)
        self.transport = InMemoryConditionalStore()
        self.coordinator = EvidenceObjectCoordinator(self.transport)
        self.session = RehearsalCustodySession(
            self.coordinator, tmp.name, run_id="fictional-manifest-1",
            logical_date="2026-10-10", enabled=True)
        self.session.bootstrap(allow_empty=True)
        initialize_application(self.session.database_path)
        with self.session.application():
            self.native = db.start_scrape_run()
        self.plan = FictionalSourcePlan(self.session)
        self.policy = FictionalManifestSourcePolicy(self.plan)
        self.china_manifest = Path(DESKS_DIR) / "china" / "manifest.json"
        self.china_digest = digest_file(self.china_manifest)

    def assert_code(self, code, callback):
        with self.assertRaises(EvidenceContractError) as err:
            callback()
        self.assertEqual(str(err.exception), code)

    def freeze(self):
        return self.policy.freeze("china", self.china_digest)

    def insert_fictional_receipts(self):
        selected = self.policy.load()["sources"]
        with self.session.application():
            for slug in selected:
                db.record_source_run_result(
                    self.native, SourceRunResult(
                        source_slug=slug, desk_id="china",
                        status="ok_no_publications"))
        return selected

    def test_manifest_inventory_is_pinned_and_plan_derived(self):
        receipt = self.freeze()
        self.assertFalse(receipt["production_selection_authorized"])
        self.assertFalse(receipt["policy_owner_approved"])
        self.assertFalse(receipt["eligible_for_publication"])
        self.assertEqual(
            self.plan.load()["sources"], self.policy.load()["sources"])
        self.assertEqual(receipt["source_count"],
                         len(self.policy.load()["sources"]))
        self.assertGreater(receipt["source_count"], 0)
        self.assertEqual(receipt["manifest_sha256"], self.china_digest)

    def test_all_manifest_sources_required_before_collection_checkpoint(self):
        self.freeze()
        self.assert_code("c2_source_ledger_incomplete",
                         self.policy.seal_collection)
        self.assertIsNone(self.coordinator.current()[0])
        selected = self.insert_fictional_receipts()
        closed = self.policy.seal_collection()
        self.assertEqual(closed["source_count"], len(selected))
        self.assertTrue(self.policy.verify_before_analysis()[
            "analysis_dispatch_eligible_fictional_only"])

    def test_manifest_replay_is_idempotent_but_omissions_are_not(self):
        self.freeze()
        self.assertEqual(self.freeze()["source_count"],
                         len(self.plan.load()["sources"]))
        self.assert_code("c2_source_plan_conflict", lambda:
            self.plan.freeze(["pla_daily"]))
        self.assert_code("c2_manifest_policy_conflict", lambda:
            self.policy.freeze("singapore", digest_file(
                Path(DESKS_DIR) / "singapore" / "manifest.json")))

    def test_wrong_manifest_digest_rejected_before_persistent_write(self):
        self.assert_code("c2_manifest_digest_changed", lambda:
            self.policy.freeze("china", "0" * 64))
        self.assertIsNone(self.transport.get(self.policy.key))
        self.assert_code("c2_source_plan_missing", self.plan.load)

    def test_malformed_or_escaped_desk_scope_is_refused(self):
        self.assert_code("c2_manifest_selection_invalid", lambda:
            self.policy.freeze("../china", self.china_digest))
        self.assert_code("c2_manifest_selection_invalid", lambda:
            self.policy.freeze("china", "not-a-checksum"))

    def test_lost_immutable_policy_write_ack_is_recoverable(self):
        self.transport.fail_next("put_new", after_write=True)
        self.assert_code("synthetic_storage_unavailable", self.freeze)
        self.assertIsNotNone(self.transport.get(self.policy.key))
        self.assert_code("c2_source_plan_missing", self.plan.load)
        self.assertGreater(self.freeze()["source_count"], 0)

    def test_changed_manifest_metadata_blocks_recovered_selection(self):
        temp = tempfile.TemporaryDirectory(prefix="ipr-manifest-fixture-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy = root / "china" / "manifest.json"
        copy.parent.mkdir()
        copy.write_bytes(self.china_manifest.read_bytes())
        with patch("storage.evidence_manifest_policy.DESKS_DIR", root):
            self.freeze()
            raw = json.loads(copy.read_text())
            raw["_c2_fixture_changed"] = True
            copy.write_text(json.dumps(raw, sort_keys=True))
            self.assert_code("c2_manifest_digest_changed", self.policy.load)
            self.assert_code("c2_manifest_digest_changed",
                             self.policy.seal_collection)

    def test_edited_manifest_source_set_cannot_hide_a_declared_source(self):
        self.freeze()
        state = dict(self.policy._read())
        state["sources"] = state["sources"][:-1]
        state["source_set_sha256"] = digest_bytes(
            canonical_bytes(state["sources"]))
        self.transport.damage_for_test(
            self.policy.key, canonical_bytes(state))
        self.assert_code("c2_manifest_policy_changed", self.policy.load)

    def test_full_fictional_manifest_collection_spend_analysis_sequence(self):
        # The entire C2 A/B/C/D stack operates on the native C1 application
        # schema with NO actual collection, model, source text or publication.
        from processing.metadata import normalize_article
        from storage.evidence_spend import FictionalSpendIntentJournal

        self.freeze()
        with self.session.application(), db.get_conn() as conn:
            conn.execute(
                "INSERT INTO sources(slug,display_name,base_url,language,desk_id) "
                "VALUES('pla_daily','Fictional official source',"
                "'https://fixture.invalid/','en','china')")
        fictional = normalize_article({
            "source_slug": "pla_daily",
            "url": "https://fixture.invalid/c2-native/1",
            "title_original": "Fictional intake",
            "text_original": "CUSTODY_SYNTHETIC_NONPUBLISHABLE",
            "published_date": "2026-10-10",
        })
        with self.session.application():
            aid = db.insert_article(fictional, self.native)
            self.assertIsNotNone(aid)
            for slug in self.policy.load()["sources"]:
                if slug == "pla_daily":
                    outcome = SourceRunResult(
                        source_slug=slug, desk_id="china", status="ok",
                        references_discovered=1, fetched=1, extracted=1,
                        new_documents=1)
                else:
                    outcome = SourceRunResult(
                        source_slug=slug, desk_id="china",
                        status="ok_no_publications")
                db.record_source_run_result(self.native, outcome)

        collection = self.policy.seal_collection()
        self.assertEqual(collection["new_article_count"], 1)
        self.assertTrue(self.policy.verify_before_analysis()[
            "analysis_dispatch_eligible_fictional_only"])
        journal = FictionalSpendIntentJournal(self.plan.barrier())
        intent = journal.reserve(aid, "relevance", "fictional-model")
        self.assertEqual(intent["state"], "reserved_spend_unknown")
        self.assertFalse(intent["provider_call_executed"])
        tokens = {
            "input_tokens": 11, "output_tokens": 7,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        }
        self.assertEqual(journal.record_outcome(
            aid, "relevance", state="measured", usage=tokens)["usage"], tokens)
        with self.session.application():
            db.update_relevance(aid, 0.8, "fictional-only", True)
        analysis = self.plan.barrier().seal_analysis()
        self.assertEqual(analysis["collected_generation"],
                         collection["generation"])
        self.assertNotEqual(analysis["analyzed_generation"],
                            collection["generation"])
        self.assertFalse(analysis["usage_receipt_durable"])
        self.assertFalse(analysis["eligible_for_publication"])
        self.assertFalse(journal.inspect(
            aid, "relevance")["automatic_retry_authorized"])

    def test_policy_reloads_after_application_restart(self):
        self.freeze()
        self.insert_fictional_receipts()
        sealed = self.policy.seal_collection()
        tmp = tempfile.TemporaryDirectory(prefix="ipr-custody-policy-restart-")
        self.addCleanup(tmp.cleanup)
        other = RehearsalCustodySession(
            self.coordinator, tmp.name, run_id=self.session.run_id,
            logical_date=self.session.logical_date, enabled=True)
        other.bootstrap()
        reopened = FictionalManifestSourcePolicy(FictionalSourcePlan(other))
        self.assertEqual(reopened.load()["source_set_sha256"],
                         sealed["source_set_sha256"])
        self.assertEqual(reopened.verify_before_analysis()[
            "collected_generation"], sealed["generation"])


if __name__ == "__main__":
    unittest.main()
