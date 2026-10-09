"""Offline exact-source owner thematic focus and private planning receipts."""
from __future__ import annotations

import copy
import json
import unittest

from core.regional_mixed_theme_choice import (
    MixedThemeChoiceError, make_unsigned_theme_choice,
    sign_owner_mixed_theme_choice, verify_owner_mixed_theme_choice,
    private_manuscript_planning_receipt,
)
from core.regional_mixed_theme_selector import propose_mixed_themes
from tests.test_regional_mixed_theme_selector import RUN_SECRET, sealed
from tests.test_regional_theme_selector import candidate, answer

CHOICE_SECRET = b"test-only-independent-mixed-theme-owner-selection-key-12345"


def selected_preview(*, ids=(42, "JP-W41-01", "VN-MPS-1791199100")):
    inputs, run = sealed()
    result = propose_mixed_themes(
        inputs, run, RUN_SECRET, allow_model=True,
        model_tool=lambda *_: answer(candidate(ids)))
    return inputs, run, result


def unsigned(inputs, run, preview, *, slug="regional-evidence-shift",
             owner="Indo-Pacific Record Editorial Owner", day="2026-10-11"):
    return make_unsigned_theme_choice(
        inputs, run, RUN_SECRET, preview,
        slug=slug, owner=owner, approved_on=day)


def approved_choice(*, ids=(42, "JP-W41-01", "VN-MPS-1791199100")):
    inputs, run, preview = selected_preview(ids=ids)
    choice = unsigned(inputs, run, preview)
    sealed_choice = sign_owner_mixed_theme_choice(
        choice, inputs, run, RUN_SECRET, preview, CHOICE_SECRET,
        owner_confirms_focus=True)
    return inputs, run, preview, sealed_choice


