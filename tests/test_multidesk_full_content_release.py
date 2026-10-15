"""Synthetic tests for the full-content source, rights and human release gates."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from core import multidesk_full_content_release as m

URL = "https://www.mod.go.jp/j/press/news/fictional-reviewed-source.html"
LICENSE = "https://www.mod.go.jp/j/info/contents.html"
KEYS = {r: (r + "-offline-fixture-key-").encode().ljust(40, b"X")
        for r in ("rights", "source_fidelity", "document_integrity",
                  "bilingual", "editor", "fact_checker")}
REVIEWERS = {r: ["Test Reviewer " + r] for r in KEYS}
CONTENT = {
    "original_text": ("これは架空の政府資料です。 "*12).encode(),
    "original_pdf": (b"%PDF-1.7\n1 0 obj<</Type/Catalog>>endobj\n" +
                     b"fictitious complete document\n%%EOF"),
    "translation_en": ("This is a fictional translation of a source document; "
                       "it is for local contract testing and makes no actual "
                       "claims about Japan, its military, or its officials.\n").encode(),
    "analysis_en": ("This is a fictional IPR analyst review. It distinguishes "
                    "institutional claims from independently verified facts, "
                    "states its limitations and cites the exact original page.\n").encode(),
}


def fixture(kinds=("original_text",)):
    source = {
        "desk": "japan",
        "source_family": "jp_mod_news_ja",
        "source_identity": "jp_mod:/j/press/news/20261015-1",
        "source_git_commit": "a" * 40,
        "source_capture_sha256": "b" * 64,
        "official_url": URL,
        "published_date": "2026-10-15",
        "source_language": "ja",
        "publisher": "Japan Ministry of Defense",
    }
    works = []
    artifacts = {}
    for k in kinds:
        body = CONTENT[k]
        artifacts[k] = body
        works.append({
            "kind": k, "content_sha256": m.sha(body),
            "source_capture_sha256": source["source_capture_sha256"],
            "rights_basis": ("ipr_original_copyright" if k == "analysis_en"
                             else "per_item_official_license"),
            "rights_evidence_sha256": "c" * 64,
            "rights_evidence_url": (URL if k == "analysis_en" else LICENSE),
            "rights_scope": m.SCOPES[k],
            "third_party_assets_cleared": k == "original_pdf",
            "attribution_text": "From original ministry publication at " + URL,
            "language": source["source_language"] if k.startswith("original_") else "en",
            "citations_verified": k in ("translation_en", "analysis_en"),
        })
    bundle = {"schema": m.SCHEMA, "source": source, "works": works}
    return bundle, artifacts


def approvals(bundle):
    digest = m.sha(m.canonical(bundle))
    out = []
    for w in bundle["works"]:
        k = w["kind"]
        for role in sorted(m.REQUIRED_ROLES[k]):
            packet = {
                "schema": m.RECEIPT_SCHEMA,
                "bundle_sha256": digest,
                "source_git_commit": bundle["source"]["source_git_commit"],
                "source_capture_sha256": bundle["source"]["source_capture_sha256"],
                "source_identity": bundle["source"]["source_identity"],
                "kind": k,
                "content_sha256": w["content_sha256"],
                "role": role,
                "reviewer": "Test Reviewer " + role,
                "reviewed_at_utc": "2026-10-15T22:00:00Z",
            }
            out.append({**packet, "signature_hmac_sha256":
                        m.sign_for_test_or_offline_reviewer(packet, KEYS[role])})
    return out


def valid(bundle, artifacts, signed=None):
    return m.verify_bundle(
        bundle, artifacts, approvals(bundle) if signed is None else signed,
        role_secrets=KEYS, authorized_reviewers=REVIEWERS,
        source_verifier=lambda _source: True,
        rights_verifier=lambda _source, _work: True)


class FullContentReleaseContracts(unittest.TestCase):
    def test_permitted_original_text_with_independent_verifiers(self):
        bundle, artifacts = fixture()
        result = valid(bundle, artifacts)
        self.assertEqual(result["source_desk"], "japan")
        self.assertEqual(result["kinds"], ["original_text"])
        self.assertFalse(result["downstream_publication_performed"])

    def test_no_auto_publication_just_because_owner_approved_metadata(self):
        bundle, artifacts = fixture()
        with self.assertRaisesRegex(m.FullContentHold,
                                    "independent_source_and_rights_verifiers_not_wired"):
            m.verify_bundle(bundle, artifacts, approvals(bundle), role_secrets=KEYS)

    def test_missing_independent_source_validation_is_hold(self):
        bundle, artifacts = fixture()
        with self.assertRaisesRegex(m.FullContentHold,
                                    "original_source_capture_not_authenticated"):
            m.verify_bundle(bundle, artifacts, approvals(bundle), role_secrets=KEYS, authorized_reviewers=REVIEWERS,
                            source_verifier=lambda _: False,
                            rights_verifier=lambda *_: True)

    def test_missing_license_assessment_is_hold(self):
        bundle, artifacts = fixture()
        with self.assertRaisesRegex(m.FullContentHold,
                                    "publisher_or_editorial_rights_not_independently_verified"):
            m.verify_bundle(bundle, artifacts, approvals(bundle), role_secrets=KEYS, authorized_reviewers=REVIEWERS,
                            source_verifier=lambda _: True,
                            rights_verifier=lambda *_: False)

    def test_source_body_changed_refuses_even_with_signatures(self):
        bundle, artifacts = fixture()
        edited = dict(artifacts, original_text=artifacts["original_text"] + b"changed")
        with self.assertRaisesRegex(m.FullContentHold, "artifact_bytes_version_mismatch"):
            valid(bundle, edited)

    def test_change_source_capture_sha_refuses_signed_approvals(self):
        bundle, artifacts = fixture()
        signed = approvals(bundle)
        bundle["source"]["source_capture_sha256"] = "f" * 64
        for w in bundle["works"]:
            w["source_capture_sha256"] = "f" * 64
        with self.assertRaisesRegex(m.FullContentHold,
                                    "human_approval_source_version_mismatch"):
            valid(bundle, artifacts, signed)

    def test_reviewer_identity_must_be_from_independent_roster(self):
        bundle, artifacts = fixture()
        signed = approvals(bundle)
        signed[0]["reviewer"] = "Unauthorized Reviewer"
        signed[0]["signature_hmac_sha256"] = m.sign_for_test_or_offline_reviewer(
            m.signature_payload(signed[0]), KEYS[signed[0]["role"]])
        with self.assertRaisesRegex(m.FullContentHold,
                                    "signer_not_in_independent_reviewer_roster"):
            valid(bundle, artifacts, signed)

    def test_same_key_must_not_sign_rights_and_content_review(self):
        bundle, artifacts = fixture()
        repeated = dict(KEYS)
        repeated["source_fidelity"] = KEYS["rights"]
        with self.assertRaisesRegex(m.FullContentHold,
                                    "reviewer_keys_not_role_separated"):
            m.verify_bundle(bundle, artifacts, approvals(bundle),
                            role_secrets=repeated,
                            authorized_reviewers=REVIEWERS,
                            source_verifier=lambda _: True,
                            rights_verifier=lambda *_: True)

    def test_unprovisioned_reviewer_roster_is_hold(self):
        bundle, artifacts = fixture()
        with self.assertRaisesRegex(m.FullContentHold,
                                    "human_editorial_approval_material_missing"):
            m.verify_bundle(bundle, artifacts, approvals(bundle),
                            role_secrets=KEYS,
                            source_verifier=lambda _: True,
                            rights_verifier=lambda *_: True)

    def test_modified_approval_signature_is_hold(self):
        bundle, artifacts = fixture()
        signed = approvals(bundle)
        signed[0]["signature_hmac_sha256"] = "0" * 64
        with self.assertRaisesRegex(m.FullContentHold,
                                    "human_review_approval_signature_invalid"):
            valid(bundle, artifacts, signed)

    def test_original_pdf_requires_embedded_assets_rights(self):
        bundle, artifacts = fixture(("original_pdf",))
        bundle["works"][0]["third_party_assets_cleared"] = False
        with self.assertRaisesRegex(m.FullContentHold,
                                    "complete_binary_and_embedded_asset_permission_missing"):
            valid(bundle, artifacts)

    def test_pdf_format_required_even_after_rights_attestation(self):
        bundle, artifacts = fixture(("original_pdf",))
        artifacts["original_pdf"] = b"fictional not-a-pdf"
        bundle["works"][0]["content_sha256"] = m.sha(artifacts["original_pdf"])
        with self.assertRaisesRegex(m.FullContentHold,
                                    "original_document_not_a_complete_pdf"):
            valid(bundle, artifacts)

    def test_republish_full_document_without_ipr_copyright_licence(self):
        bundle, artifacts = fixture(("original_pdf",))
        bundle["works"][0]["rights_basis"] = "ipr_original_copyright"
        with self.assertRaisesRegex(m.FullContentHold,
                                    "complete_binary_and_embedded_asset_permission_missing"):
            valid(bundle, artifacts)

    def test_translation_cannot_inherit_link_only_authority(self):
        bundle, artifacts = fixture(("translation_en",))
        bundle["works"][0]["rights_scope"] = "outbound_official_url_only"
        with self.assertRaisesRegex(m.FullContentHold, "rights_scope_unapproved"):
            valid(bundle, artifacts)

    def test_translation_requires_independent_bilingual_and_editor(self):
        bundle, artifacts = fixture(("translation_en",))
        signed = [x for x in approvals(bundle) if x["role"] != "bilingual"]
        with self.assertRaisesRegex(m.FullContentHold,
                                    "necessary_human_work_review_missing"):
            valid(bundle, artifacts, signed)

    def test_translation_reviewer_cannot_self_edit(self):
        bundle, artifacts = fixture(("translation_en",))
        signed = approvals(bundle)
        for a in signed:
            if a["role"] == "editor":
                a["reviewer"] = "Test Reviewer bilingual"
                a["signature_hmac_sha256"] = m.sign_for_test_or_offline_reviewer(
                    m.signature_payload(a), KEYS[a["role"]])
        with self.assertRaisesRegex(m.FullContentHold,
                                    "independent_language_or_fact_check_missing"):
            valid(bundle, artifacts, signed)

    def test_analysis_needs_separate_fact_checker_editor(self):
        bundle, artifacts = fixture(("analysis_en",))
        valid(bundle, artifacts)
        missing = [a for a in approvals(bundle) if a["role"] != "fact_checker"]
        with self.assertRaisesRegex(m.FullContentHold,
                                    "necessary_human_work_review_missing"):
            valid(bundle, artifacts, missing)

    def test_analysis_must_be_independent_original_writing(self):
        bundle, artifacts = fixture(("analysis_en",))
        bundle["works"][0]["rights_basis"] = "per_item_official_license"
        with self.assertRaisesRegex(m.FullContentHold,
                                    "analysis_must_be_independent_ipr_authorship"):
            valid(bundle, artifacts)

    def test_analysis_without_checked_citations_is_held(self):
        bundle, artifacts = fixture(("analysis_en",))
        bundle["works"][0]["citations_verified"] = False
        with self.assertRaisesRegex(m.FullContentHold,
                                    "translation_or_analysis_evidence_missing"):
            valid(bundle, artifacts)

    def test_singapore_source_is_not_allowed_under_japan_license(self):
        bundle, artifacts = fixture()
        bundle["source"]["desk"] = "singapore"
        bundle["source"]["source_family"] = "sg_mindef_releases"
        with self.assertRaisesRegex(m.FullContentHold,
                                    "official_source_host_not_allowlisted"):
            valid(bundle, artifacts)

    def test_unlisted_source_family_is_never_implicitly_permitted(self):
        bundle, artifacts = fixture()
        bundle["source"]["source_family"] = "vn_unknown_policy"
        with self.assertRaisesRegex(m.FullContentHold, "source_family_not_approved"):
            valid(bundle, artifacts)

    def test_all_four_forms_can_be_validated_independently(self):
        b, a = fixture(tuple(sorted(m.KINDS)))
        out = valid(b, a)
        self.assertEqual(out["kinds"], sorted(m.KINDS))

    def test_staging_only_to_new_external_directory(self):
        b, a = fixture(("original_text", "translation_en", "analysis_en"))
        signed = approvals(b)
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "staged"
            out = m.stage_approved_bundle(b, a, signed,
                role_secrets=KEYS, authorized_reviewers=REVIEWERS,
                source_verifier=lambda _: True,
                rights_verifier=lambda *_: True,
                target_dir=target)
            self.assertFalse(out["downstream_publication_performed"])
            self.assertTrue((target / "japan").is_dir())
            site=list(target.glob("japan/*/index.html"))
            self.assertEqual(len(site),1)
            page=site[0].read_text(encoding="utf-8")
            self.assertIn("Unofficial IPR translation", page)
            self.assertIn("Independent IPR analysis", page)
            self.assertIn("noindex", page)
            self.assertFalse((target / "gh-pages").exists())

    def test_stage_existing_destination_is_refused_without_writing(self):
        b, a=fixture()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)
            before=sorted(p.name for p in path.iterdir())
            with self.assertRaisesRegex(m.FullContentHold,
                                        "staging_must_be_new_external_directory"):
                m.stage_approved_bundle(b,a,approvals(b),
                    role_secrets=KEYS, authorized_reviewers=REVIEWERS,source_verifier=lambda _:True,
                    rights_verifier=lambda *_:True,target_dir=path)
            self.assertEqual(before,sorted(p.name for p in path.iterdir()))

    def test_source_identity_accepts_kemhan_path_but_rejects_traversal(self):
        b,a=fixture()
        b["source"]["source_identity"] = (
            "kemhan:/2026/10/15/fictional-ministry-release.html")
        valid(b,a)
        b["source"]["source_identity"] = "kemhan:/../escape"
        with self.assertRaisesRegex(m.FullContentHold,
                                    "source_identity_not_canonical"):
            valid(b,a)

    def test_unapproved_extra_artifact_is_not_staged(self):
        b,a=fixture()
        a["unknown_photo"]=b"fictional private photo"
        with self.assertRaisesRegex(m.FullContentHold, "artifact_roster_invalid"):
            valid(b,a)

    def test_unsafe_control_characters_in_text_refused(self):
        b,a=fixture()
        a["original_text"]=a["original_text"] + b"\x00"
        b["works"][0]["content_sha256"]=m.sha(a["original_text"])
        with self.assertRaisesRegex(m.FullContentHold,
                                    "artifact_text_incomplete_or_unsafe"):
            valid(b,a)

    def test_emitted_receipt_does_not_reveal_source_or_document_text(self):
        b,a=fixture(("original_text","analysis_en"))
        output=valid(b,a)
        literal=json.dumps(output)
        self.assertNotIn("fictional",literal)
        self.assertNotIn("Japan Ministry of Defense",literal)
        self.assertFalse(output["downstream_publication_performed"])


if __name__ == "__main__":
    unittest.main()
