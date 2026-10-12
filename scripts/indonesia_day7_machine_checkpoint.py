"""Fail-closed Indonesian Day 7 machine checkpoint, not a human approval.

Reconciles a pinned post-Oct13 original/capture review report with the
independently authenticated Actions census. Only count-only evidence leaves
the isolated runner. Machine consistency never grants rights or corpus status.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.audit_indonesia_shadow_provenance import utc

DAY7 = "2026-10-13"
FIRST = "2026-10-07"
EARLIEST = datetime(2026, 10, 13, 16, 52, 15, tzinfo=timezone.utc)
FIRST_NOMINAL_RUN = datetime(2026, 10, 13, 17, 17, tzinfo=timezone.utc)
EXPECTED_DAYS = [
    "2026-10-%02d" % day for day in range(7, 14)
]


class Day7Error(ValueError):
    """Source/attempt/history evidence cannot support a Day 7 machine receipt."""


def require(ok, reason):
    if not ok:
        raise Day7Error(reason)


def checkpoint(review, census, commit, now=None):
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None and now.utcoffset() == timedelta(0) and
            now >= FIRST_NOMINAL_RUN, "Day 7 review attempted before required collection slot")
    require(type(commit) is str and re.fullmatch(r"[0-9a-f]{40}", commit),
            "immutable state SHA required")
    require(type(review) is dict and review.get("desk") == "indonesia" and
            review.get("as_of") == DAY7 and
            review.get("mode") == "formal_commit_snapshot" and
            review.get("state_commit") == commit and
            review.get("state_ref") == "shadow/indonesia-kemhan",
            "formal Day 7 Indonesia state identity mismatch")
    require(review.get("findings") == [] and
            review.get("missing_successful_days") == [] and
            review.get("review_holds") == [] and
            review.get("historical_backfill_run_ids") == [],
            "original/capture integrity or logical-day findings present")
    require(type(review.get("records")) is int and review["records"] >= 24 and
            type(review.get("ledgers")) is int and review["ledgers"] >= 9 and
            type(review.get("qualifying_ledgers")) is int and
            review["qualifying_ledgers"] >= 9,
            "insufficient original records or qualifying Day 7 ledger history")
    hashes = review.get("input_hashes")
    require(type(hashes) is dict and
            type(hashes.get("state/shadow.db")) is str and
            re.fullmatch(r"[0-9a-f]{64}", hashes["state/shadow.db"]),
            "original database digest missing from formal review")
    require(review.get("human_review_completed") is False and
            review.get("promotion_authorized") is False,
            "machine report improperly claims human review or promotion")

    require(type(census) is dict and
            census.get("schema") == "ipr-indonesia-authenticated-actions-census/1" and
            census.get("as_of") == DAY7 and
            census.get("pinned_state_commit") == commit and
            census.get("source_workflow_id") == 376840713 and
            census.get("source") == "authenticated_repository_GitHub_Actions_API",
            "Day 7 census missing authenticated common source identity")
    require(census.get("rights_approved") is False and
            census.get("independent_original_language_review") is False and
            census.get("production_eligible") is False and
            census.get("public_article_release_authorized") is False,
            "attempt census incorrectly asserts source or production authority")
    result = census.get("result")
    require(type(result) is dict and
            result.get("schema") == "ipr-indonesia-shared-actions-attempt-inventory/1" and
            result.get("verdict") == "CONSISTENT_THROUGH_AS_OF_NOT_DAY7_SIGNOFF" and
            result.get("holds") == [] and
            result.get("missing_scheduled_indonesia_days") == [] and
            result.get("duplicate_scheduled_indonesia_days") == [] and
            result.get("pinned_ledger_unmapped_count") == 0 and
            result.get("scheduled_indonesia_days_observed") == EXPECTED_DAYS and
            result.get("run_listing_pagination_count_verified") is True and
            result.get("all_attempt_artifact_pages_count_verified") is True,
            "incomplete/held Indonesia Day 7 scheduled or attempt inventory")
    counts = result.get("counts")
    require(type(counts) is dict and
            type(counts.get("indonesia_attempts")) is int and
            counts["indonesia_attempts"] >= 8 and
            counts.get("indonesia_failures_or_cancellations") == 0 and
            counts.get("indonesia_rerun_attempts") == 0 and
            counts.get("indonesia_success_without_pinned_ledger") == 0 and
            counts.get("ambiguous_shared_failures") == 0 and
            counts.get("shared_unselected_attempts") == 0,
            "unresolved Indonesia attempt failure, rerun or shared-workflow ambiguity")
    require(result.get("independent_human_source_review_completed") is False and
            result.get("day7_human_checkpoint_completed") is False and
            result.get("publication_authorized") is False and
            result.get("production_eligible") is False,
            "attempt census improperly grants human or publication authority")
    return {
        "schema": "ipr-indonesia-day7-machine-only-checkpoint/1",
        "as_of": DAY7,
        "day_zero_utc": "2026-10-06T16:52:15Z",
        "day7_earliest_utc": EARLIEST.isoformat(),
        "pinned_state_commit": commit,
        "stored_private_originals": review["records"],
        "qualifying_ledgers": review["qualifying_ledgers"],
        "scheduled_dates_verified": len(EXPECTED_DAYS),
        "indonesia_actions_attempts_verified": counts["indonesia_attempts"],
        "missing_schedule_dates": 0,
        "unresolved_machine_findings": 0,
        "source_family": "id_kemhan_news",
        "status": "MACHINE_EVIDENCE_CONSISTENT_HUMAN_REVIEW_PENDING",
        "publisher_geography_anomaly_still_held": True,
        "independent_indonesian_language_review_completed": False,
        "publisher_body_republication_authorized": False,
        "human_day7_signoff_completed": False,
        "qualified_for_production": False,
        "new_public_citations_approved": False,
        "changes_to_corpus_or_site": 0,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review-report", type=Path, required=True)
    p.add_argument("--census-report", type=Path, required=True)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        review = json.loads(args.review_report.read_text(encoding="utf-8"))
        census = json.loads(args.census_report.read_text(encoding="utf-8"))
        receipt = checkpoint(review, census, args.state_commit)
        code = 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        receipt = {
            "schema": "ipr-indonesia-day7-machine-only-checkpoint/1",
            "as_of": DAY7,
            "status": "HOLD_DAY7_MACHINE_EVIDENCE_INCOMPLETE",
            "independent_indonesian_language_review_completed": False,
            "human_day7_signoff_completed": False,
            "publisher_body_republication_authorized": False,
            "qualified_for_production": False,
            "changes_to_corpus_or_site": 0,
        }
        code = 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
