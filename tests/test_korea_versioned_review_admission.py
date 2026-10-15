"""Synthetic signer review for Korea candidate metadata; never a real grant."""
import copy
import json
import unittest

from core import korea_versioned_review_admission as gate
from scripts import stage_korea_production_candidates as intake

REVIEWER_KEY = b"synthetic-reviewer-key-00000000000000001"
OWNER_KEY = b"synthetic-owner-key-0000000000000000001"
SOURCE = "korea-policy:156799901"


def packet(source=SOURCE):
    ident = source.partition(":")[2]
    title = "completely fabricated title"
    body = "completely fabricated original"
    text_sha = intake.digest(body.encode())
    doc_sha = intake.digest(b"fictional HWPX bytes")
    html_sha = intake.digest(b"fictional publisher HTML")
    day = "2026-10-15"
    version = intake.digest(intake.canonical({
        "source_identity": source, "source_url": intake.URL + ident,
        "published_date": day, "original_text_sha256": text_sha,
        "publisher_html_sha256": html_sha, "original_hwpx_sha256": doc_sha,
    }))
    row = {
        "candidate_version_sha256": version,
        "desk_id": "korea",
        "source_identity": source,
        "source_slug": intake.SOURCE,
        "institution_id": "kr_mnd",
        "publisher_institution_id": "kr_policy_briefing",
        "authority_tier": "B",
        "originality": "syndicated",
        "language_tag": "ko",
        "canonical_source_url": intake.URL + ident,
        "publisher_posted_date": day,
        "original_title_sha256": intake.digest(title.encode()),
        "original_text_sha256": text_sha,
        "publisher_html_sha256": html_sha,
        "original_hwpx_sha256": doc_sha,
        "first_seen_run": "38636466191-1",
        "editorial_exception": (
            "unresolved_2025_2026_excavation_year_issue_601"
            if ident == "156785161" else None),
        "disposition": "held_pending_exact_version_human_and_rights_review",
        "original_text_included": False,
        "original_title_included": False,
        "original_media_included": False,
        "approved_for_production": False,
        "approved_for_publication": False,
        "approved_for_model_or_email": False,
    }
    return {
        "schema": intake.SCHEMA,
        "source_git_commit": "a" * 40,
        "frozen_fourteen_ancestor": intake.FROZEN_14,
        "source_db_sha256": "b" * 64,
        "source_original_count": 1,
        "records": [row],
        "candidate_count": 1,
        "approved_count": 0,
        "public_body_count": 0,
        "production_import_enabled": False,
        "reviewer_identity_authenticated": False,
        "per_source_rights_granted": False,
        "private_custody_and_independent_restore_verified": False,
        "collection_window_qualified": False,
        "model_email_or_publication_authorized": False,
    }


def signed(p, *, disposition=gate.METADATA):
    doc = gate.blank(p, p["records"][0]["source_identity"])
    doc.update({
        "reviewer": "Synthetic Independent Reviewer",
        "reviewed_at_utc": "2026-10-15T16:00:00Z",
        "review_checks": {k: True for k in gate.CHECKS},
        "rights_basis": gate.RIGHTS,
        "rights_reference": "fictional-government-license-example",
        "disposition": disposition,
        "discrepancies": None,
    })
    reviewer = gate.reviewer_sign(doc, secret=REVIEWER_KEY)
    owner = gate.owner_blank(doc)
    owner.update({
        "owner": "Synthetic Project Owner",
        "decided_at_utc": "2026-10-15T17:00:00Z",
        "explicit_metadata_link_rehearsal_only": disposition == gate.METADATA,
    })
    return gate.owner_sign(reviewer, owner, secret=OWNER_KEY)


def check(p, review, reviewer_key=REVIEWER_KEY, owner_key=OWNER_KEY):
    return gate.verify(p, review, reviewer_key=reviewer_key,
                       owner_key=owner_key, as_of_utc="2026-10-15T18:00:00Z")


