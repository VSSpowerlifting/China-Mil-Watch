"""Offline source-use agenda tests; test fixtures never grant model permissions."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.prepare_vietnam_source_use_review_agenda import (
    SCHEMA, build_agenda, main, prepare,
)
from scripts.prepare_vietnam_briefs_evidence import (
    VietnamFeederError, canonical_json,
)
from tests.test_vietnam_briefs_evidence_feeder import NOTES, SAT, queue, signed

ROOT = Path(__file__).resolve().parents[1]


def new_article(q):
    item = copy.deepcopy(q["records"][0])
    item.update(
        source_identity="mps-vi:1791366010",
        canonical_url=("https://bocongan.gov.vn/bai-viet/"
                       "dua-hop-tac-an-ninh-thuc-thi-phap-luat-tro-thanh-tru-cot-"
                       "trong-quan-he-viet-nam-australia-1791366010"),
        published_date="2026-10-07",
        title_original=("Đưa hợp tác an ninh, thực thi pháp luật trở thành "
                        "trụ cột trong quan hệ Việt Nam - Australia"),
        content_sha256="8707eaee31b0423d8b6835fee0d02a25207c2a8e5813718aa57c434c927fd6b5",
    )
    q["records"].append(item)
    q["record_count"] += 1
    return signed(q)


def without_new_australia_note():
    # The live Oct 7 source is now correctly included in NOTES on main.
    # Build an intentionally INCOMPLETE catalog to test actionable gaps,
    # rather than assuming the shared fixture still contains only two notes.
    notes = copy.deepcopy(NOTES)
    historical_two = {"mps-vi:1791199100", "mps-vi:1791199677"}
    notes["entries"] = [
        note for note in notes["entries"]
        if note["source_identity"] in historical_two
    ]
    assert {note["source_identity"] for note in notes["entries"]} == historical_two
    return notes


class UnsignedAgendaTests(unittest.TestCase):
    def test_live_third_source_missing_note_is_exact_metadata_only(self):
        original = queue()
        agenda = build_agenda(new_article(original), without_new_australia_note(), SAT)
        self.assertEqual(agenda["schema"], SCHEMA)
        self.assertEqual(agenda["in_window_machine_eligible"], 3)
        self.assertEqual(agenda["already_has_matching_private_notes"], 2)
        self.assertEqual(agenda["missing_or_stale_source_notes"], 1)
        self.assertEqual(len(agenda["source_version_review_leads"]), 1)
        x = agenda["source_version_review_leads"][0]
        self.assertEqual(x["source_identity"], "mps-vi:1791366010")
        self.assertEqual(x["research_note_state"], "missing-source-specific-note")
        self.assertEqual(x["published_date"], "2026-10-07")
        self.assertEqual(x["current_content_sha256"],
                         "8707eaee31b0423d8b6835fee0d02a25207c2a8e5813718aa57c434c927fd6b5")
        self.assertTrue(x["source_url"].startswith("https://bocongan.gov.vn/bai-viet/"))
        self.assertIsNone(x["prior_note_sha256"])
        for key in ("external_excerpt_authorized", "ready_for_private_model",
                    "original_text_in_agenda", "public_citation_approved"):
            self.assertIs(x[key], False)
        self.assertEqual(x["source_use_review_state"], "not-authorized")
        self.assertFalse(agenda["human_source_use_review_completed"])
        self.assertFalse(agenda["publisher_silence_verified"])
        self.assertFalse(agenda["full_week_collection_verified"])
        self.assertFalse(agenda["third_party_model_called"])
        self.assertFalse(agenda["editorial_email_sent"])
        self.assertNotIn("text_original", str(agenda))
        self.assertNotIn("article_body", str(agenda))
        self.assertNotIn("max_excerpt_chars", str(agenda))
        self.assertNotIn("allow-private-model-bounded-excerpt", str(agenda))

    def test_all_three_current_notes_need_no_source_use_review(self):
        # Once PR #245 merged, current research includes all three MPS notes;
        # the agenda must not invent an outstanding human action.
        agenda = build_agenda(new_article(queue()), NOTES, SAT)
        self.assertEqual(agenda["in_window_machine_eligible"], 3)
        self.assertEqual(agenda["already_has_matching_private_notes"], 3)
        self.assertEqual(agenda["missing_or_stale_source_notes"], 0)
        self.assertEqual(agenda["source_version_review_leads"], [])
        self.assertEqual(agenda["automatically_authorized_source_count"], 0)
        self.assertFalse(agenda["human_source_use_review_completed"])

    def test_matching_note_is_not_permission_and_has_no_agenda_row(self):
        agenda = build_agenda(queue(), NOTES, SAT)
        self.assertEqual(agenda["already_has_matching_private_notes"], 2)
        self.assertEqual(agenda["source_version_review_leads"], [])
        self.assertEqual(agenda["automatically_authorized_source_count"], 0)
        self.assertFalse(agenda["human_source_use_review_completed"])

    def test_missing_and_stale_notes_not_interchangeable(self):
        notes = copy.deepcopy(NOTES)
        stale = next(note for note in notes["entries"]
                     if note["source_identity"] == "mps-vi:1791199100")
        stale["content_sha256"] = "f" * 64
        agenda = build_agenda(queue(), notes, SAT)
        self.assertEqual(agenda["missing_or_stale_source_notes"], 1)
        row = agenda["source_version_review_leads"][0]
        self.assertEqual(row["research_note_state"], "stale-source-version-note")
        self.assertEqual(row["prior_note_sha256"], "f" * 64)
        self.assertEqual(row["current_content_sha256"],
                         queue()["records"][0]["content_sha256"])
        absent = {"schema": "vietnam-editorial-notes/1", "entries": []}
        agenda = build_agenda(queue(), absent, SAT)
        self.assertEqual(agenda["missing_or_stale_source_notes"], 2)
        self.assertEqual({x["research_note_state"]
                          for x in agenda["source_version_review_leads"]},
                         {"missing-source-specific-note"})

    def test_machine_held_source_is_not_offered_for_model_use_review(self):
        q = queue()
        q["records"][0]["machine_review_candidate"] = False
        q["records"][0]["machine_blockers"] = ["unresolved_capture_integrity"]
        agenda = build_agenda(signed(q), NOTES, SAT)
        self.assertEqual(agenda["machine_held_not_eligible_for_review"], 1)
        self.assertEqual(agenda["source_version_review_leads"], [])

    def test_bad_queue_hash_and_reused_out_of_week_notes_refuse(self):
        q = queue()
        q["records"][0]["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(VietnamFeederError, "hash mismatch"):
            build_agenda(q, NOTES, SAT)
        agenda = build_agenda(queue(), NOTES, "2026-10-17")
        self.assertEqual(agenda["in_window_machine_eligible"], 0)
        self.assertEqual(agenda["source_version_review_leads"], [])

    def test_exact_current_shadow_tip_is_required_before_review_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "agenda.json"
            with patch("scripts.prepare_vietnam_source_use_review_agenda.formal.resolve_state_repo",
                       return_value=root), patch(
                    "scripts.prepare_vietnam_source_use_review_agenda.formal.verify_state_commit",
                    return_value={"state_ref_tip": "b" * 40}), patch(
                    "scripts.prepare_vietnam_source_use_review_agenda.queues.prepare") as builder:
                with self.assertRaisesRegex(VietnamFeederError, "current MPS shadow"):
                    prepare(root, "a" * 40, SAT, None, output)
                builder.assert_not_called()
                self.assertFalse(output.exists())

    def test_full_cli_offline_with_signed_queue_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            q = new_article(queue())
            output = root / "agenda.json"
            notes = root / "notes.json"
            notes.write_text(canonical_json(without_new_australia_note()), encoding="utf-8")
            def fake_queue(_repo, _sha, directory):
                directory.mkdir()
                (directory / "review_queue.json").write_text(
                    canonical_json(q), encoding="utf-8")
            with patch("scripts.prepare_vietnam_source_use_review_agenda.formal.resolve_state_repo",
                       return_value=root), patch(
                    "scripts.prepare_vietnam_source_use_review_agenda.formal.verify_state_commit",
                    return_value={"state_ref_tip": "a" * 40}), patch(
                    "scripts.prepare_vietnam_source_use_review_agenda.queues.prepare",
                    side_effect=fake_queue) as verify:
                result = prepare(root, "a" * 40, SAT, notes, output)
                verify.assert_called_once()
                self.assertEqual(result["missing_or_stale_source_notes"], 1)
                self.assertTrue(output.is_file())
                with self.assertRaises(VietnamFeederError):
                    prepare(root, "a" * 40, SAT, notes, output)
            self.assertEqual(json.loads(output.read_text())["schema"], SCHEMA)
            self.assertNotIn("source_use_basis", output.read_text())

    def test_program_contains_no_publisher_fetch_model_or_approval(self):
        source = (ROOT / "scripts/prepare_vietnam_source_use_review_agenda.py").read_text()
        for forbidden in ("import anthropic", "import requests", "import httpx",
                          "urllib.request", "smtplib", "git push", "send_packet("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
