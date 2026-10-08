"""Offline contract tests for Vietnam's unapproved private Briefs candidate lane."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from core.vietnam_briefs_handoff import (
    VietnamCandidateError, load_candidates, PACKS_DIR,
)
from scripts.weekly_editorial_handoff import render_packet
from scripts.validate_editorial_return import (
    ReturnValidationError, validate_return,
)
from scripts.weekly_briefs_saturday_audit import parse_original_packet


SAT = "2026-10-10"
FRI = "2026-10-09"


def example():
    return {
        "source_identity": "mps-vi:1791199100",
        "source_slug": "vn_mps_foreign_affairs_vi",
        "canonical_url":
            "https://bocongan.gov.vn/bai-viet/official-example-1791199100",
        "published_date": "2026-10-05",
        "original_title": "Hợp tác công nghệ an ninh với các đối tác",
        "content_sha256": "a" * 64,
        "editorial_angle": "Should the editor compare this with another official source?",
        "review_status": "requires_independent_human_review",
    }


def pack():
    return {
        "schema": "vietnam-briefs-human-review-candidates/1",
        "week_ending": SAT,
        "state_commit": "b" * 40,
        "candidates": [example()],
    }


def scaffold():
    return {
        "editorial_status": "draft",
        "issue_number": None,
        "week_start": "2026-10-04",
        "week_ending": SAT,
        "desks": ["china", "singapore"],
        "coverage_by_desk": {
            "china": {"records": 1, "by_screening": {"analyzed": 1}},
            "singapore": {"records": 1, "by_screening": {"analyzed": 1}},
        },
        "source_trail": [
            {"record_id": 51, "desk": "china", "date": "2026-10-05",
             "source": "Source A", "title": "First real production record",
             "title_original": "First real production record", "lang": "en",
             "url": "https://example.org/one", "screening": "analyzed"},
            {"record_id": 52, "desk": "singapore", "date": "2026-10-06",
             "source": "Source B", "title": "Second real production record",
             "title_original": "Second real production record", "lang": "en",
             "url": "https://example.org/two", "screening": "analyzed"},
        ],
    }


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def load(self, data=None, *, sat=SAT, fri=FRI):
        path = self.directory / (sat + ".json")
        path.write_text(json.dumps(pack() if data is None else data,
                                   ensure_ascii=False), encoding="utf-8")
        return load_candidates(sat, fri, directory=self.directory)

    def test_real_week_pack_contains_exactly_two_machine_only_items(self):
        self.assertEqual(len(load_candidates(SAT, FRI)), 2)
        ids = {r["source_identity"] for r in load_candidates(SAT, FRI)}
        self.assertEqual(ids, {"mps-vi:1791199100", "mps-vi:1791199677"})
        self.assertEqual(load_candidates("2026-10-17", "2026-10-16"), [])

    def test_sunday_full_week_handoff_preserves_friday_shadow_candidates(self):
        # On Sunday the full-week production draft uses Saturday as its
        # cutoff. The two pinned MPS candidates remain available to the
        # editor, while none becomes a production source-trail record.
        friday = load_candidates(SAT, FRI)
        sunday = load_candidates(SAT, SAT)
        self.assertEqual(sunday, friday)
        packet = render_packet(scaffold(), as_of=SAT, vietnam_candidates=sunday)
        self.assertIn("VIETNAM SHADOW CANDIDATES", packet)
        self.assertIn("REQUIRES INDEPENDENT HUMAN REVIEW", packet)
        self.assertNotIn("Desks: china, singapore, vietnam", packet)
        self.assertNotIn("Record mps-vi:", packet)

    def test_sunday_does_not_expand_unreviewed_candidate_source_window(self):
        fixture = pack()
        fixture["candidates"][0]["published_date"] = SAT
        with self.assertRaisesRegex(VietnamCandidateError, "Sunday-Friday"):
            self.load(fixture, sat=SAT, fri=SAT)

    def test_valid_local_candidate_is_unapproved(self):
        rows = self.load()
        self.assertEqual(rows[0]["review_status"],
                         "requires_independent_human_review")
        self.assertNotIn("body", rows[0])
        self.assertEqual(rows[0]["state_commit"], "b" * 40)

    def test_wrong_week_or_cutoff_refused(self):
        for sat, fri in [(SAT, "2026-10-08"),
                         ("2026-10-09", "2026-10-08"),
                         (SAT, "2026-10-10")]:
            with self.subTest(sat=sat, fri=fri), self.assertRaises(VietnamCandidateError):
                load_candidates(sat, fri, directory=self.directory)

    def test_out_of_week_dates_refused(self):
        for day in ("2026-10-02", "2026-10-03", "2026-10-10",
                    "2026-10-11"):
            p = pack()
            p["candidates"][0]["published_date"] = day
            with self.subTest(date=day), self.assertRaises(VietnamCandidateError):
                self.load(p)

    def test_unapproved_only_no_forged_review_flags(self):
        for state in ("approved", "human_reviewed", "", None, True):
            p = pack()
            p["candidates"][0]["review_status"] = state
            with self.subTest(state=state), self.assertRaises(VietnamCandidateError):
                self.load(p)

    def test_rejects_copied_bodies_translations_and_extra_fields(self):
        for key in ("body", "translation", "reviewed_by", "rights_approved"):
            p = pack()
            p["candidates"][0][key] = "not allowed"
            with self.subTest(key=key), self.assertRaises(VietnamCandidateError):
                self.load(p)

    def test_rejects_wrong_domain_http_userinfo_query_and_id_mismatch(self):
        urls = [
            "http://bocongan.gov.vn/bai-viet/official-example-1791199100",
            "https://bocongan.gov.vn.evil.test/bai-viet/official-example-1791199100",
            "https://evil@bocongan.gov.vn/bai-viet/official-example-1791199100",
            "https://bocongan.gov.vn/bai-viet/official-example-1791199100?id=2",
            "https://bocongan.gov.vn/bai-viet/official-example-1791199101",
            "https://bocongan.gov.vn:bad/bai-viet/official-example-1791199100",
            "https://bocongan.gov.vn/bai-viet/official-example-1791199100#frag",
        ]
        for value in urls:
            p = pack()
            p["candidates"][0]["canonical_url"] = value
            with self.subTest(url=value), self.assertRaises(VietnamCandidateError):
                self.load(p)

    def test_missing_commit_hash_and_body_hash_refused(self):
        for key, value in (("state_commit", "b" * 39),
                           ("content_sha256", "invalid")):
            p = pack()
            if key == "state_commit":
                p[key] = value
            else:
                p["candidates"][0][key] = value
            with self.subTest(key=key), self.assertRaises(VietnamCandidateError):
                self.load(p)

    def test_duplicate_identity_refused(self):
        p = pack()
        p["candidates"].append(copy.deepcopy(p["candidates"][0]))
        with self.assertRaises(VietnamCandidateError):
            self.load(p)

    def test_duplicate_json_keys_refused(self):
        path = self.directory / (SAT + ".json")
        path.write_text('{"schema":"vietnam-briefs-human-review-candidates/1",'
                        '"schema":"different","week_ending":"2026-10-10",'
                        '"state_commit":"' + "b" * 40 + '","candidates":[]}',
                        encoding="utf-8")
        with self.assertRaises(VietnamCandidateError):
            load_candidates(SAT, FRI, directory=self.directory)

    def test_dangling_symlink_packet_refused(self):
        dangling = self.directory / (SAT + ".json")
        dangling.symlink_to(self.directory / "absent.json")
        with self.assertRaisesRegex(VietnamCandidateError, "unsafe candidate"):
            load_candidates(SAT, FRI, directory=self.directory)

    def test_packet_is_separate_from_production_records(self):
        rows = self.load()
        text = render_packet(scaffold(), as_of=FRI, vietnam_candidates=rows)
        self.assertIn("VIETNAM SHADOW CANDIDATES", text)
        self.assertIn("REQUIRES INDEPENDENT HUMAN REVIEW", text)
        self.assertIn(rows[0]["canonical_url"], text)
        self.assertNotIn("Record mps-vi", text)
        self.assertNotIn("Desks: china, singapore, vietnam", text)
        self.assertEqual(text.count("END OF SOURCE APPENDIX"), 1)
        self.assertEqual(text.count("=== SOURCE APPENDIX — DO NOT EDIT ==="), 1)
        self.assertTrue(text.rstrip().endswith("END OF UNAPPROVED WORKSHEET"))

    def test_editorial_return_cannot_alter_candidate_packet(self):
        rows = self.load()
        original = render_packet(scaffold(), as_of=FRI, vietnam_candidates=rows)
        edited = original.replace("One concrete development, not a regional roundup",
                                  "A source-specific revised title", 1)
        result = validate_return(original, edited)
        self.assertEqual(result["source_records"], 2)
        tampered = edited.replace(rows[0]["canonical_url"], "https://example.com/forgery")
        with self.assertRaises(ReturnValidationError):
            validate_return(original, tampered)

    def test_saturday_audit_ignores_unapproved_external_candidates(self):
        rows = self.load()
        packet = render_packet(scaffold(), as_of=FRI, vietnam_candidates=rows)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "original.txt"
            p.write_text(packet, encoding="utf-8")
            parsed = parse_original_packet(p, saturday=__import__("datetime").date(2026, 10, 10))
        self.assertEqual(parsed["records"], {51: "china", 52: "singapore"})


if __name__ == "__main__":
    unittest.main()
