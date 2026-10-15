"""Real staged three-source Korea intake: strictly structural, never source approval."""
import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.korea_private_research_candidates import KoreaResearchHold, ROOT, load
from core import korea_week42_private_review as intake
from scripts import korea_week42_private_review as cli


CLOCK = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)


def reported_complete(data, index=0):
    row = data["entries"][index]
    # Synthetic test-only line hash: structurally valid, NOT evidence from HWPX.
    row["evidence_anchors"] = [{
        "line_number": 1,
        "line_sha256": "a" * 64,
        "claim_kind": "reported_action",
        "editorial_linkage": "Test-only asserted source relationship, never independently authenticated",
    }]
    human = row["human_review"]
    human["disposition"] = "reviewed_source_version"
    human["reviewer"] = "Korean Reviewer Example"
    human["reviewed_at_utc"] = "2026-10-15T08:00:00Z"
    for key in intake.HUMAN_FLAGS:
        human[key] = True
    rights = row["rights_review"]
    rights["disposition"] = "assessed_for_local_use_only"
    rights["reviewer"] = "Rights Reviewer Example"
    rights["reviewed_at_utc"] = "2026-10-15T09:00:00Z"
    for key in intake.RIGHTS_FLAGS:
        rights[key] = True
    owner = row["owner_review"]
    owner["disposition"] = "acknowledged_local_rehearsal_only"
    owner["reviewer"] = "Owner Example"
    owner["reviewed_at_utc"] = "2026-10-15T10:00:00Z"
    owner["explicit_local_no_send_rehearsal_only"] = True
    return data


