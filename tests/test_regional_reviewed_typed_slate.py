"""Offline signed source review → mixed manual regional slate, no model/email."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from core.regional_reviewed_typed_slate import (
    ReviewedTypedSlateError, build_reviewed_mixed_context,
    validate_manual_mixed_theme,
)
from core.regional_typed_source_use_decision import (
    make_unsigned_decision, sign_owner_decision,
)
from core.regional_editorial_slate import validate_slate
from tests.test_regional_typed_research_holds import fixture
from tests.test_regional_theme_selector import signed, candidate, answer, SECRET
from tests.test_regional_typed_machine_receipts import (
    japan_receipt, queue_at, OCT5, OCT7,
)

TYPED_SECRET = b"synthetic-private-typed-slate-secret-not-real-at-least-32-bytes"


def assemble(*, approved=("JP-W41-01", "VN-MPS-1791199100"),
             have_japan=True, have_vietnam=True, blobs=None):
    inventory, rows = fixture()
    form = make_unsigned_decision(
        inventory, rows, owner="Test Owner", decided_on="2026-10-11")
    if blobs is None:
        blobs = {ident: ("Synthetic publisher bytes: " + ident).encode("utf-8")
                 for ident in approved}
    for item in form["decisions"]:
        if item["id"] not in approved:
            continue
        item.update({
            "decision": "private_analyst_synopsis_reviewed",
            "original_language_human_checked": True,
            "current_publisher_version_human_checked": True,
            "current_publisher_observation_sha256":
                hashlib.sha256(blobs[item["id"]]).hexdigest(),
            "current_publisher_observed_utc": "2026-10-11T10:00:00Z",
            "current_publisher_edition_reference":
                "Independent operator official source capture and issuer date check",
            "translation_and_attribution_cautions":
                "Publisher is making an official claim, not independent implementation proof.",
            "rights_basis_type": "explicit_official_reuse_terms",
            "rights_basis_reference":
                "https://www.mod.go.jp/en/notice.html reviewed manually in this test",
            "private_synopsis_use_scope_confirmed": True,
            "independent_analyst_synopsis":
                "The official issuer describes a factual event whose actual "
                "operational effects require independent corroboration.",
            "evidence_limitations":
                "This source is a current publisher edition; historical bytes may differ.",
        })
    seal = sign_owner_decision(form, inventory, rows, TYPED_SECRET)
    kw = {
        "japan_machine_receipt": japan_receipt() if have_japan else None,
        "vietnam_queues": [
            queue_at(OCT5, ("mps-vi:1791199100", "mps-vi:1791199677")),
            queue_at(OCT7, ("mps-vi:1791366010",)),
        ] if have_vietnam else None,
        "current_official_captures": blobs,
    }
    return inventory, rows, seal, kw


def build(*, approved=("JP-W41-01", "VN-MPS-1791199100")):
    inv, rows, seal, kw = assemble(approved=approved)
    return build_reviewed_mixed_context(
        inv, signed(inv), SECRET, rows, seal, TYPED_SECRET, **kw)


class MixedRegionalSlateTests(unittest.TestCase):
    def test_all_held_produces_production_only_no_false_japan_coverage(self):
        context = build(approved=())
        self.assertEqual(context["approved_typed_ids"], [])
        self.assertEqual(len(context["held_typed_ids"]), 6)
        self.assertEqual([x["id"] for x in context["reviewed_synopses"]], [42])
        states = {x["desk"]: x["state"] for x in
                  context["editorial_slate"]["coverage"]}
        self.assertEqual(states["japan"], "awaiting_validation")
        self.assertEqual(states["vietnam"], "awaiting_validation")
        self.assertFalse(context["model_input_authorized"])
        self.assertFalse(context["publication_authorized"])

    def test_signed_japan_and_vietnam_make_one_private_manual_slate(self):
        ctx = build()
        self.assertEqual(ctx["approved_typed_ids"],
                         ["JP-W41-01", "VN-MPS-1791199100"])
        slate = ctx["editorial_slate"]
        self.assertEqual({x["id"] for x in slate["evidence"]},
                         {42, "JP-W41-01", "VN-MPS-1791199100"})
        coverage = {x["desk"]: x["state"] for x in slate["coverage"]}
        self.assertEqual(coverage["japan"], "reviewable")
        self.assertEqual(coverage["vietnam"], "reviewable")
        self.assertEqual(coverage["philippines"], "collector_unavailable")
        self.assertIsNone(slate["provisional_lead"])
        self.assertEqual(slate["candidates"], [])
        self.assertIs(validate_slate(slate), slate)
        self.assertFalse(ctx["publisher_capture_bytes_included"])
        self.assertFalse(ctx["publisher_body_text_included"])
        self.assertFalse(ctx["model_input_authorized"])
        self.assertFalse(ctx["editor_email_authorized"])
        self.assertFalse(ctx["publication_authorized"])
        self.assertFalse(ctx["japan_vietnam_production_activated"])

    def test_manual_cross_desk_theme_can_cite_production_and_typed(self):
        ctx = build()
        response = answer(candidate([42, "JP-W41-01", "VN-MPS-1791199100"]))
        preview = validate_manual_mixed_theme(ctx, response)
        self.assertEqual(preview["candidate_analysis"][0]["represented_desks"],
                         ["china", "japan", "vietnam"])
        self.assertFalse(preview["candidate_analysis"][0]
                         ["requires_public_single_desk_exception"])
        self.assertTrue(preview["manual_only_no_model_was_invoked"])
        self.assertFalse(preview["publication_authorized"])
        self.assertEqual(preview["proposal"]["candidates"][0]["source_ids"],
                         [42, "JP-W41-01", "VN-MPS-1791199100"])

    def test_hidden_research_or_forged_numeric_identity_refused(self):
        ctx = build()
        for ids in (["JP-W41-02"], [47], [42, "JP-W41-02"],
                    [42, "VN-MPS-1791199677"], [42, True], [42, 42]):
            with self.subTest(ids=ids), self.assertRaises(ReviewedTypedSlateError):
                validate_manual_mixed_theme(ctx, answer(candidate(ids)))
        assert "JP-W41-02" in ctx["held_typed_ids"]

    def test_unsigned_forged_or_wrong_key_fails_before_offering(self):
        inv, rows, signed_typed, kw = assemble()
        tampered = copy.deepcopy(signed_typed)
        tampered["review"]["decisions"][0]["independent_analyst_synopsis"] = (
            "Unverified alteration " * 8)
        for value, secret in ((tampered, TYPED_SECRET),
                              (signed_typed, b"wrong-secret" * 5),
                              ({}, TYPED_SECRET)):
            with self.assertRaises(ReviewedTypedSlateError):
                build_reviewed_mixed_context(
                    inv, signed(inv), SECRET, rows, value, secret, **kw)

    def test_source_byte_mismatch_and_missing_bytes_fail_before_model(self):
        inv, rows, seal, kw = assemble()
        failures = (
            {},
            {"JP-W41-01": kw["current_official_captures"]["JP-W41-01"]},
            {**kw["current_official_captures"],
             "JP-W41-01": b"Wrong current issuer capture!"},
            {**kw["current_official_captures"], "JP-W41-02": b"unreviewed"},
            {**kw["current_official_captures"], "JP-W41-01": "not bytes"},
        )
        for blobs in failures:
            with self.subTest(keys=list(blobs)), self.assertRaises(
                    ReviewedTypedSlateError):
                build_reviewed_mixed_context(
                    inv, signed(inv), SECRET, rows, seal, TYPED_SECRET,
                    **dict(kw, current_official_captures=blobs))

    def test_historical_machine_receipts_required_for_each_selected_source(self):
        inv, rows, seal, kw = assemble(have_japan=False)
        with self.assertRaisesRegex(ReviewedTypedSlateError, "historical"):
            build_reviewed_mixed_context(
                inv, signed(inv), SECRET, rows, seal, TYPED_SECRET, **kw)
        inv, rows, seal, kw = assemble(have_vietnam=False)
        with self.assertRaisesRegex(ReviewedTypedSlateError, "historical"):
            build_reviewed_mixed_context(
                inv, signed(inv), SECRET, rows, seal, TYPED_SECRET, **kw)

    def test_mutated_machine_queue_or_snapshot_refused(self):
        inv, rows, seal, kw = assemble()
        broken = copy.deepcopy(kw)
        broken["vietnam_queues"][0]["records"][0]["content_sha256"] = "f" * 64
        with self.assertRaises(ReviewedTypedSlateError):
            build_reviewed_mixed_context(
                inv, signed(inv), SECRET, rows, seal, TYPED_SECRET, **broken)
        different = copy.deepcopy(inv)
        different["source_metadata_digest_sha256"] = "0" * 64
        with self.assertRaises(ReviewedTypedSlateError):
            build_reviewed_mixed_context(
                different, signed(inv), SECRET, rows, seal, TYPED_SECRET, **kw)

    def test_bad_manual_manifest_extra_authority_and_fabricated_theme_rejected(self):
        ctx = build()
        for edited in (
            {"candidates": [], "provisional_lead": None,
             "lead_rationale": "No lead", "publication_authorized": True},
            answer(candidate([42, "JP-W41-01"]), lead="not-an-option"),
            answer(candidate([42, "JP-W41-01"]), candidate([42, "JP-W41-01"],
                                                           slug="two"),
                   candidate([42, "JP-W41-01"], slug="three"),
                   candidate([42, "JP-W41-01"], slug="four")),
            answer(candidate([42, "JP-W41-01", "JP-W41-01"])),
        ):
            with self.assertRaises(ReviewedTypedSlateError):
                validate_manual_mixed_theme(ctx, edited)

    def test_no_original_pdf_or_html_bytes_leak_into_context_or_preview(self):
        inv, rows, seal, kw = assemble()
        report = build_reviewed_mixed_context(
            inv, signed(inv), SECRET, rows, seal, TYPED_SECRET, **kw)
        rendered = json.dumps(report, ensure_ascii=False)
        for blob in kw["current_official_captures"].values():
            self.assertNotIn(blob.decode("utf-8"), rendered)
        for entry in rows:
            self.assertNotIn(entry["summary"], rendered)
        self.assertFalse(report["historical_edition_fidelity_automatically_proven"])
        self.assertFalse(report["publisher_permission_independently_proven_by_software"])


if __name__ == "__main__":
    unittest.main()
