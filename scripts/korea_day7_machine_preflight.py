"""Offline Korea Day 7 machine preflight, NOT a source or Actions approval.

Consumes existing formal SHA-pinned shadow review and generic logical-slot
candidate reports; does not independently authenticate all Actions attempts.
Never reads Korean bodies, fetches a publisher or changes production/public files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = "ipr-korea-day7-machine-preflight/1"
DAY7 = "2026-10-13"
EXPECTED = ["2026-10-%02d" % x for x in range(7, 14)]
NOT_BEFORE = datetime(2026, 10, 13, 23, 47, tzinfo=timezone.utc)
GOOD = {"scheduled_success_no_new_records_candidate",
        "scheduled_success_new_records_candidate"}


class EvidenceHold(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise EvidenceHold(reason)


def assess(review, slots, now=None):
    now = now or datetime.now(timezone.utc)
    require(isinstance(now, datetime) and now.tzinfo is not None
            and now.utcoffset() == timedelta(0) and now >= NOT_BEFORE,
            "the October 13 Korea collection slot plus grace has not finished")

    require(type(review) is dict and review.get("desk") == "korea"
            and review.get("as_of") == DAY7
            and review.get("mode") == "formal_commit_snapshot"
            and review.get("state_ref") == "shadow/korea-policy-briefing",
            "not the formal pinned Korea Day 7 source review")
    commit = review.get("state_commit")
    require(type(commit) is str and re.fullmatch(r"[0-9a-f]{40}", commit),
            "immutable Korea state commit missing")
    for key in ("findings", "missing_successful_days", "review_holds",
                "historical_backfill_run_ids"):
        require(review.get(key) == [], "unresolved pinned source finding: " + key)
    require(type(review.get("records")) is int and review["records"] >= 5
            and type(review.get("ledgers")) is int and review["ledgers"] >= 8
            and type(review.get("qualifying_ledgers")) is int
            and review["qualifying_ledgers"] >= 8,
            "incomplete five-original and day-zero-plus-seven ledger record")
    digests = review.get("input_hashes")
    require(type(digests) is dict
            and type(digests.get("state/shadow.db")) is str
            and re.fullmatch(r"[0-9a-f]{64}", digests["state/shadow.db"]),
            "formal archived SQLite digest missing")
    require(review.get("human_review_completed") is False
            and review.get("promotion_authorized") is False,
            "a machine review cannot claim human or production approval")

    require(type(slots) is dict
            and slots.get("schema") == "ipr-shadow-slot-candidates/1"
            and slots.get("source_slug") == "kr_policy_mnd_releases"
            and slots.get("state_branch") == "shadow/korea-policy-briefing"
            and slots.get("start_date") == EXPECTED[0]
            and slots.get("cron_utc") == "17:47"
            and slots.get("grace_hours") == 6,
            "wrong Korea logical schedule or evidence contract")
    for key in ("supplied_actions_export_authenticated",
                "source_capture_chain_verified_by_this_audit",
                "all_historical_scheduled_attempts_exhaustively_observed",
                "desk_production_eligible", "weekly_ai_writer_eligible",
                "editor_delivery_authorized"):
        require(slots.get(key) is False,
                "slot-candidate report falsely grants independent authority")
    require(slots.get("writes") == 0
            and slots.get("unscoped_observations") == [],
            "slot-candidate report changed state or contains unscoped runs")
    rows = slots.get("slots")
    require(type(rows) is list and len(rows) == 7
            and all(type(x) is dict for x in rows)
            and [x.get("logical_date") for x in rows] == EXPECTED,
            "incomplete seven scheduled Korea dates")
    used = set()
    for row in rows:
        ids = row.get("observed_run_ids")
        require(row.get("status") in GOOD
                and row.get("new_record_count_is_not_publication_completeness") is True
                and type(ids) is list and len(ids) == 1
                and type(ids[0]) is str
                and re.fullmatch(r"[1-9][0-9]*-1", ids[0])
                and ids[0] not in used,
                "missing, recovered, duplicate, rerun or unresolved Korea slot")
        used.add(ids[0])
    counts = slots.get("counts")
    require(type(counts) is dict
            and counts.get("candidate_supported") == 7
            and counts.get("pending") == 0
            and counts.get("review_required") == 0
            and counts.get("missing_from_supplied_evidence") == 0,
            "an unresolved Korea slot cannot pass Day 7 preflight")
    return {
        "schema": SCHEMA, "as_of": DAY7,
        "pinned_state_commit": commit,
        "private_original_count": review["records"],
        "qualifying_ledger_count": review["qualifying_ledgers"],
        "scheduled_slot_candidates_count": 7,
        "status": "MACHINE_LEDGER_CANDIDATES_CONSISTENT_ACTIONS_CENSUS_HELD",
        "authenticated_all_actions_attempts": False,
        "independent_korean_human_review_completed": False,
        "source_and_attachment_rights_approved": False,
        "human_day7_signoff_completed": False,
        "production_eligible": False,
        "sunday_brief_eligible": False,
        "new_public_references_approved": False,
        "corpus_or_site_mutations": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-review", type=Path, required=True)
    parser.add_argument("--slot-candidates", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    opts = parser.parse_args(argv)
    try:
        review = json.loads(opts.formal_review.read_text(encoding="utf-8"))
        candidates = json.loads(opts.slot_candidates.read_text(encoding="utf-8"))
        output, rc = assess(review, candidates), 0
    except (OSError, UnicodeError, TypeError, ValueError, KeyError):
        output, rc = {
            "schema": SCHEMA, "as_of": DAY7,
            "status": "HOLD_DAY7_MACHINE_EVIDENCE_INCOMPLETE",
            "authenticated_all_actions_attempts": False,
            "human_day7_signoff_completed": False,
            "production_eligible": False,
            "sunday_brief_eligible": False,
            "new_public_references_approved": False,
            "corpus_or_site_mutations": 0,
        }, 2
    target = opts.receipt.expanduser()
    if not target.is_absolute() or not target.parent.is_dir() or \
            target.parent.is_symlink() or target.is_symlink() or target.exists():
        parser.error("receipt must be a new absolute, private, non-symlink path")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(output, indent=2, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
