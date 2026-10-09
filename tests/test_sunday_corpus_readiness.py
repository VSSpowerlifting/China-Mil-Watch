"""Sunday weekly source-readiness is factual, read-only and non-approving."""
import json
from datetime import date, timedelta
import tempfile
import unittest
from pathlib import Path

from scripts.sunday_corpus_readiness import ReadinessError, evaluate, main


def row(identity, desk, published, *, chars=350, analyzed=False, passed=None):
    return {
        "id": identity, "desk_id": desk, "published_date": published,
        "text_original": "Official original text. " * 16 if chars >= 250 else "tiny",
        "text_english": "E" * chars if chars >= 250 else None,
        "analyzed_at": "2026-10-08" if analyzed else None,
        "passed_relevance": passed,
    }


def assess(rows=None, *, as_of="2026-10-10", review_day="2026-10-11",
           marker="2026-10-11", desks=None):
    return evaluate(
        rows=rows if rows is not None else [
            row(1, "china", "2026-10-08"),
            row(2, "singapore", "2026-10-07")],
        desks=desks if desks is not None else ["china", "singapore"],
        week_ending="2026-10-10", as_of=as_of,
        review_day=review_day, marker=marker)


class SundayCorpusReadinessTests(unittest.TestCase):
    def test_full_sunday_two_desks_is_model_candidate_not_approval(self):
        r = assess()
        self.assertEqual(r["machine_preflight_verdict"],
                         "candidate_for_no_send_model_preview_not_approved")
        self.assertEqual(r["usable_text_records"], 2)
        self.assertEqual(r["desks_with_usable_text"], ["china", "singapore"])
        self.assertEqual(r["unmet_gates"], [])
        for k in ("actual_model_draft_reviewed", "publication_authorized",
                  "editor_delivery_authorized", "changes_production_archive",
                  "external_research_source_review_completed"):
            self.assertFalse(r[k])
        self.assertNotIn("Official original text", json.dumps(r))
        self.assertNotIn("EEEE", json.dumps(r))

    def test_thursday_partial_week_not_ready_even_with_text(self):
        r = assess(as_of="2026-10-08", review_day="2026-10-08",
                   marker="2026-10-08")
        self.assertEqual(r["machine_preflight_verdict"], "hold_before_model_or_email")
        self.assertIn("reporting_week_not_complete", r["unmet_gates"])
        self.assertIn("sunday_production_update_not_due", r["unmet_gates"])
        self.assertEqual(r["required_sunday_marker"], "2026-10-11")

    def test_saturday_is_not_same_as_sunday_collection(self):
        r = assess(review_day="2026-10-10", marker="2026-10-10")
        self.assertIn("sunday_production_update_not_due", r["unmet_gates"])
        self.assertNotEqual(r["machine_preflight_verdict"],
                            "candidate_for_no_send_model_preview_not_approved")

    def test_sunday_stale_or_missing_marker_is_hold(self):
        for marker in ("", "2026-10-10", "2026-10-08"):
            with self.subTest(marker=marker):
                r = assess(marker=marker)
                self.assertIn("same_sunday_success_marker_missing_or_stale",
                              r["unmet_gates"])
                self.assertFalse(r["editor_delivery_authorized"])

    def test_sunday_full_text_requires_distinct_desk_sources(self):
        r = assess(rows=[row(1, "china", "2026-10-08"),
                         row(2, "singapore", "2026-10-08", chars=40)])
        self.assertIn("fewer_than_two_desks_with_usable_source_text",
                      r["unmet_gates"])
        self.assertEqual(r["stored_records"], 2)
        self.assertEqual(r["usable_text_records"], 1)

    def test_screened_not_selected_is_not_offered(self):
        r = assess(rows=[row(1, "china", "2026-10-08", passed=0),
                         row(2, "singapore", "2026-10-08")])
        self.assertEqual(r["screened_not_selected_records"], 1)
        self.assertEqual(r["offered_records"], 1)
        self.assertEqual(r["usable_text_records"], 1)
        self.assertIn("fewer_than_two_desks_with_usable_source_text",
                      r["unmet_gates"])

    def test_unscreened_original_text_counts_not_only_model_processed(self):
        r = assess(rows=[row(1, "china", "2026-10-08", analyzed=True, passed=1),
                         row(2, "singapore", "2026-10-08")])
        self.assertEqual(r["usable_text_records"], 2)
        self.assertEqual(r["offered_records"], 2)

    def test_empty_records_produce_holds_not_fake_source_coverage(self):
        r = assess(rows=[])
        self.assertEqual(r["stored_records"], 0)
        self.assertIn("no_unscreened_or_selected_production_records", r["unmet_gates"])
        self.assertIn("fewer_than_two_desks_with_usable_source_text",
                      r["unmet_gates"])

    def test_strict_dates_and_no_future_evidence(self):
        for kwargs in (
            {"as_of": "2026-10-12"},
            {"as_of": "2026-10-10", "review_day": "2026-10-09"},
            {"review_day": "2026-10-11", "marker": "2026-10-12"},
            {"as_of": "2026-10-4"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ReadinessError):
                assess(**kwargs)

    def test_duplicate_record_or_disguised_desk_refused(self):
        with self.assertRaisesRegex(ReadinessError, "duplicate"):
            assess(rows=[row(1, "china", "2026-10-07"),
                         row(1, "singapore", "2026-10-07")])
        with self.assertRaisesRegex(ReadinessError, "desk/date"):
            assess(rows=[row(1, "japan", "2026-10-07")])
        with self.assertRaisesRegex(ReadinessError, "distinct"):
            assess(desks=["china", "china"])

    def test_preflight_refuses_non_saturday_week(self):
        with self.assertRaisesRegex(ReadinessError, "Saturday"):
            evaluate(rows=[], desks=["china", "singapore"],
                     week_ending="2026-10-09", as_of="2026-10-08",
                     review_day="2026-10-08", marker="")

    def test_historical_replay_bound_matches_saturday_resolver_week(self):
        # The resolver's earliest Saturday is 91 days behind the latest
        # reached Saturday; a Friday manual review can be 96 days after
        # the original Sunday, not merely 91.
        sunday = date(2026, 10, 11)
        latest_allowed = (sunday + timedelta(days=96)).isoformat()
        report = assess(review_day=latest_allowed, marker="")
        self.assertEqual(report["evaluated_local_date"], latest_allowed)
        self.assertEqual(report["unmet_gates"],
                         ["same_sunday_success_marker_missing_or_stale"])
        with self.assertRaisesRegex(ReadinessError, "outside permitted"):
            assess(review_day=(sunday + timedelta(days=97)).isoformat(),
                   marker="")

    def test_cli_refuses_overwriting_existing_readiness_report(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.json"
            output.write_text("do not overwrite")
            with self.assertRaises(SystemExit):
                main(["--week-ending", "2026-10-10", "--as-of", "2026-10-08",
                      "--review-local-day", "2026-10-08",
                      "--output", str(output)])
            self.assertEqual(output.read_text(), "do not overwrite")


if __name__ == "__main__":
    unittest.main()
