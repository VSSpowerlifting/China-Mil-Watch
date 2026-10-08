"""Strict synthetic no-network checks for fixed Sunday MPS evidence drift."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.attest_vietnam_sunday_roster import attest, main
from scripts.prepare_vietnam_briefs_evidence import (
    VietnamFeederError, canonical_json, make_packet,
)
from tests.test_vietnam_briefs_evidence_feeder import NOTES, SAT, queue, signed

ROOT = Path(__file__).resolve().parents[1]


def provision(root, static=None, notes=NOTES):
    pkt = root / (SAT + "-offered.json")
    notes_file = root / "notes.json"
    candidate = static if static is not None else make_packet(queue(), NOTES, SAT)
    pkt.write_text(canonical_json(candidate), encoding="utf-8")
    notes_file.write_text(canonical_json(notes), encoding="utf-8")
    return pkt, notes_file


def attest_with_queue(root, *, original=None, queue_override=None,
                      all_eligible=True, static=None, notes=NOTES):
    offered, notes_path = provision(root, static=static, notes=notes)
    source = queue_override if queue_override is not None else queue()

    def fake_queue(_repo, _sha, directory):
        directory.mkdir()
        (directory / "review_queue.json").write_text(
            canonical_json(source), encoding="utf-8")

    with patch("scripts.build_vietnam_sunday_packet.queue_builder.prepare",
               side_effect=fake_queue) as reviewer, patch(
                   "scripts.attest_vietnam_sunday_roster.formal.resolve_state_repo",
                   return_value=root), patch(
                   "scripts.attest_vietnam_sunday_roster.formal.verify_state_commit",
                   return_value={"state_tree": "b" * 40}) as ancestry:
        result = attest(
            state_repo=root, state_commit="a" * 40, week_ending=SAT,
            notes=notes_path, offered_packet=offered,
            require_all_eligible=all_eligible)
    reviewer.assert_called_once()
    ancestry.assert_called()
    return result, offered


class CurrentRosterTests(unittest.TestCase):
    def test_two_real_week_identity_shapes_rederived_without_approvals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result, offered = attest_with_queue(root)
            self.assertEqual(result["offered_vietnam_sources"], 2)
            self.assertEqual(result["current_source_version_matches"], 2)
            self.assertEqual(result["in_window_machine_eligible"], 2)
            self.assertEqual(result["source_version_drift"], 0)
            for flag in ("publisher_silence_verified", "source_use_approved",
                         "human_review_approved", "email_sent", "model_called",
                         "full_reporting_week_collection_verified",
                         "original_article_bodies_exported"):
                self.assertFalse(result[flag], flag)
            self.assertEqual(result["production_writes"], 0)
            self.assertEqual(
                json.loads(offered.read_text())["items"],
                make_packet(queue(), NOTES, SAT)["items"])

    def test_historical_source_commit_is_allowed_only_when_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            static = make_packet(queue(), NOTES, SAT)
            for x in static["items"]:
                x["state_commit"] = "b" * 40
            result, _ = attest_with_queue(root, static=static)
            self.assertEqual(result["current_source_version_matches"], 2)
            offered, notes = provision(root, static=static)
            with patch("scripts.build_vietnam_sunday_packet.queue_builder.prepare",
                       side_effect=lambda _, __, d: (
                           d.mkdir(),
                           (d / "review_queue.json").write_text(
                               canonical_json(queue()), encoding="utf-8"))), patch(
                                   "scripts.attest_vietnam_sunday_roster.formal.resolve_state_repo",
                                   return_value=root), patch(
                                   "scripts.attest_vietnam_sunday_roster.formal.verify_state_commit",
                                   side_effect=ValueError("not an ancestor")):
                with self.assertRaisesRegex(ValueError, "not an ancestor"):
                    attest(state_repo=root, state_commit="a" * 40,
                           week_ending=SAT, notes=notes,
                           offered_packet=offered, require_all_eligible=True)

    def test_new_eligible_article_without_synopsis_fails_strict_sunday(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            q = queue()
            extra = copy.deepcopy(q["records"][0])
            extra["source_identity"] = "mps-vi:1791199999"
            extra["canonical_url"] = (
                "https://bocongan.gov.vn/bai-viet/another-test-record-1791199999")
            q["records"].append(extra)
            q["record_count"] = 3
            q = signed(q)
            with self.assertRaisesRegex(VietnamFeederError,
                                        "eligible MPS publications lack"):
                attest_with_queue(root, queue_override=q, all_eligible=True)
            result, _ = attest_with_queue(root, queue_override=q,
                                          all_eligible=False)
            self.assertEqual(result["in_window_machine_eligible"], 3)
            self.assertEqual(result["offered_vietnam_sources"], 2)
            self.assertFalse(result["publisher_silence_verified"])

    def test_forged_or_stale_static_sources_are_refused(self):
        modifications = [
            lambda rows: rows[0].update(source_content_sha256="f" * 64),
            lambda rows: rows[0].update(
                source_url="https://bocongan.gov.vn/bai-viet/forged-1791199100"),
            lambda rows: rows[0].update(summary="Altered summary"),
            lambda rows: rows[0].update(
                status="approved-production-publication"),
            lambda rows: rows[0].update(state_commit=None),
            lambda rows: rows.pop(),
        ]
        for change in modifications:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                static = make_packet(queue(), NOTES, SAT)
                change(static["items"])
                with self.subTest(change=change), self.assertRaises(VietnamFeederError):
                    attest_with_queue(root, static=static)

    def test_stale_official_body_version_does_not_reuse_old_notes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            q = queue()
            q["records"][0]["content_sha256"] = "c" * 64
            with self.assertRaisesRegex(VietnamFeederError, "not pinned"):
                attest_with_queue(root, queue_override=signed(q))

    def test_zero_vietnam_wrong_week_and_extra_fields_fail_closed(self):
        for mutate in (
            lambda p: p["items"].clear(),
            lambda p: p.update(week_ending="2026-10-17"),
            lambda p: p.update(artifacts_uploaded=True),
            lambda p: p["items"][0].update(extra_approval=True),
            lambda p: p["items"].append(copy.deepcopy(p["items"][0])),
        ):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                static = make_packet(queue(), NOTES, SAT)
                mutate(static)
                with self.assertRaises(VietnamFeederError):
                    attest_with_queue(root, static=static)

    def test_cli_never_overwrites_or_writes_inside_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            offered, notes = provision(root)
            dest = root / "status.json"
            with patch("scripts.attest_vietnam_sunday_roster.attest",
                       return_value={"schema": "test"}) as attester:
                self.assertEqual(main([
                    "--state-repo", str(root), "--state-commit", "a" * 40,
                    "--week-ending", SAT, "--notes", str(notes),
                    "--offered-packet", str(offered), "--out", str(dest)]), 0)
                attester.assert_called_once()
                with self.assertRaises(VietnamFeederError):
                    main([
                        "--state-repo", str(root), "--state-commit", "a" * 40,
                        "--week-ending", SAT, "--notes", str(notes),
                        "--offered-packet", str(offered), "--out", str(dest)])
            self.assertEqual(json.loads(dest.read_text()), {"schema": "test"})

    def test_no_publisher_fetch_model_email_or_production_write(self):
        source = (ROOT / "scripts/attest_vietnam_sunday_roster.py").read_text()
        for forbidden in ("import requests", "import httpx", "urllib.request",
                          "smtplib", "anthropic", "git push", "DB_PATH",
                          "send_packet(", "publish("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
