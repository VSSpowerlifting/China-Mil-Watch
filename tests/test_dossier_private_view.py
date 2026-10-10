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


def build(doc=None, archive=None, authority=None, previous=None):
    d = fake_dossier() if doc is None else doc
    a = fake_archive(d) if archive is None else archive
    t = fake_authority(d) if authority is None else authority
    return build_private_dossier_view(d, a, synthetic_authority=t,
                                      previous_sidecar=previous)


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


def fictional_revision_two():
    """Create an approved-looking edited successor; still wholly imaginary."""
    before = fake_dossier()
    later = copy.deepcopy(before)
    later["revision"] = 2
    later["sections"][0]["claims"][0]["text"] = (
        "A fictional issuer described a differently phrased planned exchange."
    )
    later["changes"].append({
        "revision": 2, "changed_on": later["updated_on"],
        "summary": "Revised the imaginary attribution for the first claim.",
        "affected_claim_ids": ["alpha-statement"],
    })
    later["approval"]["content_sha256"] = dossier_content_digest(later)
    packet = fake_authority(later)
    packet["history_checked"] = True
    return before, later, packet


def fictional_archive_for(d):
    """Sidecar-aligned fictional B1.2-shaped report, NEVER a real DB receipt."""
    report = fake_archive(d)
    report["selected_record_ids"] = [src["record_id"] for src in d["sources"]]
    report["evidence"] = [{
        "record_id": src["record_id"],
        "archive_identity_reconciled": True,
        "model_screening": "selected",
    } for src in d["sources"]]
    return report


def recalculate_fictional_review(d, packet):
    d["approval"]["content_sha256"] = dossier_content_digest(d)
    auth = fake_authority(d)
    auth["history_checked"] = True
    auth["claim_ids"] = sorted(c["id"] for sec in d["sections"] for c in sec["claims"])
    # All receipts/decisions here are fabricated in-process test values.
    template_policy = next(iter(packet["sources"].values()))
    auth["sources"] = {
        str(src["record_id"]): copy.deepcopy(
            packet["sources"].get(str(src["record_id"]), template_policy)
        )
        for src in d["sources"]
    }
    return auth


