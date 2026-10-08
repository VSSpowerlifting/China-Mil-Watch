"""Synthetic only: Japan official-source Friday supplement boundaries.

No web requests, no source archives, no proof of document authenticity,
no reviewer attestations, no automated editorial use.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import render_japan_friday_supplement as japan  # noqa: E402


class JapanFridayUnsignedPacket(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(japan.DEFAULT_PACKET.read_text(encoding="utf-8"))

    def validate(self, packet=None):
        return japan.validate(self.packet if packet is None else packet)

    def test_four_sources_and_one_original_japanese_pair(self):
        result = self.validate()
        self.assertEqual(result["official_mod_public_urls"], 4)
        self.assertEqual(result["japanese_original_paired_to_english_release"], 1)
        self.assertEqual(result["japan_production_records_added"], 0)
        self.assertEqual(result["japan_records_admitted_to_weekly_writer"], 0)
        self.assertEqual(result["editorial_claims_approved"], 0)
        self.assertEqual(result["verified_original_archive_captures"], 0)
        self.assertEqual(result["automatic_emails_sent"], 0)
        self.assertTrue(result["requires_current_friday_recheck"])
        self.assertFalse(result["manuscript_or_publication_approved"])

    def test_render_contains_editorial_notes_and_exact_source_links(self):
        result = japan.render(self.packet)
        self.assertIn("JS Kunisaki", result)
        self.assertIn("56 missions", result)
        self.assertIn("280 tons", result)
        self.assertIn("Japanese original", result)
        self.assertIn("NOT approved, archived, or emailed", result)
        self.assertIn("Do NOT fabricate record IDs", result)
        for row in self.packet["source_candidates"]:
            self.assertIn(row["public_source_url"], result)
        self.assertNotIn("SOURCE RECORD ID: 123", result)

    def test_no_premature_friday_or_saturday_reporting(self):
        for key, invalid in (
            ("reporting_friday", "2026-10-08"),
            ("reviewed_as_of", "2026-10-09"),
            ("reporting_week_start", "2026-10-05"),
        ):
            data = copy.deepcopy(self.packet)
            data[key] = invalid
            with self.subTest(key=key):
                with self.assertRaises(japan.JapanBriefError):
                    self.validate(data)

    def test_source_date_never_exceeds_thursday_cutoff(self):
        data = copy.deepcopy(self.packet)
        data["source_candidates"][0]["publisher_date"] = "2026-10-09"
        with self.assertRaises(japan.JapanBriefError):
            self.validate(data)

    def test_issuer_host_and_stable_exact_urls_required(self):
        data = copy.deepcopy(self.packet)
        data["source_candidates"][0]["institution"] = "Japanese Joint Staff"
        with self.assertRaisesRegex(japan.JapanBriefError, "source-first"):
            self.validate(data)
        for bad in ("http://www.mod.go.jp/j/press/news/2026/10/06a.html",
                    "https://www.mod.go.jp.evil.example/en/article/2026/10/x",
                    "https://example.com/en/article/2026/10/x"):
            data = copy.deepcopy(self.packet)
            data["source_candidates"][0]["public_source_url"] = bad
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(japan.JapanBriefError, "URL"):
                    self.validate(data)

    def test_japanese_original_link_may_not_be_invented(self):
        data = copy.deepcopy(self.packet)
        data["source_candidates"][1]["japanese_original_url"] = (
            "https://www.mod.go.jp/j/press/news/2026/10/not-real.html"
        )
        with self.assertRaisesRegex(japan.JapanBriefError, "language-pair"):
            self.validate(data)

    def test_false_IPR_record_id_or_sha_rejected(self):
        for field, value in (
            ("ipr_record_id", 5555),
            ("first_party_original_capture_sha256", "f" * 64),
        ):
            data = copy.deepcopy(self.packet)
            data["source_candidates"][0][field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(japan.JapanBriefError, "fabricate"):
                    self.validate(data)

    def test_false_human_approval_rejected(self):
        for key in ("reviewer_verified_full_page", "editorial_approved"):
            data = copy.deepcopy(self.packet)
            data["source_candidates"][0][key] = True
            with self.subTest(key=key):
                with self.assertRaisesRegex(japan.JapanBriefError, "reviewer"):
                    self.validate(data)

    def test_writer_and_publication_switches_are_fail_closed(self):
        for key in japan.DISABLED_FLAGS:
            data = copy.deepcopy(self.packet)
            data["workflow"][key] = True
            with self.subTest(key=key):
                with self.assertRaisesRegex(japan.JapanBriefError, "silently promoted"):
                    self.validate(data)

    def test_no_impersonation_of_dylan_approval_or_automatic_send(self):
        data = copy.deepcopy(self.packet)
        data["workflow"]["email_sent"] = True
        with self.assertRaises(japan.JapanBriefError):
            self.validate(data)
        data = copy.deepcopy(self.packet)
        data["workflow"]["may_copy_into_dylan_draft_only_after_independent_review"] = False
        with self.assertRaises(japan.JapanBriefError):
            self.validate(data)

    def test_distinct_meetings_do_not_become_distinct_criminal_incidents(self):
        data = copy.deepcopy(self.packet)
        data["source_relationships"]["japan_us_alliance_communications"][
            "distinct_provisionally_attributed_issuing_institutions"
        ] = 3
        with self.assertRaisesRegex(japan.JapanBriefError, "not independent"):
            self.validate(data)
        data = copy.deepcopy(self.packet)
        data["source_relationships"]["japan_us_alliance_communications"][
            "recurring_issue"
        ] = "three independent incidents"
        with self.assertRaisesRegex(japan.JapanBriefError, "warnings"):
            self.validate(data)

    def test_no_fabricated_crossdesk_institutional_confirmations(self):
        data = copy.deepcopy(self.packet)
        data["source_relationships"]["japan_indonesia_disaster_relief_completion"][
            "independently_verified_external_institutions"
        ] = 1
        with self.assertRaisesRegex(japan.JapanBriefError, "not independent"):
            self.validate(data)

    def test_duplicate_candidate_missing_candidate_rejected(self):
        data = copy.deepcopy(self.packet)
        data["source_candidates"][1]["candidate_id"] = "JP-W41-01"
        with self.assertRaisesRegex(japan.JapanBriefError, "duplicate"):
            self.validate(data)
        data = copy.deepcopy(self.packet)
        data["source_candidates"].pop()
        with self.assertRaisesRegex(japan.JapanBriefError, "roster"):
            self.validate(data)

    def test_rights_notice_and_translation_caveat_cannot_disappear(self):
        data = copy.deepcopy(self.packet)
        data["source_terms_url"] = "https://example.com/terms"
        with self.assertRaisesRegex(japan.JapanBriefError, "terms"):
            self.validate(data)
        data = copy.deepcopy(self.packet)
        data["independent_review_needed"] = []
        with self.assertRaisesRegex(japan.JapanBriefError, "warnings"):
            self.validate(data)

    def test_cli_validate_is_readonly_and_reports_no_approvals(self):
        with tempfile.TemporaryDirectory() as temp:
            input_file = Path(temp) / "evidence.json"
            input_file.write_text(json.dumps(self.packet), encoding="utf-8")
            before = input_file.read_bytes()
            result = subprocess.run([
                sys.executable,
                str(ROOT / "scripts/render_japan_friday_supplement.py"),
                "validate", "--packet", str(input_file),
            ], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(output["japan_production_records_added"], 0)
            self.assertEqual(input_file.read_bytes(), before)

    def test_cli_render_outputs_only_text_and_does_not_write_state(self):
        with tempfile.TemporaryDirectory() as temp:
            input_file = Path(temp) / "evidence.json"
            input_file.write_text(json.dumps(self.packet), encoding="utf-8")
            before = input_file.read_bytes()
            result = subprocess.run([
                sys.executable,
                str(ROOT / "scripts/render_japan_friday_supplement.py"),
                "render", "--packet", str(input_file),
            ], cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PROVISIONAL FRIDAY EDITOR SUPPLEMENT", result.stdout)
            self.assertEqual(input_file.read_bytes(), before)

    def test_unknown_source_rejected_even_if_official_domain(self):
        data = copy.deepcopy(self.packet)
        data["source_candidates"][0]["candidate_id"] = "JP-W41-99"
        with self.assertRaisesRegex(japan.JapanBriefError, "unknown"):
            self.validate(data)

    def test_no_production_desk_or_taxonomy_activation(self):
        data = copy.deepcopy(self.packet)
        data["no_classification"] = False
        with self.assertRaisesRegex(japan.JapanBriefError, "assign"):
            self.validate(data)
        data = copy.deepcopy(self.packet)
        data["no_publication"] = False
        with self.assertRaisesRegex(japan.JapanBriefError, "publish"):
            self.validate(data)


if __name__ == "__main__":
    unittest.main()
