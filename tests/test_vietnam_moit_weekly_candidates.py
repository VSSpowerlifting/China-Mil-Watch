"""Synthetic, no-network tests: MOIT metadata does NOT imply approval."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.collection.vietnam_sources import SOURCES
from scripts.prepare_vietnam_moit_weekly_candidates import (
    MOITInventoryRefused, MOIT_SOURCES, SCHEMA, canonical, summary, prepare, main,
)

E = "vn_moit_energy_vi"
I = "vn_moit_foundational_industry_vi"
SHADOW = "a" * 40
TREE = "b" * 40
SOURCES_URL = {
    E: "https://moit.gov.vn/tin-tuc/bo-cong-thuong-lay-y-kien-du-thao-nghi-dinh-ve-kinh-doanh-xang-dau.html",
    I: "https://moit.gov.vn/tin-tuc/hoi-thao-khoa-hoc-quoc-gia-dinh-huong-phat-trien-cong-nghiep-ho-tro-viet-nam-.html",
}


def fixture(slug=E, published="2026-09-30"):
    url = SOURCES_URL[slug]
    ident = SOURCES[slug].identity(url)
    record = {
        "source_slug": slug, "source_identity": ident,
        "url": url, "canonical_url": url, "published_date": published,
        "current_content_sha256": "c" * 64,
    }
    version = {
        "source_identity": ident, "content_sha256": "c" * 64,
        "body_status": "text",
        "title_original": "Bộ Công Thương thảo luận định hướng ngành năng lượng",
        "text_original": "Thông tin cơ quan chủ quản về lĩnh vực năng lượng.",
        "first_seen_run": "run-1", "first_capture_sha256": "d" * 64,
    }
    observation = {
        "source_identity": ident, "run_id": "run-1",
        "content_sha256": "c" * 64, "capture_sha256": "d" * 64,
        "anomalies_json": "[]",
    }
    return {
        "source_slug": slug,
        "clock": {"day_zero_utc": "2026-10-07T17:16:45+00:00"},
        "runs": [{"run_id": "run-1", "target_date": "2026-09-30", "health": "ok"},
                 {"run_id": "run-2", "target_date": "2026-10-07", "health": "ok"}],
        "records": [record], "versions": [version],
        "observations": [observation],
    }


class MOITCandidateTests(unittest.TestCase):
    def test_actual_october_week_range_cannot_reuse_old_moit_publications(self):
        for slug in (E, I):
            result = summary(fixture(slug), slug, SHADOW, TREE, "2026-10-10")
            self.assertEqual(result["schema"], SCHEMA)
            self.assertEqual(result["in_window_record_count"], 0)
            self.assertEqual(result["machine_eligible_in_window"], 0)
            self.assertEqual(result["total_archived_records"], 1)
            self.assertEqual(result["out_of_window_archived_records"], 1)
            self.assertEqual(result["items"], [])
            self.assertEqual(result["last_successful_observed_target"], "2026-10-07")
            self.assertFalse(result["full_week_collection_verified"])
            self.assertFalse(result["publisher_silence_verified"])
            self.assertFalse(result["qualified_production_desk"])
            self.assertFalse(result["original_full_text_included"])
            self.assertEqual(result["human_approvals"], 0)
            raw = dict(result)
            digest = raw.pop("inventory_sha256")
            self.assertEqual(digest, hashlib.sha256(canonical(raw).encode()).hexdigest())

    def test_september_window_produces_one_official_metadata_lead_only(self):
        for slug in (E, I):
            result = summary(fixture(slug), slug, SHADOW, TREE, "2026-10-03")
            self.assertEqual(result["in_window_record_count"], 1)
            self.assertEqual(result["machine_eligible_in_window"], 1)
            row = result["items"][0]
            self.assertEqual(row["source_identity"],
                             SOURCES[slug].identity(SOURCES_URL[slug]))
            self.assertEqual(row["hash_rule"], "moit-vi-content-v1")
            self.assertEqual(row["source_content_sha256"], "c" * 64)
            self.assertEqual(row["machine_blockers"], [])
            self.assertFalse(row["human_source_reviewed"])
            self.assertFalse(row["source_use_authorized"])
            self.assertFalse(row["private_model_contribution_authorized"])
            for forbidden in ("text_original", "article_body",
                              "lead_original", "blocks_json", "full_translation"):
                self.assertNotIn(forbidden, row)

    def test_missing_version_or_capture_holds_instead_of_promoting(self):
        for kind in ("version", "capture", "anomaly", "body", "title"):
            ev = fixture()
            if kind == "version":
                ev["versions"] = []
            elif kind == "capture":
                ev["observations"] = []
            elif kind == "anomaly":
                ev["observations"][0]["anomalies_json"] = '["wrong_capture"]'
            elif kind == "body":
                ev["versions"][0]["body_status"] = "blocked"
            else:
                ev["versions"][0]["title_original"] = ""
            result = summary(ev, E, SHADOW, TREE, "2026-10-03")
            with self.subTest(kind=kind):
                self.assertEqual(result["machine_eligible_in_window"], 0)
                self.assertEqual(result["machine_held_in_window"], 1)
                self.assertTrue(result["items"][0]["machine_blockers"])

    def test_first_party_identity_spoof_and_wrong_source_family_refused(self):
        bad = fixture()
        bad["records"][0]["url"] = "https://moit.gov.vn.evil.invalid/tin-tuc/a.html"
        with self.assertRaises(MOITInventoryRefused):
            summary(bad, E, SHADOW, TREE, "2026-10-03")
        with self.assertRaises(MOITInventoryRefused):
            summary(fixture(E), I, SHADOW, TREE, "2026-10-03")
        with self.assertRaises(MOITInventoryRefused):
            summary(fixture(E), "vn_mps_foreign_affairs_vi", SHADOW, TREE, "2026-10-03")
        with self.assertRaises(MOITInventoryRefused):
            summary(fixture(E), E, "not-a-git-commit", TREE, "2026-10-03")

    def test_duplicate_source_id_and_invalid_report_week_are_refused(self):
        ev = fixture()
        ev["records"].append(copy.deepcopy(ev["records"][0]))
        with self.assertRaisesRegex(MOITInventoryRefused, "duplicate"):
            summary(ev, E, SHADOW, TREE, "2026-10-03")
        for week in ("2026-10-02", "2026-02-30", "2026-10-3"):
            with self.subTest(week=week), self.assertRaises(MOITInventoryRefused):
                summary(fixture(), E, SHADOW, TREE, week)

    def test_git_commit_and_isolated_branch_must_be_verified_before_output(self):
        for slug in (E, I):
            with patch("scripts.prepare_vietnam_moit_weekly_candidates.formal.resolve_state_repo",
                       return_value=Path("/fake/repo")), \
                 patch("scripts.prepare_vietnam_moit_weekly_candidates.formal.verify_state_commit",
                       return_value={"state_tree": TREE}) as verified, \
                 patch("scripts.prepare_vietnam_moit_weekly_candidates.formal.export_state_tree",
                       return_value=Path("/fake/state")), \
                 patch("scripts.prepare_vietnam_moit_weekly_candidates.ministry.review",
                       return_value=fixture(slug)) as reviewed:
                result = prepare("/fake/repo", SHADOW, slug, "2026-10-10")
            verified.assert_called_once_with(
                Path("/fake/repo"), SHADOW, SOURCES[slug].state_branch)
            reviewed.assert_called_once_with(Path("/fake/state"), slug)
            self.assertEqual(result["state_commit"], SHADOW)

    def test_cli_fails_closed_on_source_or_output_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            existing = Path(tmp) / "existing.json"
            existing.write_text("not authorized", encoding="utf-8")
            with self.assertRaisesRegex(MOITInventoryRefused, "new private file"):
                main(["--state-repo", tmp, "--state-commit", SHADOW,
                      "--source", E, "--week-ending", "2026-10-03",
                      "--out", str(existing)])
            self.assertEqual(existing.read_text(), "not authorized")


if __name__ == "__main__":
    unittest.main()
