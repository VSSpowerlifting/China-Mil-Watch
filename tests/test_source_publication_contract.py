"""Synthetic-only S1 evidence projection and public-artifact audit contracts."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from core.source_publication_contract import (
    PRIVATE_SCHEMA, RECEIPT_SCHEMA, ProjectionContractError, original_digest,
    project_public_manifest, project_public_record, validate_private_record,
    validate_public_record, validate_public_manifest, validate_review_receipt,
)
from scripts.audit_source_projection import audit_synthetic_tree, main


BODY = "SYNTHETIC_PROTECTED_BODY_TOKEN_84931"
TITLE = "Fictional exercise statement"
URL = "https://example.org/dummy-fake-release"
SUMMARY = "SYNTHETIC_MODEL_SUMMARY_TOKEN_99001"


def record(rid=900001, body=BODY):
    return {
        "schema": PRIVATE_SCHEMA, "record_id": rid,
        "source_slug": "fictional_ministry", "institution_id": "imaginary_command",
        "language_tag": "en", "publisher_date": "2026-10-01", "captured_on": "2026-10-02",
        "source_url": URL, "title_original": TITLE, "text_original": body,
        "machine_summary": SUMMARY, "original_sha256": original_digest(TITLE, body),
    }


def receipt(**kwargs):
    data = {"schema": RECEIPT_SCHEMA, "source_slug": "fictional_ministry",
            "action": "full_body", "status": "approved", "reviewed_on": "2026-10-03",
            "reference": "fictional:review:100"}
    data.update(kwargs)
    return data


class S1PrivateProjectionTests(unittest.TestCase):
    def test_private_record_valid_and_unmodified(self):
        row = record()
        self.assertIs(validate_private_record(row), row)
        self.assertIn(BODY, row["text_original"])

    def test_private_unknown_key_rejected(self):
        with self.assertRaisesRegex(ProjectionContractError, "invalid_private_record_fields"):
            validate_private_record(dict(record(), debug_text="hidden"))

    def test_private_missing_field_rejected(self):
        row = record()
        del row["source_url"]
        with self.assertRaises(ProjectionContractError):
            validate_private_record(row)

    def test_private_boolean_record_id_rejected(self):
        with self.assertRaises(ProjectionContractError):
            validate_private_record(dict(record(), record_id=True))

    def test_private_duplicate_id_rejected_in_manifest(self):
        with self.assertRaisesRegex(ProjectionContractError, "duplicate_record_id"):
            project_public_manifest([record(), record()])

    def test_corrupted_digest_rejected_without_exposing_prose(self):
        with self.assertRaises(ProjectionContractError) as cm:
            project_public_record(dict(record(), text_original=BODY + " alteration"))
        self.assertNotIn(BODY, str(cm.exception))

    def test_invalid_date_rejected(self):
        with self.assertRaisesRegex(ProjectionContractError, "invalid_date"):
            validate_private_record(dict(record(), publisher_date="2026-02-30"))

    def test_capture_before_publication_rejected(self):
        with self.assertRaisesRegex(ProjectionContractError, "invalid_capture_date"):
            validate_private_record(dict(record(), captured_on="2026-09-30"))

    def test_unsafe_original_url_rejected(self):
        for value in ("http://example.org/a", "https://alice:secret@example.org/a",
                      "javascript:alert(1)", "https://example.org/a#fragment"):
            with self.subTest(value=value), self.assertRaises(ProjectionContractError):
                validate_private_record(dict(record(), source_url=value))

    def test_bad_source_identifier_rejected(self):
        with self.assertRaises(ProjectionContractError):
            validate_private_record(dict(record(), source_slug="some/source"))

    def test_body_optional_but_semantics_not_claimed_missing(self):
        pub = project_public_record(record(body=""))
        self.assertEqual(pub["text_access"], "no_captured_body")
        self.assertEqual(project_public_record(record())["text_access"],
                         "withheld_pending_rights_review")

    def test_public_allowlist_never_contains_originals(self):
        pub = project_public_record(record())
        blob = json.dumps(pub)
        for forbidden in (BODY, TITLE, URL, SUMMARY, "text_original", "source_url",
                          "machine_summary", "title_original"):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(pub["citation_path"], "record/900001.html")
        self.assertFalse(pub["original_url_public"])

    def test_approved_self_authored_receipt_does_not_grant_any_action(self):
        for action in ("full_body", "brief_quote", "link", "photo", "private_retention"):
            with self.subTest(action=action):
                pub = project_public_record(record(), [receipt(action=action)])
                self.assertNotIn(BODY, json.dumps(pub))
                self.assertFalse(pub["original_url_public"])
                self.assertEqual(pub["source_use"], "not_authorized_by_projection")

    def test_cross_source_receipt_rejected(self):
        with self.assertRaisesRegex(ProjectionContractError, "receipt_source_mismatch"):
            project_public_record(record(), [receipt(source_slug="another_source")])

    def test_malformed_receipt_rejected(self):
        with self.assertRaises(ProjectionContractError):
            validate_review_receipt(dict(receipt(), injected_permission=True))

    def test_unsafe_receipt_reference_rejected(self):
        with self.assertRaises(ProjectionContractError):
            validate_review_receipt(receipt(reference="raw MINDEF permission?\n"))

    def test_missing_review_has_no_permissions(self):
        self.assertEqual(project_public_record(record())["source_use"],
                         "not_authorized_by_projection")

    def test_projection_deterministic_regardless_of_input_order(self):
        a, b = record(900002), record(900001)
        x = project_public_manifest([a, b])
        y = project_public_manifest([b, a])
        self.assertEqual(x, y)
        self.assertEqual([i["record_id"] for i in x["records"]], [900001, 900002])
        self.assertEqual(len(x["public_projection_sha256"]), 64)
        self.assertFalse(x["eligible_for_publication"])

    def test_public_schema_forbids_extra_or_missing_keys(self):
        pub = project_public_record(record())
        with self.assertRaisesRegex(ProjectionContractError, "invalid_public_record_fields"):
            validate_public_record(dict(pub, text_original=BODY))
        del pub["original_sha256"]
        with self.assertRaises(ProjectionContractError):
            validate_public_record(pub)

    def test_public_schema_rejects_unauthenticated_display_claim(self):
        pub = project_public_record(record())
        with self.assertRaisesRegex(ProjectionContractError, "unverified_public_authorization"):
            validate_public_record(dict(pub, original_url_public=True))
        with self.assertRaisesRegex(ProjectionContractError, "unverified_public_authorization"):
            validate_public_record(dict(pub, source_use="approved"))

    def test_public_schema_rejects_false_citation_path(self):
        with self.assertRaises(ProjectionContractError):
            validate_public_record(dict(project_public_record(record()),
                                        citation_path="record/900000.html"))

    def test_manifest_digest_detects_tampering(self):
        manifest = project_public_manifest([record()])
        manifest["records"][0]["language_tag"] = "zh"
        with self.assertRaisesRegex(ProjectionContractError,
                                    "public_projection_digest_mismatch"):
            validate_public_manifest(manifest)

    def test_manifest_authorization_false_only(self):
        manifest = project_public_manifest([record()])
        manifest["eligible_for_publication"] = True
        with self.assertRaisesRegex(ProjectionContractError,
                                    "unverified_manifest_authorization"):
            validate_public_manifest(manifest)

    def test_empty_public_collection_does_not_publish(self):
        empty = project_public_manifest([])
        self.assertEqual(empty["record_count"], 0)
        self.assertFalse(empty["eligible_for_publication"])

    def test_manifest_does_not_leak_private_fields(self):
        payload = json.dumps(project_public_manifest([record()]))
        for hidden in (BODY, SUMMARY, TITLE, URL, "machine_summary", "text_original"):
            self.assertNotIn(hidden, payload)

    def test_invalid_receipt_collection_rejected(self):
        with self.assertRaises(ProjectionContractError):
            project_public_record(record(), reviews={"status": "approved"})


class S1SyntheticArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.tokens = self.root / "tokens.txt"
        self.tokens.write_text(BODY + "\n" + SUMMARY + "\n", encoding="utf-8")

    def run_audit(self):
        return audit_synthetic_tree(self.site, [BODY, SUMMARY])

    def test_clean_public_manifest_passes_but_is_not_publishable(self):
        (self.site / "corpus-index.json").write_text(
            json.dumps(project_public_manifest([record()])), encoding="utf-8")
        result = self.run_audit()
        self.assertEqual(result["counts"]["violations"], 0)
        self.assertFalse(result["eligible_for_publication"])

    def test_raw_html_leak_detected_without_printing_token(self):
        (self.site / "record.html").write_text("<p>" + BODY + "</p>", encoding="utf-8")
        result = self.run_audit()
        self.assertIn("synthetic_token_exposed", result["finding_codes"])
        self.assertNotIn(BODY, json.dumps(result))

    def test_escaped_html_leak_detected(self):
        token = "SYNTHETIC & <RESTRICTED> 33555"
        (self.site / "page.html").write_text("SYNTHETIC &amp; &lt;RESTRICTED&gt; 33555", encoding="utf-8")
        self.assertIn("synthetic_token_exposed",
                      audit_synthetic_tree(self.site, [token])["finding_codes"])

    def test_base64_encodings_leak_detected(self):
        import base64
        (self.site / "bundle.js").write_text(base64.b64encode(BODY.encode()).decode(), encoding="utf-8")
        self.assertIn("synthetic_token_exposed", self.run_audit()["finding_codes"])

    def test_nested_json_private_field_rejected(self):
        (self.site / "index.json").write_text(json.dumps({"records": [{"text_original": "dummy"}]}),
                                               encoding="utf-8")
        self.assertIn("private_field_in_json", self.run_audit()["finding_codes"])

    def test_duplicate_json_key_rejected(self):
        (self.site / "bad.json").write_text('{"ok":1,"ok":2}', encoding="utf-8")
        self.assertIn("invalid_json", self.run_audit()["finding_codes"])

    def test_unknown_extension_rejected(self):
        (self.site / "leak.dat").write_text("none", encoding="utf-8")
        self.assertIn("unknown_artifact_type", self.run_audit()["finding_codes"])

    def test_binary_is_explicitly_unscanned(self):
        (self.site / "cover.png").write_bytes(BODY.encode())
        result = self.run_audit()
        self.assertEqual(result["counts"]["binary_unscanned"], 1)
        self.assertNotEqual(result["schema"], "ipr-publication-approval")

    def test_symlink_rejected(self):
        fake = self.site / "fake.json"
        try:
            fake.symlink_to(self.tokens)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.assertIn("symlink", self.run_audit()["finding_codes"])

    def test_cli_clean_and_safe_report(self):
        (self.site / "index.html").write_text("fictional metadata only", encoding="utf-8")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(["--synthetic-only", "--tree", str(self.site),
                         "--synthetic-tokens-file", str(self.tokens)])
        self.assertEqual(code, 0)
        self.assertFalse(json.loads(stream.getvalue())["eligible_for_publication"])

    def test_cli_leak_fails_and_never_echoes_token(self):
        (self.site / "feed.xml").write_text(BODY, encoding="utf-8")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(["--synthetic-only", "--tree", str(self.site),
                         "--synthetic-tokens-file", str(self.tokens)])
        self.assertEqual(code, 1)
        self.assertNotIn(BODY, stream.getvalue())

    def test_cli_rejects_bad_sentinel_file_without_leak(self):
        self.tokens.write_text("short\n", encoding="utf-8")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(["--synthetic-only", "--tree", str(self.site),
                         "--synthetic-tokens-file", str(self.tokens)])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stream.getvalue())["error"], "audit_input_rejected")

    def test_no_mutation_of_synthetic_output(self):
        f = self.site / "record.html"
        f.write_text("<p>fictional</p>", encoding="utf-8")
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        self.run_audit()
        self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), digest)

    def test_absent_sentinels_rejected(self):
        with self.assertRaises(ProjectionContractError):
            audit_synthetic_tree(self.site, [])


if __name__ == "__main__":
    unittest.main()
