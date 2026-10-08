"""Synthetic/offline checks for the October 9 Indonesia AI editorial source bridge."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.indonesia_weekly_writer_sources import (
    CAPTURE_SHA256, DEFAULT_PACKET, SOURCE_ID, STATE_COMMIT, STATUS,
    load_indonesia_writer_sources,
)
from scripts.japan_weekly_writer_sources import load_japan_writer_sources
from scripts.weekly_briefs_auto_writer import (
    CITED_FIELDS, compose, validate_manuscript, writing_schema,
)
from scripts.weekly_editorial_handoff import main, render_packet
from tests.test_japan_weekly_writer_sources import japan_manuscript
from tests.test_weekly_briefs_auto_writer import evidence
from tests.test_weekly_editorial_handoff import draft


def indonesia():
    return load_indonesia_writer_sources("2026-10-10", "2026-10-09")


def mixed_sources():
    return load_japan_writer_sources("2026-10-10", "2026-10-09") + indonesia()


def mixed_manuscript():
    result = japan_manuscript()
    result["supplemental_citations"]["what_stood_out"].append(SOURCE_ID)
    result["supplemental_angle"] = (
        "Consider the Indonesian ministry's October 6 account of the "
        "Singapore attaché departure as a separate defense-diplomacy "
        "thread, without implying the same event or coordination with "
        "Japan's concluded Indonesia disaster-relief response."
    )
    result["supplemental_angle_citations"].append(SOURCE_ID)
    return result


class IndonesiaEditorialEvidence(unittest.TestCase):
    def test_exact_week_one_pinned_original_language_source(self):
        rows = indonesia()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], SOURCE_ID)
        self.assertEqual(rows[0]["desk"], "indonesia")
        self.assertEqual(rows[0]["status"], STATUS)
        self.assertEqual(rows[0]["source_language"], "id")
        self.assertIn("not_an_archived_body", rows[0]["evidence_representation"])
        self.assertIn("www.kemhan.go.id/2026/10/06/", rows[0]["url"])
        self.assertNotIn("production_record_id", rows[0])
        self.assertEqual(rows[0]["shadow_state_commit"], STATE_COMMIT)
        self.assertEqual(rows[0]["captured_response_sha256"], CAPTURE_SHA256)

    def test_shadow_provenance_is_pinned_but_not_fake_production_admission(self):
        packet = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
        self.assertEqual(packet["shadow_state_commit"], STATE_COMMIT)
        self.assertEqual(packet["shadow_run_id"], "37693074726-1")
        self.assertEqual(packet["source_candidates"][0]["captured_response_sha256"],
                         CAPTURE_SHA256)
        self.assertIsNone(packet["source_candidates"][0]["production_record_id"])
        self.assertFalse(packet["source_candidates"][0]["source_admission_approved"])
        self.assertFalse(packet["source_candidates"][0]["original_body_independently_human_verified"])

    def test_outside_october_week_does_not_replay_research(self):
        self.assertEqual(load_indonesia_writer_sources("2026-10-17", "2026-10-16"), [])
        self.assertEqual(load_indonesia_writer_sources("2026-10-03", "2026-10-02"), [])
        with self.assertRaisesRegex(ValueError, "restricted"):
            load_indonesia_writer_sources("2026-10-10", "2026-10-08")

    def test_missing_packet_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "missing or unsafe"):
                load_indonesia_writer_sources("2026-10-10", "2026-10-09",
                                              packet_path=Path(root) / "absent.json")

    def test_tampered_source_refusals(self):
        original = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
        mutations = (
            ("candidate_id", "ID-W41-22"),
            ("title", "Fabricated strategic defense agreement"),
            ("public_source_url", "https://bad.example/report"),
            ("publisher_date", "2026-10-11"),
            ("event_date", "2026-10-07"),
            ("captured_response_sha256", "0" * 64),
            ("production_record_id", 2042),
            ("original_body_independently_human_verified", True),
            ("source_admission_approved", True),
        )
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "source.json"
            for key, value in mutations:
                packet = copy.deepcopy(original)
                packet["source_candidates"][0][key] = value
                path.write_text(json.dumps(packet), encoding="utf-8")
                with self.subTest(key=key):
                    with self.assertRaises(ValueError):
                        load_indonesia_writer_sources("2026-10-10", "2026-10-09",
                                                      packet_path=path)
            packet = copy.deepcopy(original)
            packet["source_candidates"][0]["provisional_claims"][0] = (
                "Official institutions agreed on coordinated operations."
            )
            path.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "claim mutation"):
                load_indonesia_writer_sources("2026-10-10", "2026-10-09",
                                              packet_path=path)
            packet = copy.deepcopy(original)
            packet["editorial_handling"]["never_counts_as_live_desk"] = False
            path.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "nonproduction"):
                load_indonesia_writer_sources("2026-10-10", "2026-10-09",
                                              packet_path=path)

    def test_mixed_source_citation_schema_keeps_production_ids_integer_only(self):
        source_ids = [x["id"] for x in mixed_sources()]
        self.assertEqual(source_ids, ["JP-W41-01", "JP-W41-05", "ID-W41-01"])
        schema = writing_schema([1, 2], supplemental_ids=source_ids)
        prod = schema["properties"]["citations"]["properties"]["what_stood_out"]["items"]
        nonprod = schema["properties"]["supplemental_citations"]["properties"][
            "what_stood_out"]["items"]
        self.assertEqual(prod["enum"], [1, 2])
        self.assertEqual(sorted(nonprod["enum"]), sorted(source_ids))
        with self.assertRaises(ValueError):
            writing_schema([1, 2], supplemental_ids=["ID-W41-01", "ID-W41-01"])
        with self.assertRaises(ValueError):
            writing_schema([1, 2], supplemental_ids=["ID-W41-01", "fake-source"])

    def test_cross_desk_production_rule_survives_indonesia_source(self):
        manuscript = mixed_manuscript()
        self.assertIs(validate_manuscript(manuscript, evidence(),
                                          supplemental=mixed_sources()), manuscript)
        manuscript["citations"]["cross_desk_comparison"] = [1]
        manuscript["supplemental_citations"]["cross_desk_comparison"] = [SOURCE_ID]
        with self.assertRaisesRegex(ValueError, "both desks"):
            validate_manuscript(manuscript, evidence(), supplemental=mixed_sources())

    def test_fake_production_citation_refused(self):
        manuscript = mixed_manuscript()
        manuscript["citations"]["what_stood_out"] = [SOURCE_ID]
        with self.assertRaisesRegex(ValueError, "source ids"):
            validate_manuscript(manuscript, evidence(), supplemental=mixed_sources())

    def test_missing_fake_duplicate_supplemental_citations_refused(self):
        for ids in ([SOURCE_ID, SOURCE_ID], ["ID-W41-44"], [999]):
            manuscript = mixed_manuscript()
            manuscript["supplemental_citations"]["what_stood_out"] = ids
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                validate_manuscript(manuscript, evidence(), supplemental=mixed_sources())

    def test_one_model_call_for_both_japan_and_indonesia(self):
        requests = []
        manuscript = mixed_manuscript()
        response = SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use", name="compose_editorial_draft",
                                     input=manuscript)],
        )
        fake_client = SimpleNamespace(messages=SimpleNamespace(
            stream=lambda **kwargs: (
                requests.append(kwargs),
                nullcontext(SimpleNamespace(get_final_message=lambda: response))
            )[1],
        ))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence", return_value=evidence()):
            self.assertIs(compose(sidecar, "2026-10-09", client=fake_client,
                                  supplemental=mixed_sources()), manuscript)
        self.assertEqual(len(requests), 1)
        prompt = requests[0]["messages"][0]["content"]
        self.assertIn("EXTERNAL JAPAN SOURCE RESEARCH", prompt)
        self.assertIn("AND INDONESIA RESEARCH", prompt)
        self.assertIn("ID-W41-01", prompt)
        self.assertIn("October 6", prompt)
        self.assertIn("The only allowed record IDs are 1, 2.", prompt)

    def test_dylan_packet_has_one_draft_and_two_separate_appendices(self):
        sidecar = draft()
        sidecar["week_start"] = "2026-10-04"
        sidecar["week_ending"] = "2026-10-10"
        txt = render_packet(sidecar, manuscript=mixed_manuscript(),
                            as_of="2026-10-09",
                            japan_sources=mixed_sources()[:2],
                            indonesia_sources=indonesia())
        self.assertIn("AI-SYNTHESIZED REGIONAL EDITORIAL CONCEPT", txt)
        self.assertIn("EXTERNAL NONPRODUCTION SOURCE IDS", txt)
        self.assertIn("INDONESIA SOURCE RESEARCH — NOT PRODUCTION", txt)
        self.assertIn("Isolated source commit: " + STATE_COMMIT, txt)
        self.assertIn("Captured response SHA-256: " + CAPTURE_SHA256, txt)
        self.assertIn("JAPAN EDITORIAL RESEARCH APPENDIX — NOT PRODUCTION", txt)
        self.assertIn("NOT production desk coverage", txt)
        self.assertIn("Record 1 | china", txt)
        self.assertNotIn("Record ID-W41-01 | indonesia", txt)

    def test_cli_preview_combines_sources_without_smtp(self):
        sidecar = draft()
        sidecar["week_start"] = "2026-10-04"
        sidecar["week_ending"] = "2026-10-10"
        with tempfile.TemporaryDirectory() as root:
            src, dest = Path(root) / "scaffold.json", Path(root) / "preview.txt"
            src.write_text(json.dumps(sidecar), encoding="utf-8")
            with patch("scripts.weekly_briefs_auto_writer.compose",
                       return_value=mixed_manuscript()) as ai:
                with patch("scripts.weekly_editorial_handoff.send_packet") as send:
                    main(["--sidecar", str(src), "--out", str(dest),
                          "--write-automatic", "--as-of", "2026-10-09",
                          "--use-japan-research", "--use-indonesia-research"])
                    send.assert_not_called()
            self.assertEqual(len(ai.call_args.kwargs["supplemental"]), 3)
            self.assertIn("ID-W41-01", dest.read_text(encoding="utf-8"))

    def test_siaran_pers_gate_does_not_enable_collector(self):
        path = (DEFAULT_PACKET.parents[1] /
                "source_expansion/siaran_pers_candidate.json")
        gate = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(gate["enabled"])
        self.assertFalse(gate["eligible_for_production"])
        self.assertFalse(gate["scheduled"])
        self.assertEqual(gate["evidence"]["source_article_byte_captures"], 0)
        workflow = (DEFAULT_PACKET.parents[3] /
                    ".github/workflows/weekly_briefs_editorial_handoff.yml")
        self.assertIn("--use-japan-research --use-indonesia-research",
                      workflow.read_text(encoding="utf-8"))
        from scripts.indonesia_weekly_writer_sources import DEFAULT_PACKET as source
        self.assertNotEqual(path, source)


if __name__ == "__main__":
    unittest.main()
