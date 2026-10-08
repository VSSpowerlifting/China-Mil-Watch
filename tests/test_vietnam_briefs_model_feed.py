"""No-network, no-publisher, no-production tests of Sunday Vietnam shadow feeder."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from core.brief_editorial_evidence import (
    load_editorial_evidence, metadata_only_summary,
)
from scripts.prepare_vietnam_briefs_model_evidence import (
    VietnamFeedRefused, assemble, metadata_card, prepare,
    require_current_week_shadow,
)

ROOT = Path(__file__).resolve().parents[1]
SAT = "2026-10-10"
COMMIT = "b" * 40
TREE = "a" * 40


def original():
    return load_editorial_evidence(SAT, SAT)


def record_from(item):
    identity = "mps-vi:" + item["id"].split("-")[-1]
    return {
        "source_slug": "vn_mps_foreign_affairs_vi",
        "source_identity": identity,
        "canonical_url": item["source_url"],
        "published_date": item["published_date"],
        "title_original": item["title_original"],
        "content_sha256": item["source_content_sha256"],
        "body_status": "text",
        "body_character_count": 475,
        "machine_review_candidate": True,
        "machine_blockers": [],
    }


def new_source(day="2026-10-09"):
    return {
        "source_slug": "vn_mps_foreign_affairs_vi",
        "source_identity": "mps-vi:1791200000",
        "canonical_url": (
            "https://bocongan.gov.vn/bai-viet/"
            "hop-tac-an-ninh-quoc-te-1791200000"
        ),
        "published_date": day,
        "title_original": "Hợp tác an ninh và quan hệ quốc tế",
        "content_sha256": "d" * 64,
        "body_status": "text",
        "body_character_count": 800,
        "machine_review_candidate": True,
        "machine_blockers": [],
    }


def queue():
    return {
        "schema": "vietnam-mps-pilot-review-queue/1",
        "source_slug": "vn_mps_foreign_affairs_vi",
        "state_branch": "shadow/vietnam-mps-foreign-affairs",
        "state_commit": COMMIT,
        "human_approvals": 0,
        "rights_approvals": 0,
        "automatic_production_admission": False,
        "full_desk_qualification": False,
        "records": [record_from(x) for x in original() if x["desk"] == "vietnam"],
    }


class VietnamSundayFeedTests(unittest.TestCase):
    def test_current_versions_retain_both_editorial_synopses_with_new_commit(self):
        packet, stats = assemble(queue(), original(), COMMIT, SAT)
        self.assertEqual(stats["vietnam_original_synopses_retained"], 2)
        self.assertEqual(stats["japan_research_items"], 3)
        self.assertEqual(stats["human_approvals_granted"], 0)
        self.assertEqual(stats["public_records_admitted"], 0)
        self.assertEqual(len(packet["items"]), 5)
        vn = [x for x in packet["items"] if x["desk"] == "vietnam"]
        self.assertTrue(all(x["state_commit"] == COMMIT for x in vn))
        self.assertTrue(all(x["source_kind"] == "shadow-extracted-original" for x in vn))

    def test_new_source_enters_as_title_only_not_invented_translation(self):
        q = queue()
        q["records"].append(new_source())
        packet, stats = assemble(q, original(), COMMIT, SAT)
        self.assertEqual(stats["vietnam_metadata_only"], 1)
        current = next(x for x in packet["items"]
                       if x["id"] == "VN-MPS-1791200000")
        self.assertEqual(current["topics"], ["source_discovery"])
        self.assertEqual(current["summary"], metadata_only_summary("2026-10-09"))
        self.assertEqual(current["source_kind"], "shadow-metadata-only")
        self.assertNotIn("article_body", json.dumps(current))
        self.assertIn("not the truth", " ".join(current["caveats"]))
        self.assertEqual(current["source_content_sha256"], "d" * 64)

    def test_changed_original_cannot_keep_old_substantive_synopsis(self):
        q = queue()
        q["records"][0]["content_sha256"] = "f" * 64
        packet, stats = assemble(q, original(), COMMIT, SAT)
        self.assertEqual(stats["vietnam_metadata_only"], 1)
        downgraded = next(x for x in packet["items"]
                          if x["source_content_sha256"] == "f" * 64)
        self.assertEqual(downgraded["source_kind"], "shadow-metadata-only")
        self.assertEqual(downgraded["topics"], ["source_discovery"])
        self.assertEqual(downgraded["summary"],
                         metadata_only_summary(downgraded["published_date"]))

    def test_bad_urls_date_mismatches_or_foreign_source_refused(self):
        for field, value in (
            ("canonical_url", "https://bocongan.gov.vn.evil.test/bai-viet/x-1791199100"),
            ("canonical_url", "http://bocongan.gov.vn/bai-viet/x-1791199100"),
            ("title_original", "Corrupted original title"),
            ("published_date", "2026-10-03"),
            ("source_slug", "vn_journal_english"),
        ):
            q = queue()
            q["records"][0][field] = value
            with self.subTest(field=field), self.assertRaises(VietnamFeedRefused):
                assemble(q, original(), COMMIT, SAT)

    def test_held_or_outside_week_source_never_reaches_model(self):
        q = queue()
        q["records"].append(new_source("2026-10-02"))
        p, stats = assemble(q, original(), COMMIT, SAT)
        self.assertEqual(stats["vietnam_items_merged"], 2)
        q["records"][-1]["published_date"] = "2026-10-08"
        q["records"][-1]["machine_review_candidate"] = False
        q["records"][-1]["machine_blockers"] = ["unresolved_observation_anomaly"]
        p, stats = assemble(q, original(), COMMIT, SAT)
        self.assertEqual(stats["vietnam_items_merged"], 2)
        self.assertNotIn("VN-MPS-1791200000", [x["id"] for x in p["items"]])

    def test_queue_may_not_forge_approval_or_production(self):
        for field, value in (
            ("human_approvals", 1),
            ("rights_approvals", 1),
            ("full_desk_qualification", True),
            ("automatic_production_admission", True),
            ("state_branch", "shadow/japan"),
        ):
            q = queue()
            q[field] = value
            with self.subTest(field=field), self.assertRaises(VietnamFeedRefused):
                assemble(q, original(), COMMIT, SAT)

    def test_duplicate_or_missing_inventory_candidates_refused(self):
        q = queue()
        q["records"] = q["records"][:1]
        with self.assertRaisesRegex(VietnamFeedRefused, "missing"):
            assemble(q, original(), COMMIT, SAT)
        q = queue()
        q["records"].append(copy.deepcopy(q["records"][0]))
        with self.assertRaises(VietnamFeedRefused):
            assemble(q, original(), COMMIT, SAT)

    def test_stale_healthy_shadow_state_rejected_before_model_evidence(self):
        for target_date in ("2026-10-05", "2026-10-12"):
            evidence = {"runs": [{
                "health": "ok", "target_date": target_date,
                "finished_utc": "2026-10-12T18:17:00+00:00",
            }]}
            with self.subTest(target=target_date), self.assertRaisesRegex(
                    VietnamFeedRefused, "stale"):
                require_current_week_shadow(
                    evidence, SAT, observed_on=date(2026, 10, 11))
        valid = {"runs": [{
            "health": "ok", "target_date": "2026-10-10",
            "finished_utc": "2026-10-10T19:03:00+00:00",
        }]}
        self.assertEqual(require_current_week_shadow(
            valid, SAT, observed_on=date(2026, 10, 11)), SAT)
        rehearsal = {"runs": [{
            "health": "ok", "target_date": "2026-10-07",
            "finished_utc": "2026-10-07T19:03:00+00:00",
        }]}
        self.assertEqual(require_current_week_shadow(
            rehearsal, SAT, observed_on=date(2026, 10, 8)), "2026-10-07")
        with self.assertRaisesRegex(VietnamFeedRefused, "stale"):
            require_current_week_shadow(
                rehearsal, SAT, observed_on=date(2026, 10, 11))
        valid["runs"][0]["health"] = "fail"
        with self.assertRaisesRegex(VietnamFeedRefused, "not healthy"):
            require_current_week_shadow(
                valid, SAT, observed_on=date(2026, 10, 11))

    def test_private_output_only_after_git_and_source_review(self):
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp)
            state = d / "state-git"
            state.mkdir()
            output = d / "private" / (SAT + ".json")
            def verify(repo, commit, branch):
                self.assertEqual(branch, "shadow/vietnam-mps-foreign-affairs")
                self.assertIn(commit, [COMMIT] + [
                    x["state_commit"] for x in original() if x["desk"] == "vietnam"])
                return {"state_commit": commit, "state_tree": TREE,
                        "state_ref_tip": COMMIT}
            with patch("scripts.prepare_vietnam_briefs_model_evidence.formal.resolve_state_repo",
                       return_value=state), \
                 patch("scripts.prepare_vietnam_briefs_model_evidence.formal.verify_state_commit",
                       side_effect=verify), \
                 patch("scripts.prepare_vietnam_briefs_model_evidence.formal.export_state_tree",
                       side_effect=lambda repo, sha, dest: dest), \
                 patch("scripts.prepare_vietnam_briefs_model_evidence.ministry.review",
                       return_value={"runs": [{
                           "health": "ok", "target_date": "2026-10-10",
                           "finished_utc": "2026-10-10T19:03:00+00:00",
                       }]}), \
                 patch("scripts.prepare_vietnam_briefs_model_evidence.compile_queue",
                       return_value=queue()):
                result = prepare(state, COMMIT, SAT, output,
                                 observed_on=date(2026, 10, 11))
            self.assertEqual(result["vietnam_original_synopses_retained"], 2)
            self.assertEqual(result["public_records_admitted"], 0)
            self.assertTrue(output.is_file())
            self.assertEqual(
                len(load_editorial_evidence(SAT, SAT, directory=output.parent)), 5)
            self.assertNotIn("text_original", output.read_text())

    def test_stale_git_branch_tip_refused_before_source_review(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / "clone"
            state.mkdir()
            out = Path(temp) / (SAT + ".json")
            with patch("scripts.prepare_vietnam_briefs_model_evidence.formal.resolve_state_repo",
                       return_value=state), \
                 patch("scripts.prepare_vietnam_briefs_model_evidence.formal.verify_state_commit",
                       return_value={"state_tree": TREE,
                                     "state_ref_tip": "9" * 40}), \
                 patch("scripts.prepare_vietnam_briefs_model_evidence.ministry.review") as review:
                with self.assertRaisesRegex(VietnamFeedRefused, "current remote"):
                    prepare(state, COMMIT, SAT, out)
                review.assert_not_called()
            self.assertFalse(out.exists())

    def test_invalid_output_location_no_git_state_touch(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / (SAT + ".json")
            path.symlink_to(Path(temp) / "absent.json")
            with self.assertRaisesRegex(VietnamFeedRefused, "symlink"):
                prepare(Path(temp), COMMIT, SAT, path)
            self.assertTrue(path.is_symlink())


if __name__ == "__main__":
    unittest.main()
