"""No-network owner-approved thematic Sunday integration contracts."""
from __future__ import annotations

import copy
import json
import hashlib
import json
import os
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
from scripts.regional_sunday_theme_preview import (
    build_private_manuscript, preflight_theme, _out_text, run,
)
from scripts.sunday_briefs_auto_writer import choose_evidence, compose
from tests.test_regional_theme_selector import SECRET, candidate, answer, china_docket
from tests.test_regional_weekly_inventory import make, row
from tests.test_weekly_briefs_auto_writer import valid_manuscript, evidence
from tests.test_weekly_editorial_handoff import draft as friday_fixture

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
                 analyzed_at=None, is_significant=None, published_date="2026-10-08",
                 url="https://official.example/42", source_name="Publisher China",
                 title_original="Official China statement", source_language_tag="en"),
            dict(id=47, desk_id="singapore", text_english="", text_original="B" * 400,
                 analyzed_at=None, is_significant=None, published_date="2026-10-08",
                 url="https://official.example/47", source_name="Publisher Singapore",
                 title_original="Official Singapore statement", source_language_tag="en"),
            dict(id=99, desk_id="china", text_english="", text_original="C" * 400,
                 analyzed_at=None, is_significant=None, published_date="2026-10-09",
                 url="https://official.example/99", source_name="Publisher China",
                 title_original="Later China statement", source_language_tag="en"),
        ]
        scaffold = {
            "week_start": "2026-10-04", "week_ending": SAT,
            "desks": ["china", "singapore"],
            "source_trail": [{"record_id": x["id"]} for x in source_rows],
        }
        pins = {
            r["id"]: {
                "desk": r["desk_id"], "source_url": r["url"],
                "published_date": r["published_date"],
                "stored_text_sha256": hashlib.sha256(
                    r["text_original"].encode("utf-8")).hexdigest(),
                "source_name": r["source_name"],
                "title_original": r["title_original"],
                "language": r["source_language_tag"],
            }
            for r in source_rows
        }
        with patch("scripts.sunday_briefs_auto_writer.read_only",
                   return_value=nullcontext(None)), patch(
                   "scripts.sunday_briefs_auto_writer.get_articles_for_desks",
                   return_value=source_rows), patch(
                   "scripts.sunday_briefs_auto_writer.trail_entry",
                   side_effect=lambda r: {"record_id": r["id"]}):
            selected = choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 47],
                                       selected_pins={i: pins[i] for i in (42, 47)})
            self.assertEqual([r["id"] for r, _ in selected], [42, 47])
            with self.assertRaisesRegex(ValueError, "absent"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 777],
                                selected_pins={42: pins[42], 777: pins[47]})
            with self.assertRaisesRegex(ValueError, "two desks"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 99],
                                selected_pins={42: pins[42], 99: pins[99]})
            with self.assertRaisesRegex(ValueError, "unique"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 42],
                                selected_pins={42: pins[42]})
            with self.assertRaisesRegex(ValueError, "digest pins"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 47])
            wrong_digest = copy.deepcopy(pins)
            wrong_digest[42]["stored_text_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "drifted"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 47],
                                selected_pins={i: wrong_digest[i] for i in (42, 47)})
            wrong_url = copy.deepcopy(pins)
            wrong_url[47]["source_url"] = "https://attacker.invalid/copied"
            with self.assertRaisesRegex(ValueError, "drifted"):
                choose_evidence(scaffold, as_of=SAT, selected_ids=[42, 47],
                                selected_pins={i: wrong_url[i] for i in (42, 47)})


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

    def test_signed_theme_cannot_bypass_research_source_attestation(self):
        inv, review, proposals = scenario()
        directive = verify_choice(inv, review, SECRET, proposals,
                                  approve(inv, review, proposals))
        directive = dict(directive, selected_source_ids=[1, 2])
        sidecar = {"week_start": "2026-10-04", "week_ending": SAT,
                   "desks": ["china", "singapore"], "source_trail": []}
        payload = [{
            "id": "JP-W41-01", "desk": "japan",
            "status": "unapproved-source-linked-editorial-candidate",
            "source_url": "https://www.mod.go.jp/en/article/example.html",
        }]
        with patch("scripts.sunday_briefs_auto_writer.choose_evidence",
                   return_value=evidence()), patch(
                   "scripts.sunday_briefs_auto_writer.research_prompt") as research:
            with self.assertRaisesRegex(ValueError, "unattested supplemental"):
                compose(sidecar, SAT, client=Mock(), selected_theme=directive,
                        supplemental=payload,
                        reviewed_synopses={
                            ident: {"analyst_synopsis": "a" * 100,
                                    "accuracy_limitations": "a" * 40}
                            for ident in (1, 2)
                        })
            research.assert_not_called()

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

    def test_complete_private_manuscript_flow_real_writer_and_renderer_no_network(self):
        # Exercises signed source review, thematic HMAC, real Sunday composer,
        # exact stored-body digest checks, and immutable appendix renderer.
        # The production DB, Claude provider and SMTP are mocked ONLY here.
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        scaffold = friday_fixture()
        scaffold["week_start"] = "2026-10-04"
        scaffold["week_ending"] = SAT
        id_map = {1: 42, 2: 47}
        for item in scaffold["source_trail"]:
            ident = id_map[item["record_id"]]
            item.update(record_id=ident, date="2026-10-08",
                        source="Official publisher",
                        title="An original headline",
                        title_original="An original headline",
                        lang="en",
                        url="https://official.example/" + str(ident))
        actual_rows = [dict(row(42, "china"), title_english=""),
                       dict(row(47, "singapore"), title_english="")]
        by_id = {item["record_id"]: item for item in scaffold["source_trail"]}
        original = valid_manuscript()
        for field, ids in original["citations"].items():
            original["citations"][field] = [id_map[i] for i in ids]
        record = []
        response = SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(
                type="tool_use", name="compose_editorial_draft",
                input=original)],
        )
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kwargs:
            (record.append(kwargs), nullcontext(SimpleNamespace(
                get_final_message=lambda: response)))[1]))
        with patch("scripts.regional_sunday_theme_preview.prepare_scaffold",
                   return_value=scaffold), patch(
                   "scripts.sunday_briefs_auto_writer.read_only",
                   return_value=nullcontext(None)), patch(
                   "scripts.sunday_briefs_auto_writer.get_articles_for_desks",
                   return_value=actual_rows), patch(
                   "scripts.sunday_briefs_auto_writer.trail_entry",
                   side_effect=lambda source: by_id[source["id"]]), patch(
                   "scripts.sunday_editorial_handoff.send_packet") as mail:
            text = build_private_manuscript(
                inventory=inv, signed_review=review, proposal=proposals,
                choice=choice, secret=SECRET, client=fake)
        self.assertIn("PRIVATE OWNER-SELECTED THEMATIC REHEARSAL", text)
        self.assertIn("NO EDITOR DELIVERY", text)
        self.assertIn("source", text.lower())
        self.assertIn("Record 42", text)
        self.assertIn("Record 47", text)
        self.assertEqual(len(record), 1)
        prompt = record[0]["messages"][0]["content"]
        self.assertIn("EDITOR-REVIEWED ANALYST SYNOPSIS", prompt)
        self.assertNotIn("Original reported wording " * 10, prompt)
        self.assertIn("42, 47", prompt)
        mail.assert_not_called()

    def test_rehearsal_passes_only_signed_synopses_to_composer(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        sidecar = {"week_start": "2026-10-04", "week_ending": SAT,
                   "desks": ["china", "singapore"],
                   "source_trail": [{"record_id": 42}, {"record_id": 47}]}
        generated = {"_private_owner_selected_production_ids": [42, 47]}
        with patch("scripts.regional_sunday_theme_preview.prepare_scaffold",
                   return_value=sidecar), patch(
                   "scripts.regional_sunday_theme_preview.choose_evidence",
                   return_value=[({"id": 42}, "verified"), ({"id": 47}, "verified")]), patch(
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

    def test_no_model_audit_checks_exact_source_pins_and_never_calls_writer(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        sidecar = {"week_start": "2026-10-04", "week_ending": SAT,
                   "desks": ["china", "singapore"],
                   "source_trail": [{"record_id": 42}, {"record_id": 47}]}
        with patch("scripts.regional_sunday_theme_preview.prepare_scaffold",
                   return_value=sidecar), patch(
                   "scripts.regional_sunday_theme_preview.choose_evidence",
                   return_value=[({"id": 42}, "read"), ({"id": 47}, "read")]) as check, patch(
                   "scripts.regional_sunday_theme_preview.compose") as writer, patch(
                   "scripts.sunday_editorial_handoff.send_packet") as mail:
            receipt, approved, _scaffold, notes = preflight_theme(
                inventory=inv, signed_review=review, proposal=proposals,
                choice=choice, secret=SECRET)
            self.assertEqual(check.call_count, 1)
            self.assertEqual(check.call_args.kwargs["selected_ids"], [42, 47])
            self.assertEqual(set(check.call_args.kwargs["selected_pins"]), {42, 47})
            writer.assert_not_called()
            mail.assert_not_called()
        self.assertEqual(receipt["schema"],
                         "ipr-regional-private-sunday-rehearsal-preflight/1")
        self.assertEqual(receipt["selected_source_ids"], [42, 47])
        self.assertFalse(receipt["model_called"])
        self.assertFalse(receipt["editor_email_authorized"])
        self.assertFalse(receipt["publication_authorized"])
        self.assertTrue(receipt["source_audit_only_not_a_reusable_model_authorization"])
        self.assertNotIn("analyst_synopsis", json.dumps(receipt))
        self.assertEqual(len(receipt["reviewed_source_pins_sha256"]), 64)
        self.assertEqual(approved["represented_desks"], ["china", "singapore"])
        self.assertEqual(set(notes), {42, 47})

    def test_no_model_audit_refuses_missing_current_source_before_any_writer(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        sidecar = {"source_trail": [{"record_id": 42}]}
        with patch("scripts.regional_sunday_theme_preview.prepare_scaffold",
                   return_value=sidecar), patch(
                   "scripts.regional_sunday_theme_preview.choose_evidence") as source, patch(
                   "scripts.regional_sunday_theme_preview.compose") as writer:
            with self.assertRaisesRegex(ValueError, "not present"):
                preflight_theme(inventory=inv, signed_review=review,
                                proposal=proposals, choice=choice, secret=SECRET)
            source.assert_not_called()
            writer.assert_not_called()

    def test_audit_cli_refuses_paid_flag_and_noninteractive_use(self):
        common = ["audit", "--week-ending", SAT, "--as-of", SAT,
                  "--review-local-day", SUN, "--signed-review", "/private/review.json",
                  "--proposals", "/private/themes.json",
                  "--choice", "/private/choice.json",
                  "--out", "/private/audit.json"]
        with patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(SystemExit):
                run(common)
        with patch("sys.stdin.isatty", return_value=True):
            with self.assertRaises(SystemExit):
                run(common + ["--allow-private-paid-writer"])

    def test_owner_audit_cli_produces_private_receipt_without_paid_model(self):
        inv, review, proposals = scenario()
        choice = approve(inv, review, proposals)
        sidecar = {"week_start": "2026-10-04", "week_ending": SAT,
                   "desks": ["china", "singapore"],
                   "source_trail": [{"record_id": 42}, {"record_id": 47}]}
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            review_path = directory / "review.json"
            proposal_path = directory / "proposal.json"
            choice_path = directory / "choice.json"
            output_path = directory / "audit.json"
            for path, value in ((review_path, review),
                                (proposal_path, proposals),
                                (choice_path, choice)):
                path.write_text(json.dumps(value), encoding="utf-8")
            args = ["audit", "--week-ending", SAT, "--as-of", SAT,
                    "--review-local-day", SUN,
                    "--signed-review", str(review_path),
                    "--proposals", str(proposal_path),
                    "--choice", str(choice_path), "--out", str(output_path)]
            with patch("sys.stdin.isatty", return_value=True), patch(
                    "getpass.getpass", return_value=SECRET.decode()), patch(
                    "scripts.regional_sunday_theme_preview.inspect",
                    return_value=inv), patch(
                    "scripts.regional_sunday_theme_preview.prepare_scaffold",
                    return_value=sidecar), patch(
                    "scripts.regional_sunday_theme_preview.choose_evidence",
                    return_value=[({"id": 42}, "read"), ({"id": 47}, "read")]), patch(
                    "scripts.regional_sunday_theme_preview.compose") as writer, patch(
                    "scripts.sunday_editorial_handoff.send_packet") as mail:
                self.assertEqual(run(args), 0)
                writer.assert_not_called()
                mail.assert_not_called()
            receipt = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertFalse(receipt["model_called"])
            self.assertEqual(receipt["selected_source_count"], 2)
            self.assertTrue(receipt["source_audit_only_not_a_reusable_model_authorization"])
            self.assertEqual(output_path.stat().st_mode & 0o777, 0o600)
            with patch("sys.stdin.isatty", return_value=True), patch(
                    "getpass.getpass", return_value=SECRET.decode()), patch(
                    "scripts.regional_sunday_theme_preview.inspect",
                    return_value=inv), patch(
                    "scripts.regional_sunday_theme_preview.prepare_scaffold",
                    return_value=sidecar), patch(
                    "scripts.regional_sunday_theme_preview.choose_evidence",
                    return_value=[({"id": 42}, "read"), ({"id": 47}, "read")]):
                with self.assertRaises(SystemExit):
                    run(args)  # Exclusive output; no overwrite/automatic retry.

    def test_preview_file_is_exclusive_private_and_unpublished(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "private-manuscript.txt"
            _out_text(dest, "PRIVATE UNSENT EDITORIAL PROOF\n")
            self.assertEqual(dest.read_text(), "PRIVATE UNSENT EDITORIAL PROOF\n")
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                _out_text(dest, "must not overwrite")

    def test_private_output_encoding_error_removes_only_our_file(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "unsent.txt"
            with self.assertRaises(UnicodeEncodeError):
                _out_text(target, "invalid surrogate " + chr(0xD800))
            self.assertFalse(target.exists())

    def test_private_output_fdopen_failure_closes_fd_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "unsent.txt"
            raw_open = os.open
            raw_close = os.close
            opened = []

            def record_open(*args, **kwargs):
                fd = raw_open(*args, **kwargs)
                opened.append(fd)
                return fd

            with patch("scripts.regional_sunday_theme_preview.os.open",
                       side_effect=record_open), patch(
                    "scripts.regional_sunday_theme_preview.os.fdopen",
                    side_effect=OSError("simulated fdopen failure")), patch(
                    "scripts.regional_sunday_theme_preview.os.close",
                    wraps=raw_close) as close:
                with self.assertRaisesRegex(OSError, "simulated fdopen failure"):
                    _out_text(target, "PRIVATE")
            self.assertFalse(target.exists())
            self.assertEqual(len(opened), 1)
            close.assert_called_once_with(opened[0])

    def test_private_output_replaced_path_survives_writer_failure(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "unsent.txt"
            successor = Path(root) / "someone-elses-file.txt"
            successor.write_text("UNRELATED", encoding="utf-8")
            raw_close = os.close

            def replace_then_fail(fd, *args, **kwargs):
                target.unlink()
                os.link(successor, target)
                raise OSError("simulated replaced path")

            with patch("scripts.regional_sunday_theme_preview.os.fdopen",
                       side_effect=replace_then_fail), patch(
                    "scripts.regional_sunday_theme_preview.os.close",
                    wraps=raw_close):
                with self.assertRaisesRegex(OSError, "simulated replaced path"):
                    _out_text(target, "PRIVATE")
            self.assertEqual(target.read_text(encoding="utf-8"), "UNRELATED")
            self.assertTrue(successor.exists())

    def test_private_output_existing_symlink_is_not_modified(self):
        with tempfile.TemporaryDirectory() as root:
            original = Path(root) / "another-document.txt"
            original.write_text("NO CHANGE", encoding="utf-8")
            target = Path(root) / "unsent.txt"
            target.symlink_to(original)
            with self.assertRaisesRegex(ValueError, "new file"):
                _out_text(target, "PRIVATE")
            self.assertTrue(target.is_symlink())
            self.assertEqual(original.read_text(encoding="utf-8"), "NO CHANGE")

    def test_sunday_delivery_workflow_does_not_import_theme_module(self):
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/sunday_briefs_editorial_handoff.yml"
                   ).read_text(encoding="utf-8")
        self.assertNotIn("regional_sunday_theme_preview", workflow)
        self.assertNotIn("--approved-theme", workflow)
        self.assertIn("scripts.sunday_editorial_handoff", workflow)


if __name__ == "__main__":
    unittest.main()
