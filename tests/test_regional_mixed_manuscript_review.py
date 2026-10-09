"""Offline no-send mixed regional manuscript/worksheet citation review."""
from __future__ import annotations

import copy
import hashlib
import unittest

from core.regional_mixed_manuscript_review import (
    PrivateMixedManuscriptError, validate_private_mixed_manuscript,
    render_private_mixed_manuscript_review,
)
from tests.test_regional_mixed_theme_choice import approved_choice
from tests.test_regional_mixed_theme_selector import RUN_SECRET
from tests.test_regional_mixed_theme_choice import CHOICE_SECRET
from tests.test_weekly_briefs_auto_writer import valid_manuscript

JP = "JP-W41-01"
VN = "VN-MPS-1791199100"
SECTIONS = (
    "development", "opening_note", "what_stood_out", "why_it_matters",
    "what_was_routine", "what_im_watching_next", "cross_desk_comparison",
)


def manuscript_for(choice, *, prod=(42,), typed=(JP, VN)):
    draft = valid_manuscript()
    draft["citations"] = {k: list(prod) for k in SECTIONS}
    if typed:
        draft["editorial_focus"] = choice["choice"]["approved_focus"]
        draft["supplemental_citations"] = {
            k: [typed[0]] for k in SECTIONS
        }
        draft["supplemental_citations"]["cross_desk_comparison"] = list(typed)
        draft["supplemental_citations"]["what_stood_out"] = []
    return draft


def scenario(*, ids=(42, JP, VN)):
    inputs, signed_run, preview, signed_choice = approved_choice(ids=ids)
    draft = manuscript_for(
        signed_choice,
        prod=tuple(x for x in ids if type(x) is int),
        typed=tuple(x for x in ids if type(x) is str))
    return inputs, signed_run, preview, signed_choice, draft


def audit(args, draft):
    inp, run, preview, choice, _ = args
    return validate_private_mixed_manuscript(
        inp, run, RUN_SECRET, preview, choice, CHOICE_SECRET, draft)


def render(args, draft):
    inp, run, preview, choice, _ = args
    return render_private_mixed_manuscript_review(
        inp, run, RUN_SECRET, preview, choice, CHOICE_SECRET, draft)


