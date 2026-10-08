"""Synthetic contract checks for unapproved PCG-attributed PIA source discovery."""
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

from scripts import validate_ph_pcg_pia_sources as validator  # noqa: E402


class DisallowedInstitutionalImpersonation(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(validator.PACKET.read_text(encoding="utf-8"))

    def test_five_strict_candidate_urls_and_three_separate_false_issuer_cases(self):
        result = validator.validate(self.data)
        self.assertEqual(result["source_candidates"], 5)
        self.assertEqual(result["negative_controls"], 3)
        self.assertEqual(result["open_source_admission_gates"], 7)
        self.assertEqual(result["archived_source_records"], 0)
        self.assertFalse(result["collection_enabled"])
        self.assertFalse(result["human_original_issuer_authentication"])
        self.assertFalse(result["automatic_rights_clearance"])
        self.assertEqual(result["production_changes"], 0)

    def test_false_source_authentication_and_rights_status_rejected(self):
        for key in validator.NO_APPROVAL:
            data = copy.deepcopy(self.data)
            data["assertions"][key] = True
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                    validator.SourceAdmissionError, "cannot enable"
                ):
                    validator.validate(data)

    def test_issuer_and_host_are_separate_fields(self):
        data = copy.deepcopy(self.data)
        data["host_institution"] = "Philippine Coast Guard"
        with self.assertRaisesRegex(validator.SourceAdmissionError, "conflates"):
            validator.validate(data)
        data = copy.deepcopy(self.data)
        data["claimed_original_issuer"] = "Philippine Information Agency (PIA)"
        with self.assertRaisesRegex(validator.SourceAdmissionError, "conflates"):
            validator.validate(data)

    def test_issuer_claim_cannot_be_rewritten_as_verified(self):
        data = copy.deepcopy(self.data)
        data["claimed_issuer_evidence"] = "PCG original verified"
        with self.assertRaisesRegex(validator.SourceAdmissionError,
                                    "cannot be represented as verified"):
            validator.validate(data)

    def test_no_arbitrary_new_or_substituted_urls(self):
        for change in (
            "https://pia.gov.ph/news/not-an-archived-pcg-source/",
            "https://pia.gov.ph.evil.example/news/pcg-deploys-aircraft/",
            "http://pia.gov.ph/news/pcg-deploys-aircraft/",
        ):
            data = copy.deepcopy(self.data)
            data["candidates"][1]["url"] = change
            with self.subTest(url=change):
                with self.assertRaisesRegex(
                    validator.SourceAdmissionError, "historical host"
                ):
                    validator.validate(data)

    def test_hidden_future_publication_or_precise_time_rejected(self):
        for published in ("2026-10-09", "2026-09-28T13:40:00Z", "2026-02-30"):
            data = copy.deepcopy(self.data)
            data["candidates"][1]["host_page_date"] = published
            with self.subTest(date=published):
                with self.assertRaises(validator.SourceAdmissionError):
                    validator.validate(data)

    def test_claimed_pcg_byline_not_replaced_by_pia_staff(self):
        data = copy.deepcopy(self.data)
        data["candidates"][0]["byline"] = "Jimmyley Guzman"
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "historical host"
        ):
            validator.validate(data)

    def test_mirror_or_media_byline_cannot_be_inserted_as_pcg_original(self):
        data = copy.deepcopy(self.data)
        data["candidates"][0]["url"] = self.data[
            "excluded_or_separately_classified_leads"
        ][0]["url"]
        with self.assertRaises(validator.SourceAdmissionError):
            validator.validate(data)

    def test_originals_are_not_fabricated_from_visible_host_pages(self):
        for field, fake in (
            ("archive_identity", "pcg-0000001"),
            ("body_sha256", "0"*64),
            ("payload_sha256", "1"*64),
            ("origin_commit", "2"*40),
            ("owner_approval", {"reviewer": "SYNTHETIC"}),
        ):
            data = copy.deepcopy(self.data)
            data["candidates"][0][field] = fake
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    validator.SourceAdmissionError, "fabricate"
                ):
                    validator.validate(data)

    def test_one_candidate_removed_or_duplicated_rejected(self):
        data = copy.deepcopy(self.data)
        data["candidates"].pop()
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "missing or new"
        ):
            validator.validate(data)
        data = copy.deepcopy(self.data)
        data["candidates"][1] = copy.deepcopy(data["candidates"][0])
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "duplicate"
        ):
            validator.validate(data)

    def test_journalistic_report_about_pnp_does_not_become_pnp_original(self):
        data = copy.deepcopy(self.data)
        data["excluded_or_separately_classified_leads"][0]["category"] = (
            "pnp_original"
        )
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "must not be relabeled"
        ):
            validator.validate(data)
        data = copy.deepcopy(self.data)
        data["excluded_or_separately_classified_leads"][0]["byline"] = "PNP"
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "byline cannot become"
        ):
            validator.validate(data)

    def test_pco_issuer_is_not_pcg_even_when_speaking_about_pcg(self):
        data = copy.deepcopy(self.data)
        data["excluded_or_separately_classified_leads"][2][
            "do_not_admit_as_pcg_or_pnp_issued"
        ] = False
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "must not be relabeled"
        ):
            validator.validate(data)

    def test_all_seven_open_gates_required(self):
        data = copy.deepcopy(self.data)
        data["open_checks"].pop()
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "missing owner"
        ):
            validator.validate(data)
        data = copy.deepcopy(self.data)
        data["open_checks"][3]["status"] = "passed"
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "must remain pending"
        ):
            validator.validate(data)

    def test_rights_language_cannot_be_upgraded_to_unqualified_permission(self):
        data = copy.deepcopy(self.data)
        data["rights_note"] = "All PIA and embedded content cleared for copying."
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "conditional PIA rights"
        ):
            validator.validate(data)

    def test_empty_archive_attachment_keys_are_mandatory(self):
        data = copy.deepcopy(self.data)
        data["candidates"][2].pop("body_sha256")
        with self.assertRaisesRegex(
            validator.SourceAdmissionError, "schema drift"
        ):
            validator.validate(data)

    def test_cli_prints_no_authorized_collection_or_production(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_ph_pcg_pia_sources.py")],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["source_candidates"], 5)
        self.assertEqual(output["archived_source_records"], 0)
        self.assertFalse(output["collection_enabled"])

    def test_explicit_packet_file_path_is_readonly(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "packet.json"
            original = json.dumps(self.data)
            file.write_text(original, encoding="utf-8")
            result = subprocess.run(
                [sys.executable,
                 str(ROOT / "scripts/validate_ph_pcg_pia_sources.py"),
                 "--packet", str(file)],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(file.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