class TwoEditionReaderHistoryTests(unittest.TestCase):
    def test_two_edition_diff_has_actual_modified_claim_and_prior_digest(self):
        old, new, packet = fictional_revision_two()
        view = build(new, authority=packet, previous=old)
        info = view["revision_comparison"]
        self.assertEqual(info["kind"], "compared-fictional-revisions")
        self.assertEqual(info["previous_revision"], 1)
        self.assertEqual(info["previous_content_sha256"], dossier_content_digest(old))
        self.assertEqual(info["modified_claim_ids"], ["alpha-statement"])
        self.assertEqual(info["changed_fields"], ["sections"])
        self.assertEqual(info["added_claim_ids"], [])
        self.assertEqual(info["removed_claim_ids"], [])
        self.assertFalse(view["eligible_for_publication"])

    def test_revision_two_must_have_a_real_supplied_predecessor(self):
        old, new, packet = fictional_revision_two()
        with self.assertRaisesRegex(PrivateDossierViewHold, "previous-fictional-revision-required"):
            build(new, authority=packet)

    def test_revision_one_refuses_invented_prior_version(self):
        doc = fake_dossier()
        with self.assertRaisesRegex(
            PrivateDossierViewHold, "initial-revision-cannot-have-predecessor"
        ):
            build(doc, previous=copy.deepcopy(doc))

    def test_prior_revision_must_be_valid_approved_fictional_document(self):
        old, new, packet = fictional_revision_two()
        old["editorial_status"] = "draft"
        old.pop("approval")
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-revision-lineage-mismatch"):
            build(new, authority=packet, previous=old)

    def test_prior_slug_change_requires_continuous_subject(self):
        old, new, packet = fictional_revision_two()
        old["slug"] = "fictional-different-subject"
        old["approval"]["content_sha256"] = dossier_content_digest(old)
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-revision-lineage-mismatch"):
            build(new, authority=packet, previous=old)

    def test_claim_section_relocation_requires_revision_acknowledgment(self):
        old, new, packet = fictional_revision_two()
        # Exchange the two claims so both thematic sections remain nonempty.
        a = new["sections"][0]["claims"][0]
        b = new["sections"][1]["claims"][0]
        new["sections"][0]["claims"] = [b]
        new["sections"][1]["claims"] = [a]
        # The older note names alpha, but shared-framing also moved.
        new["approval"]["content_sha256"] = dossier_content_digest(new)
        packet = fake_authority(new)
        packet["history_checked"] = True
        with self.assertRaisesRegex(
            PrivateDossierViewHold, "fictional-revision-omits-claim-changes"
        ):
            build(new, authority=packet, previous=old)

    def test_acknowledged_section_relocation_is_explicit_in_revision_diff(self):
        old, new, packet = fictional_revision_two()
        a = new["sections"][0]["claims"][0]
        b = new["sections"][1]["claims"][0]
        new["sections"][0]["claims"] = [b]
        new["sections"][1]["claims"] = [a]
        new["changes"][-1]["affected_claim_ids"] = [
            "alpha-statement", "shared-framing"
        ]
        new["approval"]["content_sha256"] = dossier_content_digest(new)
        packet = fake_authority(new)
        packet["history_checked"] = True
        view = build(new, authority=packet, previous=old)
        self.assertEqual(
            view["revision_comparison"]["relocated_claim_ids"],
            ["alpha-statement", "shared-framing"],
        )
        self.assertEqual(
            view["revision_comparison"]["modified_claim_ids"],
            ["alpha-statement", "shared-framing"],
        )
        self.assertFalse(view["eligible_for_publication"])

    def test_prior_change_history_cannot_be_rewritten(self):
        old, new, packet = fictional_revision_two()
        old["changes"][0]["summary"] = "Edited earlier issue after the fact."
        old["approval"]["content_sha256"] = dossier_content_digest(old)
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-revision-lineage-mismatch"):
            build(new, authority=packet, previous=old)

    def test_changelog_only_revision_is_not_a_substantive_update(self):
        old, new, packet = fictional_revision_two()
        new["sections"][0]["claims"][0]["text"] = old["sections"][0]["claims"][0]["text"]
        new["approval"]["content_sha256"] = dossier_content_digest(new)
        packet = fake_authority(new)
        packet["history_checked"] = True
        with self.assertRaisesRegex(
            PrivateDossierViewHold, "fictional-revision-without-substantive-change"
        ):
            build(new, authority=packet, previous=old)

    def test_silent_modified_claim_missing_from_note_is_refused(self):
        old, new, packet = fictional_revision_two()
        new["changes"][-1]["affected_claim_ids"] = ["shared-framing"]
        new["approval"]["content_sha256"] = dossier_content_digest(new)
        packet = fake_authority(new)
        packet["history_checked"] = True
        with self.assertRaisesRegex(
            PrivateDossierViewHold, "fictional-revision-omits-claim-changes"
        ):
            build(new, authority=packet, previous=old)

    def test_review_flags_cannot_replace_actual_prior_version(self):
        old, new, packet = fictional_revision_two()
        packet["history_checked"] = True
        with self.assertRaises(PrivateDossierViewHold):
            build(new, authority=packet, previous=None)

    def test_scope_only_update_is_reported_without_inventing_claim_diff(self):
        old, new, packet = fictional_revision_two()
        new["sections"][0]["claims"][0]["text"] = old["sections"][0]["claims"][0]["text"]
        new["scope"]["collection_limits"] = "A revised limitation for an invented desk."
        new["changes"][-1]["affected_claim_ids"] = []
        new["approval"]["content_sha256"] = dossier_content_digest(new)
        packet = fake_authority(new)
        packet["history_checked"] = True
        view = build(new, authority=packet, previous=old)
        self.assertEqual(view["revision_comparison"]["changed_fields"], ["scope"])
        self.assertEqual(view["revision_comparison"]["modified_claim_ids"], [])
        self.assertFalse(view["eligible_for_publication"])

    def test_prior_real_archive_ids_refused_even_when_named_fictional(self):
        old, new, packet = fictional_revision_two()
        old["sources"][0]["record_id"] = 4428
        old["sections"][0]["claims"][0]["source_record_ids"] = [4428]
        old["sections"][1]["claims"][0]["source_record_ids"] = [4428, 900002]
        old["approval"]["content_sha256"] = dossier_content_digest(old)
        with self.assertRaisesRegex(
            PrivateDossierViewHold, "fictional-revision-lineage-mismatch"
        ):
            build(new, authority=packet, previous=old)

    def test_original_sidecars_and_packets_unchanged(self):
        old, new, packet = fictional_revision_two()
        original = copy.deepcopy((old, new, packet))
        build(new, authority=packet, previous=old)
        self.assertEqual((old, new, packet), original)


