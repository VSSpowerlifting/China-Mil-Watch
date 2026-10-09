"""No-network, no-signature-material, no-model typed source-use contracts."""
from __future__ import annotations

import copy
import json
import unittest

from core.regional_typed_source_use_decision import (
    TypedSourceDecisionError, make_unsigned_decision,
    sign_owner_decision, verify_owner_decision,
)
from tests.test_regional_typed_research_holds import fixture

OWNER_KEY = b"test-only-typed-review-key-very-long-32-bytes-not-production"
SAT = "2026-10-10"
SUN = "2026-10-11"


def docket():
    inventory, rows = fixture()
    form = make_unsigned_decision(
        inventory, rows, owner="IPR Editorial Owner", decided_on=SUN)
    return inventory, rows, form


def approve(item):
    item.update({
        "decision": "private_analyst_synopsis_reviewed",
        "original_language_human_checked": True,
        "current_publisher_version_human_checked": True,
        "current_publisher_observation_sha256": "a" * 64,
        "current_publisher_observed_utc": "2026-10-11T12:30:00Z",
        "current_publisher_edition_reference":
            "Official publisher live bytes: private observation receipt October 11",
        "translation_and_attribution_cautions":
            "Review this issuer statement as an attribution, not third-party validation.",
        "rights_basis_type": "explicit_official_reuse_terms",
        "rights_basis_reference":
            "https://www.mod.go.jp/en/notice.html 2026 review of applicable terms",
        "private_synopsis_use_scope_confirmed": True,
        "independent_analyst_synopsis":
            "The ministry described a source-attributed development, with no "
            "independently verified implementation or third-party outcome.",
        "evidence_limitations":
            "Historical HTML edition equality is not established by a live-page capture.",
    })


