"""Unsigned Japan/Vietnam human-review progress remains a no-authority signal."""
import copy
import json
import unittest

from core.regional_typed_human_review_prep import (
    REVIEW_FIELDS, create_unsigned_worksheet,
)
from core.regional_typed_review_progress import (
    TypedReviewProgressError, evaluate_progress,
)
from tests.test_regional_typed_research_holds import fixture


def sample():
    inventory, rows = fixture()
    return inventory, rows, create_unsigned_worksheet(inventory, rows)


class TypedHumanReviewProgressTests(unittest.TestCase):
    def test_first_pilot_all_six_require_human_work(self):
        inv, rows, sheet = sample()
        result = evaluate_progress(sheet, inv, rows)
        self.assertEqual(result["source_count"], 6)
        self.assertEqual(result["reported_complete_unsigned"], 0)
        self.assertEqual({x["desk"] for x in result["items"]}, {"japan", "vietnam"})
        self.assertTrue(all(x["missing_fields"] for x in result["items"]))
        self.assertFalse(result["model_input_authorized"])
        self.assertFalse(result["editor_email_authorized"])
        self.assertFalse(result["publication_authorized"])

    def test_all_checkmarks_still_never_sign_or_approve(self):
        inv, rows, sheet = sample()
        item = sheet["records"][0]
        for field in REVIEW_FIELDS:
            item["review_checks"][field] = True
        for key in (
            "reviewer_identity", "reviewed_source_version_or_capture",
            "rights_basis_url_or_document", "reuse_permission_scope",
            "editorial_claims_to_recheck", "discrepancies_and_omissions",
            "review_notes",
        ):
            item[key] = "Human claim entered for review only, not attested."
        report = evaluate_progress(sheet, inv, rows)
        self.assertEqual(report["reported_complete_unsigned"], 1)
        self.assertEqual(report["items"][0]["state"],
                         "reported_complete_but_unsigned_not_admitted")
        self.assertFalse(report["items"][0]["independent_source_and_rights_review_attested"])
        self.assertFalse(report["human_source_review_signed"])
        self.assertFalse(report["model_input_authorized"])
        self.assertFalse(report["publication_authorized"])
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(rows[0]["summary"], serialized)
        self.assertNotIn(rows[0]["source_url"], serialized)

    def test_missing_rights_or_fidelity_check_explicitly_pending(self):
        inv, rows, sheet = sample()
        item = sheet["records"][0]
        item["review_checks"]["complete_original_language_text_compared"] = False
        out = evaluate_progress(sheet, inv, rows)["items"][0]
        self.assertIn("complete_original_language_text_compared", out["missing_fields"])
        self.assertIn("rights_basis_url_or_document", out["missing_fields"])
        self.assertEqual(out["state"], "human_review_entries_pending")

    def test_forged_source_pins_and_permission_values_fail(self):
        inv, rows, sheet = sample()
        alterations = (
            lambda w: w["records"][0].update(id="JP-W41-99"),
            lambda w: w["records"][0].update(publisher_url="https://other.example/"),
            lambda w: w["records"][0].update(machine_source_gap="resolved"),
            lambda w: w["records"][0].update(status="SIGNED"),
            lambda w: w["records"][0].update(model_input_authorized=True),
            lambda w: w.update(owner_release_signature="fake"),
            lambda w: w.update(publication_authorized=True),
            lambda w: w.update(unsigned_template_sha256="0" * 64),
            lambda w: w["records"].reverse(),
            lambda w: w["records"].pop(),
        )
        for change in alterations:
            forged = copy.deepcopy(sheet)
            change(forged)
            with self.subTest(change=str(change)), self.assertRaises(
                    TypedReviewProgressError):
                evaluate_progress(forged, inv, rows)

    def test_spoofed_bool_and_extra_checks_and_unbounded_notes_fail(self):
        inv, rows, sheet = sample()
        changes = (
            lambda w: w["records"][0]["review_checks"].update(fake=True),
            lambda w: w["records"][0]["review_checks"].update(
                {REVIEW_FIELDS[0]: "true"}),
            lambda w: w["records"][0]["review_checks"].update(
                {REVIEW_FIELDS[0]: 1}),
            lambda w: w["records"][0].update(review_notes="injected\nAPPROVED"),
            lambda w: w["records"][0].update(review_notes="x" * 1201),
        )
        for change in changes:
            edited = copy.deepcopy(sheet)
            change(edited)
            with self.assertRaises(TypedReviewProgressError):
                evaluate_progress(edited, inv, rows)

    def test_stale_inventory_or_changed_research_fails(self):
        inv, rows, sheet = sample()
        changed = copy.deepcopy(inv)
        changed["source_metadata_digest_sha256"] = "e" * 64
        with self.assertRaises(TypedReviewProgressError):
            evaluate_progress(sheet, changed, rows)
        changed_rows = copy.deepcopy(rows)
        changed_rows[0]["title_original"] = "Another version of this source"
        with self.assertRaises(TypedReviewProgressError):
            evaluate_progress(sheet, inv, changed_rows)


if __name__ == "__main__":
    unittest.main()