class MixedOwnerChoiceTests(unittest.TestCase):
    def test_explicit_multi_desk_human_choice_yields_no_send_receipt(self):
        inputs, run, preview, signature = approved_choice()
        checked = verify_owner_mixed_theme_choice(
            inputs, run, RUN_SECRET, preview, signature, CHOICE_SECRET)
        self.assertEqual(checked["theme_slug"], "regional-evidence-shift")
        self.assertEqual(checked["source_desks"], ["china", "japan", "vietnam"])
        self.assertEqual(checked["source_ids"],
                         [42, "JP-W41-01", "VN-MPS-1791199100"])
        self.assertFalse(checked["model_output_origin_independently_attested"])
        self.assertFalse(checked["private_manuscript_model_authorized"])
        out = private_manuscript_planning_receipt(
            inputs, run, RUN_SECRET, preview, signature, CHOICE_SECRET)
        self.assertEqual(out["schema"],
                         "ipr-regional-owner-mixed-private-manuscript-brief/1")
        self.assertEqual(out["represented_desks"], ["china", "japan", "vietnam"])
        self.assertFalse(out["manuscript_content_included"])
        self.assertFalse(out["manuscript_model_authorized"])
        self.assertFalse(out["editor_email_authorized"])
        self.assertFalse(out["publication_authorized"])
        self.assertEqual(len(out["owner_theme_choice_hmac_sha256"]), 64)

    def test_unsigned_form_is_never_itself_owner_approval(self):
        inputs, run, preview = selected_preview()
        form = unsigned(inputs, run, preview)
        self.assertNotIn("hmac_sha256", form)
        with self.assertRaisesRegex(MixedThemeChoiceError, "affirmative"):
            sign_owner_mixed_theme_choice(
                form, inputs, run, RUN_SECRET, preview, CHOICE_SECRET)
        with self.assertRaises(MixedThemeChoiceError):
            verify_owner_mixed_theme_choice(
                inputs, run, RUN_SECRET, preview, form, CHOICE_SECRET)

    def test_multi_desk_numeric_and_typed_sources_valid(self):
        inputs, run, preview, sig = approved_choice(ids=(42, "JP-W41-01"))
        out = private_manuscript_planning_receipt(
            inputs, run, RUN_SECRET, preview, sig, CHOICE_SECRET)
        self.assertEqual(out["selected_source_ids"], [42, "JP-W41-01"])
        self.assertEqual(out["represented_desks"], ["china", "japan"])

    def test_one_desk_or_one_source_or_too_many_sources_held(self):
        for ids in ((42,), ("JP-W41-01",), (42, 42)):
            with self.subTest(ids=ids):
                if ids == (42, 42):
                    # The preceding model response already rejects duplicate IDs.
                    with self.assertRaises(ValueError):
                        selected_preview(ids=ids)
                    continue
                inputs, run, preview = selected_preview(ids=ids)
                with self.assertRaisesRegex(MixedThemeChoiceError,
                                            "2–10|single-desk"):
                    unsigned(inputs, run, preview)

    def test_empty_candidate_slate_cannot_be_owner_selected(self):
        inputs, run = sealed()
        preview = propose_mixed_themes(
            inputs, run, RUN_SECRET, allow_model=True,
            model_tool=lambda *_: answer())
        with self.assertRaisesRegex(MixedThemeChoiceError, "precisely one"):
            unsigned(inputs, run, preview)

    def test_nonexistent_or_mismatched_candidate_rejected(self):
        inputs, run, preview = selected_preview()
        with self.assertRaises(MixedThemeChoiceError):
            unsigned(inputs, run, preview, slug="invented-editorial-theme")
        changed = copy.deepcopy(preview)
        changed["validated_model_proposed_slate"]["candidates"][0]["source_ids"] = [
            42, "JP-W41-02"]
        with self.assertRaises(MixedThemeChoiceError):
            unsigned(inputs, run, changed)

    def test_altered_model_proposal_or_forged_publication_flag_rejected(self):
        inputs, run, preview = selected_preview()
        for mod in (
            lambda d: d.update(publication_authorized=True),
            lambda d: d.update(model_id="someone-elses-model"),
            lambda d: d.update(candidate_analysis=[]),
            lambda d: d["validated_model_proposed_slate"]["candidates"][0]
                .update(thesis="Changed claim after model proposal."),
            lambda d: d["validated_model_proposed_slate"]["evidence"][0]
                .update(source_url="https://publisher.example/fake"),
            lambda d: d.update(owner_run_hmac_sha256="a" * 64),
        ):
            changed = copy.deepcopy(preview)
            mod(changed)
            with self.subTest(mutation=str(mod)), self.assertRaises(ValueError):
                unsigned(inputs, run, changed)

    def test_signed_owner_choice_tampering_and_wrong_key_refused(self):
        inputs, run, preview, sig = approved_choice()
        for mod in (
            lambda d: d["choice"].update(publication_authorized=True),
            lambda d: d["choice"].update(editor_email_authorized=True),
            lambda d: d["choice"].update(approved_focus="Entirely new claim"),
            lambda d: d["choice"].update(source_ids=[42, 47]),
            lambda d: d["choice"].update(source_desks=["china"]),
            lambda d: d["choice"].update(model_proposal_digest_sha256="0" * 64),
            lambda d: d.update(hmac_sha256="0" * 64),
            lambda d: d.update(unexpected_approval=True),
        ):
            altered = copy.deepcopy(sig)
            mod(altered)
            with self.subTest(mutation=str(mod)), self.assertRaises(ValueError):
                verify_owner_mixed_theme_choice(
                    inputs, run, RUN_SECRET, preview, altered, CHOICE_SECRET)
        with self.assertRaises(ValueError):
            verify_owner_mixed_theme_choice(
                inputs, run, RUN_SECRET, preview, sig,
                b"wrong-independent-owner-choice-key-long-enough-0000")

    def test_choice_signer_fails_extra_keys_false_rights_or_changed_ids(self):
        inputs, run, preview = selected_preview()
        form = unsigned(inputs, run, preview)
        for mod in (
            lambda d: d.update(publication_authorized=True),
            lambda d: d.update(model_output_origin_independently_attested=True),
            lambda d: d.update(private_manuscript_model_authorized=True),
            lambda d: d.update(extra_field="malicious data"),
            lambda d: d.update(source_ids=[42, "JP-W41-01"]),
            lambda d: d.update(source_basis=[]),
        ):
            corrupted = copy.deepcopy(form)
            mod(corrupted)
            with self.assertRaises(ValueError):
                sign_owner_mixed_theme_choice(
                    corrupted, inputs, run, RUN_SECRET, preview,
                    CHOICE_SECRET, owner_confirms_focus=True)

    def test_fourth_distinct_choice_secret_required(self):
        inputs, run, preview = selected_preview()
        form = unsigned(inputs, run, preview)
        for secret in (b"short", RUN_SECRET,
                       inputs["production_key"], inputs["typed_key"]):
            with self.subTest(key=secret[:4]), self.assertRaises(ValueError):
                sign_owner_mixed_theme_choice(
                    form, inputs, run, RUN_SECRET, preview,
                    secret, owner_confirms_focus=True)

    def test_choice_date_name_and_temporal_gates(self):
        inputs, run, preview = selected_preview()
        for day in ("2026-10-09", "2026-10-10", "2026-10-12", "2026/10/11"):
            with self.subTest(day=day), self.assertRaises(ValueError):
                unsigned(inputs, run, preview, day=day)
        for owner in ("", " ", "Not valid\nOwner"):
            with self.subTest(owner=owner), self.assertRaises(ValueError):
                unsigned(inputs, run, preview, owner=owner)

    def test_source_capture_drift_stops_owner_handoff(self):
        inputs, run, preview, sig = approved_choice()
        changed = copy.deepcopy(inputs)
        changed["current_official_captures"]["JP-W41-01"] = b"tampered"
        with self.assertRaises(ValueError):
            private_manuscript_planning_receipt(
                changed, run, RUN_SECRET, preview, sig, CHOICE_SECRET)
        changed = copy.deepcopy(inputs)
        changed["typed_research_rows"][0]["source_url"] = (
            "https://www.mod.go.jp/en/unexpected.html")
        with self.assertRaises(ValueError):
            verify_owner_mixed_theme_choice(
                changed, run, RUN_SECRET, preview, sig, CHOICE_SECRET)

    def test_signed_choice_cannot_survive_replaced_recommendation(self):
        inputs, run, preview, sig = approved_choice()
        changed = copy.deepcopy(preview)
        changed["validated_model_proposed_slate"]["candidates"][0]["why_now"] = (
            "A different narrative after source review and owner selection.")
        with self.assertRaises(ValueError):
            verify_owner_mixed_theme_choice(
                inputs, run, RUN_SECRET, changed, sig, CHOICE_SECRET)

    def test_no_original_body_or_rights_docs_in_private_receipt(self):
        inputs, run, preview, sig = approved_choice()
        receipt = private_manuscript_planning_receipt(
            inputs, run, RUN_SECRET, preview, sig, CHOICE_SECRET)
        packed = json.dumps(receipt, ensure_ascii=False)
        for blob in inputs["current_official_captures"].values():
            self.assertNotIn(blob.decode("utf-8"), packed)
        for row in inputs["typed_research_rows"]:
            self.assertNotIn(row["summary"], packed)
            self.assertNotIn(row["source_url"], packed)
        self.assertNotIn("rights_basis_reference", packed)


if __name__ == "__main__":
    unittest.main()
