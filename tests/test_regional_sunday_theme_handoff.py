"""No-network owner-approved thematic Sunday integration contracts."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.regional_reviewed_evidence import sign_private_review
from core.regional_theme_handoff import (
    ThemeHandoffError, sign_choice, verify_choice,
)
from core.regional_theme_selector import propose
from scripts.regional_sunday_theme_preview import build_private_manuscript, _out_text
from scripts.sunday_briefs_auto_writer import choose_evidence, compose
from tests.test_regional_theme_selector import SECRET, candidate, answer, china_docket
from tests.test_regional_weekly_inventory import make, row
from tests.test_weekly_briefs_auto_writer import valid_manuscript, evidence

SAT, SUN = "2026-10-10", "2026-10-11"


def scenario(*, source_ids=(42, 47)):
    inv = make()
    raw = china_docket(inv)
    if 47 in source_ids:
        second = copy.deepcopy(raw["decisions"][0])
        sg = next(s for s in inv["production_evidence"] if s["id"] == 47)
        second.update(id=47, desk=sg["desk"], source_url=sg["source_url"],
                      published_date=sg["published_date"],
                      stored_text_sha256=sg["stored_text_sha256"])
        raw["decisions"].append(second)
    signed = sign_private_review(raw, inv, SECRET)
    themes = propose(inv, signed, SECRET,
                     model_tool=lambda *_: answer(candidate(source_ids)),
                     allow_model=True)
    return inv, signed, themes


def approve(inv, review, proposals):
    return sign_choice(inv, review, SECRET, proposals,
                       slug="regional-evidence-shift",
                       owner="IPR Editor-in-Chief", approved_on=SUN)


class ThemeSundayHandoffTests(unittest.TestCase):
    def test_two_desk_theme_requires_owner_signature(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        verified = verify_choice(inv, review, SECRET, proposals, choice)
        self.assertEqual(verified["selected_source_ids"], [42, 47])
        self.assertEqual(verified["represented_desks"], ["china", "singapore"])
        self.assertEqual(verified["permission"],
                         "private_no_send_themed_sunday_manuscript_trial_only")
        self.assertIs(verified["publication_authorized"], False)
        self.assertIs(verified["editor_email_authorized"], False)

    def test_single_desk_theme_stays_out_of_automatic_writer(self):
        inv, review, proposals = scenario(source_ids=(42,))
        with self.assertRaisesRegex(ThemeHandoffError, "2–10"):
            approve(inv, review, proposals)

    def test_owner_decision_cannot_replace_source_ids_or_thesis(self):
        inv, review, proposals = scenario()
        signed = approve(inv, review, proposals)
        cases = [
            lambda x: x["choice"].update(selected_source_ids=[47]),
            lambda x: x["choice"].update(approved_focus="A fabricated editorial thesis"),
            lambda x: x["choice"].update(editor_email_authorized=True),
            lambda x: x["choice"].update(permission="approved_for_publication"),
            lambda x: x.update(hmac_sha256="0" * 64),
        ]
        for edit in cases:
            changed = copy.deepcopy(signed)
            edit(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                verify_choice(inv, review, SECRET, proposals, changed)

    def test_proposal_alteration_or_wrong_review_key_fails_closed(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        manipulated = copy.deepcopy(proposals)
        manipulated["model_proposed_slate"]["candidates"][0]["thesis"] = (
            "A fabricated government initiative was operationally implemented.")
        with self.assertRaises(ValueError):
            verify_choice(inv, review, SECRET, manipulated, choice)
        with self.assertRaises(ValueError):
            verify_choice(inv, review, b"different-owner-key" * 3, proposals, choice)

    def test_changed_archived_source_blocks_old_focus(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        fresh = make(rows=[
            row(42, "china", text_original="Updated source body " * 45),
            row(47, "singapore")])
        with self.assertRaises(ValueError):
            verify_choice(fresh, review, SECRET, proposals, choice)

    def test_refuse_future_owner_date_and_unsupported_theme_slug(self):
        inv, review, proposals = scenario()
        for params in (
            {"slug": "invented-theme", "owner": "IPR Editor-in-Chief", "approved_on": SUN},
            {"slug": "regional-evidence-shift", "owner": "IPR Editor-in-Chief",
             "approved_on": "2026-10-12"},
        ):
            with self.subTest(params=params), self.assertRaises(ValueError):
                sign_choice(inv, review, SECRET, proposals, **params)

    def test_selected_writer_records_exactly_match_approved_ids(self):
        source_rows = [
            dict(id=42, desk_id="china", text_english="", text_original="A" * 400,
                 analyzed_at=None, is_significant=None, published_date="2026-10-08"),
            dict(id=47, desk_id="singapore", text_english="", text_original="B" * 400,
                 analyzed_at=None, is_significant=None, published_date="2026-10-08"),
            dict(id=99, desk_id="china", text_english="", text_original="C" * 400,
                 analyzed_at=None, is_significant=None, published_date="2026-10-09"),
        ]
        scaffold = {
            "week_start": "2026-10-04", "week_ending": SAT,
            "desks": ["china", "singapore"],
            "source_trail": [{"record_id": x["id"]} for x in source_rows],
        }
        with patch("scripts.sunday_briefs_auto_writer.read_only",
                   return_value=nullcontext(None)), patch(
                   "scripts.sunday_briefs_auto_writer.get_articles_for_desks",
                   return_value=source_rows), patch(
                   "scripts.sunday_briefs_auto_writer.trail_entry",
                   side_effect=lambda r: {"record_id": r["id"]}):
            selected = choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 47])
            self.assertEqual([r["id"] for r, _ in selected], [42, 47])
            with self.assertRaisesRegex(ValueError, "absent"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 777])
            with self.assertRaisesRegex(ValueError, "two desks"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 99])
            with self.assertRaisesRegex(ValueError, "unique"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 42])

    def test_composer_includes_approved_focus_only_in_optional_private_mode(self):
        inv, review, proposals = scenario()
        directive = verify_choice(inv, review, SECRET, proposals,
                                  approve(inv, review, proposals))
        written = valid_manuscript()
        # Test-only synthetic ids follow the existing writer fixture.
        directive = dict(directive, selected_source_ids=[1, 2])
        response = SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use", name="compose_editorial_draft",
                                     input=written)])
        recorded = []
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kwargs: (
            recorded.append(kwargs), nullcontext(
                SimpleNamespace(get_final_message=lambda: response)))[1]))
        scaffold = {
            "week_start": "2026-10-04", "week_ending": SAT,
            "desks": ["china", "singapore"], "source_trail": [],
        }
        notes = {
            1: {"analyst_synopsis": (
                    "The official institution reported a dated dialogue about "
                    "regional cooperation, with no evidence that it was implemented."),
                "accuracy_limitations": (
                    "This is an official announcement without independent implementation evidence.")},
            2: {"analyst_synopsis": (
                    "A second issuing institution presented an attributed account "
                    "of regional discussions; no joint operational result is established."),
                "accuracy_limitations": (
                    "The publisher statement alone does not demonstrate policy coordination.")},
        }
        with patch("scripts.sunday_briefs_auto_writer.choose_evidence",
                   return_value=evidence()) as selected:
            with self.assertRaisesRegex(ValueError, "exact owner-reviewed synopsis"):
                compose(scaffold, SAT, client=fake, selected_theme=directive)
            output = compose(scaffold, SAT, client=fake, selected_theme=directive,
                             reviewed_synopses=notes)
        self.assertEqual(selected.call_args.kwargs["selected_ids"], [1, 2])
        self.assertEqual(output["_private_owner_selected_production_ids"], [1, 2])
        self.assertEqual(output["_private_owner_selected_theme_slug"],
                         "regional-evidence-shift")
        self.assertIn(directive["approved_focus"],
                      recorded[0]["messages"][0]["content"])
        self.assertIn("EDITOR-REVIEWED ANALYST SYNOPSIS",
                      recorded[0]["messages"][0]["content"])
        self.assertIn(notes[1]["analyst_synopsis"],
                      recorded[0]["messages"][0]["content"])
        self.assertNotIn("A" * 300, recorded[0]["messages"][0]["content"])
        self.assertNotIn("B" * 300, recorded[0]["messages"][0]["content"])
        self.assertFalse("publication_authorized" in output)

    def test_one_owner_paid_model_call_only_even_on_bad_citations(self):
        inv, review, proposals = scenario()
        directive = verify_choice(inv, review, SECRET, proposals,
                                  approve(inv, review, proposals))
        directive = dict(directive, selected_source_ids=[1, 2])
        synopsis = {
            ident: {
                "analyst_synopsis": (
                    "The official institution reported a dated security discussion "
                    "with no independently verified policy implementation or outcome."),
                "accuracy_limitations": (
                    "The published account establishes only the issuer's statement, not the result."),
            } for ident in (1, 2)
        }
        bad = valid_manuscript()
        bad["citations"]["cross_desk_comparison"] = [1]
        response = SimpleNamespace(stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use",
                                     name="compose_editorial_draft", input=bad)])
        calls = []
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kwargs: (
            calls.append(kwargs), nullcontext(
                SimpleNamespace(get_final_message=lambda: response)))[1]))
        scaffold = {"week_start": "2026-10-04", "week_ending": SAT,
                    "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.sunday_briefs_auto_writer.choose_evidence",
                   return_value=evidence()):
            with self.assertRaisesRegex(ValueError, "both desks"):
                compose(scaffold, SAT, client=fake, selected_theme=directive,
                        reviewed_synopses=synopsis)
        self.assertEqual(len(calls), 1)

    def test_build_private_manuscript_cannot_call_writer_without_current_trail(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        sidecar = {"week_start": "2026-10-04", "week_ending": SAT,
                   "desks": ["china", "singapore"], "source_trail": [
                       {"record_id": 42}]}
        with patch("scripts.regional_sunday_theme_preview.prepare_scaffold",
                   return_value=sidecar), patch(
                   "scripts.regional_sunday_theme_preview.compose") as writer:
            with self.assertRaisesRegex(ValueError, "not present"):
                build_private_manuscript(
                    inventory=inv, signed_review=review,
                    proposal=proposals, choice=choice, secret=SECRET)
            writer.assert_not_called()

    def test_rehearsal_passes_only_signed_synopses_to_composer(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        sidecar = {"week_start": "2026-10-04", "week_ending": SAT,
                   "desks": ["china", "singapore"],
                   "source_trail": [{"record_id": 42}, {"record_id": 47}]}
        generated = {"_private_owner_selected_production_ids": [42, 47]}
        with patch("scripts.regional_sunday_theme_preview.prepare_scaffold",
                   return_value=sidecar), patch(
                   "scripts.regional_sunday_theme_preview.compose",
                   return_value=generated) as writer, patch(
                   "scripts.regional_sunday_theme_preview.render_packet",
                   return_value="PRIVATE DRAFT") as renderer:
            result = build_private_manuscript(
                inventory=inv, signed_review=review, proposal=proposals,
                choice=choice, secret=SECRET, client=Mock())
        self.assertIn("PRIVATE DRAFT", result)
        self.assertIn("NO EDITOR DELIVERY", result)
        renderer.assert_called_once()
        writer.assert_called_once()
        kwargs = writer.call_args.kwargs
        self.assertEqual(kwargs["selected_theme"]["selected_source_ids"], [42, 47])
        notes = kwargs["reviewed_synopses"]
        self.assertEqual(set(notes), {42, 47})
        self.assertTrue(all(len(v["analyst_synopsis"]) >= 65 for v in notes.values()))
        self.assertFalse(any("text_original" in v or "text_english" in v
                             for v in notes.values()))

    def test_preview_file_is_exclusive_private_and_unpublished(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "private-manuscript.txt"
            _out_text(dest, "PRIVATE UNSENT EDITORIAL PROOF\n")
            self.assertEqual(dest.read_text(), "PRIVATE UNSENT EDITORIAL PROOF\n")
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                _out_text(dest, "must not overwrite")

    def test_sunday_delivery_workflow_does_not_import_theme_module(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/sunday_briefs_editorial_handoff.yml"
                   ).read_text(encoding="utf-8")
        self.assertNotIn("regional_sunday_theme_preview", workflow)
        self.assertNotIn("--approved-theme", workflow)
        self.assertIn("scripts.sunday_editorial_handoff", workflow)


if __name__ == "__main__":
    unittest.main()
