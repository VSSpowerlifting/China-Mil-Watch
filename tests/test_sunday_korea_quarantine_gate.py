"""Defense in depth: no held Korea originals in Sunday AI/editor packets."""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import sunday_korea_quarantine_gate as gate

ROOT = Path(__file__).resolve().parents[1]
WEEK = "2026-10-17"
LIVE = ROOT / "research" / "briefs_editorial_evidence" / (WEEK + ".json")


class KoreaSundayQuarantineTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(LIVE.read_text(encoding="utf-8"))
        self.assertTrue(self.raw["items"])
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.packet = self.folder / (WEEK + ".json")
        self.write(self.raw)

    def write(self, data):
        self.packet.write_text(json.dumps(data, ensure_ascii=False) + "\n",
                               encoding="utf-8")

    def check(self, **kwargs):
        return gate.inspect(packet=self.packet, week_ending=WEEK,
                            as_of=WEEK, **kwargs)

    def test_real_week42_japan_indonesia_packet_passes_without_korea(self):
        result = self.check()
        self.assertEqual(result["other_desk_source_count"], 2)
        self.assertEqual(result["korea_research_offered_to_model_or_email"], 0)
        for flag in ("korea_source_admission_authorized", "model_called",
                     "email_sent", "publication_or_production_authorized",
                     "korean_original_body_loaded", "mutated_research_packet"):
            self.assertIs(result[flag], False)
        self.assertEqual(self.raw, json.loads(self.packet.read_text()))

    def test_korean_desk_forged_into_valid_packet_is_refused(self):
        for variation in ("desk", "id", "hostname", "held_research"):
            packet = copy.deepcopy(self.raw)
            existing = packet["items"][0]
            if variation == "desk":
                existing["desk"] = "korea"
            elif variation == "id":
                existing["id"] = "KR-MND-W42-01"
            elif variation == "hostname":
                existing["source_url"] = (
                    "https://www.korea.kr/briefing/pressReleaseView.do"
                    "?newsId=156784873")
            else:
                held = copy.deepcopy(existing)
                held["desk"] = "korea"
                held["id"] = "KR-MND-W42-02"
                packet["items"].append(held)
            self.write(packet)
            with self.subTest(variation=variation), self.assertRaisesRegex(
                    gate.KoreaSundayHold, "korea_not_admitted_to_sunday"):
                self.check()

    def test_independent_quarantine_survives_allowlist_growth(self):
        # This validator rejects Korea directly, *before* calling the general
        # evidence loader. It will keep rejecting it if that loader grows.
        raw = copy.deepcopy(self.raw)
        raw["items"][0]["desk"] = "korea"
        self.write(raw)
        original = gate.load_editorial_evidence
        gate.load_editorial_evidence = lambda *args, **kwargs: raw["items"]
        try:
            with self.assertRaisesRegex(gate.KoreaSundayHold,
                                        "korea_not_admitted_to_sunday"):
                self.check()
        finally:
            gate.load_editorial_evidence = original

    def test_other_unknown_desks_do_not_silently_pass(self):
        x = copy.deepcopy(self.raw)
        x["items"][0]["desk"] = "singapore"
        self.write(x)
        with self.assertRaisesRegex(gate.KoreaSundayHold,
                                    "unexpected_unapproved_sunday_desk"):
            self.check()

    def test_wrong_week_symlink_and_missing_or_malformed_fail(self):
        with self.assertRaises(gate.KoreaSundayHold):
            gate.inspect(packet=self.packet, week_ending="2026-10-10",
                         as_of="2026-10-10")
        other = self.folder / "else.json"
        other.symlink_to(self.packet)
        with self.assertRaises(gate.KoreaSundayHold):
            gate.inspect(packet=other, week_ending=WEEK, as_of=WEEK)
        self.packet.unlink()
        with self.assertRaisesRegex(gate.KoreaSundayHold,
                                    "expected_sunday_packet_missing"):
            self.check()
        result = self.check(permit_missing=True)
        self.assertEqual(result["status"], "missing_packet_no_korea_admission")
        self.assertEqual(result["other_desk_source_count"], 0)
        self.packet.write_text('{"items":[{"id":"x"}],"items":[]}')
        with self.assertRaises(gate.KoreaSundayHold):
            self.check()

    def test_strict_loader_still_catches_copied_originals_and_permissions(self):
        for field, value in (("copy_scope", "approved-for-publishing"),
                             ("status", "approved-model-and-editor"),
                             ("summary", "Copied text\ninvalid")):
            x = copy.deepcopy(self.raw)
            x["items"][0][field] = value
            self.write(x)
            with self.subTest(field=field), self.assertRaisesRegex(
                    gate.KoreaSundayHold, "existing_sunday_source_contract_rejected"):
                self.check()

    def test_clean_cli_receipt_and_hold_have_no_claim_body(self):
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(gate.main([
                "--packet", str(self.packet), "--week-ending", WEEK,
                "--as-of", WEEK]), 0)
        receipt = json.loads(stdout.getvalue())
        self.assertEqual(receipt["other_desk_source_count"], 2)
        self.assertNotIn(self.raw["items"][0]["summary"], stdout.getvalue())
        x = copy.deepcopy(self.raw)
        x["items"][0]["id"] = "KR-MND-W42-01"
        self.write(x)
        with redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(gate.main([
                "--packet", str(self.packet), "--week-ending", WEEK,
                "--as-of", WEEK]), 2)
        self.assertIn('"status": "HOLD"', stdout.getvalue())
        self.assertNotIn(self.raw["items"][0]["summary"], stdout.getvalue())

    def test_actual_sunday_flow_checks_before_model_on_3_boundaries(self):
        yaml = (ROOT / ".github" / "workflows" /
                "sunday_briefs_editorial_handoff.yml").read_text()
        self.assertEqual(yaml.count("python -m scripts.sunday_korea_quarantine_gate"),
                         3)
        first = yaml.index("Quarantine Korea before any Sunday source refresh")
        refresh = yaml.index("- name: Audit current Vietnam MPS shadow state")
        after = yaml.index("- name: Quarantine Korea in refreshed model source packet")
        scope = yaml.index("- name: Separate Vietnam private-model")
        final = yaml.index("- name: Quarantine Korea in final model and email packet")
        writer = yaml.index("- name: Generate source-cited Sunday manuscript")
        self.assertLess(first, refresh)
        self.assertLess(refresh, after)
        self.assertLess(after, scope)
        self.assertLess(scope, final)
        self.assertLess(final, writer)


if __name__ == "__main__":
    unittest.main()
