"""B2.2a inert fictional reader data; no public site or publisher source."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.dossier_contract import dossier_content_digest
from core.dossier_private_view import (
    MARKER, VIEW_SCHEMA, PrivateDossierViewHold, build_private_dossier_view,
)
from tests.test_dossier_publication import fake_archive, fake_authority, fake_dossier


def build(doc=None, archive=None, authority=None):
    d = fake_dossier() if doc is None else doc
    a = fake_archive(d) if archive is None else archive
    t = fake_authority(d) if authority is None else authority
    return build_private_dossier_view(d, a, synthetic_authority=t)


class PrivateReaderProjectionTests(unittest.TestCase):
    def test_fictional_data_can_be_projected_privately(self):
        view = build()
        self.assertEqual(view["schema"], VIEW_SCHEMA)
        self.assertEqual(view["warning"], MARKER)
        self.assertTrue(view["private_synthetic_preview_only"])
        self.assertFalse(view["eligible_for_publication"])
        self.assertFalse(view["publication_authority_configured"])

    def test_never_emits_a_route_canonical_sitemap_or_feed(self):
        view = build()
        for key in ("canonical", "public_route", "sitemap_route", "feed_route"):
            self.assertIsNone(view[key])
        self.assertFalse(view["indexable"])
        self.assertEqual(view["related_research_links"], [])

    def test_thematic_sections_and_citation_anchors_are_precise(self):
        view = build()
        self.assertEqual(len(view["sections"]), 2)
        self.assertEqual([s["id"] for s in view["sections"]],
                         ["statements", "comparisons"])
        self.assertEqual(view["sections"][0]["claims"][0]["attribution_label"],
                         "Attributed issuer statement")
        claim = view["sections"][1]["claims"][0]
        self.assertEqual(claim["attribution_label"], "IPR editorial interpretation")
        self.assertEqual(
            [c["source_anchor"] for c in claim["supporting_citations"]],
            ["#source-900001", "#source-900002"],
        )

    def test_source_ledger_is_fictional_and_language_aware(self):
        view = build()
        self.assertEqual([x["record_id"] for x in view["source_ledger"]],
                         [900001, 900002])
        self.assertEqual(view["source_ledger"][0]["language"], "en")
        self.assertEqual(view["source_ledger"][0]["anchor"], "source-900001")
        self.assertEqual(view["source_ledger"][0]["link_mode"], "fictional-publisher-example")
        self.assertTrue(all(
            src["fictional_publisher_url"].startswith("https://example.org")
            for src in view["source_ledger"]
        ))
        self.assertTrue(all(x["local_record_link"] is None for x in view["source_ledger"]))

    def test_change_history_and_limits_retained(self):
        view = build()
        self.assertEqual(view["revision"], 1)
        self.assertEqual(view["changes"][0]["revision"], 1)
        self.assertIn("#claim-alpha-statement",
                      view["changes"][0]["affected_claim_anchors"])
        self.assertIn("collection_limits", view["scope"])
        self.assertEqual(view["updated_on"], "2026-10-09")

    def test_source_record_ids_not_in_fixture_range_refused(self):
        d = fake_dossier()
        d["sources"][0]["record_id"] = 4428
        d["sections"][0]["claims"][0]["source_record_ids"] = [4428]
        d["sections"][1]["claims"][0]["source_record_ids"] = [4428, 900002]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        with self.assertRaises(PrivateDossierViewHold):
            build(d)

    def test_draft_is_never_renderable_even_in_private_model(self):
        d = fake_dossier()
        d["editorial_status"] = "draft"
        d.pop("approval")
        with self.assertRaises(PrivateDossierViewHold):
            build(d)

    def test_stale_archive_report_refused(self):
        a = fake_archive(fake_dossier())
        a["content_sha256"] = "0" * 64
        with self.assertRaises(PrivateDossierViewHold):
            build(archive=a)

    def test_uncleared_publisher_and_local_links_refused(self):
        d = fake_dossier()
        packet = fake_authority(d)
        packet["sources"]["900001"]["publisher_link"] = False
        packet["sources"]["900001"]["local_record_link"] = False
        with self.assertRaises(PrivateDossierViewHold):
            build(d, authority=packet)

    def test_no_b1_report_passing_as_b12_evidence(self):
        d = fake_dossier()
        private_cli = {
            "schema": "ipr-dossier-private-review/1",
            "eligible_for_publication": False,
            "status": "review_hold",
            "dossiers": [{"slug": d["slug"], "archive_reconciled": True}],
        }
        with self.assertRaises(PrivateDossierViewHold):
            build(d, archive=private_cli)

    def test_no_author_receipts_original_bodies_or_public_markup_leak(self):
        d = fake_dossier()
        view = build(d)
        text = json.dumps(view, sort_keys=True)
        for excluded in (
            "Fake Alpha original",
            "Fake Beta original",
            "synthetic-editor-review-does-not-grant-permission",
            "text_original", "source_use_decision_ref", "editorial_admission_ref",
            "<html", "<script", "noindex\"",
        ):
            self.assertNotIn(excluded, text)
        self.assertFalse(view["eligible_for_publication"])

    def test_determinism_and_no_mutation(self):
        d = fake_dossier()
        initial = copy.deepcopy(d)
        a = fake_archive(d)
        p = fake_authority(d)
        one = build(d, a, p)
        two = build(copy.deepcopy(d), copy.deepcopy(a), copy.deepcopy(p))
        self.assertEqual(json.dumps(one, sort_keys=True), json.dumps(two, sort_keys=True))
        self.assertEqual(d, initial)

    def test_editorial_disagreement_remains_attributed_not_resolved_by_code(self):
        d = fake_dossier()
        d["disagreements"] = [{
            "id": "fictional-contrast",
            "claim_ids": ["alpha-statement", "shared-framing"],
            "status": "unresolved",
            "note": "The fictional issuers' accounts differ.",
        }]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        view = build(d)
        self.assertEqual(view["disagreements"][0]["status"], "unresolved")
        self.assertEqual(view["disagreements"][0]["claim_anchors"],
                         ["#claim-alpha-statement", "#claim-shared-framing"])

    def test_unapproved_related_slugs_never_become_public_links(self):
        d = fake_dossier()
        d["related_briefs"] = ["fictional-brief"]
        d["related_timelines"] = ["fictional-timeline"]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        view = build(d)
        self.assertEqual(view["related_research_links"], [])
        self.assertIsNone(view["public_route"])

    def test_counterevidence_preserved_without_hiding_the_contradiction(self):
        d = fake_dossier()
        second = d["sections"][1]["claims"][0]
        second["source_record_ids"] = [900001]
        second["counterevidence_ids"] = [900002]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        view = build(d)
        result = view["sections"][1]["claims"][0]
        self.assertEqual(result["supporting_citations"][0]["record_id"], 900001)
        self.assertEqual(result["counterevidence_citations"][0]["record_id"], 900002)

    def test_actual_synthetic_sqlite_reconciler_handoff(self):
        from tests.test_dossier_contract import approved
        from tests.test_dossier_sources import BODIES, fake_registry, synthetic_sqlite
        from core.dossier_sources import reconcile_dossier_sources

        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "fictional-archive.db"
            synthetic_sqlite(db_path)
            doc = approved()
            for source in doc["sources"]:
                source["stored_original_sha256"] = hashlib.sha256(
                    BODIES[source["record_id"]].encode("utf-8")
                ).hexdigest()
            doc["approval"]["content_sha256"] = dossier_content_digest(doc)
            received = reconcile_dossier_sources(doc, db_path, registry=fake_registry())
            auth = fake_authority(doc)
            auth["claim_ids"] = sorted(c["id"] for s in doc["sections"] for c in s["claims"])
            before = hashlib.sha256(db_path.read_bytes()).hexdigest()
            view = build_private_dossier_view(doc, received, synthetic_authority=auth)
            self.assertEqual(hashlib.sha256(db_path.read_bytes()).hexdigest(), before)
            self.assertTrue(view["private_synthetic_preview_only"])
            self.assertEqual(len(view["source_ledger"]), 2)
            self.assertFalse(view["eligible_for_publication"])
            self.assertNotIn(BODIES[900001], json.dumps(view))

    def test_real_sqlite_body_drift_refuses_view(self):
        from tests.test_dossier_contract import approved
        from tests.test_dossier_sources import BODIES, fake_registry, synthetic_sqlite
        from core.dossier_sources import reconcile_dossier_sources

        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / "fictional-archive.db"
            synthetic_sqlite(db_path)
            doc = approved()
            for source in doc["sources"]:
                source["stored_original_sha256"] = hashlib.sha256(
                    BODIES[source["record_id"]].encode("utf-8")
                ).hexdigest()
            doc["approval"]["content_sha256"] = dossier_content_digest(doc)
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "UPDATE articles SET text_original=? WHERE id=900002",
                    ("ALTERED FICTIONAL TEXT",),
                )
                connection.commit()
            from core.dossier_sources import reconcile_dossier_sources
            received = reconcile_dossier_sources(doc, db_path, registry=fake_registry())
            self.assertFalse(received["archive_reconciled"])
            auth = fake_authority(doc)
            auth["claim_ids"] = sorted(c["id"] for s in doc["sections"] for c in s["claims"])
            with self.assertRaises(PrivateDossierViewHold):
                build_private_dossier_view(doc, received, synthetic_authority=auth)


if __name__ == "__main__":
    unittest.main()
