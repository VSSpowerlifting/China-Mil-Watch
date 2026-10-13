"""Validate a real first-party Japan editorial source packet without network/model/mail.

This file is a separately reviewable research candidate. It is not the
scheduled Sunday input, an approved Brief or an archived source body.
"""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from core.brief_editorial_evidence import load_editorial_evidence, evidence_prompt


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "japan" / "week_2026-10-11" / "source_packets"
URL = "https://www.mod.go.jp/js/pdf/2026/p20261013_01.pdf"


class JapanJointStaffStagedPacketTest(unittest.TestCase):
    def test_real_oct13_source_is_typed_and_no_original_body_is_retained(self):
        rows = load_editorial_evidence("2026-10-17", "2026-10-17", directory=DIR)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["source_url"], URL)
        self.assertEqual(row["id"], "JP-W42-07")
        self.assertEqual(row["source_name"], "Japan Joint Staff")
        self.assertEqual(row["status"], "unapproved-source-linked-editorial-candidate")
        self.assertEqual(row["source_kind"], "official-publisher-page-reviewed-for-research")
        self.assertIsNone(row["state_commit"])
        self.assertIsNone(row["source_content_sha256"])
        self.assertIsNone(row["hash_rule"])
        prompt = evidence_prompt(rows)
        self.assertIn(URL, prompt)
        self.assertIn("one institutional account", prompt)
        self.assertNotIn("text_original", prompt)
        self.assertNotIn("body_original", prompt)

    def test_actual_week42_packet_runs_only_mocked_no_send_preview(self):
        # Read the committed real-source packet; do not contact the publisher,
        # invoke an external model, use SMTP or write public output.
        from scripts.sunday_editorial_handoff import main
        from tests.test_briefs_editorial_evidence import scaffold, manuscript

        with tempfile.TemporaryDirectory() as d:
            temp = Path(d)
            sidecar = scaffold()
            sidecar["week_start"] = "2026-10-11"
            sidecar["week_ending"] = "2026-10-17"
            sidecar_path = temp / "scaffold.json"
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
            target = temp / "japan-owner-only-preview.txt"
            result = manuscript()
            result["supplemental_citations"]["cross_desk_comparison"] = [
                "JP-W42-07"
            ]
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=result) as writer:
                with patch("scripts.sunday_editorial_handoff.send_packet") as send:
                    main([
                        "--sidecar", str(sidecar_path),
                        "--out", str(target),
                        "--write-automatic", "--full-week", "--include-research",
                        "--research-packet", str(DIR / "2026-10-17.json"),
                        "--as-of", "2026-10-17",
                    ])
            writer.assert_called_once()
            self.assertEqual(
                writer.call_args.kwargs["supplemental"][0]["source_url"], URL)
            self.assertIn("External source JP-W42-07",
                          target.read_text(encoding="utf-8"))
            send.assert_not_called()


    def test_actual_indonesia_and_japan_sources_share_one_no_send_editorial_draft(self):
        """Real source-linked notes, one manuscript, no model, mail, or public release."""
        from scripts.sunday_editorial_handoff import main
        from scripts.validate_editorial_return import validate_return, ReturnValidationError
        from core.brief_editorial_source_use import summarize_source_use
        from tests.test_briefs_editorial_evidence import scaffold, valid_manuscript

        saturday = "2026-10-17"
        indonesia = json.loads((
            ROOT / "research" / "briefs_editorial_evidence" /
            (saturday + ".json")).read_text(encoding="utf-8"))
        japan = json.loads((DIR / (saturday + ".json")).read_text(encoding="utf-8"))
        combined = dict(indonesia, items=indonesia["items"] + japan["items"])
        self.assertEqual(
            {item["id"] for item in combined["items"]},
            {"ID-W42-01", "JP-W42-07"})

        m = valid_manuscript()
        m["editorial_focus"] = (
            "Separate reported government security activity from actual policy "
            "implementation, without implying that two unrelated events were coordinated."
        )
        m["supplemental_citations"] = {key: [] for key in m["citations"]}
        m["supplemental_citations"]["cross_desk_comparison"] = [
            "ID-W42-01", "JP-W42-07"]
        m["supplemental_citations"]["why_it_matters"] = ["ID-W42-01"]
        sidecar = scaffold()
        sidecar["week_start"], sidecar["week_ending"] = "2026-10-11", saturday

        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            packet_path = folder / (saturday + ".json")
            packet_path.write_text(
                json.dumps(combined, ensure_ascii=False), encoding="utf-8")
            checked = load_editorial_evidence(saturday, saturday, directory=folder)
            self.assertEqual({row["desk"] for row in checked},
                             {"indonesia", "japan"})
            audit = summarize_source_use(m, sidecar["source_trail"], checked)
            self.assertEqual(audit["research_by_desk"]["japan"]["cited"], 1)
            self.assertEqual(audit["research_by_desk"]["indonesia"]["cited"], 1)

            scaffold_path, target = folder / "scaffold.json", folder / "result.txt"
            scaffold_path.write_text(
                json.dumps(sidecar), encoding="utf-8")
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=m) as writer, patch(
                       "scripts.sunday_editorial_handoff.send_packet") as mail:
                main(["--sidecar", str(scaffold_path), "--out", str(target),
                      "--write-automatic", "--full-week", "--include-research",
                      "--research-packet", str(packet_path), "--as-of", saturday])
            writer.assert_called_once()
            self.assertEqual({x["id"] for x in
                              writer.call_args.kwargs["supplemental"]},
                             {"ID-W42-01", "JP-W42-07"})
            mail.assert_not_called()
            original = target.read_text(encoding="utf-8")
            for ident in ("ID-W42-01", "JP-W42-07"):
                self.assertIn("External source " + ident + " |", original)
            edited = original.replace(
                "Separate reported government security activity",
                "Distinguish reported government security activity", 1)
            self.assertNotEqual(edited, original)
            self.assertEqual(validate_return(original, edited)["external_sources"], 2)
            with self.assertRaises(ReturnValidationError):
                validate_return(
                    original, edited.replace(
                        "External source JP-W42-07 |",
                        "External source JP-W42-99 |", 1))


if __name__ == "__main__":
    unittest.main()