class KoreaSignedVersionReviewTests(unittest.TestCase):
    def test_blank_template_has_no_implicit_permissions(self):
        p = packet()
        doc = gate.blank(p, SOURCE)
        self.assertEqual(doc["disposition"], "hold")
        self.assertEqual(doc["review_checks"], {k: False for k in gate.CHECKS})
        self.assertFalse(any(doc[k] for k in (
            "original_body_use_authorized", "media_use_authorized",
            "model_or_email_authorized")))
        self.assertFalse(gate.owner_blank(doc)["production_import_authorized"])

    def test_distinct_keys_allow_only_metadata_disposable_rehearsal(self):
        p = packet()
        out = check(p, signed(p))
        self.assertTrue(out["metadata_only_disposable_db_rehearsal_candidate"])
        self.assertEqual(out["source_git_commit"], "a" * 40)
        self.assertEqual(out["candidate_version_sha256"],
                         p["records"][0]["candidate_version_sha256"])
        for field in (
            "production_rows_written", "source_body_or_media_authorized",
            "site_publication_authorized", "model_or_email_authorized",
            "rights_claim_authenticated_by_signature",
            "human_identity_verified_beyond_key_possession"):
            self.assertFalse(out[field])
        self.assertNotIn("completely fabricated", json.dumps(out))
        self.assertNotIn("reviewer", json.dumps(out))

    def test_signed_hold_stays_hold(self):
        p = packet()
        out = check(p, signed(p, disposition=gate.HOLD))
        self.assertFalse(out["metadata_only_disposable_db_rehearsal_candidate"])

    def test_reviewed_disputed_extraction_year_is_still_held(self):
        p = packet("korea-policy:156785161")
        with self.assertRaisesRegex(gate.AdmissionHold, "excavation"):
            check(p, signed(p))

    def test_owner_cannot_inherit_full_body_ai_or_public_site_rights(self):
        p = packet()
        for key in (
            "source_body_redistribution_authorized",
            "translation_authorized", "media_authorized",
            "production_import_authorized", "site_publication_authorized",
            "model_or_email_authorized",
        ):
            doc = signed(p)
            doc["owner"][key] = True
            doc = gate.owner_sign(doc["review"], doc["owner"], secret=OWNER_KEY)
            with self.subTest(key=key), self.assertRaises(gate.AdmissionHold):
                check(p, doc)

    def test_owner_and_reviewer_must_have_distinct_trusted_keys(self):
        p = packet()
        with self.assertRaises(gate.AdmissionHold):
            check(p, signed(p), reviewer_key=OWNER_KEY)
        with self.assertRaises(gate.AdmissionHold):
            check(p, signed(p), owner_key=REVIEWER_KEY)
        with self.assertRaises(gate.AdmissionHold):
            check(p, signed(p), reviewer_key=b"short")
        doc = signed(p)
        doc["reviewer_hmac_sha256"] = "f" * 64
        # Tampered key or nested payload never verifies as a real reviewer.
        with self.assertRaises(gate.AdmissionHold):
            check(p, doc)

    def test_stale_or_forged_candidate_identity_fails_even_if_resigned(self):
        p = packet()
        old = signed(p)
        p2 = copy.deepcopy(p)
        p2["source_git_commit"] = "c" * 40
        with self.assertRaises(gate.AdmissionHold):
            check(p2, old)
        p3 = copy.deepcopy(p)
        p3["records"][0]["original_text_sha256"] = "f" * 64
        with self.assertRaises(gate.AdmissionHold):
            check(p3, signed(p3))
        p4 = copy.deepcopy(p)
        p4["records"][0]["candidate_version_sha256"] = "f" * 64
        with self.assertRaises(gate.AdmissionHold):
            check(p4, signed(p4))

    def test_partial_human_rights_or_owner_signoff_cannot_admit(self):
        p = packet()
        for k in gate.CHECKS:
            reviewed = signed(p)
            reviewed["review"]["decision"]["review_checks"][k] = False
            reviewed = gate.owner_sign(gate.reviewer_sign(
                reviewed["review"]["decision"], secret=REVIEWER_KEY),
                reviewed["owner"], secret=OWNER_KEY)
            with self.subTest(k=k), self.assertRaises(gate.AdmissionHold):
                check(p, reviewed)
        seal = signed(p)
        seal["owner"]["explicit_metadata_link_rehearsal_only"] = False
        seal = gate.owner_sign(seal["review"], seal["owner"], secret=OWNER_KEY)
        with self.assertRaises(gate.AdmissionHold):
            check(p, seal)

    def test_seal_is_version_bound_time_ordered_and_cannot_self_authorize(self):
        p = packet()
        a = signed(p)
        a["owner"]["candidate_version_sha256"] = "f" * 64
        a = gate.owner_sign(a["review"], a["owner"], secret=OWNER_KEY)
        with self.assertRaises(gate.AdmissionHold):
            check(p, a)
        a = signed(p)
        a["owner"]["decided_at_utc"] = "2026-10-15T15:00:00Z"
        a = gate.owner_sign(a["review"], a["owner"], secret=OWNER_KEY)
        with self.assertRaises(gate.AdmissionHold):
            check(p, a)
        a = signed(p)
        a["review"]["decision"]["reviewed_at_utc"] = "2026-10-16T16:00:00Z"
        a = gate.owner_sign(gate.reviewer_sign(
            a["review"]["decision"], secret=REVIEWER_KEY),
            a["owner"], secret=OWNER_KEY)
        with self.assertRaises(gate.AdmissionHold):
            check(p, a)


if __name__ == "__main__":
    unittest.main()
