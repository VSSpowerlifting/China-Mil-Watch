"""Synthetic contracts for role-blind, six-language HADR reviewer handoff.

No named person, source interpretation, or decision in these tests is genuine.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import topic_v2_hadr_language_handoff as handoff  # noqa: E402
from scripts.topic_v2_hadr_review import (  # noqa: E402
    TargetedReviewError,
    compare,
    make_template,
    validate_decisions,
)


def synthetic_reviewed(language: str) -> dict:
    """TEST DATA ONLY: none of these are human decisions or permissions."""
    payload = handoff.make_assignment(language)
    for row in payload["records"]:
        row["decision"] = "unassessable" if row["body_chars"] == 0 else "abstain"
        row["topics"] = []
        row["rationale"] = "SYNTHETIC TEST FIXTURE; not an actual source reading."
        row["read_full_source"] = row["body_chars"] != 0
        row["reviewer"] = {
            "name": "SYNTHETIC TEST REVIEWER, NOT A PERSON",
            "language_read": handoff.LANGUAGE_NAMES[language] if row["body_chars"] else "",
            "independent_reading_attested": True,
            "original_language_reading_attested": row["body_chars"] != 0,
        }
        row["reviewed_at_utc"] = "2026-10-08T04:59:00Z"
    return payload


class BlindLanguagePackets(unittest.TestCase):
    def test_all_records_covered_once_in_six_language_groups(self):
        canonical = make_template()
        expected = {r["pilot_id"] for r in canonical["records"]}
        groups = [handoff.make_assignment(lang) for lang in handoff.LANGUAGES]
        ids = [r["pilot_id"] for group in groups for r in group["records"]]
        self.assertEqual(len(groups), 6)
        self.assertEqual(len(ids), 11)
        self.assertEqual(len(set(ids)), 11)
        self.assertEqual(set(ids), expected)
        self.assertEqual(
            {g["source_language"]: len(g["records"]) for g in groups},
            {"en": 5, "zh": 2, "ja": 1, "id": 1, "vi": 1, "ko": 1}
        )

    def test_packets_are_subset_of_original_blind_packet(self):
        for lang, ids in handoff.LANGUAGES.items():
            with self.subTest(language=lang):
                text = handoff.packet_for_language(lang)
                sections = [line for line in text.splitlines()
                            if line.startswith("## P")]
                self.assertEqual(len(sections), len(ids))
                self.assertEqual(
                    {s.split()[1] for s in sections}, set(ids)
                )
                self.assertIn("entire pinned", text.lower())
                self.assertIn("model-selected", text.lower())
                self.assertNotIn("positive_candidate", text)
                self.assertNotIn("negative_control", text)
                self.assertNotIn("unassessable_body", text)
                self.assertNotIn("review_question", text)
                self.assertNotIn("event_key", text)
                self.assertNotIn("editor provisional role", text.lower())

    def test_english_packet_retains_explicit_bodyless_warning(self):
        text = handoff.packet_for_language("en")
        self.assertIn("## P36", text)
        self.assertIn("No archived body/excerpt", text)
        self.assertIn("Do not borrow another record", text)
        original = make_template()
        p36 = next(r for r in original["records"] if r["pilot_id"] == "P36")
        self.assertEqual(p36["body_chars"], 0)

    def test_unsigned_templates_do_not_insert_assigned_reviewers(self):
        for language in handoff.LANGUAGES:
            packet = handoff.make_assignment(language)
            self.assertEqual(packet["contract"]["taxonomy"]["version"], 2)
            self.assertEqual(packet["assignment_protocol"], 1)
            self.assertEqual(
                handoff.validate_assignment(packet, language)["reviewed"], 0
            )
            for row in packet["records"]:
                self.assertEqual(row["decision"], "pending")
                self.assertEqual(row["topics"], [])
                self.assertEqual(row["reviewer"]["name"], "")
                self.assertFalse(row["reviewer"]["independent_reading_attested"])

    def test_unknown_language_cannot_generate_assignments(self):
        with self.assertRaisesRegex(handoff.AssignmentError, "unsupported"):
            handoff.make_assignment("ru")
        with self.assertRaisesRegex(handoff.AssignmentError, "unsupported"):
            handoff.packet_for_language("xx")

    def test_documented_direct_cli_template_and_packet(self):
        for args in (("template", "--language", "ja"),
                     ("packet", "--language", "vi")):
            with self.subTest(args=args):
                run = subprocess.run(
                    [sys.executable,
                     str(ROOT / "scripts/topic_v2_hadr_language_handoff.py"),
                     *args],
                    cwd=ROOT, capture_output=True, text=True, check=False,
                )
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn("P38" if args[2] == "ja" else "P44", run.stdout)


class FailClosedAssembly(unittest.TestCase):
    def test_single_language_complete_fixture_is_structurally_valid(self):
        for language in handoff.LANGUAGES:
            result = handoff.validate_assignment(
                synthetic_reviewed(language), language, require_complete=True
            )
            self.assertEqual(result["pending"], 0)
            self.assertFalse(result["owner_approval"])
            self.assertFalse(result["identity_independently_authenticated"])
            self.assertEqual(result["production_assignments"], 0)

    def test_assemble_six_signed_synthetic_packets_matches_canonical_order(self):
        inputs = [synthetic_reviewed(lang) for lang in reversed(tuple(handoff.LANGUAGES))]
        result = handoff.assemble_assignments(inputs, require_complete=True)
        self.assertEqual(
            [r["pilot_id"] for r in result["records"]],
            [r["pilot_id"] for r in make_template()["records"]]
        )
        checked = validate_decisions(result, require_complete=True)
        self.assertEqual(checked["reviewed"], 11)
        self.assertEqual(checked["human_approval"], False)
        self.assertEqual(checked["production_assignments"], 0)

    def test_all_pending_packets_can_assemble_but_not_be_compared(self):
        packets = [handoff.make_assignment(lang) for lang in handoff.LANGUAGES]
        assembled = handoff.assemble_assignments(packets)
        self.assertEqual(validate_decisions(assembled)["reviewed"], 0)
        with self.assertRaisesRegex(handoff.AssignmentError, "all eleven"):
            handoff.assemble_assignments(packets, require_complete=True)
        with self.assertRaisesRegex(TargetedReviewError, "all eleven"):
            compare(assembled)

    def test_missing_and_duplicate_language_assignments_rejected(self):
        packet = [handoff.make_assignment(lang) for lang in handoff.LANGUAGES]
        with self.assertRaisesRegex(handoff.AssignmentError, "exactly six"):
            handoff.assemble_assignments(packet[:5])
        duplicate = copy.deepcopy(packet)
        duplicate[1] = copy.deepcopy(duplicate[0])
        with self.assertRaisesRegex(handoff.AssignmentError, "duplicate"):
            handoff.assemble_assignments(duplicate)

    def test_source_version_provenance_cannot_drift(self):
        data = handoff.make_assignment("zh")
        data["contract"]["taxonomy"]["version"] = 1
        with self.assertRaisesRegex(handoff.AssignmentError, "contract changed"):
            handoff.validate_assignment(data, "zh")
        data = handoff.make_assignment("zh")
        data["contract"]["packet_sha256"] = "0" * 64
        with self.assertRaisesRegex(handoff.AssignmentError, "contract changed"):
            handoff.validate_assignment(data, "zh")

    def test_record_identity_tampering_refused_by_merged_gate(self):
        packet = handoff.make_assignment("ja")
        packet["records"][0]["body_sha256"] = "0" * 64
        with self.assertRaisesRegex(handoff.AssignmentError, "source identity"):
            handoff.validate_assignment(packet, "ja")

    def test_extra_record_and_missing_record_refused(self):
        packet = handoff.make_assignment("zh")
        packet["records"].append(copy.deepcopy(packet["records"][0]))
        with self.assertRaisesRegex(handoff.AssignmentError, "membership"):
            handoff.validate_assignment(packet, "zh")
        packet = handoff.make_assignment("zh")
        packet["records"].pop()
        with self.assertRaisesRegex(handoff.AssignmentError, "membership"):
            handoff.validate_assignment(packet, "zh")

    def test_pending_records_cannot_claim_reviewer(self):
        packet = handoff.make_assignment("ko")
        packet["records"][0]["reviewer"]["name"] = "TEST REVIEWER"
        with self.assertRaisesRegex(handoff.AssignmentError, "pending"):
            handoff.validate_assignment(packet, "ko")

    def test_bodyless_cannot_be_classified_with_borrowed_text(self):
        packet = synthetic_reviewed("en")
        p36 = next(r for r in packet["records"] if r["pilot_id"] == "P36")
        p36["decision"] = "classified"
        p36["topics"] = ["military_hadr"]
        p36["read_full_source"] = True
        p36["reviewer"]["language_read"] = "English"
        p36["reviewer"]["original_language_reading_attested"] = True
        with self.assertRaisesRegex(handoff.AssignmentError, "missing-body"):
            handoff.validate_assignment(packet, "en")

    def test_missing_original_language_attestation_refused(self):
        packet = synthetic_reviewed("id")
        packet["records"][0]["reviewer"]["original_language_reading_attested"] = False
        with self.assertRaisesRegex(handoff.AssignmentError, "original-language"):
            handoff.validate_assignment(packet, "id")

    def test_unknown_language_or_extra_field_refused(self):
        packet = handoff.make_assignment("vi")
        packet["model_role"] = "positive_candidate"
        with self.assertRaisesRegex(handoff.AssignmentError, "top-level"):
            handoff.validate_assignment(packet, "vi")
        packet = handoff.make_assignment("vi")
        packet["source_language"] = "ko"
        with self.assertRaisesRegex(handoff.AssignmentError, "contract changed"):
            handoff.validate_assignment(packet, "vi")

    def test_cli_assembles_synthetic_packets_but_never_marks_approved(self):
        with tempfile.TemporaryDirectory() as root:
            paths = []
            for lang in handoff.LANGUAGES:
                path = Path(root) / (lang + ".json")
                path.write_text(json.dumps(synthetic_reviewed(lang)),
                                encoding="utf-8")
                paths.append(path)
            proc = subprocess.run(
                [sys.executable,
                 str(ROOT / "scripts/topic_v2_hadr_language_handoff.py"),
                 "assemble", "--decisions", *[str(p) for p in paths],
                 "--require-complete"],
                cwd=ROOT, capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(len(result["records"]), 11)
            self.assertEqual(result["taxonomy"]["version"], 2)
            self.assertNotIn("owner_approval", result)
            self.assertNotIn("model_roles", result)


if __name__ == "__main__":
    unittest.main()
