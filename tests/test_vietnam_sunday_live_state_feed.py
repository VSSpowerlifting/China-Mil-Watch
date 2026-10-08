"""Sunday live MPS source feeder precedes the one-theme model and all email."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.prepare_vietnam_briefs_evidence import canonical_json, make_packet
from scripts.sunday_editorial_handoff import main
from tests.test_briefs_editorial_evidence import scaffold, manuscript, packet
from tests.test_vietnam_briefs_evidence_feeder import NOTES, SAT, queue

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"
ACTION = ROOT / ".github/actions/vietnam-editorial-evidence/action.yml"


class SundayMPSIntegration(unittest.TestCase):
    def test_live_gate_precedes_model_without_publisher_body_transfer(self):
        code = WORKFLOW.read_text(encoding="utf-8")
        steps = (
            "- name: Select bounded source notes and regional packet",
            "- name: Audit current Vietnam MPS shadow state",
            "- name: Verify refreshed exact-week research",
            "- name: Create read-only full Saturday-ending week",
            "- name: Generate source-cited Sunday manuscript",
        )
        offsets = [code.index(s) for s in steps]
        self.assertEqual(offsets, sorted(offsets))
        self.assertIn("uses: ./.github/actions/vietnam-editorial-evidence", code)
        self.assertIn('REPORTING_SATURDAY="$IPR_SUNDAY_WEEK_END"', code)
        self.assertIn('echo "week_ending=$REPORTING_SATURDAY" >> "$GITHUB_OUTPUT"', code)
        self.assertIn("week-ending: $" + "{{ steps.vietnam_sources.outputs.week_ending }}", code)
        self.assertNotIn("week-ending: $" + "{{ env.IPR_SUNDAY_WEEK_END }}", code)
        self.assertIn("PRIVATE_WEEK_PACKET: $" + "{{ steps.vietnam_current.outputs.packet }}", code)
        self.assertIn("PRIVATE_VN_MACHINE_ELIGIBLE: $" + "{{ steps.vietnam_current.outputs.machine-eligible-count }}", code)
        self.assertIn('if week == "2026-10-10" and eligible != vn:', code)
        self.assertIn("strict pilot must account for all in-window MPS sources", code)
        self.assertIn("omission is NOT official silence", code)
        self.assertIn("machine-eligible-count:", ACTION.read_text(encoding="utf-8"))
        self.assertIn('--research-packet "$PRIVATE_WEEK_PACKET"', code)
        self.assertIn('[[ -n "$PRIVATE_WEEK_PACKET" && -f "$PRIVATE_WEEK_PACKET" ]]', code)
        self.assertNotIn("git push", code)
        self.assertNotIn("actions/upload-artifact", code)
        self.assertIn("permissions:\n  contents: read", code)
        action = ACTION.read_text(encoding="utf-8")
        self.assertNotIn("ANTHROPIC_API_KEY", action)
        self.assertNotIn("IPR_SMTP_APP_PASSWORD", action)

    def test_october_strict_and_future_weeks_explicit_missing_notes(self):
        code = WORKFLOW.read_text(encoding="utf-8")
        select = code.split("- name: Select bounded source notes", 1)[1]
        select = select.split("- name: Audit current Vietnam MPS", 1)[0]
        self.assertIn('[[ "$REPORTING_SATURDAY" == "2026-10-10" ]]', select)
        for value in ("missing_policy=refuse", "require_vietnam=true",
                      "missing_policy=continue-without-vietnam",
                      "require_vietnam=false", "existing=$packet", "notes=$notes"):
            self.assertIn(value, select)
        self.assertIn('[[ -L "$candidate" ]]', select)
        self.assertIn('[[ -e "$candidate" && ! -f "$candidate" ]]', select)

    def test_rederived_vietnam_and_original_japan_feed_one_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            draft = work / "scaffold.json"
            draft.write_text(json.dumps(scaffold()), encoding="utf-8")
            original = packet()
            fresh = make_packet(queue(), NOTES, SAT, previous=original)
            candidate = work / (SAT + ".json")
            candidate.write_text(canonical_json(fresh), encoding="utf-8")
            output = work / "manuscript.txt"
            with patch("scripts.sunday_briefs_auto_writer.compose",
                       return_value=manuscript()) as compose, patch(
                           "scripts.sunday_editorial_handoff.send_packet") as mail:
                main(["--sidecar", str(draft), "--out", str(output),
                      "--as-of", SAT, "--full-week", "--write-automatic",
                      "--include-research", "--research-packet", str(candidate)])
                mail.assert_not_called()
            compose.assert_called_once()
            rows = compose.call_args.kwargs["supplemental"]
            self.assertEqual(sum(x["desk"] == "vietnam" for x in rows), 2)
            self.assertEqual(sum(x["desk"] == "japan" for x in rows), 3)
            self.assertTrue(output.is_file())
            self.assertEqual(
                [x for x in fresh["items"] if x["desk"] == "japan"],
                [x for x in original["items"] if x["desk"] == "japan"])


if __name__ == "__main__":
    unittest.main()
