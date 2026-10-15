"""Source-free regression checks for reconciled AFP 22+1 originals."""
import copy
import unittest

from scripts.reconcile_ph_afp_first23_originals import BATCHES, TOTAL, (
    LATEST, ReviewReconciliationHold, reconcile,
)


def fixtures():
    batches, rows = [], []
    for j, (sha, run, count, day) in enumerate(BATCHES):
        original = []
        for n in range(count):
            sid = "afp:%d" % (1300 + j * 100 + n)
            url = "https://www.afp.mil.ph/news/notice-%d-%d" % (j, n)
            title = "First-party fake %d %d" % (j, n)
            rec = {"source_identity": sid, "source_url": url, "title_original": title,
                   "published_date": day, "capture_sha256": "a" * 64,
                   "text_sha256": "b" * 64, "review_status": "not_started",
                   "human_review_authenticated": False}
            original.append(rec)
            rows.append({
                "identity": sid, "url": url, "title": title,
                "published_date": day, "source_slug": "ph_afp_articles",
                "state_commit": LATEST, "country": "philippines",
                "first_seen_run": run,
                "review_status": "not_human_reviewed_for_public_use"
            })
        batches.append({
            "historical_state_commit": sha,
            "target_date": day,
            "run_id": run, "new_records": count, "records": original,
        })
    docket = {
        "protocol": "ipr_ph_afp_metadata_review_docket_v1",
        "source": "philippines_afp_shadow",
        "total_source_records": TOTAL,
        "body_unavailable_records": 0,
        "source_bodies_or_raw_api_responses_included": False,
        "human_review_completed": False, "source_reuse_approved": False,
        "production_eligible": False, "weekly_ai_writer_eligible": False,
        "automated_review_decisions": 0, "batches": batches
    }
    private = {
        "schema": "ipr-private-shadow-desk-reader/1",
        "status": "private_research_not_source_admitted",
        "desk_filter": "philippines", "query": "",
        "truncated": False, "source_body_text_exported": False,
        "automated_source_rights_approved": False,
        "human_source_review_completed": False,
        "public_release_authorized": False,
        "production_records_changed": False, "country_desks_promoted": False,
        "sources": [{"source_slug": "ph_afp_articles",
                     "country": "philippines", "state_commit": LATEST,
                     "stored_records": TOTAL, "query_matches": TOTAL}],
        "results": rows, "matched_total": TOTAL
    }
    return docket, private


class AFP23ReconciliationTests(unittest.TestCase):
    def test_exact_23_with_one_held_new_original(self):
        docket, reader = fixtures()
        x = reconcile(docket, reader)
        self.assertEqual(x["total_pinned_originals"], 23)
        self.assertEqual(x["previously_pinned_originals"], 22)
        self.assertEqual(x["new_original_run_id"], "38731523240-1")
        self.assertFalse(x["production_admission_authorized"])
        self.assertFalse(x["all_human_reviews_complete"])

    def test_missing_last_original_is_hold(self):
        docket, reader = fixtures()
        reader["results"].pop()
        with self.assertRaisesRegex(ReviewReconciliationHold, "incomplete_current"):
            reconcile(docket, reader)

    def test_premature_approval_is_hold(self):
        docket, reader = fixtures()
        docket["human_review_completed"] = True
        with self.assertRaisesRegex(ReviewReconciliationHold, "authorization_drift"):
            reconcile(docket, reader)

    def test_unpinned_current_commit_is_hold(self):
        docket, reader = fixtures()
        reader["sources"][0]["state_commit"] = "f" * 40
        with self.assertRaisesRegex(ReviewReconciliationHold, "incomplete_current"):
            reconcile(docket, reader)

    def test_omitted_historical_capture_batch_is_hold(self):
        docket, reader = fixtures()
        docket["batches"].pop(1)
        with self.assertRaisesRegex(ReviewReconciliationHold, "missing_historical"):
            reconcile(docket, reader)

    def test_wrong_first_seen_run_is_hold(self):
        docket, reader = fixtures()
        reader["results"][-1]["first_seen_run"] = BATCHES[0][1]
        with self.assertRaisesRegex(ReviewReconciliationHold, "current_source_version"):
            reconcile(docket, reader)

    def test_wrong_original_publication_date_is_hold(self):
        docket, reader = fixtures()
        reader["results"][-1]["published_date"] = "2026-10-14"
        with self.assertRaisesRegex(ReviewReconciliationHold, "current_source_version"):
            reconcile(docket, reader)

    def test_tampered_original_article_url_is_hold(self):
        docket, reader = fixtures()
        reader["results"][-1]["url"] += "-edited"
        with self.assertRaisesRegex(ReviewReconciliationHold, "current_source_version"):
            reconcile(docket, reader)

    def test_extra_unreviewed_id_is_hold(self):
        docket, reader = fixtures()
        reader["results"][-1]["identity"] = "afp:999999"
        with self.assertRaisesRegex(ReviewReconciliationHold, "new_or_missing"):
            reconcile(docket, reader)

    def test_duplicate_identity_is_hold(self):
        docket, reader = fixtures()
        reader["results"][-1] = copy.deepcopy(reader["results"][0])
        with self.assertRaisesRegex(ReviewReconciliationHold, "new_or_missing"):
            reconcile(docket, reader)

    def test_reader_claims_public_authority_is_hold(self):
        docket, reader = fixtures()
        reader["public_release_authorized"] = True
        with self.assertRaisesRegex(ReviewReconciliationHold, "reader_approval"):
            reconcile(docket, reader)

    def test_historical_reviews_cannot_be_marked_approved(self):
        docket, reader = fixtures()
        docket["batches"][0]["records"][0]["review_status"] = "approved"
        with self.assertRaisesRegex(ReviewReconciliationHold, "source_review_record"):
            reconcile(docket, reader)

    def test_total_fixture_is_23(self):
        docket, reader = fixtures()
        self.assertEqual(sum(b["new_records"] for b in docket["batches"]), TOTAL)
        self.assertEqual(len(reader["results"]), TOTAL)


if __name__ == "__main__":
    unittest.main()
