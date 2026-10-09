"""Ensure pilot Japan research is really in the unified AI source packet."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.sunday_japan_offer_gate import (
    FIRST_JAPAN_IDS, FIRST_SATURDAY, JapanOfferRefused, inspect_offer, main,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research/briefs_editorial_evidence/2026-10-10.json"
WORKFLOW = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"


def packet_at(root, *, week=FIRST_SATURDAY, transform=None):
    if week == FIRST_SATURDAY:
        data = json.loads(SOURCE.read_text(encoding="utf-8"))
    else:
        data = {
            "schema": "ipr-private-drafting-evidence/1",
            "week_ending": week,
            "status": "unapproved-source-linked-editorial-candidate",
            "items": [],
        }
    if transform is not None:
        transform(data)
    path = Path(root) / (week + ".json")
    path.write_text(json.dumps(data, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


class SundayJapanOfferIntegrity(unittest.TestCase):
    def test_exact_first_sunday_roster_offered_not_approved(self):
        with tempfile.TemporaryDirectory() as d:
            path = packet_at(d)
            report = inspect_offer(
                week_ending=FIRST_SATURDAY,
                as_of=FIRST_SATURDAY, directory=path.parent)
        self.assertEqual(report["japan_research_offered"], 3)
        self.assertEqual(report["vietnam_research_offered"], 3)
        self.assertTrue(FIRST_JAPAN_IDS.issubset(
            report["all_offered_source_ids"]))
        self.assertFalse(report["model_was_called"])
        self.assertFalse(report["archived_japan_original_pdf_fidelity_reviewed"])
        self.assertFalse(report["source_use_or_editorial_approved"])
        self.assertFalse(report["japan_production_activated"])
        self.assertFalse(report["email_sent"])
        self.assertNotIn("source_url", json.dumps(report))

    def test_missing_japan_record_stops_oct10_model(self):
        for remove in FIRST_JAPAN_IDS:
            with self.subTest(remove=remove), tempfile.TemporaryDirectory() as d:
                path = packet_at(d, transform=lambda x: x["items"].__setitem__(
                    slice(None),
                    [r for r in x["items"] if r["id"] != remove]))
                with self.assertRaisesRegex(JapanOfferRefused,
                                            "three exact Japan"):
                    inspect_offer(week_ending=FIRST_SATURDAY,
                                  as_of=FIRST_SATURDAY,
                                  directory=path.parent)

    def test_vietnam_only_is_not_falsely_both_desks(self):
        with tempfile.TemporaryDirectory() as d:
            path = packet_at(d, transform=lambda x: x["items"].__setitem__(
                slice(None),
                [r for r in x["items"] if r["desk"] == "vietnam"]))
            with self.assertRaises(JapanOfferRefused):
                inspect_offer(week_ending=FIRST_SATURDAY,
                              as_of=FIRST_SATURDAY, directory=path.parent)

    def test_japan_only_is_not_falsely_both_desks(self):
        with tempfile.TemporaryDirectory() as d:
            path = packet_at(d, transform=lambda x: x["items"].__setitem__(
                slice(None),
                [r for r in x["items"] if r["desk"] == "japan"]))
            with self.assertRaisesRegex(JapanOfferRefused, "Vietnam"):
                inspect_offer(week_ending=FIRST_SATURDAY,
                              as_of=FIRST_SATURDAY, directory=path.parent)

    def test_future_no_japan_reports_omission_not_silence(self):
        with tempfile.TemporaryDirectory() as d:
            week = "2026-10-17"
            packet_at(d, week=week)
            report = inspect_offer(
                week_ending=week, as_of=week, directory=Path(d))
        self.assertEqual(report["japan_research_offered"], 0)
        self.assertEqual(report["all_offered_source_ids"], [])
        self.assertEqual(report["japan_research_state"],
                         "no_japan_candidate_available_not_official_silence")
        self.assertFalse(report["source_use_or_editorial_approved"])

    def test_no_packet_oct10_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(JapanOfferRefused):
                inspect_offer(week_ending=FIRST_SATURDAY,
                              as_of=FIRST_SATURDAY, directory=Path(d))

    def test_duplicate_or_bad_official_source_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path = packet_at(d, transform=lambda x: x["items"].append(
                dict(x["items"][0])))
            with self.assertRaises(ValueError):
                inspect_offer(week_ending=FIRST_SATURDAY,
                              as_of=FIRST_SATURDAY, directory=path.parent)
        with tempfile.TemporaryDirectory() as d:
            path = packet_at(d, transform=lambda x: x["items"][0].update(
                status="approved"))
            with self.assertRaises(ValueError):
                inspect_offer(week_ending=FIRST_SATURDAY,
                              as_of=FIRST_SATURDAY, directory=path.parent)

    def test_cli_rejects_wrong_week_file_and_never_emails(self):
        with tempfile.TemporaryDirectory() as d:
            path = packet_at(d)
            with self.assertRaises(SystemExit):
                main(["--week-ending", "2026-10-17",
                      "--as-of", "2026-10-17", "--packet", str(path)])
            with patch("scripts.sunday_japan_offer_gate.print") as out:
                self.assertEqual(main([
                    "--week-ending", FIRST_SATURDAY,
                    "--as-of", FIRST_SATURDAY,
                    "--packet", str(path)]), 0)
                self.assertIn("japan_research_offered", out.call_args.args[0])

    def test_workflow_tests_exact_refreshed_packet_before_model(self):
        contents = WORKFLOW.read_text(encoding="utf-8")
        gate = contents.index(
            "- name: Attest Japan research offer in the refreshed single-theme packet")
        vietnam = contents.index(
            "- name: Audit current Vietnam MPS shadow state and refresh")
        model = contents.index(
            "- name: Generate source-cited Sunday manuscript")
        self.assertLess(vietnam, gate)
        self.assertLess(gate, model)
        section = contents[gate:contents.index(
            "- name: Create read-only full Saturday-ending week source scaffold", gate)]
        self.assertIn("steps.vietnam_current.outputs.packet", section)
        self.assertIn("python -m scripts.sunday_japan_offer_gate", section)
        for forbidden in ("IPR_SMTP_APP_PASSWORD", "ANTHROPIC_API_KEY",
                          "upload-artifact", "git push", "send_packet"):
            self.assertNotIn(forbidden, section)


if __name__ == "__main__":
    unittest.main()
