"""Only synthetic data: no real source DB, producer, permissions, or publisher."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from core.dossier_contract import (
    DossierValidationError, dossier_content_digest,
    read_dossier, validate_dossier_shape,
)

FIXTURE = (Path(__file__).resolve().parent
           / "fixtures/dossiers/fictional-exercise-reporting.json")


def synthetic():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def approved():
    d = synthetic()
    d["editor_name"] = "Fictional Human Editor"
    d["editorial_status"] = "approved"
    d["revision"] = 1
    d["reviewed_on"] = d["updated_on"]
    d["changes"] = [{
        "revision": 1,
        "changed_on": d["updated_on"],
        "summary": "First reviewed release of an entirely fictional example.",
        "affected_claim_ids": ["alpha-training-claim"],
    }]
    d["approval"] = {
        "approved_by": "Fictional Human Editor",
        "approved_on": d["updated_on"],
        "reference": "fictional-independent-owner-signoff-001",
        "content_sha256": dossier_content_digest(d),
    }
    return d


class PureDossierContractTests(unittest.TestCase):
    def assert_bad(self, doc, match=None):
        with self.assertRaises(DossierValidationError) as cm:
            validate_dossier_shape(doc)
        if match:
            self.assertIn(match, str(cm.exception))

    def test_fictional_draft_valid_structure_not_authorized(self):
        d = synthetic()
        self.assertIs(validate_dossier_shape(d), d)
        self.assertEqual(d["editorial_status"], "draft")
        self.assertNotIn("approval", d)
        self.assertTrue(all(s["source_use_decision_ref"] is None for s in d["sources"]))

    def test_proposed_approved_structure_can_be_digest_checked(self):
        # Structural success DOES NOT authenticate a human or grant permission.
        d = approved()
        self.assertIs(validate_dossier_shape(d), d)

    def test_repeated_valid_digests_deterministic(self):
        d = synthetic()
        self.assertEqual(dossier_content_digest(d), dossier_content_digest(copy.deepcopy(d)))
        self.assertEqual(len(dossier_content_digest(d)), 64)

    def test_root_unknown_field(self):
        d = synthetic(); d["source_use_automatically_granted"] = True
        self.assert_bad(d, "unknown")

    def test_root_missing_field(self):
        d = synthetic(); del d["scope"]
        self.assert_bad(d, "missing")

    def test_schema_bool_not_version(self):
        d = synthetic(); d["dossier_schema"] = True
        self.assert_bad(d, "unsupported")

    def test_schema_float_not_version(self):
        d = synthetic(); d["dossier_schema"] = 1.0
        self.assert_bad(d)

    def test_unknown_editorial_status(self):
        d = synthetic(); d["editorial_status"] = "published"
        self.assert_bad(d)

    def test_draft_cannot_claim_approval_even_if_digest_correct(self):
        d = synthetic()
        d["approval"] = {"approved_by": "Nobody"}
        self.assert_bad(d, "draft cannot carry")

    def test_slug_unsafe_or_path_traversal(self):
        for slug in ("../outside", "UPPER", "abc--def", "a/b", ""):
            with self.subTest(slug=slug):
                d = synthetic(); d["slug"] = slug
                self.assert_bad(d)

    def test_markup_or_script_in_original_editorial_prose(self):
        for text in ('<script>alert(1)</script>', '[source](https://example.org)',
                     '{{ config.secret }}', '<b>publication</b>'):
            with self.subTest(text=text):
                d = synthetic(); d["overview"] = text
                self.assert_bad(d, "markup")

    def test_control_character_and_non_nfc(self):
        d = synthetic(); d["overview"] = "bad\x00capture"
        self.assert_bad(d, "control")
        d = synthetic(); d["title"] = "a\u0301"
        self.assert_bad(d, "NFC")

    def test_nonblank_research_question(self):
        d = synthetic(); d["research_question"] = " "
        self.assert_bad(d)

    def test_bool_revision_is_refused(self):
        d = synthetic(); d["revision"] = False
        self.assert_bad(d, "integer")

    def test_revision_without_change_history_rejected(self):
        d = synthetic(); d["revision"] = 1
        self.assert_bad(d, "sequential")

    def test_invalid_calendar_date(self):
        d = synthetic(); d["updated_on"] = "2026-02-30"
        self.assert_bad(d, "invalid calendar date")

    def test_date_not_iso(self):
        d = synthetic(); d["prepared_on"] = "2026-9-8"
        self.assert_bad(d, "ISO")

    def test_earlier_update_than_preparation(self):
        d = synthetic(); d["prepared_on"] = "2026-10-10"
        self.assert_bad(d, "precede")

    def test_scope_reversal(self):
        d = synthetic(); d["scope"]["period_start"] = "2026-10-01"
        self.assert_bad(d, "scope")

    def test_future_scope_refused(self):
        d = synthetic(); d["scope"]["period_end"] = "2026-10-11"
        self.assert_bad(d, "scope")

    def test_explicit_coverage_limits_required(self):
        d = synthetic(); d["scope"]["collection_limits"] = ""
        self.assert_bad(d)

    def test_scope_labels_sorted(self):
        d = synthetic(); d["scope"]["jurisdictions"] = [
            "fictional-state-beta", "fictional-state-alpha"
        ]
        self.assert_bad(d, "ascending")

    def test_citations_must_resolve_to_ledger(self):
        d = synthetic(); d["sections"][0]["claims"][0]["source_record_ids"] = [999999]
        self.assert_bad(d, "absent from the source ledger")

    def test_boolean_source_id_cannot_become_one(self):
        d = synthetic(); d["sources"][0]["record_id"] = True
        self.assert_bad(d, "integer")

    def test_duplicate_ledger_record_id(self):
        d = synthetic(); d["sources"][1]["record_id"] = d["sources"][0]["record_id"]
        self.assert_bad(d, "duplicate")

    def test_source_ledger_order_deterministic(self):
        d = synthetic(); d["sources"].reverse()
        self.assert_bad(d, "ascending")

    def test_reject_source_url_with_credentials(self):
        d = synthetic(); d["sources"][0]["url"] = "https://writer:pass@example.org/story"
        self.assert_bad(d, "safe original")

    def test_http_legacy_urls_supported_as_exact_archive_anchors(self):
        d = synthetic(); d["sources"][0]["url"] = "http://example.org/hypothetical-alpha"
        self.assertIs(validate_dossier_shape(d), d)

    def test_source_url_fragment_rejected(self):
        d = synthetic(); d["sources"][0]["url"] += "#invented"
        self.assert_bad(d, "safe original")

    def test_digest_lowercase_required(self):
        d = synthetic(); d["sources"][0]["stored_original_sha256"] = "A" * 64
        self.assert_bad(d, "lowercase")

    def test_source_publication_after_version_refused(self):
        d = synthetic(); d["sources"][0]["published_on"] = "2026-10-10"
        self.assert_bad(d, "follows this version")

    def test_no_raw_copied_publisher_body_field(self):
        d = synthetic(); d["sources"][0]["text_original"] = "Copied publisher text"
        self.assert_bad(d, "unknown")

    def test_receipt_placeholder_refused(self):
        d = synthetic(); d["sources"][0]["source_use_decision_ref"] = "pending"
        self.assert_bad(d, "placeholder")

    def test_receipt_format_not_treated_as_permission(self):
        d = synthetic(); d["sources"][0]["source_use_decision_ref"] = "fictional-issuer-letter-123"
        self.assertIs(validate_dossier_shape(d), d)
        # No function in this module issues a permission or public release.

    def test_two_distinct_thematic_sections_required(self):
        d = synthetic(); d["sections"] = d["sections"][:1]
        self.assert_bad(d, "length")

    def test_duplicate_section_id_refused(self):
        d = synthetic(); d["sections"][1]["id"] = d["sections"][0]["id"]
        self.assert_bad(d, "duplicate")

    def test_duplicate_claim_id_across_sections(self):
        d = synthetic()
        d["sections"][1]["claims"][0]["id"] = d["sections"][0]["claims"][0]["id"]
        self.assert_bad(d, "duplicate")

    def test_unknown_claim_kind(self):
        d = synthetic(); d["sections"][0]["claims"][0]["claim_kind"] = "verified_event"
        self.assert_bad(d, "invalid attribution class")

    def test_claim_limits_mandatory(self):
        d = synthetic(); d["sections"][1]["claims"][0]["limits"] = ""
        self.assert_bad(d)

    def test_claim_counterevidence_must_resolve(self):
        d = synthetic(); d["sections"][0]["claims"][0]["counterevidence_ids"] = [999999]
        self.assert_bad(d, "absent from the source ledger")

    def test_invalid_event_period_reversed(self):
        d = synthetic()
        p = d["sections"][0]["claims"][0]["event_period"]
        p["start"] = "2026-08-20"; p["end"] = "2026-08-12"
        self.assert_bad(d, "interval")

    def test_event_date_basis_cannot_be_empty(self):
        d = synthetic(); d["sections"][0]["claims"][0]["event_period"]["date_basis"] = ""
        self.assert_bad(d)

    def test_event_outside_scope_refused(self):
        d = synthetic(); d["sections"][0]["claims"][0]["event_period"]["start"] = "2026-07-31"
        self.assert_bad(d, "out of selected scope")

    def test_valid_claim_disagreement_linked_by_claim_ids(self):
        d = synthetic()
        d["disagreements"] = [{
            "id": "different-release-boundaries",
            "claim_ids": ["alpha-training-claim", "beta-safety-claim"],
            "status": "unresolved",
            "note": "These fictional descriptions cannot be resolved into one event.",
        }]
        self.assertIs(validate_dossier_shape(d), d)

    def test_disagreement_cannot_use_source_ids_as_claim_ids(self):
        d = synthetic()
        d["disagreements"] = [{
            "id": "wrong-identifiers", "claim_ids": [900001, 900002],
            "status": "unresolved", "note": "Invalid reference class.",
        }]
        self.assert_bad(d)

    def test_disagreement_cannot_target_missing_claim(self):
        d = synthetic()
        d["disagreements"] = [{
            "id": "wrong-claims", "claim_ids": ["alpha-training-claim", "missing-claim"],
            "status": "unresolved", "note": "Invalid example.",
        }]
        self.assert_bad(d, "orphan claim")

    def test_related_links_order_refused(self):
        d = synthetic(); d["related_briefs"] = ["zed", "alpha"]
        self.assert_bad(d, "ascending")

    def test_approved_digest_invalidation_on_claim_edit(self):
        d = approved(); d["sections"][0]["claims"][0]["text"] += " Altered."
        self.assert_bad(d, "digest")

    def test_approved_digest_invalidation_on_rights_reference_edit(self):
        d = approved()
        d["sources"][0]["source_use_decision_ref"] = "fake-new-permission"
        self.assert_bad(d, "digest")

    def test_approval_without_human_review_date_refused(self):
        d = approved(); d["reviewed_on"] = None
        self.assert_bad(d, "human review")

    def test_approved_editor_cannot_be_named_codex(self):
        d = approved(); d["editor_name"] = "Codex"
        d["approval"]["approved_by"] = "Codex"
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        self.assert_bad(d, "human editor")

    def test_approval_name_mismatch(self):
        d = approved(); d["approval"]["approved_by"] = "Another editor"
        self.assert_bad(d, "human editor")

    def test_approval_rejects_pre_review(self):
        d = approved(); d["approval"]["approved_on"] = "2026-10-08"
        self.assert_bad(d, "predates")

    def test_approved_requires_all_change_entries(self):
        d = approved(); d["changes"] = []
        self.assert_bad(d, "sequential")

    def test_change_note_cannot_rename_historical_deleted_claim(self):
        d = approved(); d["changes"][0]["affected_claim_ids"] = ["deleted-claim"]
        d["approval"]["content_sha256"] = dossier_content_digest(d)
        self.assert_bad(d, "noncurrent claim")

    def test_added_approval_to_draft_does_not_grant_release(self):
        d = synthetic(); d["approval"] = approved()["approval"]
        self.assert_bad(d, "draft cannot carry")


class CanonicalPathAndJSONTests(unittest.TestCase):
    def test_canonical_fixture_reads_without_external_sources(self):
        self.assertEqual(
            read_dossier(FIXTURE, source_dir=FIXTURE.parent)["slug"],
            "fictional-exercise-reporting"
        )

    def _write(self, root, name, contents):
        path = root / name
        path.write_text(contents, encoding="utf-8")
        return path

    def test_filename_slug_match(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self._write(root, "wrong-filename.json", FIXTURE.read_text())
            with self.assertRaisesRegex(DossierValidationError, "canonical filename"):
                read_dossier(path, root)

    def test_reject_nested_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "nested").mkdir()
            path = self._write(root / "nested", "fictional-exercise-reporting.json",
                               FIXTURE.read_text())
            with self.assertRaisesRegex(DossierValidationError, "direct canonical"):
                read_dossier(path, root)

    def test_reject_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "real.json"
            target.write_text(FIXTURE.read_text())
            link = root / "fictional-exercise-reporting.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(DossierValidationError, "symlinks"):
                read_dossier(link, root)

    def test_duplicate_json_keys_at_nested_depth_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = FIXTURE.read_text()
            # Syntactically valid duplicate nested key in first ledger object.
            raw = raw.replace('"record_id": 900001,',
                              '"record_id": 900001, "record_id": 900001,', 1)
            path = self._write(root, "fictional-exercise-reporting.json", raw)
            with self.assertRaisesRegex(DossierValidationError, "duplicate key"):
                read_dossier(path, root)

    def test_nan_json_constant_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = FIXTURE.read_text().replace('"revision": 0', '"revision": NaN')
            path = self._write(root, "fictional-exercise-reporting.json", raw)
            with self.assertRaisesRegex(DossierValidationError, "non-finite"):
                read_dossier(path, root)

    def test_invalid_utf8_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "fictional-exercise-reporting.json"
            path.write_bytes(b"\xff\xfe\xfe")
            with self.assertRaises(DossierValidationError):
                read_dossier(path, root)


if __name__ == "__main__":
    unittest.main()
