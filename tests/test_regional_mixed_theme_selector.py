"""No-network mock callbacks for separately owner-signed mixed regional themes."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import Mock

from core.regional_mixed_theme_selector import (
    MixedThemeApprovalError, make_unsigned_model_request, mixed_tool_schema,
    preview_authorized_prompt, prompt_for_reviewed_context,
    propose_mixed_themes, sign_explicit_model_request,
)
from core.regional_reviewed_typed_slate import build_reviewed_mixed_context
from tests.test_regional_reviewed_typed_slate import assemble, TYPED_SECRET
from tests.test_regional_theme_selector import signed, SECRET, candidate, answer

RUN_SECRET = b"synthetic-standalone-owner-model-run-HMAC-key-only-for-test"
RUN_ID = "17c94ad0214b4c65bc739875e6a309ff"
MODEL_ID = "synthetic.private-regional-theme-v1"


def prepared(*, approved=("JP-W41-01", "VN-MPS-1791199100")):
    inv, rows, typed_sealed, kwargs = assemble(approved=approved)
    sources = dict(
        inventory=inv,
        signed_production_review=signed(inv),
        production_key=SECRET,
        typed_research_rows=rows,
        signed_typed_decisions=typed_sealed,
        typed_key=TYPED_SECRET,
        **kwargs,
    )
    request = make_unsigned_model_request(
        sources, owner="Research and Editorial Owner",
        approved_on="2026-10-11", model_id=MODEL_ID, run_id=RUN_ID)
    return sources, request


def sealed(*, approved=("JP-W41-01", "VN-MPS-1791199100")):
    inputs, request = prepared(approved=approved)
    owner = sign_explicit_model_request(
        request, inputs, RUN_SECRET, owner_confirms_call=True)
    return inputs, owner


class RegionalMixedOwnerModelTests(unittest.TestCase):
    def test_default_request_is_unsigned_and_not_model_permission(self):
        inputs, req = prepared()
        self.assertFalse(req["owner_approved_private_model_call"])
        self.assertFalse(req["publication_authorized"])
        self.assertFalse(req["editor_email_authorized"])
        self.assertEqual(req["max_calls_per_invocation"], 1)
        self.assertTrue(req["no_global_replay_ledger"])
        with self.assertRaisesRegex(MixedThemeApprovalError, "explicit owner"):
            sign_explicit_model_request(req, inputs, RUN_SECRET)
        cb = Mock()
        with self.assertRaises(MixedThemeApprovalError):
            propose_mixed_themes(inputs, {"approval": req, "hmac_sha256": "f" * 64},
                                 RUN_SECRET, model_tool=cb, allow_model=True)
        cb.assert_not_called()

    def test_signed_preview_is_in_memory_and_zero_provider_calls(self):
        inputs, approval = sealed()
        preview = preview_authorized_prompt(inputs, approval, RUN_SECRET)
        self.assertTrue(preview["model_not_invoked"])
        self.assertEqual(preview["model_id"], MODEL_ID)
        self.assertIn("JP-W41-01", preview["prompt"])
        self.assertIn("VN-MPS-1791199100", preview["prompt"])
        self.assertIn("42", preview["prompt"])
        self.assertNotIn("JP-W41-02", preview["prompt"])
        self.assertIn("UNTRUSTED JSON", preview["prompt"])
        self.assertFalse(preview["publication_authorized"])
        for blob in inputs["current_official_captures"].values():
            self.assertNotIn(blob.decode("utf-8"), preview["prompt"])
        for research in inputs["typed_research_rows"]:
            self.assertNotIn(research["summary"], preview["prompt"])

    def test_model_tool_schema_accepts_mixed_ids_only(self):
        tool = mixed_tool_schema()
        self.assertFalse(tool["additionalProperties"])
        self.assertEqual(tool["properties"]["candidates"]["maxItems"], 3)
        items = tool["properties"]["candidates"]["items"]["properties"]["source_ids"]["items"]
        self.assertEqual(items["anyOf"][0]["type"], "integer")
        self.assertEqual(items["anyOf"][1]["type"], "string")

    def test_one_authorized_mock_callback_returns_nonbinding_mixed_candidates(self):
        inputs, permit = sealed()
        cb = Mock(return_value=answer(
            candidate([42, "JP-W41-01", "VN-MPS-1791199100"])))
        result = propose_mixed_themes(
            inputs, permit, RUN_SECRET, model_tool=cb, allow_model=True)
        cb.assert_called_once()
        prompt, schema, model_id = cb.call_args.args
        self.assertEqual(model_id, MODEL_ID)
        self.assertIn("JP-W41-01", prompt)
        self.assertEqual(len(schema["properties"]["candidates"]["items"]["properties"]
                             ["source_ids"]["items"]["anyOf"]), 2)
        self.assertEqual(result["schema"],
                         "ipr-regional-mixed-private-model-theme-preview/1")
        self.assertEqual(result["candidate_analysis"][0]["represented_desks"],
                         ["china", "japan", "vietnam"])
        self.assertFalse(result["publication_authorized"])
        self.assertFalse(result["editor_email_authorized"])
        self.assertTrue(result["manual_theme_approval_required"])
        self.assertTrue(result["model_proposal_not_owner_selected"])
        self.assertTrue(result["not_a_global_single_use_token"])

    def test_explicit_live_opt_in_and_mock_provider_are_both_required(self):
        inputs, permit = sealed()
        cb = Mock()
        with self.assertRaisesRegex(MixedThemeApprovalError, "no model invocation"):
            propose_mixed_themes(inputs, permit, RUN_SECRET, model_tool=cb)
        with self.assertRaisesRegex(MixedThemeApprovalError, "no model invocation"):
            propose_mixed_themes(inputs, permit, RUN_SECRET,
                                 model_tool=None, allow_model=True)
        cb.assert_not_called()

    def test_invalid_or_held_evidence_never_survives_mock_model(self):
        bad_ids = (
            ["JP-W41-02"], ["VN-MPS-1791366010"], [47],
            [42, True], [42, "JP-W41-99"], [42, 42],
            [42, "JP-W41-01", "JP-W41-01"],
        )
        inputs, permit = sealed()
        for ids in bad_ids:
            cb = Mock(return_value=answer(candidate(ids)))
            with self.subTest(ids=ids), self.assertRaises(
                    MixedThemeApprovalError):
                propose_mixed_themes(inputs, permit, RUN_SECRET,
                                     allow_model=True, model_tool=cb)
            cb.assert_called_once()

    def test_model_may_abstain_but_cannot_set_publication_flag(self):
        inputs, permit = sealed()
        result = propose_mixed_themes(
            inputs, permit, RUN_SECRET, model_tool=lambda *_: answer(),
            allow_model=True)
        self.assertEqual(result["candidate_analysis"], [])
        self.assertIsNone(result["validated_model_proposed_slate"]["provisional_lead"])
        poisoned = answer(candidate([42, "JP-W41-01"]))
        poisoned["publication_authorized"] = True
        with self.assertRaises(MixedThemeApprovalError):
            propose_mixed_themes(inputs, permit, RUN_SECRET,
                                 model_tool=lambda *_: poisoned, allow_model=True)

    def test_owner_signature_rejects_different_model_week_or_snapshot(self):
        inputs, req = prepared()
        signed_request = sign_explicit_model_request(
            req, inputs, RUN_SECRET, owner_confirms_call=True)
        for mutate in (
            lambda x: x["approval"].update(model_id="another.model-v1"),
            lambda x: x["approval"].update(prompt_sha256="0" * 64),
            lambda x: x["approval"].update(tool_schema_sha256="0" * 64),
            lambda x: x["approval"].update(run_id="0" * 32),
            lambda x: x["approval"].update(approved_on="2026-10-12"),
            lambda x: x["approval"].update(publication_authorized=True),
            lambda x: x["approval"].update(max_calls_per_invocation=2),
            lambda x: x.update(hmac_sha256="0" * 64),
        ):
            altered = copy.deepcopy(signed_request)
            mutate(altered)
            cb = Mock()
            with self.subTest(mutate=str(mutate)), self.assertRaises(
                    MixedThemeApprovalError):
                propose_mixed_themes(
                    inputs, altered, RUN_SECRET, model_tool=cb, allow_model=True)
            cb.assert_not_called()
        cb = Mock()
        changed = copy.deepcopy(inputs)
        changed["inventory"]["source_metadata_digest_sha256"] = "f" * 64
        with self.assertRaises(MixedThemeApprovalError):
            propose_mixed_themes(
                changed, signed_request, RUN_SECRET, model_tool=cb,
                allow_model=True)
        cb.assert_not_called()

    def test_short_or_reused_secret_cannot_authorize(self):
        inputs, unsigned = prepared()
        for secret in (b"short", SECRET, TYPED_SECRET):
            with self.subTest(length=len(secret)), self.assertRaises(ValueError):
                sign_explicit_model_request(
                    unsigned, inputs, secret, owner_confirms_call=True)

    def test_owner_rejects_broadened_or_malformed_unsigned_requests(self):
        bad = (
            lambda x: x.update(owner_approved_private_model_call=True),
            lambda x: x.update(editor_email_authorized=True),
            lambda x: x.update(purpose="any publisher text for public drafting"),
            lambda x: x.update(production_review_seal_sha256="b" * 64),
            lambda x: x.update(another_run=True),
            lambda x: x.update(prompt_sha256="0" * 64),
        )
        inputs, unsigned = prepared()
        for modify in bad:
            form = copy.deepcopy(unsigned)
            modify(form)
            with self.subTest(modify=str(modify)), self.assertRaises(ValueError):
                sign_explicit_model_request(
                    form, inputs, RUN_SECRET, owner_confirms_call=True)

    def test_run_identity_review_date_and_specific_model_are_required(self):
        inputs, _ = prepared()
        for kwargs in (
            {"model_id": ""}, {"model_id": "some model ID"},
            {"approved_on": "2026-10-09"}, {"approved_on": "2026-10-12"},
            {"run_id": "not a 32 byte hex nonce"}, {"owner": "  "},
        ):
            params = dict(owner="Editorial Owner", approved_on="2026-10-11",
                          model_id=MODEL_ID, run_id=RUN_ID)
            params.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                make_unsigned_model_request(inputs, **params)

    def test_changed_source_or_model_callback_input_mutation_is_refused(self):
        inputs, permit = sealed()
        corrupted = copy.deepcopy(inputs)
        corrupted["current_official_captures"]["JP-W41-01"] = b"different bytes"
        cb = Mock()
        with self.assertRaises(MixedThemeApprovalError):
            propose_mixed_themes(corrupted, permit, RUN_SECRET,
                                 model_tool=cb, allow_model=True)
        cb.assert_not_called()
        working = copy.deepcopy(inputs)
        def poison(prompt, schema, model):
            working["typed_research_rows"][0]["source_url"] = (
                "https://www.mod.go.jp/en/altered.html")
            return answer(candidate([42, "JP-W41-01"]))
        with self.assertRaises(MixedThemeApprovalError):
            propose_mixed_themes(working, permit, RUN_SECRET,
                                 model_tool=poison, allow_model=True)

    def test_provider_errors_are_never_retried_or_masked(self):
        inputs, permit = sealed()
        cb = Mock(side_effect=RuntimeError("provider offline/unavailable"))
        with self.assertRaisesRegex(RuntimeError, "provider offline/unavailable"):
            propose_mixed_themes(inputs, permit, RUN_SECRET,
                                 allow_model=True, model_tool=cb)
        cb.assert_called_once()

    def test_no_overlong_untrusted_metadata_bypasses_bounded_prompt(self):
        inputs, _ = prepared()
        context = build_reviewed_mixed_context(**inputs)
        context["reviewed_synopses"][0]["analyst_synopsis"] = "A" * 40001
        with self.assertRaises(MixedThemeApprovalError):
            prompt_for_reviewed_context(context)


if __name__ == "__main__":
    unittest.main()
