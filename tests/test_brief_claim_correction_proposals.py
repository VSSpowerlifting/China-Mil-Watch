"""Draft Brief correction review cannot mutate or approve published materials."""
import copy
import json
from pathlib import Path
import unittest

from scripts.audit_brief_claim_correction_proposals import (
    ISSUES, PACKET, RECORDS, audit,
)

# Frozen October 14 evidence (5,230 records, 5,144 China records).
# Live output/corpus-index.json advances with daily collection and is not
# the source of truth for exact 2026-10-14 historical audit assertions.
INDEX = Path(__file__).resolve().parent / "fixtures/china-corpus-index-2026-10-14.json"


def actual():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    issues = {}
    pages = {}
    for case in packet["cases"]:
        issues[case["issue_date"]] = json.loads(
            (ISSUES / (case["issue_date"] + ".json")).read_text(
                encoding="utf-8"))
        pages[case["source_record_id"]] = (
            RECORDS / ("%d.html" % case["source_record_id"])).read_text(
                encoding="utf-8")
    return index, packet, issues, pages


class BriefClaimCorrectionReviewTest(unittest.TestCase):
    def test_two_real_cases_remain_unsigned_and_no_files_change(self):
        args = actual()
        original = copy.deepcopy(args)
        report = audit(*args)
        self.assertEqual(args, original)
        self.assertEqual(report["case_count"], 3)
        self.assertEqual(report["unmodified_published_source_record_count"], 5230)
        self.assertEqual(report["status_counts"], {
            "claim_check_only_not_a_proposed_edit": 2,
            "owner_review_required": 1,
        })
        self.assertFalse(report["publication_enabled"])
        self.assertFalse(report["owner_approved"])
        self.assertTrue(all(not c["correction_authorized"]
                            and not c["editor_reviewed"] and not c["owner_approved"]
                            for c in report["cases"]))
        draft = next(x for x in report["cases"] if x["issue_number"] == 12)
        self.assertIn("KVD002", draft["proposed_full_paragraph_private_not_to_publish"])
        self.assertNotIn("the Atlas drone swarm system's live-fire debut",
                         draft["proposed_full_paragraph_private_not_to_publish"])
        self.assertIn("Type 076 Sichuan", draft["proposed_full_paragraph_private_not_to_publish"])
        no10 = next(x for x in report["cases"] if x["issue_number"] == 10)
        self.assertIsNone(no10["proposed_full_paragraph_private_not_to_publish"])
        self.assertIsNone(no10["proposed_exact_excerpt"])

    def test_do_not_allow_unsigned_publication_or_fake_video_review(self):
        for field in ("publication_enabled", "owner_approved"):
            args = list(actual())
            args[1][field] = True
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "cannot authorize publication"):
                audit(*args)
        for field in ("human_original_video_verified", "human_editor_reviewed", "owner_approved"):
            args = list(actual())
            args[1]["cases"][0][field] = True
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "impersonate"):
                audit(*args)

    def test_cannot_apply_direct_correction_to_claim_check_only_issue(self):
        args = list(actual())
        no10 = next(c for c in args[1]["cases"] if c["issue_number"] == 10)
        no10["proposed_exact_text"] = "An invented replacement that should never get published."
        with self.assertRaisesRegex(ValueError, "cannot propose a Brief edit"):
            audit(*args)

    def test_no13_y20b_first_use_is_held_for_earlier_april_records(self):
        index, packet, issues, pages = actual()
        claim = next(c for c in packet["cases"] if c["issue_number"] == 13)
        self.assertEqual(claim["source_record_id"], 2993)
        self.assertIn("first confirmed operational use", claim["existing_exact_text"])
        self.assertIn("202604", claim["primary_evidence"][1]["url"])
        report = audit(index, packet, issues, pages)
        no13 = next(c for c in report["cases"] if c["issue_number"] == 13)
        self.assertIsNone(no13["proposed_exact_excerpt"])
        self.assertFalse(no13["correction_authorized"])
        issue = issues["2026-08-08"]
        issue["why_it_matters"] = issue["why_it_matters"].replace(
            "first confirmed operational use", "operational use")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            audit(index, packet, issues, pages)

    def test_old_exact_text_must_be_present_and_unique(self):
        args = list(actual())
        args[1]["cases"][0]["existing_exact_text"] = "A phrase not in the issue at all"
        with self.assertRaisesRegex(ValueError, "exactly once"):
            audit(*args)
        args = list(actual())
        args[2]["2026-08-01"]["opening_note"] += (
            " " + args[1]["cases"][0]["existing_exact_text"])
        with self.assertRaisesRegex(ValueError, "exactly once"):
            audit(*args)

    def test_source_trail_and_original_record_page_must_be_linked(self):
        args = list(actual())
        args[2]["2026-08-01"]["source_trail"] = []
        with self.assertRaisesRegex(ValueError, "source link removed"):
            audit(*args)
        args = list(actual())
        args[3][2881] = args[3][2881].replace("Original URL", "Removed original")
        with self.assertRaisesRegex(ValueError, "original URL is missing"):
            audit(*args)
        args = list(actual())
        args[1]["cases"][0]["original_source_title"] = "wrong title"
        with self.assertRaisesRegex(ValueError, "issuer/title/date drift"):
            audit(*args)
        args = list(actual())
        args[0]["trail_ids"].remove(2881)
        with self.assertRaisesRegex(ValueError, "citation missing"):
            audit(*args)

    def test_unreviewed_future_records_never_join_correction_packet(self):
        index, packet, issues, pages = actual()
        index["snapshot"] = {"date": "2026-10-16", "records": 5231}
        index["records"].append(
            [max(row[0] for row in index["records"]) + 1,
             "2026-10-16", 0, 0, "", "新入库记录"])
        result = audit(index, packet, issues, pages)
        self.assertEqual(result["case_count"], 3)
        self.assertFalse(result["publication_enabled"])
        self.assertEqual(result["unmodified_published_source_record_count"], 5231)

    def test_evidence_and_sources_fail_closed(self):
        args = list(actual())
        args[1]["cases"][0]["primary_evidence"][0]["url"] = (
            "https://attacker:secret@publisher.example/a")
        with self.assertRaisesRegex(ValueError, "unambiguous HTTPS"):
            audit(*args)
        args = list(actual())
        args[1]["cases"][0]["primary_evidence"] = []
        with self.assertRaisesRegex(ValueError, "publisher evidence"):
            audit(*args)
        args = list(actual())
        args[0]["snapshot"]["date"] = "2026-10-01"
        with self.assertRaisesRegex(ValueError, "regressed"):
            audit(*args)

    def test_draft_cannot_invent_a_new_citation_or_issue(self):
        args = list(actual())
        args[1]["cases"][0]["issue_number"] = 13
        with self.assertRaisesRegex(ValueError, "published issue identity/date"):
            audit(*args)
        args = list(actual())
        args[1]["cases"][0]["case_id"] = "unknown correction"
        with self.assertRaisesRegex(ValueError, "unknown claim"):
            audit(*args)


if __name__ == "__main__":
    unittest.main()
