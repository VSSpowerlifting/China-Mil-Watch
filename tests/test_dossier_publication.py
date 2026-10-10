"""B2.1 synthetic-only, nonpublishing policy-boundary tests."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.dossier_contract import dossier_content_digest
from core.dossier_publication import (
    SCHEMA, SYNTHETIC_MARKER, assess_dossier_release,
)


def fake_dossier():
    """Fictional, B1-compatible approved-looking JSON; not genuine approval."""
    d = {
        "dossier_schema": 1, "slug": "fictional-harbor-relations",
        "title": "Fictional Harbor Cooperation", "dek": "Entirely invented research example.",
        "research_question": "How do two imaginary issuers frame cooperation?",
        "editorial_status": "approved", "author_name": "Synthetic Author",
        "editor_name": "Fictional Human Editor", "prepared_on": "2026-10-01",
        "updated_on": "2026-10-09", "reviewed_on": "2026-10-09",
        "revision": 1,
        "scope": {
            "period_start": "2026-09-01", "period_end": "2026-09-30",
            "jurisdictions": ["imaginary-alpha", "imaginary-beta"],
            "institutions": ["fixture-ministry-alpha", "fixture-ministry-beta"],
            "included": "Two invented maritime statements.",
            "excluded": "All actual historical activity.",
            "method": "Fictional review of invented reports.",
            "collection_limits": "Not an actual collected corpus.",
        },
        "overview": "This is a fictional editorial comparison with no asserted external facts.",
        "sources": [
            {"record_id": 900001, "desk": "fixture-alpha", "source_id": "fake-alpha",
             "institution_id": "fixture-ministry-alpha", "language": "en",
             "published_on": "2026-09-05", "url": "https://example.org/fake-alpha",
             "stored_original_sha256": hashlib.sha256(b"Fake Alpha original").hexdigest(),
             "editorial_admission_ref": None, "source_use_decision_ref": None},
            {"record_id": 900002, "desk": "fixture-beta", "source_id": "fake-beta",
             "institution_id": "fixture-ministry-beta", "language": "en",
             "published_on": "2026-09-15", "url": "https://example.org/fake-beta",
             "stored_original_sha256": hashlib.sha256(b"Fake Beta original").hexdigest(),
             "editorial_admission_ref": None, "source_use_decision_ref": None},
        ],
        "sections": [
            {"id": "statements", "heading": "Attributed statements",
             "intro": "What the imaginary issuers said.",
             "claims": [
                 {"id": "alpha-statement", "claim_kind": "issuer_statement",
                  "text": "A fictional issuer described a planned exchange.",
                  "source_record_ids": [900001], "event_period": None,
                  "limits": "Nothing occurred in reality.", "counterevidence_ids": []},
             ]},
            {"id": "comparisons", "heading": "Editorial comparison",
             "intro": "This section does not make historical claims.",
             "claims": [
                 {"id": "shared-framing", "claim_kind": "editorial_interpretation",
                  "text": "The invented reports use different imaginary descriptions.",
                  "source_record_ids": [900001, 900002], "event_period": None,
                  "limits": "Neither statement is evidence of real activity.",
                  "counterevidence_ids": []},
             ]},
        ],
        "disagreements": [], "related_briefs": [], "related_timelines": [],
        "changes": [{"revision": 1, "changed_on": "2026-10-09",
                     "summary": "First fictional version.",
                     "affected_claim_ids": ["alpha-statement", "shared-framing"]}],
    }
    d["approval"] = {
        "approved_by": d["editor_name"], "approved_on": "2026-10-09",
        "reference": "synthetic-editor-review-does-not-grant-permission",
        "content_sha256": dossier_content_digest(d),
    }
    return d


def fake_archive(d):
    return {
        "schema": "ipr-dossier-source-review/1", "dossier_slug": d["slug"],
        "editorial_status": d["editorial_status"],
        "content_sha256": dossier_content_digest(d),
        "selected_record_ids": [900001, 900002],
        "archive_reconciled": True, "eligible_for_publication": False,
        "errors": [], "holds": [{"code": "human-claim-and-inference-review-required"}],
        "evidence": [
            {"record_id": 900001, "archive_identity_reconciled": True,
             "model_screening": "not_selected"},
            {"record_id": 900002, "archive_identity_reconciled": True,
             "model_screening": "selected"},
        ],
    }


def fake_authority(d):
    return {
        "marker": SYNTHETIC_MARKER,
        "content_sha256": dossier_content_digest(d), "revision": d["revision"],
        "editor_reviewed": True, "claim_ids": ["alpha-statement", "shared-framing"],
        "history_checked": False,
        "sources": {
            str(rid): {
                "admitted": True, "screening_reviewed": True, "metadata_use": True,
                "publisher_link": True, "publisher_origin_reviewed": True,
                "local_record_link": False, "local_record_body_use_cleared": False,
            } for rid in (900001, 900002)
        },
    }


def names(report):
    return [i["code"] for i in report["issues"]]


class DossierPublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.d = fake_dossier()
        self.a = fake_archive(self.d)
        self.t = fake_authority(self.d)

    def test_public_release_always_disabled_even_with_fake_receipts(self):
        result = assess_dossier_release(self.d, self.a, synthetic_authority=self.t)
        self.assertEqual(result["schema"], SCHEMA)
        self.assertFalse(result["eligible_for_publication"])
        self.assertFalse(result["private_synthetic_preview_ready"])
        self.assertFalse(result["production_authority_configured"])
        self.assertIn("independent-production-authority-not-implemented", names(result))

    def test_exact_synthetic_evidence_private_preview_only(self):
        result = assess_dossier_release(self.d, self.a, synthetic_authority=self.t,
                                        private_synthetic_preview=True)
        self.assertTrue(result["private_synthetic_preview_ready"])
        self.assertFalse(result["eligible_for_publication"])
        self.assertEqual(names(result), ["public-release-disabled-by-design"])
        self.assertEqual([x["record_id"] for x in result["synthetic_preview_link_policy"]],
                         [900001, 900002])

    def test_real_archive_record_id_cannot_be_relabelled_as_fictional(self):
        d = copy.deepcopy(self.d)
        d["sources"][0]["record_id"] = 4428
        d["sections"][0]["claims"][0]["source_record_ids"] = [4428]
        d["sections"][1]["claims"][0]["source_record_ids"] = [4428, 900002]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        result = assess_dossier_release(d, fake_archive(d), synthetic_authority=fake_authority(d),
                                        private_synthetic_preview=True)
        self.assertIn("nonfictional-preview-refused", names(result))
        self.assertFalse(result["private_synthetic_preview_ready"])

    def test_counterevidence_requires_navigable_source_clearance(self):
        d = copy.deepcopy(self.d)
        d["sections"][1]["claims"][0]["source_record_ids"] = [900001]
        d["sections"][1]["claims"][0]["counterevidence_ids"] = [900002]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        authority = fake_authority(d)
        authority["sources"]["900002"]["publisher_link"] = False
        result = assess_dossier_release(d, fake_archive(d), synthetic_authority=authority,
                                        private_synthetic_preview=True)
        self.assertIn("claim-has-uncleared-citation", names(result))
        self.assertFalse(result["private_synthetic_preview_ready"])

    def test_no_fake_authority_denies_preview(self):
        result = assess_dossier_release(self.d, self.a, private_synthetic_preview=True)
        self.assertIn("synthetic-review-packet-missing-or-invalid", names(result))
        self.assertFalse(result["private_synthetic_preview_ready"])

    def test_private_preview_requires_example_domain(self):
        d = copy.deepcopy(self.d)
        d["sources"][0]["url"] = "https://real-government.gov/release"
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        result = assess_dossier_release(d, fake_archive(d), synthetic_authority=fake_authority(d),
                                        private_synthetic_preview=True)
        self.assertIn("nonfictional-preview-refused", names(result))

    def test_fake_marker_mismatch_denies(self):
        t = copy.deepcopy(self.t); t["marker"] = "real-approval"
        self.assertIn("synthetic-review-version-drift", names(assess_dossier_release(
            self.d, self.a, synthetic_authority=t, private_synthetic_preview=True)))

    def test_modified_claim_invalidates_archive_and_review_digest(self):
        d = copy.deepcopy(self.d)
        d["sections"][0]["claims"][0]["text"] = "Altered synthetic assertion."
        result = assess_dossier_release(d, self.a, synthetic_authority=self.t,
                                        private_synthetic_preview=True)
        self.assertIn("dossier-contract-invalid", names(result))

    def test_draft_cannot_become_approved_preview(self):
        d = copy.deepcopy(self.d)
        d["editorial_status"] = "draft"
        d.pop("approval")
        report = assess_dossier_release(d, fake_archive(d),
                                        synthetic_authority=fake_authority(d),
                                        private_synthetic_preview=True)
        self.assertFalse(report["private_synthetic_preview_ready"])
        self.assertIn("dossier-not-approved", names(report))

    def test_archive_status_mismatch_refused(self):
        a = copy.deepcopy(self.a); a["editorial_status"] = "draft"
        result = assess_dossier_release(self.d, a, synthetic_authority=self.t,
                                        private_synthetic_preview=True)
        self.assertIn("archive-parity-or-digest-not-verified", names(result))

    def test_archive_digest_must_match_current_content(self):
        a = copy.deepcopy(self.a); a["content_sha256"] = "0" * 64
        self.assertIn("archive-parity-or-digest-not-verified", names(assess_dossier_release(
            self.d, a, synthetic_authority=self.t, private_synthetic_preview=True)))

    def test_archive_report_self_claiming_publishable_rejected(self):
        a = copy.deepcopy(self.a); a["eligible_for_publication"] = True
        self.assertIn("archive-parity-or-digest-not-verified", names(assess_dossier_release(
            self.d, a, synthetic_authority=self.t, private_synthetic_preview=True)))

    def test_archive_error_cannot_be_bypassed(self):
        a = copy.deepcopy(self.a); a["errors"] = [{"code": "source-original-body-drift"}]
        self.assertIn("archive-parity-or-digest-not-verified", names(assess_dossier_release(
            self.d, a, synthetic_authority=self.t, private_synthetic_preview=True)))

    def test_archive_record_id_change_rejected(self):
        a = copy.deepcopy(self.a); a["evidence"][0]["record_id"] = 900004
        self.assertIn("archive-evidence-invalid", names(assess_dossier_release(
            self.d, a, synthetic_authority=self.t, private_synthetic_preview=True)))

    def test_archive_boolean_record_id_rejected(self):
        a = copy.deepcopy(self.a); a["evidence"][0]["record_id"] = True
        self.assertIn("archive-evidence-invalid", names(assess_dossier_release(
            self.d, a, synthetic_authority=self.t, private_synthetic_preview=True)))

    def test_scraped_screened_out_source_needs_separate_human_review(self):
        t = copy.deepcopy(self.t); t["sources"]["900001"]["screening_reviewed"] = False
        report = assess_dossier_release(self.d, self.a, synthetic_authority=t,
                                        private_synthetic_preview=True)
        self.assertIn("source-screening-disposition-missing", names(report))
        self.assertFalse(report["private_synthetic_preview_ready"])

    def test_source_admission_not_model_pass(self):
        t = copy.deepcopy(self.t); t["sources"]["900002"]["admitted"] = False
        self.assertIn("source-human-admission-missing", names(assess_dossier_release(
            self.d, self.a, synthetic_authority=t, private_synthetic_preview=True)))

    def test_independent_metadata_use_required(self):
        t = copy.deepcopy(self.t); t["sources"]["900002"]["metadata_use"] = False
        self.assertIn("source-metadata-use-not-cleared", names(assess_dossier_release(
            self.d, self.a, synthetic_authority=t, private_synthetic_preview=True)))

    def test_publisher_link_without_origin_review_refused(self):
        t = copy.deepcopy(self.t); t["sources"]["900001"]["publisher_origin_reviewed"] = False
        report = assess_dossier_release(self.d, self.a, synthetic_authority=t,
                                        private_synthetic_preview=True)
        self.assertIn("publisher-origin-not-reviewed", names(report))
        self.assertIn("claim-citation-navigation-not-cleared", names(report))

    def test_local_record_link_not_allowed_without_body_use_review(self):
        t = copy.deepcopy(self.t)
        p = t["sources"]["900001"]
        p.update({"publisher_link": False, "local_record_link": True,
                  "local_record_body_use_cleared": False})
        report = assess_dossier_release(self.d, self.a, synthetic_authority=t,
                                        private_synthetic_preview=True)
        self.assertIn("local-record-body-use-not-cleared", names(report))
        self.assertIn("claim-has-uncleared-citation", names(report))

    def test_separately_cleared_local_record_link_can_support_synthetic_preview(self):
        t = copy.deepcopy(self.t)
        p = t["sources"]["900001"]
        p.update({"publisher_link": False, "local_record_link": True,
                  "local_record_body_use_cleared": True})
        report = assess_dossier_release(self.d, self.a, synthetic_authority=t,
                                        private_synthetic_preview=True)
        self.assertTrue(report["private_synthetic_preview_ready"])
        self.assertTrue(report["synthetic_preview_link_policy"][0]["local_record_link"])
        self.assertFalse(report["eligible_for_publication"])

    def test_unknown_action_field_rejected(self):
        t = copy.deepcopy(self.t)
        t["sources"]["900001"]["full_body_use"] = True
        self.assertIn("synthetic-source-decision-invalid", names(assess_dossier_release(
            self.d, self.a, synthetic_authority=t, private_synthetic_preview=True)))

    def test_fake_boolean_action_fails_strictly(self):
        t = copy.deepcopy(self.t)
        t["sources"]["900001"]["publisher_link"] = 1
        self.assertIn("synthetic-source-decision-invalid", names(assess_dossier_release(
            self.d, self.a, synthetic_authority=t, private_synthetic_preview=True)))

    def test_fake_editor_review_required(self):
        t = copy.deepcopy(self.t); t["editor_reviewed"] = False
        self.assertIn("synthetic-editor-review-missing", names(assess_dossier_release(
            self.d, self.a, synthetic_authority=t, private_synthetic_preview=True)))

    def test_claim_review_exact_set_required(self):
        t = copy.deepcopy(self.t); t["claim_ids"] = ["alpha-statement"]
        self.assertIn("synthetic-claim-review-incomplete", names(assess_dossier_release(
            self.d, self.a, synthetic_authority=t, private_synthetic_preview=True)))

    def test_history_proof_required_on_later_revision(self):
        d = copy.deepcopy(self.d)
        d["revision"] = 2
        d["changes"].append({"revision": 2, "changed_on": "2026-10-09",
                             "summary": "Second fictional revision.",
                             "affected_claim_ids": ["shared-framing"]})
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        t = fake_authority(d)
        result = assess_dossier_release(d, fake_archive(d), synthetic_authority=t,
                                        private_synthetic_preview=True)
        self.assertIn("prior-version-evidence-missing", names(result))

    def test_synthetic_result_does_not_include_authored_source_urls_or_prose(self):
        report = assess_dossier_release(self.d, self.a, synthetic_authority=self.t,
                                        private_synthetic_preview=True)
        content = json.dumps(report)
        for secret in ("https://example.org", "Fake Alpha original", "invented research", "synthetic-editor"):
            self.assertNotIn(secret, content)

    def test_missing_or_wrong_archive_type_fail_closed(self):
        for bad in (None, [], {}, "string"):
            report = assess_dossier_release(self.d, bad, synthetic_authority=self.t,
                                            private_synthetic_preview=True)
            self.assertFalse(report["private_synthetic_preview_ready"])
            self.assertIn("archive-report-missing-or-invalid", names(report))


class B12ToB21RealIntegrationTests(unittest.TestCase):
    """End-to-end on actual B1.2 code; all archives and sources are fictional."""

    def setUp(self):
        from tests.test_dossier_contract import approved
        from tests.test_dossier_sources import BODIES, fake_registry, synthetic_sqlite

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "fictional.db"
        synthetic_sqlite(self.path)
        self.registry = fake_registry()
        self.bodies = BODIES
        self.d = approved()
        for src in self.d["sources"]:
            src["stored_original_sha256"] = hashlib.sha256(
                self.bodies[src["record_id"]].encode("utf-8")
            ).hexdigest()
        self.d["approval"]["content_sha256"] = dossier_content_digest(self.d)
        self.t = fake_authority(self.d)
        self.t["claim_ids"] = sorted(
            claim["id"]
            for section in self.d["sections"]
            for claim in section["claims"]
        )

    def actual_archive(self):
        from core.dossier_sources import reconcile_dossier_sources
        return reconcile_dossier_sources(self.d, self.path, registry=self.registry)

    def review(self, archive=None, packet=None):
        return assess_dossier_release(
            self.d,
            self.actual_archive() if archive is None else archive,
            synthetic_authority=self.t if packet is None else packet,
            private_synthetic_preview=True,
        )

    def test_actual_b12_reconciliation_can_feed_private_b21_preview(self):
        archive = self.actual_archive()
        self.assertTrue(archive["archive_reconciled"])
        self.assertTrue(archive["holds"])
        self.assertEqual(archive["errors"], [])
        result = self.review(archive)
        self.assertTrue(result["private_synthetic_preview_ready"])
        self.assertFalse(result["eligible_for_publication"])
        self.assertFalse(result["production_authority_configured"])
        self.assertEqual(names(result), ["public-release-disabled-by-design"])

    def test_actual_sqlite_body_drift_blocks_private_preview(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE articles SET text_original=? WHERE id=?",
                       ("CHANGED FICTIONAL BODY " * 8, 900001))
            db.commit()
        archive = self.actual_archive()
        self.assertIn("source-original-body-drift",
                      [entry["code"] for entry in archive["errors"]])
        result = self.review(archive)
        self.assertFalse(result["private_synthetic_preview_ready"])
        self.assertIn("archive-parity-or-digest-not-verified", names(result))
        self.assertEqual(result["synthetic_preview_link_policy"], [])

    def test_actual_sqlite_source_disablement_blocks_private_preview(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE sources SET enabled=0 WHERE id=2")
            db.commit()
        archive = self.actual_archive()
        self.assertIn("source-not-public-eligible",
                      [entry["code"] for entry in archive["errors"]])
        self.assertFalse(self.review(archive)["private_synthetic_preview_ready"])

    def test_actual_negative_screen_requires_distinct_review(self):
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE articles SET passed_relevance=0 WHERE id=900001")
            db.commit()
        archive = self.actual_archive()
        self.assertTrue(archive["archive_reconciled"])
        self.assertIn("screening-not-selected-human-review",
                      [entry["code"] for entry in archive["holds"]])
        packet = copy.deepcopy(self.t)
        packet["sources"]["900001"]["screening_reviewed"] = False
        result = self.review(archive, packet)
        self.assertFalse(result["private_synthetic_preview_ready"])
        self.assertIn("source-screening-disposition-missing", names(result))
        self.assertFalse(result["eligible_for_publication"])

    def test_actual_b12_handoff_preserves_bytes_and_hides_publisher_text(self):
        initial = hashlib.sha256(self.path.read_bytes()).hexdigest()
        archive = self.actual_archive()
        result = self.review(archive)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), initial)
        self.assertFalse(Path(str(self.path) + "-wal").exists())
        self.assertFalse(Path(str(self.path) + "-shm").exists())
        serialized = json.dumps({"archive": archive, "release": result})
        for text in self.bodies.values():
            self.assertNotIn(text, serialized)
        self.assertNotIn("https://example.org/", json.dumps(result))
        self.assertFalse(result["eligible_for_publication"])


if __name__ == "__main__":
    unittest.main()
