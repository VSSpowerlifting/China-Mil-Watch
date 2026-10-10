"""The Sunday source-offer auditor reproduces writer choices without model/SMTP."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts.audit_sunday_source_offer import (
    explain_offer, inspect_offer, parse_watch_ids,
)
from scripts.author_brief import build_draft
from scripts.sunday_briefs_auto_writer import choose_evidence

SAT = "2026-10-10"
WEEK_START = "2026-10-04"


def row(ident, desk, published="2026-10-08", *, chars=450,
        analyzed=False, significant=False, passed=None,
        text_english=None):
    return {
        "id": ident,
        "desk_id": desk,
        "source_slug": "official",
        "source_name": "Issuer source",
        "url": "https://publisher.example/" + str(ident),
        "published_date": published,
        "title_original": "Original source headline",
        "title_english": "Original source headline",
        "source_language_tag": "en",
        "text_original": "Original official body " * 40 if chars >= 250 else "short",
        "text_english": ("E" * chars) if text_english is None else text_english,
        "analyzed_at": "2026-10-10T12:00:00" if analyzed else None,
        "is_significant": 1 if significant else 0,
        "passed_relevance": passed,
    }


def sidecar(rows):
    return build_draft(rows, desks=["china", "singapore"],
                       week_start=WEEK_START, week_ending=SAT)


def default_choice(rows, draft):
    # Patch only the I/O boundary; execute the exact production selection.
    with patch("scripts.sunday_briefs_auto_writer.read_only"), patch(
            "scripts.sunday_briefs_auto_writer.get_articles_for_desks",
            return_value=rows):
        return choose_evidence(draft, as_of=SAT, db=Path("not-opened.db"))


class SundayOfferAuditTests(TestCase):

    def test_newer_singapore_rows_crowd_out_relevant_older_reply(self):
        rows = [
            row(4911, "singapore", "2026-10-05", chars=378),
            row(5070, "singapore", "2026-10-10", chars=4706),
            row(5071, "singapore", "2026-10-10", chars=7556),
            row(4937, "china", "2026-10-08", analyzed=True),
        ] + [
            row(i, "china", "2026-10-09", analyzed=True)
            for i in range(6001, 6008)
        ]
        draft = sidecar(rows)
        chosen = default_choice(rows, draft)
        report = explain_offer(
            rows=rows, sidecar=draft, chosen=chosen,
            watched_ids=[4911, 4937, 5070, 5071])
        self.assertEqual(len(report["selected_numeric_record_ids"]), 10)
        self.assertEqual(report["selected_desk_counts"],
                         {"china": 8, "singapore": 2})
        states = {w["record_id"]: w["outcome"]
                  for w in report["watched_records"]}
        self.assertEqual(states[4911], "eligible_but_omitted_by_default_ranking")
        self.assertEqual(states[4937], "selected_for_default_model_offer")
        self.assertEqual(states[5070], "selected_for_default_model_offer")
        self.assertEqual(states[5071], "selected_for_default_model_offer")
        # Source bodies, full URLs, titles and private digests never print.
        public = json.dumps(report)
        self.assertNotIn("publisher.example", public)
        self.assertNotIn("Original source headline", public)
        self.assertNotIn("Original official body", public)

    def test_short_translation_does_not_fallback_to_long_original(self):
        rows = [row(7, "singapore", text_english="brief",
                    chars=800), row(8, "china", analyzed=True)]
        draft = sidecar(rows)
        report = explain_offer(rows=rows, sidecar=draft,
                               chosen=[(rows[1], "E" * 450)], watched_ids=[7])
        self.assertEqual(report["watched_records"][0]["outcome"],
                         "insufficient_full_text")

    def test_screened_out_and_absent_week_record_differ(self):
        rows = [row(7, "singapore", passed=0),
                row(8, "china", analyzed=True)]
        draft = sidecar(rows)
        result = explain_offer(
            rows=rows, sidecar=draft, chosen=[(rows[1], "E" * 450)],
            watched_ids=[7, 999])
        self.assertEqual([r["outcome"] for r in result["watched_records"]],
                         ["screened_not_selected", "not_in_week_corpus"])

    def test_corrupt_source_trail_is_not_eligible(self):
        rows = [row(7, "singapore"), row(8, "china", analyzed=True)]
        draft = sidecar(rows)
        for entry in draft["source_trail"]:
            if entry["record_id"] == 7:
                entry["url"] = "https://altered.example.invalid"
        result = explain_offer(
            rows=rows, sidecar=draft, chosen=[(rows[1], "E" * 450)],
            watched_ids=[7])
        self.assertEqual(result["watched_records"][0]["outcome"],
                         "source_trail_mismatch")

    def test_reject_duplicate_corpus_ids(self):
        rows = [row(7, "singapore"), row(7, "singapore")]
        draft = sidecar(rows)
        with self.assertRaisesRegex(ValueError, "duplicate production"):
            explain_offer(rows=rows, sidecar=draft, chosen=[],
                          watched_ids=[7])

    def test_bounded_numeric_id_parser(self):
        self.assertEqual(parse_watch_ids("4911,4937"), [4911, 4937])
        for invalid in ("", "4,", "1,1", "0", "-1", "1, 2", "1e3",
                        "https://publisher.example", ",".join(
                            str(i) for i in range(1, 27))):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_watch_ids(invalid)

    def test_actual_inspector_keeps_health_hold_and_no_authorizations(self):
        rows = [row(4911, "singapore"), row(4937, "china", analyzed=True)]
        fake_registry = [
            SimpleNamespace(slug=x, is_collecting=True,
                            has_production_records=True)
            for x in ("china", "singapore")
        ]
        with patch("scripts.audit_sunday_source_offer.load_registry",
                   return_value=fake_registry), patch(
            "scripts.audit_sunday_source_offer.read_only"
        ), patch(
            "scripts.audit_sunday_source_offer.get_articles_for_desks",
            return_value=rows
        ), patch(
            "scripts.audit_sunday_source_offer.choose_evidence",
            return_value=[(r, "model source") for r in rows]
        ) as chooser, patch(
            "scripts.audit_sunday_source_offer.inspect",
            return_value={
                "machine_preflight_verdict": "hold_before_model_or_email",
                "unmet_gates": ["sunday_production_update_not_due",
                                "same_sunday_success_marker_missing_or_stale"],
            }
        ):
            r = inspect_offer(
                week_ending=SAT, as_of=SAT,
                review_local_day="2026-10-10", watched_ids=[4911, 4937],
                database=Path("no-write.db"), marker_path=Path("no-marker"))
        chooser.assert_called_once()
        self.assertEqual(chooser.call_args.kwargs["as_of"], SAT)
        self.assertFalse(r["model_called"])
        self.assertFalse(r["editor_email_authorized"])
        self.assertFalse(r["publication_authorized"])
        self.assertFalse(r["archive_modified"])
        self.assertEqual(r["sunday_corpus_readiness"],
                         "hold_before_model_or_email")
        self.assertEqual(r["source_offer_count"], 2)
        self.assertEqual([v["outcome"] for v in r["watched_records"]],
                         ["selected_for_default_model_offer"] * 2)

    def test_never_represent_a_saturday_as_sunday_collection(self):
        with self.assertRaisesRegex(ValueError, "future source cutoff"):
            inspect_offer(week_ending=SAT, as_of=SAT,
                          review_local_day="2026-10-09",
                          watched_ids=[4911])
