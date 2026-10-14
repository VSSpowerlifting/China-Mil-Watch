"""Vietnam editor-email permission remains distinct from private AI-draft consent.

No network, composer, email or repository mutations occur in these tests.
Real Oct 10 candidate metadata is used only as an offline typed fixture.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.brief_editorial_evidence import EditorialEvidenceError
from scripts.sunday_research_editor_delivery_gate import (
    EditorDeliveryNotAuthorized, check, main,
)

ROOT = Path(__file__).resolve().parents[1]
WEEK = "2026-10-10"
INPUT = ROOT / "research/briefs_editorial_evidence" / (WEEK + ".json")
WORKFLOW = ROOT / ".github/workflows/sunday_briefs_editorial_handoff.yml"


class ResearchEmailPermissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.data = json.loads(INPUT.read_text(encoding="utf-8"))
        self.assertEqual(len(self.data["items"]), 6)
        self.assertEqual({r["desk"] for r in self.data["items"]},
                         {"japan", "vietnam"})

    def write(self, data=None):
        path = self.folder / (WEEK + ".json")
        path.write_text(json.dumps(data or self.data, ensure_ascii=False),
                        encoding="utf-8")
        return path

    def test_model_only_consent_permits_private_no_send_with_vietnam(self):
        result = check(week_ending=WEEK, as_of=WEEK,
                       packet=self.write(), send_email=False)
        self.assertGreater(result["vietnam_private_model_sources"], 0)
        self.assertTrue(result["vietnam_editor_send_authorized"])
        self.assertFalse(result["email_sent"])
        self.assertFalse(result["publication_or_source_approval"])

    def test_scheduled_email_is_denied_without_separate_week_approval(self):
        path = self.write()
        for reviewed in ("", "2026-10-17", "approved", "2026-10-09"):
            with self.subTest(reviewed=reviewed):
                with self.assertRaisesRegex(
                        EditorDeliveryNotAuthorized,
                        "supply a private scratch output"):
                    check(week_ending=WEEK, as_of=WEEK, packet=path,
                          send_email=True, vietnam_email_approved_week=reviewed)
        # Refuse prior to the model and any SMTP, not after distribution.
        with patch("scripts.sunday_editorial_handoff.send_packet") as sender, \
             patch("scripts.sunday_briefs_auto_writer.compose") as writer:
            with self.assertRaises(EditorDeliveryNotAuthorized):
                check(week_ending=WEEK, as_of=WEEK, packet=path, send_email=True)
            writer.assert_not_called()
            sender.assert_not_called()

    def test_scheduled_editor_worksheet_filters_only_model_only_vietnam(self):
        original = self.write()
        prior = json.loads(original.read_text(encoding="utf-8"))
        safe_folder = self.folder / "editor-safe"
        safe_folder.mkdir()
        safe = safe_folder / (WEEK + ".json")
        receipt = check(
            week_ending=WEEK, as_of=WEEK, packet=original,
            send_email=True, safe_out=safe,
        )
        self.assertEqual(receipt["vietnam_private_model_sources"], 3)
        self.assertEqual(receipt["vietnam_withheld_from_editor_count"], 3)
        self.assertFalse(receipt["vietnam_editor_send_authorized"])
        self.assertEqual(receipt["editor_packet_source_count"], 3)
        self.assertEqual(receipt["effective_packet"], str(safe.resolve()))
        # The private model-original packet is preserved byte-for-byte.
        self.assertEqual(json.loads(original.read_text(encoding="utf-8")), prior)
        filtered = json.loads(safe.read_text(encoding="utf-8"))
        self.assertEqual(
            filtered["items"],
            [item for item in prior["items"] if item["desk"] == "japan"],
        )
        self.assertTrue(all(item["desk"] != "vietnam"
                            for item in filtered["items"]))
        self.assertFalse(receipt["model_was_called"])
        self.assertFalse(receipt["email_sent"])

    def test_editor_safe_file_is_new_and_never_overwritten(self):
        path = self.write()
        safe_folder = self.folder / "editor-safe"
        safe_folder.mkdir()
        safe = safe_folder / (WEEK + ".json")
        safe.write_text("original protected contents", encoding="utf-8")
        with self.assertRaisesRegex(EditorDeliveryNotAuthorized, "new"):
            check(week_ending=WEEK, as_of=WEEK, packet=path,
                  send_email=True, safe_out=safe)
        self.assertEqual(safe.read_text(), "original protected contents")

    def test_exact_week_editor_approval_does_not_approve_publication(self):
        result = check(week_ending=WEEK, as_of=WEEK, packet=self.write(),
                       send_email=True, vietnam_email_approved_week=WEEK)
        self.assertTrue(result["vietnam_editor_send_authorized"])
        self.assertFalse(result["publication_or_source_approval"])
        self.assertFalse(result["model_was_called"])
        self.assertFalse(result["email_sent"])

    def test_ordinary_non_vietnam_editor_worksheet_is_not_blocked(self):
        data = dict(self.data, items=[r for r in self.data["items"]
                                      if r["desk"] == "japan"])
        result = check(week_ending=WEEK, as_of=WEEK,
                       packet=self.write(data), send_email=True)
        self.assertEqual(result["vietnam_private_model_sources"], 0)
        self.assertEqual(result["editor_packet_source_count"], 3)
        self.assertTrue(result["vietnam_editor_send_authorized"])

    def test_malformed_or_wrong_week_packet_does_not_bypass_gate(self):
        actual = self.write()
        with self.assertRaisesRegex(EditorDeliveryNotAuthorized, "wrong-week"):
            check(week_ending="2026-10-17", as_of="2026-10-17",
                  packet=actual, send_email=True)
        bad = json.loads(actual.read_text(encoding="utf-8"))
        bad["items"][0]["status"] = "approved"
        actual.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises((EditorialEvidenceError, ValueError)):
            check(week_ending=WEEK, as_of=WEEK, packet=actual,
                  send_email=True, vietnam_email_approved_week=WEEK)

    def test_workflow_revalidates_source_and_permission_before_model_and_mail(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        audit = workflow.index("- name: Verify refreshed exact-week research")
        owner = workflow.index(
            "- name: Separate Vietnam private-model and editor-email research scope")
        model = workflow.index("- name: Generate source-cited Sunday manuscript")
        self.assertLess(audit, owner)
        self.assertLess(owner, model)
        self.assertIn("--approved-week \"$IPR_VN_EMAIL_REVIEWED_WEEK\"", workflow)
        self.assertIn("--safe-out \"$scratch/$IPR_SUNDAY_WEEK_END.json\"", workflow)
        self.assertIn("IPR_SUNDAY_VIETNAM_EDITOR_SEND_REVIEWED_WEEK", workflow)
        self.assertIn("steps.editor_scope.outputs.packet", workflow)
        self.assertIn('print("vietnam_withheld="', workflow)
        self.assertIn(
            'if [[ "$IPR_SUNDAY_SHOULD_SEND" == "true" || "$IPR_PREVIEW_REQUESTED" == "true" ]]; then',
            workflow,
        )
        # Even an owner-only preview is an actual SMTP transmission:
        # no separate Vietnam email consent means filter it before modeling.
        gate = workflow[workflow.index(
            "- name: Separate Vietnam private-model and editor-email research scope"
        ):workflow.index(
            "- name: Attest Japan research offer"
        )]
        self.assertIn("IPR_PREVIEW_REQUESTED:", gate)
        self.assertIn("args+=(--send-email)", gate)
        self.assertIn("scripts.sunday_research_editor_delivery_gate", workflow)
        self.assertNotIn("actions/upload-artifact", workflow)

    def test_cli_preflight_is_no_send_by_default(self):
        with patch("builtins.print") as output:
            self.assertEqual(main(["--week-ending", WEEK, "--as-of", WEEK,
                                   "--packet", str(self.write())]), 0)
        self.assertTrue(output.called)


if __name__ == "__main__":
    unittest.main()
