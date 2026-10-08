"""Synthetic-only tests for the Vietnam shadow queue → private model bridge."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_vietnam_sunday_packet import build as build_from_state
from scripts.prepare_vietnam_briefs_evidence import (
    VietnamFeederError, canonical_json, make_packet, main,
)

ROOT = Path(__file__).resolve().parents[1]
NOTES = json.loads((ROOT / "research/vietnam_briefs_candidates" /
                    "editorial_notes_2026-10-10.json").read_text(encoding="utf-8"))
SAT = "2026-10-10"


def queue():
    first = NOTES["entries"][0]
    second = NOTES["entries"][1]
    rows = []
    for n in (first, second):
        rows.append({
            "source_slug": "vn_mps_foreign_affairs_vi",
            "source_identity": n["source_identity"],
            "canonical_url": n["source_url"],
            "published_date": n["published_date"],
            "title_original": "Bộ Công an mở rộng hợp tác công nghệ", 
            "content_sha256": n["content_sha256"],
            "body_status": "text",
            "machine_review_candidate": True,
            "machine_blockers": [],
            "human_source_reviewed": False,
            "reuse_rights_reviewed": False,
            "production_publication_authorized": False,
        })
    q = {
        "schema": "vietnam-mps-pilot-review-queue/1",
        "source_slug": "vn_mps_foreign_affairs_vi",
        "state_branch": "shadow/vietnam-mps-foreign-affairs",
        "state_commit": "a" * 40,
        "state_tree": "b" * 40,
        "successful_run_count": 2,
        "record_count": len(rows),
        "human_approvals": 0,
        "rights_approvals": 0,
        "automatic_production_admission": False,
        "full_desk_qualification": False,
        "original_article_bodies_in_packet": False,
        "records": rows,
    }
    q["queue_sha256"] = hashlib.sha256(canonical_json(q).encode()).hexdigest()
    return q


def signed(q):
    q = copy.deepcopy(q)
    q.pop("queue_sha256", None)
    q["queue_sha256"] = hashlib.sha256(canonical_json(q).encode()).hexdigest()
    return q


class FeederTests(unittest.TestCase):
    def test_both_vietnam_candidates_are_admitted_to_private_draft_only(self):
        result = make_packet(queue(), NOTES, SAT)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual({r["desk"] for r in result["items"]}, {"vietnam"})
        self.assertEqual({r["id"] for r in result["items"]},
                         {"VN-MPS-1791199100", "VN-MPS-1791199677"})
        self.assertTrue(all(r["status"].startswith("unapproved-")
                            for r in result["items"]))
        self.assertTrue(all(r["source_kind"] == "shadow-extracted-original"
                            for r in result["items"]))
        self.assertTrue(all(r["hash_rule"] == "mps-vi-content-v1"
                            for r in result["items"]))
        self.assertTrue(all("text_original" not in r and "article_body" not in r
                            for r in result["items"]))

    def test_independent_japan_source_rows_are_kept_verbatim(self):
        original = {
            "schema": "ipr-private-drafting-evidence/1",
            "week_ending": SAT,
            "status": "unapproved-source-linked-editorial-candidate",
            "items": [{
                "id": "JP-W41-01", "desk": "japan", "source_url":
                "https://www.mod.go.jp/en/article/2026/10/one.html",
                "source_name": "Japan Ministry of Defense",
                "title_original": "A first party source example", "language": "en",
                "published_date": "2026-10-06", "state_commit": None,
                "source_content_sha256": None, "hash_rule": None,
                "source_kind": "official-publisher-page-reviewed-for-research",
                "summary": "The MOD gave an attributed official summary of an event, not independently verified evidence.",
                "caveats": ["A source attribution is not proof of operational success."],
                "topics": ["hadr"], "status": "unapproved-source-linked-editorial-candidate",
                "copy_scope": "private-model-drafting-only-no-source-body",
            }],
        }
        result = make_packet(queue(), NOTES, SAT, previous=original)
        self.assertEqual(result["items"][0], original["items"][0])
        self.assertEqual(len(result["items"]), 3)
        self.assertEqual(original["items"][0]["id"], "JP-W41-01")

    def test_unpinned_or_new_versions_are_not_synthesized(self):
        q = queue()
        q["records"][0]["content_sha256"] = "f" * 64
        q = signed(q)
        with self.assertRaisesRegex(VietnamFeederError, "not pinned"):
            make_packet(q, NOTES, SAT)

    def test_missing_synopsis_does_not_invent_new_claims(self):
        notes = copy.deepcopy(NOTES)
        notes["entries"] = notes["entries"][:1]
        result = make_packet(queue(), notes, SAT)
        self.assertEqual(len(result["items"]), 1)

    def test_missing_validated_capture_or_machine_blockers_hold_record(self):
        q = queue()
        q["records"][0]["machine_review_candidate"] = False
        q["records"][0]["machine_blockers"] = ["unresolved_observation_anomaly"]
        result = make_packet(signed(q), NOTES, SAT)
        self.assertEqual(len(result["items"]), 1)

    def test_future_or_previous_reporting_week_never_reuses_notes(self):
        self.assertEqual(make_packet(queue(), NOTES, "2026-10-17")["items"], [])
        self.assertEqual(make_packet(queue(), NOTES, "2026-10-03")["items"], [])

    def test_queue_hash_tampering_and_forged_approvals_refused(self):
        q = queue()
        q["records"][0]["canonical_url"] = "https://evil.test"
        with self.assertRaisesRegex(VietnamFeederError, "hash mismatch"):
            make_packet(q, NOTES, SAT)
        for name, value in (("human_approvals", 1),
                            ("rights_approvals", 1),
                            ("automatic_production_admission", True),
                            ("full_desk_qualification", True)):
            q = queue()
            q[name] = value
            with self.subTest(name=name), self.assertRaises(VietnamFeederError):
                make_packet(signed(q), NOTES, SAT)

    def test_source_spoofing_and_review_flags_refused(self):
        edits = [
            ("canonical_url", "https://bocongan.gov.vn.evil.test/bai-viet/a-1791199100"),
            ("canonical_url", "https://evil.test/bai-viet/a-1791199100"),
            ("source_identity", "mps-vi:0000000000"),
            ("body_status", "blocked"),
            ("human_source_reviewed", True),
        ]
        for field, value in edits:
            q = queue()
            q["records"][0][field] = value
            with self.subTest(field=field), self.assertRaises(VietnamFeederError):
                make_packet(signed(q), NOTES, SAT)

    def test_read_only_state_orchestrator_preserves_japan_and_stops_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            parent = d / "editor"
            parent.mkdir()
            notes = d / "notes.json"
            notes.write_text(canonical_json(NOTES), encoding="utf-8")
            output = parent / (SAT + ".json")

            def fake_queue(_repo, _commit, target):
                target.mkdir()
                (target / "review_queue.json").write_text(
                    canonical_json(queue()), encoding="utf-8")
                return {"machine_review_candidate_count": 2}

            with patch("scripts.build_vietnam_sunday_packet.queue_builder.prepare",
                       side_effect=fake_queue) as gen:
                result = build_from_state(
                    state_repo=d, state_commit="a" * 40,
                    week_ending=SAT, notes=notes, output=output)
            gen.assert_called_once()
            self.assertEqual(result["vietnam_sources"], 2)
            self.assertIs(result["email_sent"], False)
            self.assertEqual(len(json.loads(output.read_text())["items"]), 2)
            with self.assertRaises(VietnamFeederError):
                build_from_state(
                    state_repo=d, state_commit="a" * 40,
                    week_ending=SAT, notes=notes, output=output)

            output.unlink()
            with patch("scripts.build_vietnam_sunday_packet.queue_builder.prepare",
                       side_effect=ValueError("inconsistent shadow receipts")):
                with self.assertRaisesRegex(ValueError, "inconsistent"):
                    build_from_state(
                        state_repo=d, state_commit="a" * 40,
                        week_ending=SAT, notes=notes, output=output)
            self.assertFalse(output.exists())

    def test_no_output_on_bad_queue_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            qp, np, out = d / "queue.json", d / "notes.json", d / "out.json"
            qp.write_text(canonical_json(queue()), encoding="utf-8")
            np.write_text(canonical_json(NOTES), encoding="utf-8")
            self.assertIsNone(main(["--queue", str(qp), "--notes", str(np),
                                    "--week-ending", SAT, "--out", str(out)]))
            saved = out.read_bytes()
            with self.assertRaises(VietnamFeederError):
                main(["--queue", str(qp), "--notes", str(np),
                      "--week-ending", SAT, "--out", str(out)])
            self.assertEqual(out.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
