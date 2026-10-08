"""Offline contract for unsigned Vietnam MPS pilot-review queue."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import prepare_vietnam_mps_pilot as pilot
from scripts import prepare_vietnam_mps_review_queue as queue
from tests.test_vietnam_mps_pilot import COMMIT, TREE, SOURCE, approval, evidence


class VietnamMPSQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def compile(self, state=None):
        return queue.compile_queue(state if state is not None else evidence(),
                                   COMMIT, TREE)

    def test_exact_source_and_pinned_provenance(self):
        result = self.compile()
        self.assertEqual(result["state_commit"], COMMIT)
        self.assertEqual(result["state_tree"], TREE)
        self.assertEqual(result["state_branch"], "shadow/vietnam-mps-foreign-affairs")
        self.assertEqual(result["source_slug"], SOURCE)
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["machine_review_candidate_count"], 1)
        self.assertEqual(result["machine_hold_count"], 0)
        self.assertTrue(result["records"][0]["machine_review_candidate"])
        self.assertEqual(result["records"][0]["content_sha256"], "a" * 64)
        self.assertEqual(result["records"][0]["first_capture_sha256"], "b" * 64)
        self.assertEqual(result["records"][0]["title_original"], "A Vietnamese ministry title")

    def test_no_editorial_rights_or_production_approval_in_any_row(self):
        result = self.compile()
        self.assertEqual(result["human_approvals"], 0)
        self.assertEqual(result["rights_approvals"], 0)
        self.assertFalse(result["automatic_production_admission"])
        self.assertFalse(result["original_article_bodies_in_packet"])
        self.assertFalse(result["full_desk_qualification"])
        self.assertFalse(result["records"][0]["human_source_reviewed"])
        self.assertFalse(result["records"][0]["reuse_rights_reviewed"])
        self.assertFalse(result["records"][0]["production_publication_authorized"])
        self.assertNotIn("text_original", json.dumps(result))
        self.assertNotIn("Vietnamese text as captured", json.dumps(result))

    def test_bad_source_and_no_remote_clock_are_refused(self):
        ev = evidence()
        ev["source_slug"] = "vn_moit_energy_vi"
        with self.assertRaisesRegex(pilot.Refused, "only the MPS"):
            self.compile(ev)
        ev = evidence()
        ev["clock"] = None
        with self.assertRaisesRegex(pilot.Refused, "remote clock"):
            self.compile(ev)
        ev = evidence()
        ev["runs"][-1]["health"] = "fail"
        with self.assertRaisesRegex(pilot.Refused, "latest stored"):
            self.compile(ev)

    def test_anomaly_holds_a_record_without_discarding_it(self):
        ev = evidence()
        ev["observations"][0]["anomalies_json"] = '["published_time_changed"]'
        result = self.compile(ev)
        self.assertEqual(result["machine_review_candidate_count"], 0)
        self.assertEqual(result["machine_hold_count"], 1)
        self.assertEqual(result["records"][0]["machine_blockers"],
                         ["unresolved_observation_anomaly"])

    def test_empty_body_and_missing_capture_hold(self):
        ev = evidence()
        ev["versions"][0]["text_original"] = ""
        result = self.compile(ev)
        self.assertEqual(result["records"][0]["machine_blockers"],
                         ["body_not_complete_text"])
        ev = evidence()
        ev["observations"][0]["capture_sha256"] = "0" * 64
        result = self.compile(ev)
        self.assertEqual(result["records"][0]["machine_blockers"],
                         ["current_version_capture_unverified"])

    def test_noncanonical_record_is_held(self):
        ev = evidence()
        ev["records"][0]["canonical_url"] = "https://example.invalid/item"
        result = self.compile(ev)
        self.assertEqual(result["records"][0]["machine_blockers"],
                         ["foreign_or_noncanonical_identity"])

    def test_missing_current_version_held_not_exported_as_eligible(self):
        ev = evidence()
        ev["versions"] = []
        result = self.compile(ev)
        self.assertIn("current_content_version_missing", result["records"][0]["machine_blockers"])
        self.assertEqual(result["machine_review_candidate_count"], 0)

    def test_duplicate_identity_rejected(self):
        ev = evidence()
        ev["records"].append(copy.deepcopy(ev["records"][0]))
        with self.assertRaisesRegex(pilot.Refused, "duplicate"):
            self.compile(ev)

    def test_output_is_deterministic_with_content_and_pin(self):
        left, right = self.compile(), self.compile()
        self.assertEqual(queue._json(left), queue._json(right))
        self.assertEqual(left["queue_sha256"], right["queue_sha256"])
        other = queue.compile_queue(evidence(), "f" * 40, TREE)
        self.assertNotEqual(left["queue_sha256"], other["queue_sha256"])
        self.assertEqual(left["record_count"], other["record_count"])

    def test_unsigned_template_is_rejected_by_published_approval_contract(self):
        prepared = self.compile()
        template = queue.unsigned_template(prepared)
        self.assertIsNone(template["reviewer"])
        self.assertIsNone(template["reviewed_at_utc"])
        self.assertEqual(template["records"], [])
        self.assertTrue(all(v is None for v in template["_record_shape"]["checks"].values()))
        path = self.dir / "unsigned.json"
        path.write_text(queue._json(template))
        with self.assertRaisesRegex(pilot.Refused, "named human reviewer"):
            pilot.read_approval(path, COMMIT)

    def test_markup_has_urls_hashes_blockers_but_not_original_bodies(self):
        data = self.compile()
        markdown = queue.review_markdown(data)
        self.assertIn("https://bocongan.gov.vn/", markdown)
        self.assertIn(COMMIT, markdown)
        self.assertIn("NOT REVIEWED", markdown)
        self.assertNotIn("Vietnamese text as captured from the publisher", markdown)
        self.assertIn(data["queue_sha256"], markdown)

    def test_destination_refuses_existing_and_repository_paths_before_io(self):
        with self.assertRaisesRegex(pilot.Refused, "inside a repository checkout"):
            queue.prepare(self.dir, COMMIT, queue.ROOT / "review-out")
        existing = self.dir / "already"
        existing.mkdir()
        with self.assertRaisesRegex(pilot.Refused, "must not already exist"):
            queue.prepare(self.dir, COMMIT, existing)

    def test_full_state_commit_and_tree_required(self):
        with self.assertRaisesRegex(pilot.Refused, "exact commit/tree"):
            queue.compile_queue(evidence(), "abc", TREE)
        with self.assertRaisesRegex(pilot.Refused, "exact commit/tree"):
            queue.compile_queue(evidence(), COMMIT, "deadbeef")


if __name__ == "__main__":
    unittest.main()
