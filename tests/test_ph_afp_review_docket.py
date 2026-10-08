"""Synthetic AFP review-docket contracts: no real source, no human approval."""
import copy
import unittest

from scripts import prepare_ph_afp_review_docket as docket
from scripts import prepare_ph_afp_run_review as review

RUN_1 = "37631681338-1"
RUN_2 = "37788547061-1"
COMMIT_1 = "a" * 40
COMMIT_2 = "b" * 40


def packet(commit=COMMIT_1, run=RUN_1, count=2, target_date="2026-10-07",
           start_id=1300):
    rows = []
    for i in range(count):
        rows.append({
            "source_identity": "afp:{}".format(start_id + i),
            "source_url": "https://www.afp.mil.ph/news/first-party-{}".format(start_id + i),
            "title_original": "Synthetic & source []() | title {}".format(i),
            "published_date": "2026-10-06",
            "first_seen_run": run,
            "body_chars": 440, "text_status": "text",
            "text_sha256": "1" * 64, "capture_sha256": "2" * 64,
            "decision": "pending", "reviewer_name": "",
            "read_original_capture": False, "reviewed_at_utc": None,
            "rationale": "", "checks": dict.fromkeys(review.CHECKS, None),
        })
    return {
        "protocol": "ipr_ph_afp_per_run_unsigned_review_v1",
        "source_kind": "AFP_first_party_shadow_not_production",
        "review_scope": "all_new_records_from_exact_scheduled_shadow_run",
        "desk_qualified": False, "human_review_complete": False,
        "human_approval": False, "production_assignments": 0,
        "historical_state_commit": commit, "original_run_id": run,
        "target_date": target_date, "machine_verified_capture_count": count,
        "records": rows,
    }


class ReviewDocketContracts(unittest.TestCase):
    def setUp(self):
        self.first = packet()
        self.second = packet(commit=COMMIT_2, run=RUN_2, count=1,
                             target_date="2026-10-08", start_id=1400)

    def test_combines_distinct_pinned_batches_without_bodies(self):
        result = docket.build_docket([self.first, self.second])
        self.assertEqual(result["total_source_records"], 3)
        self.assertEqual(len(result["batches"]), 2)
        self.assertEqual(result["batches"][0]["historical_state_commit"], COMMIT_1)
        self.assertFalse(result["human_review_completed"])
        self.assertFalse(result["source_reuse_approved"])
        self.assertFalse(result["production_eligible"])
        self.assertFalse(result["weekly_ai_writer_eligible"])
        self.assertEqual(result["automated_review_decisions"], 0)
        self.assertNotIn("text_original", str(result))
        self.assertNotIn("original_api_response_utf8", str(result))

    def test_markdown_sanitizes_untrusted_titles(self):
        result = docket.markdown_docket(docket.build_docket([self.first]))
        self.assertIn("afp:1300", result)
        self.assertIn(r"\[\]\(\)", result)
        self.assertIn(r"\|", result)
        self.assertIn("Pending", result)
        self.assertNotIn("Approved", result)

    def test_unpinned_or_symbolic_commits_rejected(self):
        for candidate in ("main:37631681338-1", "a"*39 + ":37631681338-1",
                          "a"*40 + ":manual", "a"*40 + ":123-0",
                          "../state:37631681338-1"):
            with self.subTest(value=candidate), self.assertRaises(docket.DocketError):
                docket.parse_batch(candidate)
        self.assertEqual(docket.parse_batch(COMMIT_1 + ":" + RUN_1),
                         (COMMIT_1, RUN_1))

    def test_forged_approval_and_review_fields_refused(self):
        for key, value in (("human_approval", True),
                           ("desk_qualified", True),
                           ("production_assignments", 1)):
            bad = copy.deepcopy(self.first)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(docket.DocketError):
                docket.build_docket([bad])
        for field, value in (("decision", "verified"),
                             ("reviewer_name", "fake"),
                             ("read_original_capture", True),
                             ("reviewed_at_utc", "2026-10-08T00:00:00Z"),
                             ("checks", dict.fromkeys(review.CHECKS, True))):
            bad = copy.deepcopy(self.first)
            bad["records"][0][field] = value
            with self.subTest(field=field), self.assertRaises(docket.DocketError):
                docket.build_docket([bad])

    def test_duplicate_source_or_run_refused(self):
        with self.assertRaises(docket.DocketError):
            docket.build_docket([self.first, self.first])
        bad = copy.deepcopy(self.second)
        bad["records"][0]["source_identity"] = self.first["records"][0]["source_identity"]
        with self.assertRaises(docket.DocketError):
            docket.build_docket([self.first, bad])

    def test_count_mismatch_refused(self):
        bad = copy.deepcopy(self.first)
        bad["machine_verified_capture_count"] = 1
        with self.assertRaises(docket.DocketError):
            docket.build_docket([bad])

    def test_article_host_and_missing_text_refused(self):
        for key, value in (("source_url", "https://evil.example/news/test"),
                           ("source_url", "https://www.afp.mil.ph/news/test?x=1"),
                           ("text_status", "corrupt"),
                           ("body_chars", 0),
                           ("text_sha256", "nonhash")):
            bad = copy.deepcopy(self.first)
            bad["records"][0][key] = value
            with self.subTest(key=key), self.assertRaises(docket.DocketError):
                docket.build_docket([bad])

    def test_no_text_record_is_not_hidden_and_requires_human_disposition(self):
        no_text = copy.deepcopy(self.first)
        no_text["records"][0]["text_status"] = "no_text"
        no_text["records"][0]["body_chars"] = 0
        result = docket.build_docket([no_text])
        self.assertEqual(result["total_source_records"], 2)
        self.assertEqual(result["body_unavailable_records"], 1)
        self.assertEqual(result["batches"][0]["records"][0]["review_status"], "not_started")
        self.assertEqual(result["batches"][0]["records"][0]["extraction_review_priority"],
                         "body_unavailable_requires_human_disposition")
        self.assertIn("No text", docket.markdown_docket(result))
        self.assertFalse(result["human_review_completed"])
        self.assertFalse(result["production_eligible"])
        wrong = copy.deepcopy(no_text)
        wrong["records"][0]["body_chars"] = 20
        with self.assertRaises(docket.DocketError):
            docket.build_docket([wrong])

    def test_run_binding_and_future_date_refused(self):
        for field, value in (("first_seen_run", RUN_2),
                             ("published_date", "2026-10-08"),
                             ("published_date", "2026-13-35")):
            bad = copy.deepcopy(self.first)
            bad["records"][0][field] = value
            with self.subTest(field=field), self.assertRaises(docket.DocketError):
                docket.build_docket([bad])

    def test_zero_new_records_is_not_a_completed_human_review(self):
        empty = packet(count=0)
        result = docket.build_docket([empty])
        self.assertEqual(result["total_source_records"], 0)
        self.assertFalse(result["human_review_completed"])

    def test_empty_input_refused(self):
        with self.assertRaises(docket.DocketError):
            docket.build_docket([])


if __name__ == "__main__":
    unittest.main()