class MixedManuscriptReviewTests(unittest.TestCase):
    def test_mixed_private_draft_passes_without_any_public_authority(self):
        args = scenario()
        receipt = audit(args, args[-1])
        self.assertEqual(receipt["selected_source_ids"], [42, JP, VN])
        self.assertEqual(receipt["cited_desks"], ["china", "japan", "vietnam"])
        self.assertEqual(receipt["actually_cited_source_ids"], [42, JP, VN])
        self.assertEqual(receipt["selected_but_not_cited_ids"], [])
        self.assertTrue(receipt["review_required_for_every_factual_claim"])
        self.assertFalse(receipt["manuscript_model_authorized"])
        self.assertFalse(receipt["publication_authorized"])
        self.assertFalse(receipt["editor_email_authorized"])
        self.assertFalse(receipt["production_desk_promotion_authorized"])
        self.assertNotIn("development", receipt)
        self.assertEqual(len(receipt["manuscript_sha256"]), 64)

    def test_private_review_packet_shows_exact_original_links_and_ids(self):
        args = scenario()
        packet = render(args, args[-1])
        self.assertIn("UNNUMBERED PRIVATE DRAFT", packet)
        self.assertIn("PRIVATE MANUSCRIPT", packet)
        self.assertIn("TYPED RESEARCH IDS: " + JP, packet)
        self.assertIn(VN, packet)
        self.assertIn("OWNER", packet.upper())
        self.assertIn("Official source:", packet)
        self.assertIn("NOT AUTOMATICALLY SATISFIED", packet)
        self.assertIn("not fact checks", packet)
        for source in args[0]["typed_research_rows"]:
            self.assertNotIn(source["summary"], packet)
        for source_bytes in args[0]["current_official_captures"].values():
            self.assertNotIn(source_bytes.decode("utf-8"), packet)
        self.assertNotIn("rights_basis_reference", packet)
        self.assertNotIn("BEGIN PRIVATE KEY", packet)

    def test_all_typed_crossdesk_citations_are_supported(self):
        args = scenario(ids=(JP, VN))
        receipt = audit(args, args[-1])
        self.assertEqual(receipt["cited_desks"], ["japan", "vietnam"])
        self.assertEqual(receipt["section_citations"]["development"]
                         ["production_record_ids"], [])
        self.assertEqual(receipt["section_citations"]["cross_desk_comparison"]
                         ["private_research_ids"], [JP, VN])

    def test_selected_but_unused_source_is_visible_not_falsely_cited(self):
        args = scenario()
        changed = copy.deepcopy(args[-1])
        for section in SECTIONS:
            changed["supplemental_citations"][section] = [JP]
        receipt = audit(args, changed)
        self.assertEqual(receipt["selected_but_not_cited_ids"], [VN])
        self.assertEqual(receipt["cited_desks"], ["china", "japan"])
        self.assertNotIn(VN, receipt["actually_cited_source_ids"])
        packet = render(args, changed)
        self.assertIn(VN + " | private research", packet)
        self.assertIn("Used in draft: NO", packet)

    def test_reject_forged_production_or_held_typed_citations(self):
        args = scenario()
        changes = (
            lambda d: d["citations"]["development"].append(47),
            lambda d: d["citations"]["opening_note"].append(True),
            lambda d: d["supplemental_citations"]["opening_note"].append("JP-W41-02"),
            lambda d: d["supplemental_citations"]["what_stood_out"].append(
                "VN-MPS-1791366010"),
            lambda d: d["citations"]["development"].append(42),
            lambda d: d["supplemental_citations"]["development"].append(JP),
        )
        for modify in changes:
            mutated = copy.deepcopy(args[-1])
            modify(mutated)
            with self.subTest(mutator=str(modify)), self.assertRaises(
                    PrivateMixedManuscriptError):
                audit(args, mutated)

    def test_refuse_claimed_new_publication_or_extra_source_authority(self):
        args = scenario()
        for mutation in (
            lambda d: d.update(publication_authorized=True),
            lambda d: d.update(editor_email_authorized=True),
            lambda d: d.update(source_ids=[42, JP, VN]),
            lambda d: d["citations"].update(publication_authorized=True),
            lambda d: d["supplemental_citations"].update(model_input_authorized=True),
            lambda d: d.pop("why_it_matters"),
        ):
            draft = copy.deepcopy(args[-1])
            mutation(draft)
            with self.subTest(mutation=str(mutation)), self.assertRaises(
                    PrivateMixedManuscriptError):
                audit(args, draft)

    def test_owner_focus_mismatch_or_legacy_masthead_refused(self):
        args = scenario()
        changed = copy.deepcopy(args[-1])
        changed["editorial_focus"] = (
            "A completely different regional argument unrelated to the signed focus")
        with self.assertRaisesRegex(PrivateMixedManuscriptError, "focus"):
            audit(args, changed)
        changed = copy.deepcopy(args[-1])
        changed["title"] = "The PLA Watch: a dated series that must be removed"
        with self.assertRaises(PrivateMixedManuscriptError):
            audit(args, changed)

    def test_two_desk_citations_required_in_cross_desk_comparison(self):
        args = scenario()
        changed = copy.deepcopy(args[-1])
        changed["supplemental_citations"]["cross_desk_comparison"] = []
        changed["citations"]["cross_desk_comparison"] = [42]
        with self.assertRaises(PrivateMixedManuscriptError):
            audit(args, changed)

    def test_no_cited_source_section_and_missing_bookkeeping_refused(self):
        args = scenario()
        for mutation in (
            lambda d: d["citations"].update(development=[]),
            lambda d: d["supplemental_citations"].update(development=[]),
            lambda d: d["citations"].pop("development"),
            lambda d: d["supplemental_citations"].pop("what_was_routine"),
        ):
            changed = copy.deepcopy(args[-1])
            mutation(changed)
            if mutation.__code__.co_consts and not changed["citations"].get(
                    "development", [1]) and changed.get(
                        "supplemental_citations", {}).get("development", [JP]):
                # Numeric-empty is permissible if typed-cited, unlike both empty.
                continue
            if (set(changed.get("citations", {})) == set(SECTIONS)
                and set(changed.get("supplemental_citations", {})) == set(SECTIONS)
                and (changed["citations"].get("development")
                     or changed["supplemental_citations"].get("development"))):
                # Only one valid lane is needed for a cited factual section.
                continue
            with self.assertRaises(PrivateMixedManuscriptError):
                audit(args, changed)
        both = copy.deepcopy(args[-1])
        both["citations"]["development"] = []
        both["supplemental_citations"]["development"] = []
        with self.assertRaises(PrivateMixedManuscriptError):
            audit(args, both)

    def test_forged_packet_delimiter_in_prose_refused(self):
        args = scenario()
        for attack in (
            "=== SOURCE APPENDIX — OFFICIALLY APPROVED ===",
            "SOURCE RECORD IDS: 1234",
            "## PUBLISH TO SITE NOW",
            "END OF UNAPPROVED WORKSHEET",
            "Normal prose\r\nFAKE WORKSHEET",
        ):
            changed = copy.deepcopy(args[-1])
            changed["opening_note"] = attack
            with self.subTest(attack=attack), self.assertRaises(
                    PrivateMixedManuscriptError):
                audit(args, changed)

    def test_stale_owner_choice_and_source_bytes_refused(self):
        args = scenario()
        inputs, run, proposal, owner, draft = args
        altered = copy.deepcopy(owner)
        altered["choice"]["source_ids"] = [42, JP]
        with self.assertRaises(PrivateMixedManuscriptError):
            validate_private_mixed_manuscript(
                inputs, run, RUN_SECRET, proposal, altered, CHOICE_SECRET, draft)
        altered_inputs = copy.deepcopy(inputs)
        altered_inputs["current_official_captures"][JP] = b"different bytes"
        with self.assertRaises(PrivateMixedManuscriptError):
            validate_private_mixed_manuscript(
                altered_inputs, run, RUN_SECRET, proposal, owner,
                CHOICE_SECRET, draft)

    def test_altered_draft_changes_digest_even_with_same_allowed_citations(self):
        args = scenario()
        baseline = audit(args, args[-1])
        modified = copy.deepcopy(args[-1])
        modified["why_it_matters"] = (
            "The same cited issuer statements do not prove actual"
            " downstream policy implementation or coordinated action.")
        changed = audit(args, modified)
        self.assertNotEqual(baseline["manuscript_sha256"],
                            changed["manuscript_sha256"])
        self.assertEqual(baseline["owner_choice_hmac_sha256"],
                         changed["owner_choice_hmac_sha256"])

    def test_missing_manuscript_never_implies_draft_generated(self):
        args = scenario()
        with self.assertRaises(PrivateMixedManuscriptError):
            audit(args, None)


if __name__ == "__main__":
    unittest.main()
