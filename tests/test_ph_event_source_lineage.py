"""Synthetic contracts for conservative Philippine source-lineage counting.

These assertions never establish actual source independence or attest that
an editorial reviewer approved any article, event, or attribution.
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

from scripts import audit_ph_event_source_lineage as lineage  # noqa: E402


class PhilippinesOriginCounting(unittest.TestCase):
    def setUp(self):
        self.pilot = json.loads(lineage.PILOT.read_text(encoding="utf-8"))
        self.dossier = json.loads(lineage.DOSSIER.read_text(encoding="utf-8"))

    def check(self, pilot=None, dossier=None):
        return lineage.validate(self.pilot if pilot is None else pilot,
                                self.dossier if dossier is None else dossier)

    def test_three_sanlakas_AFP_reports_are_one_attributed_issuer(self):
        result = self.check()
        stage = next(x for x in result["event_candidates"]
                     if "sanlakas" in x["event_candidate_id"])
        self.assertEqual(stage["provisional_archived_article_count"], 3)
        self.assertEqual(stage["distinct_host_organizations"], 1)
        self.assertEqual(stage["distinct_provisionally_attributed_origins"], 1)
        self.assertEqual(stage["provisionally_attributed_origin_organizations"],
                         ["ph-afp"])
        self.assertEqual(stage["independently_authenticated_origin_organizations"], 0)
        self.assertFalse(stage["event_approved"])

    def test_September_meeting_is_separate_single_record_event(self):
        result = self.check()
        jpscc = next(x for x in result["event_candidates"]
                     if "jpscc" in x["event_candidate_id"])
        self.assertEqual(jpscc["provisional_archived_article_count"], 1)
        self.assertEqual(jpscc["distinct_provisionally_attributed_origins"], 1)
        self.assertEqual(jpscc["independently_authenticated_origin_organizations"], 0)

    def test_unarchived_pcg_byline_candidates_are_not_confirmations(self):
        result = self.check()
        self.assertEqual(result["total_archived_AFP_documents"], 4)
        self.assertEqual(result["total_unadmitted_PIA_hosted_PCG_credited_leads"], 2)
        self.assertTrue(result["all_external_issuer_authentication_pending"])
        self.assertFalse(result["independent_corroboration_confirmed"])
        self.assertFalse(result["reviewer_authentication_complete"])
        self.assertFalse(result["timeline_publication_approved"])
        self.assertEqual(result["production_writes"], 0)
        for event in result["event_candidates"]:
            self.assertEqual(event["external_PIA_PCG_leads_used_as_corrob"], 0)

    def test_pia_host_cannot_become_pcg_origin(self):
        modified = copy.deepcopy(self.pilot)
        modified["external_unadmitted_hosts"][0]["host_institution"] = "ph-pcg"
        with self.assertRaisesRegex(lineage.SourceLineageError, "PIA-hosted"):
            self.check(modified)

    def test_pcg_byline_cannot_become_authenticated_issuer(self):
        modified = copy.deepcopy(self.pilot)
        modified["external_unadmitted_hosts"][0]["issuer_authenticated"] = True
        with self.assertRaisesRegex(lineage.SourceLineageError, "unverified"):
            self.check(modified)

    def test_external_lead_cannot_be_slotted_into_unrelated_exercise(self):
        modified = copy.deepcopy(self.pilot)
        modified["external_unadmitted_hosts"][0]["link_to_candidate_event_ids"] = [
            "ph-2026-iax-02-pagsasanay-sanlakas"
        ]
        with self.assertRaisesRegex(lineage.SourceLineageError, "not AFP event evidence"):
            self.check(modified)

    def test_external_lead_cannot_forge_archive_capture(self):
        modified = copy.deepcopy(self.pilot)
        modified["external_unadmitted_hosts"][0]["source_capture_sha256"] = "0"*64
        with self.assertRaisesRegex(lineage.SourceLineageError, "unarchived"):
            self.check(modified)

    def test_external_lead_cannot_claim_rights_clearance(self):
        modified = copy.deepcopy(self.pilot)
        modified["external_unadmitted_hosts"][0]["rights_review_complete"] = True
        with self.assertRaisesRegex(lineage.SourceLineageError, "PIA-hosted"):
            self.check(modified)

    def test_single_pia_lead_substitution_rejected(self):
        modified = copy.deepcopy(self.pilot)
        modified["external_unadmitted_hosts"][0]["source_url"] = (
            "https://pia.gov.ph/news/unrelated/"
        )
        with self.assertRaisesRegex(lineage.SourceLineageError, "host lead"):
            self.check(modified)

    def test_event_group_merging_is_forbidden(self):
        modified = copy.deepcopy(self.pilot)
        modified["event_memberships"][0]["source_record_ids"].append("afp:1390")
        with self.assertRaisesRegex(lineage.SourceLineageError, "source-specific"):
            self.check(modified)

    def test_claim_source_cannot_move_between_exercise_and_jpscc(self):
        modified = copy.deepcopy(self.dossier)
        modified["claims"][0]["evidence"][0]["record_id"] = "afp:1390"
        with self.assertRaisesRegex(lineage.SourceLineageError, "grouping drifted"):
            self.check(dossier=modified)

    def test_new_event_is_not_silently_added(self):
        modified = copy.deepcopy(self.pilot)
        modified["event_memberships"].append({
            "candidate_event_id": "fictional-2026-third-event",
            "source_record_ids": ["afp:1394"], "candidate_only": True,
        })
        with self.assertRaisesRegex(lineage.SourceLineageError, "two specific"):
            self.check(modified)

    def test_primary_original_source_must_stay_afp(self):
        modified = copy.deepcopy(self.pilot)
        modified["archived_record_lineages"][0]["origin_institution"] = "ph-pcg"
        with self.assertRaisesRegex(lineage.SourceLineageError, "first-party"):
            self.check(modified)

    def test_archived_record_cannot_be_auto_approved(self):
        modified = copy.deepcopy(self.pilot)
        modified["archived_record_lineages"][0]["human_review_complete"] = True
        with self.assertRaisesRegex(lineage.SourceLineageError, "first-party"):
            self.check(modified)

    def test_event_permissions_cannot_be_auto_approved(self):
        for key in lineage.FALSE_GATES:
            modified = copy.deepcopy(self.pilot)
            modified["review_gates"][key] = True
            with self.subTest(gate=key):
                with self.assertRaisesRegex(lineage.SourceLineageError, "may not approve"):
                    self.check(modified)

    def test_original_AFP_capture_digest_mutation_rejected(self):
        modified = copy.deepcopy(self.dossier)
        modified["records"][0]["capture_sha256"] = "0"*64
        with self.assertRaisesRegex(lineage.SourceLineageError, "fingerprint"):
            self.check(dossier=modified)

    def test_original_AFP_source_record_deletion_rejected(self):
        modified = copy.deepcopy(self.dossier)
        modified["records"].pop()
        with self.assertRaisesRegex(lineage.SourceLineageError, "source set"):
            self.check(dossier=modified)

    def test_mirror_of_second_host_does_not_double_count_origin(self):
        synthetic_mirror_records = [
            {"origin_institution": "ph-pcg", "host_institution": "ph-pcg",
             "issuer_authenticated": True, "human_review_complete": True},
            {"origin_institution": "ph-pcg", "host_institution": "ph-pia",
             "issuer_authenticated": True, "human_review_complete": True},
        ]
        self.assertEqual(lineage.verified_origin_count(synthetic_mirror_records), 1)

    def test_two_separately_adjudicated_organizations_can_count_as_two(self):
        synthetic = [
            {"origin_institution": "ph-afp", "host_institution": "ph-afp",
             "issuer_authenticated": True, "human_review_complete": True},
            {"origin_institution": "ph-pcg", "host_institution": "ph-pia",
             "issuer_authenticated": True, "human_review_complete": True},
        ]
        self.assertEqual(lineage.verified_origin_count(synthetic), 2)

    def test_missing_either_issuer_or_human_attestation_cannot_count(self):
        incomplete = [
            {"origin_institution": "ph-afp", "host_institution": "ph-afp",
             "issuer_authenticated": True, "human_review_complete": False},
            {"origin_institution": "ph-pcg", "host_institution": "ph-pia",
             "issuer_authenticated": False, "human_review_complete": True},
        ]
        self.assertEqual(lineage.verified_origin_count(incomplete), 0)

    def test_host_and_origin_identifiers_cannot_be_missing(self):
        for row in (
            {"host_institution": "ph-pia", "issuer_authenticated": True,
             "human_review_complete": True},
            {"origin_institution": "ph-pcg", "issuer_authenticated": True,
             "human_review_complete": True},
        ):
            with self.assertRaisesRegex(lineage.SourceLineageError, "separate"):
                lineage.verified_origin_count([row])

    def test_cli_outputs_unchanged_report_and_does_not_write_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            pilot = Path(tmp) / "pilot.json"
            dossier = Path(tmp) / "dossier.json"
            pilot.write_text(json.dumps(self.pilot), encoding="utf-8")
            dossier.write_text(json.dumps(self.dossier), encoding="utf-8")
            before = (pilot.read_bytes(), dossier.read_bytes())
            out = subprocess.run(
                [sys.executable, str(ROOT / "scripts/audit_ph_event_source_lineage.py"),
                 "--pilot", str(pilot), "--dossier", str(dossier)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(out.returncode, 0, out.stderr)
            parsed = json.loads(out.stdout)
            self.assertFalse(parsed["timeline_publication_approved"])
            self.assertEqual(parsed["total_archived_AFP_documents"], 4)
            self.assertEqual((pilot.read_bytes(), dossier.read_bytes()), before)

    def test_missing_dossier_fails_closed(self):
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts/audit_ph_event_source_lineage.py"),
             "--dossier", "/definitely-not-an-evidence-file.json"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("Philippines source-lineage audit", out.stderr)


if __name__ == "__main__":
    unittest.main()