class TypedSourceUseDecisionTests(unittest.TestCase):
    def test_real_six_sources_are_hold_by_default_even_if_signed(self):
        inventory, rows, form = docket()
        self.assertEqual(len(form["decisions"]), 6)
        self.assertTrue(all(item["decision"] == "hold" for item in form["decisions"]))
        signed = sign_owner_decision(form, inventory, rows, OWNER_KEY)
        out = verify_owner_decision(signed, inventory, rows, OWNER_KEY)
        self.assertEqual(out["source_ids_human_approved_in_signed_docket"], [])
        self.assertEqual(len(out["held_source_ids"]), 6)
        self.assertFalse(out["model_input_authorized"])
        self.assertFalse(out["dylan_editor_email_authorized"])
        self.assertFalse(out["publication_authorized"])
        self.assertTrue(out["future_selector_integration_required"])
        serialized = json.dumps(out)
        for entry in rows:
            self.assertNotIn(entry["source_url"], serialized)
            self.assertNotIn(entry["summary"], serialized)

    def test_one_explicit_owner_approved_synopsis_still_does_not_dispatch(self):
        inventory, rows, form = docket()
        item = next(x for x in form["decisions"] if x["id"] == "JP-W41-01")
        approve(item)
        signed = sign_owner_decision(form, inventory, rows, OWNER_KEY)
        out = verify_owner_decision(signed, inventory, rows, OWNER_KEY)
        self.assertEqual(out["source_ids_human_approved_in_signed_docket"],
                         ["JP-W41-01"])
        self.assertEqual(len(out["held_source_ids"]), 5)
        self.assertFalse(out["publisher_permission_independently_proven_by_software"])
        self.assertFalse(out["model_input_authorized"])
        self.assertFalse(out["japan_vietnam_production_activated"])

    def test_missing_observation_or_rights_or_original_language_refused(self):
        for change in (
            lambda item: item.update(current_publisher_observation_sha256=None),
            lambda item: item.update(current_publisher_observed_utc=None),
            lambda item: item.update(current_publisher_edition_reference=None),
            lambda item: item.update(original_language_human_checked=False),
            lambda item: item.update(private_synopsis_use_scope_confirmed=False),
            lambda item: item.update(rights_basis_type="attribution_footer_only"),
            lambda item: item.update(rights_basis_reference=None),
            lambda item: item.update(evidence_limitations="too short"),
            lambda item: item.update(independent_analyst_synopsis=""),
            lambda item: item.update(current_publisher_observed_utc="2026-10-12T00:00:00Z"),
        ):
            inv, rows, form = docket()
            approve(form["decisions"][0])
            change(form["decisions"][0])
            with self.subTest(change=str(change)), self.assertRaises(ValueError):
                sign_owner_decision(form, inv, rows, OWNER_KEY)

    def test_source_pin_and_authority_and_extra_body_field_refused(self):
        modifications = (
            lambda form: form["decisions"][0].update(publisher_url_sha256="b" * 64),
            lambda form: form["decisions"][0].update(historical_state_commit="f" * 40),
            lambda form: form["decisions"][0].update(id="JP-W41-99"),
            lambda form: form["decisions"][0].update(publication_authorized=True),
            lambda form: form["decisions"][0].update(publisher_body_copy_authorized=True),
            lambda form: form.update(publication_authorized=True),
            lambda form: form.update(does_not_authorize_model_dispatch=False),
            lambda form: form.update(purpose="publish"),
            lambda form: form["decisions"][0].update(article_body="malicious insertion"),
            lambda form: form["decisions"].reverse(),
            lambda form: form["decisions"].pop(),
        )
        for mutate in modifications:
            inv, rows, form = docket()
            mutate(form)
            with self.subTest(change=str(mutate)), self.assertRaises(ValueError):
                sign_owner_decision(form, inv, rows, OWNER_KEY)

    def test_signature_change_or_wrong_key_or_new_inventory_fails(self):
        inv, rows, form = docket()
        approve(form["decisions"][0])
        seal = sign_owner_decision(form, inv, rows, OWNER_KEY)
        for mutate in (
            lambda value: value["review"]["decisions"][0].update(
                independent_analyst_synopsis="Edited editorial claim after signing"),
            lambda value: value.update(hmac_sha256="f" * 64),
        ):
            changed = copy.deepcopy(seal)
            mutate(changed)
            with self.assertRaises(ValueError):
                verify_owner_decision(changed, inv, rows, OWNER_KEY)
        with self.assertRaises(ValueError):
            verify_owner_decision(seal, inv, rows, b"another-owner-key" * 4)
        changed_inv = copy.deepcopy(inv)
        changed_inv["source_metadata_digest_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_owner_decision(seal, changed_inv, rows, OWNER_KEY)

    def test_partial_week_and_undated_or_premature_signatures_fail(self):
        inv, rows, _ = docket()
        for date in ("2026-10-09", "2026-10-12", "2026/10/11"):
            with self.subTest(date=date), self.assertRaises(ValueError):
                make_unsigned_decision(
                    inv, rows, owner="Editorial Owner", decided_on=date)
        earlier = copy.deepcopy(inv)
        earlier["source_as_of"] = "2026-10-09"
        with self.assertRaises(ValueError):
            make_unsigned_decision(
                earlier, rows, owner="Editorial Owner", decided_on=SUN)

    def test_bad_snapshot_roster_or_secret_refused(self):
        inv, rows, form = docket()
        changed = copy.deepcopy(rows)
        changed[0]["source_url"] = "https://www.mod.go.jp/en/article/changed.html"
        with self.assertRaises(ValueError):
            sign_owner_decision(form, inv, changed, OWNER_KEY)
        with self.assertRaises(ValueError):
            sign_owner_decision(form, inv, rows, b"short")
        with self.assertRaises(ValueError):
            verify_owner_decision({}, inv, rows, OWNER_KEY)

    def test_hold_cannot_claim_human_permissions_or_review(self):
        inv, rows, form = docket()
        form["decisions"][0]["original_language_human_checked"] = True
        with self.assertRaises(ValueError):
            sign_owner_decision(form, inv, rows, OWNER_KEY)


if __name__ == "__main__":
    unittest.main()