class KoreaWeek42HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.packet = intake.template()

    def test_real_three_sources_and_all_gates_pending(self):
        actual = load()
        self.assertEqual(len(self.packet["entries"]), 3)
        for draft, source in zip(self.packet["entries"], actual):
            for key in ("source_id", "source_url", "published_date",
                        "document_distribution_date", "source_content_sha256",
                        "hwpx_capture_sha256", "publisher_html_capture_sha256"):
                self.assertEqual(draft[key], source[key])
            self.assertEqual(draft["human_review"]["disposition"], "pending")
            self.assertEqual(draft["rights_review"]["disposition"], "pending")
            self.assertEqual(draft["owner_review"]["disposition"], "pending")
        r = intake.validate(self.packet, now=CLOCK)
        self.assertEqual(r["candidate_count"], 3)
        self.assertEqual(r["human_review_reports_structurally_complete"], 0)
        for forbidden in ("publication_authorized", "model_use_authorized",
                          "sunday_admission_authorized", "reviewer_identity_authenticated",
                          "source_line_evidence_independently_checked"):
            self.assertIs(r[forbidden], False)

    def test_any_pinned_original_identity_or_date_change_fails(self):
        for i in range(3):
            for key in ("source_id", "source_url", "published_date",
                        "document_distribution_date", "source_content_sha256",
                        "hwpx_capture_sha256", "publisher_html_capture_sha256"):
                packet = copy.deepcopy(self.packet)
                packet["entries"][i][key] += "X"
                with self.subTest(i=i, key=key), self.assertRaises(KoreaResearchHold):
                    intake.validate(packet, now=CLOCK)

    def test_reordered_missing_extra_disputed_or_unlicensed_sources_fail(self):
        for modification in ("reverse", "truncate", "extra", "disputed"):
            packet = copy.deepcopy(self.packet)
            if modification == "reverse":
                packet["entries"].reverse()
            elif modification == "truncate":
                packet["entries"].pop()
            elif modification == "extra":
                packet["entries"].append(copy.deepcopy(packet["entries"][0]))
            else:
                packet["entries"][0]["source_url"] = (
                    "https://www.korea.kr/briefing/pressReleaseView.do?newsId=156785161")
            with self.subTest(modification=modification), self.assertRaises(KoreaResearchHold):
                intake.validate(packet, now=CLOCK)

    def test_false_or_forged_approval_and_body_fields_fail(self):
        for key in intake.CONTROLS:
            packet = copy.deepcopy(self.packet)
            packet["controls"][key] = True
            with self.subTest(key=key), self.assertRaises(KoreaResearchHold):
                intake.validate(packet, now=CLOCK)
        packet = copy.deepcopy(self.packet)
        packet["entries"][0]["original_korean_body"] = "not permitted"
        with self.assertRaises(KoreaResearchHold):
            intake.validate(packet, now=CLOCK)
        packet = copy.deepcopy(self.packet)
        packet["entries"][0]["human_review"]["reviewer"] = "Unsigned Fake"
        with self.assertRaises(KoreaResearchHold):
            intake.validate(packet, now=CLOCK)
        packet = copy.deepcopy(self.packet)
        packet["entries"][0]["human_review"]["rendered_hwpx_compared"] = True
        with self.assertRaises(KoreaResearchHold):
            intake.validate(packet, now=CLOCK)

    def test_completed_report_is_not_legal_or_model_authorization(self):
        for i in range(3):
            reported_complete(self.packet, i)
        receipt = intake.validate(self.packet, now=CLOCK)
        self.assertEqual(receipt["human_review_reports_structurally_complete"], 3)
        self.assertEqual(receipt["rights_review_reports_structurally_complete"], 3)
        self.assertEqual(receipt["owner_local_rehearsal_reports_structurally_complete"], 3)
        self.assertIs(receipt["reviewer_identity_authenticated"], False)
        self.assertIs(receipt["source_line_evidence_independently_checked"], False)
        self.assertIs(receipt["legal_rights_adjudicated_by_software"], False)
        self.assertIs(receipt["source_rights_automatically_approved"], False)
        self.assertIs(receipt["sunday_admission_authorized"], False)
        self.assertIs(receipt["model_use_authorized"], False)
        self.assertNotIn("Korean Reviewer Example", json.dumps(receipt))
        self.assertNotIn("Rights Reviewer Example", json.dumps(receipt))

    def test_original_language_line_anchors_required_and_bounded(self):
        for corruption in ("missing", "duplicate", "bad-hash", "bad-kind",
                           "bad-linkage", "before-publication"):
            packet = copy.deepcopy(self.packet)
            reported_complete(packet, 2)
            anchors = packet["entries"][2]["evidence_anchors"]
            if corruption == "missing":
                anchors.clear()
            elif corruption == "duplicate":
                anchors.append(copy.deepcopy(anchors[0]))
            elif corruption == "bad-hash":
                anchors[0]["line_sha256"] = "not-a-digest"
            elif corruption == "bad-kind":
                anchors[0]["claim_kind"] = "completed_joint_deployment"
            elif corruption == "bad-linkage":
                anchors[0]["editorial_linkage"] = "<script>secret</script>"
            else:
                packet["entries"][2]["human_review"]["reviewed_at_utc"] = "2026-10-13T12:00:00Z"
                packet["entries"][2]["rights_review"]["reviewed_at_utc"] = "2026-10-13T13:00:00Z"
                packet["entries"][2]["owner_review"]["reviewed_at_utc"] = "2026-10-13T14:00:00Z"
            with self.subTest(corruption=corruption), self.assertRaises(KoreaResearchHold):
                intake.validate(packet, now=CLOCK)

    def test_review_stage_order_and_timestamp_fail_closed(self):
        packet = copy.deepcopy(self.packet)
        reported_complete(packet)
        packet["entries"][0]["human_review"]["reviewed_at_utc"] = "2026-10-16T08:00:00Z"
        with self.assertRaises(KoreaResearchHold):
            intake.validate(packet, now=CLOCK)
        packet = copy.deepcopy(self.packet)
        reported_complete(packet)
        packet["entries"][0]["rights_review"]["reviewed_at_utc"] = "2026-10-15T07:00:00Z"
        with self.assertRaises(KoreaResearchHold):
            intake.validate(packet, now=CLOCK)
        packet = copy.deepcopy(self.packet)
        reported_complete(packet)
        packet["entries"][0]["owner_review"]["reviewed_at_utc"] = "2026-10-15T08:30:00Z"
        with self.assertRaises(KoreaResearchHold):
            intake.validate(packet, now=CLOCK)
        packet = copy.deepcopy(self.packet)
        packet["entries"][0]["owner_review"]["disposition"] = "acknowledged_local_rehearsal_only"
        with self.assertRaises(KoreaResearchHold):
            intake.validate(packet, now=CLOCK)

    def test_private_create_check_file_mode_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "korea-review.json"
            self.assertEqual(intake.create_private_template(str(path)), path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            receipt = intake.check_private_review(str(path), now=CLOCK)
            self.assertEqual(receipt["candidate_count"], 3)
            with self.assertRaises(KoreaResearchHold):
                intake.create_private_template(str(path))
            with self.assertRaises(KoreaResearchHold):
                intake.create_private_template("relative.json")
            link = Path(folder) / "linked.json"
            link.symlink_to(path)
            with self.assertRaises(KoreaResearchHold):
                intake.check_private_review(str(link))
            if os.name == "posix":
                path.chmod(0o644)
                with self.assertRaises(KoreaResearchHold):
                    intake.check_private_review(str(path))
                path.chmod(0o600)
            path.write_text('{"schema":"foo","schema":"bar"}', encoding="utf-8")
            with self.assertRaises(KoreaResearchHold):
                intake.check_private_review(str(path))
            self.assertFalse((ROOT / "korea-review.json").exists())

    def test_cli_requires_acknowledgement_and_prints_no_private_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "review.json")
            with self.assertRaises(SystemExit):
                cli.main(["--create", path])
            self.assertFalse(Path(path).exists())
            self.assertEqual(cli.main(["--create", path, "--explicit-local-only"]), 0)
            self.assertEqual(cli.main(["--check", path, "--explicit-local-only"]), 0)


if __name__ == "__main__":
    unittest.main()
