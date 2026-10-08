"""No-network tests: Vietnamese source presence is NOT model-ready evidence."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_vietnam_weekly_model_readiness import audit, main
from scripts.prepare_vietnam_briefs_evidence import (
    VietnamFeederError, canonical_json,
)
from tests.test_vietnam_briefs_evidence_feeder import (
    NOTES, SAT, queue, signed,
)


class ReadinessTests(unittest.TestCase):
    def test_exact_october_ten_sources_are_ready_without_promotion(self):
        report, pack = audit(queue(), NOTES, SAT)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["counts"]["in_window_machine_eligible"], 2)
        self.assertEqual(report["counts"]["ready_private_model"], 2)
        self.assertEqual(report["counts"]["awaiting_source_specific_synopsis"], 0)
        self.assertFalse(report["publication_approval"])
        self.assertFalse(report["desk_qualified"])
        self.assertTrue(report["never_infer_official_silence"])
        self.assertEqual({row["id"] for row in pack["items"]},
                         {"VN-MPS-1791199100", "VN-MPS-1791199677"})

    def test_without_notes_collector_still_has_two_official_source_items(self):
        report, pack = audit(queue(),
                             {"schema": "vietnam-editorial-notes/1", "entries": []},
                             SAT)
        self.assertEqual(report["status"], "synopsis-gap")
        self.assertEqual(report["counts"]["in_window_machine_eligible"], 2)
        self.assertEqual(report["counts"]["awaiting_source_specific_synopsis"], 2)
        self.assertEqual(report["counts"]["ready_private_model"], 0)
        self.assertEqual(pack["items"], [])
        self.assertTrue(report["never_infer_official_silence"])

    def test_stale_version_is_visible_and_not_forwarded_to_model(self):
        notes = copy.deepcopy(NOTES)
        notes["entries"][0]["content_sha256"] = "f" * 64
        report, pack = audit(queue(), notes, SAT)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["counts"]["stale_source_version_synopsis"], 1)
        self.assertEqual(report["counts"]["ready_private_model"], 1)
        self.assertNotIn("VN-MPS-1791199100", {row["id"] for row in pack["items"]})

    def test_machine_blocker_survives_human_synopsis_presence(self):
        q = queue()
        q["records"][0]["machine_review_candidate"] = False
        q["records"][0]["machine_blockers"] = ["raw_observation_hash_drift"]
        report, pack = audit(signed(q), NOTES, SAT)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["counts"]["machine_held_in_window"], 1)
        self.assertEqual(report["counts"]["blocked_source_with_synopsis"], 1)
        self.assertEqual(report["counts"]["ready_private_model"], 1)
        self.assertEqual(len(pack["items"]), 1)

    def test_future_week_does_not_inherit_last_week_vietnam_records(self):
        report, packet = audit(queue(), NOTES, "2026-10-17")
        self.assertEqual(report["status"], "no-eligible-in-window")
        self.assertEqual(report["counts"]["out_of_window_observations"], 2)
        self.assertEqual(report["counts"]["ready_private_model"], 0)
        self.assertFalse(report["desk_qualified"])
        self.assertEqual(packet["items"], [])

    def test_corrupted_queue_and_noncanonical_note_ids_refused(self):
        q = queue()
        q["records"][0]["content_sha256"] = "1" * 64
        with self.assertRaisesRegex(VietnamFeederError, "hash mismatch"):
            audit(q, NOTES, SAT)
        notes = copy.deepcopy(NOTES)
        notes["entries"][0]["source_identity"] = "mps-vi:bad"
        with self.assertRaises(VietnamFeederError):
            audit(queue(), notes, SAT)
        notes = copy.deepcopy(NOTES)
        notes["entries"].append(copy.deepcopy(notes["entries"][0]))
        with self.assertRaises(VietnamFeederError):
            audit(queue(), notes, SAT)

    def test_existing_japan_rows_are_not_dropped_or_reclassified(self):
        original = {
            "schema": "ipr-private-drafting-evidence/1",
            "week_ending": SAT,
            "status": "unapproved-source-linked-editorial-candidate",
            "items": [{
                "id": "JP-W41-01", "desk": "japan",
                "source_name": "Japan Ministry of Defense",
                "source_url": "https://www.mod.go.jp/en/article/2026/10/example.html",
                "published_date": "2026-10-06", "language": "en",
                "title_original": "An official Japanese ministry notice",
                "source_kind": "official-publisher-page-reviewed-for-research",
                "state_commit": None, "source_content_sha256": None,
                "hash_rule": None,
                "summary": ("A Japanese ministry reported a particular dated event, "
                            "with no independent verification of its effectiveness."),
                "caveats": ["Attribution to a ministry is not independent corroboration."],
                "topics": ["hadr"],
                "status": "unapproved-source-linked-editorial-candidate",
                "copy_scope": "private-model-drafting-only-no-source-body",
            }],
        }
        report, merged = audit(queue(), NOTES, SAT, existing=original)
        self.assertEqual(report["non_vietnam_sources_preserved"], 1)
        self.assertEqual(merged["items"][0], original["items"][0])
        self.assertEqual(len(merged["items"]), 3)

    def test_console_reports_only_counts_and_explicit_strict_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            q = root / "queue.json"
            q.write_text(canonical_json(queue()), encoding="utf-8")
            report_path = root / "private-report.json"
            from unittest.mock import patch
            from io import StringIO
            log = StringIO()
            with patch("sys.stdout", log):
                self.assertEqual(main([
                    "--queue", str(q), "--week-ending", SAT,
                    "--out", str(report_path),
                ]), 0)
            logged = log.getvalue()
            self.assertIn('"synopsis-gap"', logged)
            self.assertNotIn("bocongan.gov.vn", logged)
            self.assertNotIn("1791199100", logged)
            result = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(result["counts"]["ready_private_model"], 0)
            with patch("sys.stdout", StringIO()):
                with self.assertRaisesRegex(SystemExit, "REFUSED"):
                    main(["--queue", str(q), "--week-ending", SAT,
                          "--require-ready"])
            self.assertEqual(result["publication_approval"], False)


if __name__ == "__main__":
    unittest.main()
