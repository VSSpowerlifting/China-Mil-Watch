"""Synthetic/offline contracts for Japan as an editorial AI input, not a desk."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.japan_weekly_writer_sources import (
    FRIDAY, SATURDAY, STATUS, load_japan_writer_sources,
)
from scripts.weekly_briefs_auto_writer import (
    CITED_FIELDS, compose, validate_manuscript, writing_schema,
)
from scripts.weekly_editorial_handoff import render_packet, main
from tests.test_weekly_briefs_auto_writer import evidence, valid_manuscript
from tests.test_weekly_editorial_handoff import draft


def japan():
    return load_japan_writer_sources("2026-10-10", "2026-10-09")


def japan_manuscript():
    draft_text = valid_manuscript()
    draft_text["supplemental_citations"] = {field: [] for field in CITED_FIELDS}
    draft_text["supplemental_citations"]["opening_note"] = ["JP-W41-05"]
    draft_text["supplemental_citations"]["what_stood_out"] = ["JP-W41-01"]
    draft_text["supplemental_angle"] = (
        "Compare Japan's announced Tsuiki relocation with other official "
        "military-exercise statements only if those live records support "
        "a real thematic connection; otherwise treat the October 6 "
        "Indonesia response as an independently sourced disaster-relief angle."
    )
    draft_text["supplemental_angle_citations"] = ["JP-W41-05", "JP-W41-01"]
    return draft_text


class JapanEditorialModelLane(unittest.TestCase):
    def test_exact_friday_reads_two_distinct_nonproduction_source_ids(self):
        items = japan()
        self.assertEqual(FRIDAY.isoformat(), "2026-10-09")
        self.assertEqual(SATURDAY.isoformat(), "2026-10-10")
        self.assertEqual([x["id"] for x in items], ["JP-W41-01", "JP-W41-05"])
        self.assertTrue(all(x["desk"] == "japan" for x in items))
        self.assertTrue(all(x["status"] == STATUS for x in items))
        self.assertTrue(all("paraphrase" in x["evidence_representation"] for x in items))
        self.assertTrue(all("mod.go.jp" in x["url"] for x in items))
        self.assertFalse(any("ipr_record_id" in x for x in items))

    def test_other_week_cannot_reuse_october_source(self):
        self.assertEqual(load_japan_writer_sources("2026-10-03", "2026-10-02"), [])
        self.assertEqual(load_japan_writer_sources("2026-10-17", "2026-10-16"), [])
        with self.assertRaisesRegex(ValueError, "restricted"):
            load_japan_writer_sources("2026-10-10", "2026-10-08")

    def test_current_week_missing_pack_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "missing or unsafe"):
                load_japan_writer_sources("2026-10-10", "2026-10-09",
                                          packet_path=Path(temp) / "missing.json")

    def test_tampered_publisher_source_fails_closed(self):
        from scripts.render_japan_friday_supplement import DEFAULT_PACKET
        data = json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))
        data["linked_public_mod_tsuiki_training_notice"]["url"] = "https://bad.example/test"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "packet.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_japan_writer_sources("2026-10-10", "2026-10-09", packet_path=path)

    def test_supplemental_schema_keeps_integer_only_production_ids(self):
        schema = writing_schema([1, 2],
                                supplemental_ids=["JP-W41-01", "JP-W41-05"])
        self.assertEqual(schema["properties"]["citations"]["properties"][
            "opening_note"]["items"]["enum"], [1, 2])
        self.assertEqual(schema["properties"]["supplemental_citations"][
            "properties"]["opening_note"]["items"]["enum"],
            ["JP-W41-01", "JP-W41-05"])
        self.assertEqual(schema["properties"]["supplemental_angle_citations"][
            "minItems"], 1)
        self.assertNotIn("supplemental_citations", writing_schema([1, 2])["properties"])
        with self.assertRaises(ValueError):
            writing_schema([1, 2], supplemental_ids=["JP-W41-01", "JP-W41-01"])

    def test_valid_japan_editorial_output_passes_without_promoting_desk(self):
        draft_text = japan_manuscript()
        self.assertIs(validate_manuscript(draft_text, evidence(),
                                          supplemental=japan()), draft_text)

    def test_fake_japan_as_numeric_production_id_refused(self):
        draft_text = japan_manuscript()
        draft_text["citations"]["development"] = ["JP-W41-05"]
        with self.assertRaisesRegex(ValueError, "source ids"):
            validate_manuscript(draft_text, evidence(), supplemental=japan())

    def test_missing_fake_or_duplicate_japan_citation_refused(self):
        for refs in (["JP-W41-99"], ["JP-W41-05", "JP-W41-05"], [99]):
            draft_text = japan_manuscript()
            draft_text["supplemental_citations"]["opening_note"] = refs
            with self.subTest(refs=refs):
                with self.assertRaisesRegex(ValueError, "unknown supplemental"):
                    validate_manuscript(draft_text, evidence(), supplemental=japan())
        draft_text = japan_manuscript()
        draft_text.pop("supplemental_angle_citations")
        with self.assertRaisesRegex(ValueError, "Japan synthesis option"):
            validate_manuscript(draft_text, evidence(), supplemental=japan())

    def test_cross_desk_still_needs_two_production_desks(self):
        draft_text = japan_manuscript()
        draft_text["citations"]["cross_desk_comparison"] = [1]
        draft_text["supplemental_citations"]["cross_desk_comparison"] = ["JP-W41-05"]
        with self.assertRaisesRegex(ValueError, "both desks"):
            validate_manuscript(draft_text, evidence(), supplemental=japan())

    def test_one_model_call_both_citation_namespaces(self):
        calls = []
        draft_text = japan_manuscript()
        response = SimpleNamespace(
            stop_reason="tool_use",
            content=[SimpleNamespace(type="tool_use", name="compose_editorial_draft",
                                     input=draft_text)],
        )
        fake = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kwargs:
            (calls.append(kwargs), nullcontext(SimpleNamespace(
                get_final_message=lambda: response)))[1]))
        sidecar = {"week_start": "2026-10-04", "week_ending": "2026-10-10",
                   "desks": ["china", "singapore"], "source_trail": []}
        with patch("scripts.weekly_briefs_auto_writer.choose_evidence",
                   return_value=evidence()):
            self.assertEqual(compose(sidecar, "2026-10-09", client=fake,
                                     supplemental=japan()), draft_text)
        self.assertEqual(len(calls), 1)
        prompt = calls[0]["messages"][0]["content"]
        self.assertIn("EXTERNAL JAPAN SOURCE RESEARCH", prompt)
        self.assertIn("JP-W41-05", prompt)
        self.assertIn("NOT IPR ARCHIVE", prompt)
        self.assertIn("The only allowed record IDs are 1, 2.", prompt)

    def test_editorial_txt_displays_japan_concept_and_separate_appendix(self):
        sidecar = draft()
        sidecar["week_start"] = "2026-10-04"
        sidecar["week_ending"] = "2026-10-10"
        rendered = render_packet(sidecar, manuscript=japan_manuscript(),
                                 as_of="2026-10-09", japan_sources=japan())
        self.assertIn("AI-SYNTHESIZED JAPAN EDITORIAL CONCEPT", rendered)
        self.assertIn("EXTERNAL JAPAN SOURCE IDS (NOT IPR RECORD IDS): JP-W41-05", rendered)
        self.assertIn("JAPAN EDITORIAL RESEARCH APPENDIX — NOT PRODUCTION", rendered)
        self.assertIn("Record 1 | china", rendered)
        self.assertIn("NOT archived IPR originals", rendered)
        self.assertNotIn("Record JP-W41-05", rendered)

    def test_cli_writes_single_generated_packet_without_sending(self):
        sidecar = draft()
        sidecar["week_start"] = "2026-10-04"
        sidecar["week_ending"] = "2026-10-10"
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "scaffold.json"
            output = Path(temp) / "draft.txt"
            source.write_text(json.dumps(sidecar), encoding="utf-8")
            with patch("scripts.weekly_briefs_auto_writer.compose",
                       return_value=japan_manuscript()) as ai:
                with patch("scripts.weekly_editorial_handoff.send_packet") as send:
                    main(["--sidecar", str(source), "--out", str(output),
                          "--write-automatic", "--as-of", "2026-10-09",
                          "--use-japan-research"])
                    send.assert_not_called()
            self.assertEqual(len(ai.call_args.kwargs["supplemental"]), 2)
            self.assertIn("JP-W41-05", output.read_text(encoding="utf-8"))

    def test_no_japan_sources_if_not_explicitly_requested(self):
        draft_text = valid_manuscript()
        self.assertNotIn("supplemental_angle", draft_text)
        schema = writing_schema([1, 2])
        self.assertNotIn("supplemental_angle", schema["properties"])


if __name__ == "__main__":
    unittest.main()