class SourceLedgerContinuityTests(unittest.TestCase):
    def setUp(self):
        self.old, self.new, self.packet = fictional_revision_two()

    def evaluate(self):
        return build(
            self.new,
            archive=fictional_archive_for(self.new),
            authority=recalculate_fictional_review(self.new, self.packet),
            previous=self.old,
        )

    def test_same_archive_id_repointed_to_different_url_refused(self):
        self.new["sources"][0]["url"] = "https://example.org/replaced-citation"
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-source-identity-drift"):
            self.evaluate()

    def test_same_archive_id_with_changed_original_body_digest_refused(self):
        self.new["sources"][0]["stored_original_sha256"] = "d" * 64
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-source-identity-drift"):
            self.evaluate()

    def test_same_archive_id_with_changed_issuer_refused(self):
        self.new["sources"][0]["institution_id"] = "fixture-ministry-alternate"
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-source-identity-drift"):
            self.evaluate()

    def test_same_archive_id_with_changed_language_refused(self):
        self.new["sources"][0]["language"] = "fr"
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-source-identity-drift"):
            self.evaluate()

    def test_same_archive_id_with_changed_publication_date_refused(self):
        self.new["sources"][0]["published_on"] = "2026-09-06"
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-source-identity-drift"):
            self.evaluate()

    def test_source_removal_requires_independent_disposition(self):
        self.new["sources"] = self.new["sources"][:1]
        self.new["sections"][1]["claims"][0]["source_record_ids"] = [900001]
        self.new["changes"][-1]["affected_claim_ids"] = [
            "alpha-statement", "shared-framing"
        ]
        with self.assertRaisesRegex(
            PrivateDossierViewHold, "fictional-source-removal-requires-review"
        ):
            self.evaluate()

    def test_new_source_cannot_enter_ledger_without_any_claim_citation(self):
        added = copy.deepcopy(self.new["sources"][1])
        added.update({
            "record_id": 900003, "source_id": "fake-gamma",
            "institution_id": "fixture-ministry-gamma",
            "url": "https://example.org/fake-gamma",
        })
        self.new["sources"].append(added)
        with self.assertRaisesRegex(PrivateDossierViewHold, "fictional-added-source-uncited"):
            self.evaluate()

    def test_new_source_used_by_claim_is_reported_as_added(self):
        added = copy.deepcopy(self.new["sources"][1])
        added.update({
            "record_id": 900003, "source_id": "fake-gamma",
            "institution_id": "fixture-ministry-gamma",
            "url": "https://example.org/fake-gamma",
        })
        self.new["sources"].append(added)
        self.new["sections"][1]["claims"][0]["source_record_ids"] = [
            900001, 900002, 900003
        ]
        self.new["changes"][-1]["affected_claim_ids"] = [
            "alpha-statement", "shared-framing"
        ]
        view = self.evaluate()
        comparison = view["revision_comparison"]
        self.assertEqual(comparison["added_source_record_ids"], [900003])
        self.assertEqual(comparison["removed_source_record_ids"], [])
        self.assertEqual(comparison["modified_claim_ids"], [
            "alpha-statement", "shared-framing"
        ])
        self.assertFalse(view["eligible_for_publication"])

    def test_new_counterevidence_source_is_counted_as_cited(self):
        added = copy.deepcopy(self.new["sources"][1])
        added.update({
            "record_id": 900003, "source_id": "fake-gamma",
            "institution_id": "fixture-ministry-gamma",
            "url": "https://example.org/fake-gamma",
        })
        self.new["sources"].append(added)
        self.new["sections"][1]["claims"][0]["counterevidence_ids"] = [900003]
        self.new["changes"][-1]["affected_claim_ids"] = [
            "alpha-statement", "shared-framing"
        ]
        view = self.evaluate()
        self.assertEqual(view["revision_comparison"]["added_source_record_ids"], [900003])
        self.assertEqual(
            view["sections"][1]["claims"][0]["counterevidence_citations"][0]["record_id"],
            900003,
        )
        self.assertFalse(view["eligible_for_publication"])

    def test_initial_revision_source_delta_is_empty(self):
        view = build(fake_dossier())
        self.assertEqual(view["revision_comparison"]["added_source_record_ids"], [])
        self.assertEqual(view["revision_comparison"]["removed_source_record_ids"], [])

    def test_source_delta_comparison_never_mutates_prior_versions(self):
        old_snapshot = copy.deepcopy(self.old)
        new_snapshot = copy.deepcopy(self.new)
        self.evaluate()
        self.assertEqual(self.old, old_snapshot)
        self.assertEqual(self.new, new_snapshot)


if __name__ == "__main__":
    unittest.main()
