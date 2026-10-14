"""Week 42 Japan/Indonesia/Vietnam combined research-to-delivery rehearsal.

Offline, synthetic MPS queue only: this is NOT a fresh shadow-state review.
Read actual committed Week 42 analyst notes and country source-linked packet,
then test the same merge, typed loader, permission gate, and handoff paths.
No publisher fetch, model API call, SMTP, production write, or publication.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.brief_editorial_evidence import load_editorial_evidence
from scripts.prepare_vietnam_briefs_evidence import (
    VietnamFeederError, canonical_json, make_packet,
)
from scripts.sunday_research_editor_delivery_gate import check
from scripts.sunday_editorial_handoff import main as handoff
from tests.test_briefs_editorial_evidence import scaffold, valid_manuscript

ROOT = Path(__file__).resolve().parents[1]
SATURDAY = "2026-10-17"
REGIONAL = ROOT / "research/briefs_editorial_evidence/2026-10-17.json"
NOTES = ROOT / "research/vietnam_briefs_candidates/editorial_notes_2026-10-17.json"
REGIONAL_IDS = {"ID-W42-01", "JP-W42-07"}
VIETNAM_IDS = {"VN-MPS-1791881212", "VN-MPS-1791882878"}


def synthetic_queue(notes):
    """Shape-valid queue, NOT a substitute for authenticated Git-state checks."""
    records = [{
        "source_slug": "vn_mps_foreign_affairs_vi",
        "source_identity": note["source_identity"],
        "canonical_url": note["source_url"],
        "published_date": note["published_date"],
        "title_original": "Synthetic queue fixture; original title not reverified",
        "content_sha256": note["content_sha256"],
        "body_status": "text",
        "machine_review_candidate": True,
        "machine_blockers": [],
        "human_source_reviewed": False,
        "reuse_rights_reviewed": False,
        "production_publication_authorized": False,
    } for note in notes["entries"]]
    queue = {
        "schema": "vietnam-mps-pilot-review-queue/1",
        "source_slug": "vn_mps_foreign_affairs_vi",
        "state_branch": "shadow/vietnam-mps-foreign-affairs",
        "state_commit": "a" * 40,
        "state_tree": "b" * 40,
        "successful_run_count": 1,
        "record_count": len(records),
        "human_approvals": 0,
        "rights_approvals": 0,
        "automatic_production_admission": False,
        "full_desk_qualification": False,
        "original_article_bodies_in_packet": False,
        "records": records,
    }
    queue["queue_sha256"] = hashlib.sha256(
        canonical_json(queue).encode("utf-8")).hexdigest()
    return queue


class ThreeDeskWeek42Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.regional = json.loads(REGIONAL.read_text(encoding="utf-8"))
        self.notes = json.loads(NOTES.read_text(encoding="utf-8"))
        self.assertEqual({item["id"] for item in self.regional["items"]},
                         REGIONAL_IDS)
        self.assertEqual({x["source_identity"] for x in self.notes["entries"]},
                         {"mps-vi:1791881212", "mps-vi:1791882878"})

    def full_packet(self):
        combined = make_packet(
            synthetic_queue(self.notes), self.notes, SATURDAY,
            previous=copy.deepcopy(self.regional))
        # Byte-identical source ROWS: Japan and Indonesia are never reauthored.
        self.assertEqual(combined["items"][:2], self.regional["items"])
        self.assertEqual({x["id"] for x in combined["items"]},
                         REGIONAL_IDS | VIETNAM_IDS)
        private = self.work / "private"
        private.mkdir()
        path = private / (SATURDAY + ".json")
        path.write_text(canonical_json(combined), encoding="utf-8")
        rows = load_editorial_evidence(SATURDAY, SATURDAY, directory=private)
        self.assertEqual(len(rows), 4)
        self.assertEqual({x["desk"] for x in rows},
                         {"japan", "indonesia", "vietnam"})
        self.assertTrue(all(x["copy_scope"] ==
                            "private-model-drafting-only-no-source-body"
                            for x in rows))
        self.assertTrue(all("text_original" not in x and
                            "article_body" not in x for x in rows))
        return path

    def sidecar(self):
        data = scaffold()
        data["week_start"] = "2026-10-11"
        data["week_ending"] = SATURDAY
        path = self.work / "scaffold.json"
        path.write_text(json.dumps(data, ensure_ascii=False),
                        encoding="utf-8")
        return path

    @staticmethod
    def manuscript(*, vietnam):
        draft = valid_manuscript()
        draft["editorial_focus"] = (
            "Compare clearly attributed official accounts, separating the "
            "reported events from independently verified outcomes.")
        draft["supplemental_citations"] = {
            field: [] for field in draft["citations"]}
        draft["supplemental_citations"]["cross_desk_comparison"] = [
            "ID-W42-01", "JP-W42-07"]
        if vietnam:
            draft["supplemental_citations"]["why_it_matters"] = [
                "VN-MPS-1791881212", "VN-MPS-1791882878"]
        return draft

    def test_no_send_private_draft_offers_all_four_real_week42_note_ids(self):
        original = self.full_packet()
        scope = check(week_ending=SATURDAY, as_of=SATURDAY,
                      packet=original, send_email=False)
        self.assertFalse(scope["vietnam_editor_send_authorized"])
        self.assertEqual(scope["vietnam_withheld_from_editor_count"], 0)
        self.assertEqual(scope["effective_packet"], str(original.resolve()))
        target = self.work / "private-draft.txt"
        with patch("scripts.sunday_briefs_auto_writer.compose",
                   return_value=self.manuscript(vietnam=True)) as model, patch(
                       "scripts.sunday_editorial_handoff.send_packet") as smtp:
            handoff(["--sidecar", str(self.sidecar()),
                     "--out", str(target), "--write-automatic",
                     "--full-week", "--include-research",
                     "--research-packet", str(original), "--as-of", SATURDAY])
        model.assert_called_once()
        self.assertEqual({x["id"] for x in
                          model.call_args.kwargs["supplemental"]},
                         REGIONAL_IDS | VIETNAM_IDS)
        smtp.assert_not_called()
        draft = target.read_text(encoding="utf-8")
        for source_id in REGIONAL_IDS | VIETNAM_IDS:
            self.assertIn("External source " + source_id, draft)

    def test_editor_and_owner_email_scope_excludes_vietnam_without_consent(self):
        original = self.full_packet()
        original_bytes = original.read_bytes()
        safe_dir = self.work / "editor-safe"
        safe_dir.mkdir()
        safe = safe_dir / (SATURDAY + ".json")
        scope = check(week_ending=SATURDAY, as_of=SATURDAY,
                      packet=original, send_email=True, safe_out=safe,
                      vietnam_email_approved_week="")
        self.assertFalse(scope["vietnam_editor_send_authorized"])
        self.assertEqual(scope["vietnam_withheld_from_editor_count"], 2)
        self.assertEqual(scope["editor_packet_source_count"], 2)
        self.assertEqual(original.read_bytes(), original_bytes)
        filtered = load_editorial_evidence(SATURDAY, SATURDAY,
                                           directory=safe_dir)
        self.assertEqual({x["id"] for x in filtered}, REGIONAL_IDS)
        self.assertEqual(json.loads(safe.read_text())["items"],
                         self.regional["items"])
        # Rehearse BOTH consumers using the same already-filtered packet;
        # mock the send boundary so no actual owner/editor mail is emitted.
        output = self.work / "email-scoped.txt"
        with patch("scripts.sunday_briefs_auto_writer.compose",
                   return_value=self.manuscript(vietnam=False)) as model, patch(
                       "scripts.sunday_editorial_handoff.send_packet") as smtp:
            handoff(["--sidecar", str(self.sidecar()),
                     "--out", str(output), "--write-automatic",
                     "--full-week", "--include-research", "--as-of", SATURDAY,
                     "--research-packet", str(safe),
                     "--preview-to-owner"])
        model.assert_called_once()
        self.assertEqual({x["id"] for x in
                          model.call_args.kwargs["supplemental"]}, REGIONAL_IDS)
        smtp.assert_called_once()
        self.assertTrue(smtp.call_args.kwargs["preview_to_owner"])
        draft = output.read_text(encoding="utf-8")
        for source_id in VIETNAM_IDS:
            self.assertNotIn(source_id, draft)
        for source_id in REGIONAL_IDS:
            self.assertIn("External source " + source_id, draft)

    def test_explicit_exact_week_email_consent_is_distinct_from_draft_consent(self):
        original = self.full_packet()
        for value in ("", "2026-10-10", "approved"):
            with self.subTest(approval=value):
                # When no scratch location is supplied, unsafe email refuses.
                with self.assertRaisesRegex(ValueError, "private scratch"):
                    check(week_ending=SATURDAY, as_of=SATURDAY,
                          packet=original, send_email=True,
                          vietnam_email_approved_week=value)
        granted = check(week_ending=SATURDAY, as_of=SATURDAY,
                        packet=original, send_email=True,
                        vietnam_email_approved_week=SATURDAY)
        self.assertEqual(granted["editor_packet_source_count"], 4)
        self.assertEqual(granted["vietnam_withheld_from_editor_count"], 0)
        self.assertTrue(granted["vietnam_editor_send_authorized"])
        self.assertFalse(granted["publication_or_source_approval"])
        self.assertFalse(granted["email_sent"])

    def test_revised_mps_source_hash_cannot_sneak_into_private_week42_packet(self):
        changed = synthetic_queue(self.notes)
        changed["records"][0]["content_sha256"] = "f" * 64
        changed.pop("queue_sha256")
        changed["queue_sha256"] = hashlib.sha256(
            canonical_json(changed).encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(VietnamFeederError, "pinned"):
            make_packet(changed, self.notes, SATURDAY,
                        previous=copy.deepcopy(self.regional))


if __name__ == "__main__":
    unittest.main()
