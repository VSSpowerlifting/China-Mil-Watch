"""Manual read-only health check for the Friday IPR Briefs source evidence.

Reports aggregate desk coverage and source-text eligibility. Never calls an
AI model, SMTP, writes a Brief sidecar, commits output or prints source bodies.

From repository root:
    python -m scripts.weekly_briefs_source_preflight --friday 2026-10-02
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config import DB_PATH
from core.brief_contract import trail_entry
from scripts.author_brief import build_draft
from scripts.reconcile_db import read_only
from scripts.weekly_briefs_auto_writer import (
    MAX_BODY_CHARS, MAX_RECORDS, choose_evidence, live_editorial_desks,
)
from storage.db import get_articles_for_desks


def _valid_friday(value: str) -> date:
    try:
        day = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Friday date must be YYYY-MM-DD") from exc
    if day.isoformat() != value or day.weekday() != 4:
        raise ValueError("Friday date must be a Friday in YYYY-MM-DD format")
    if day > datetime.now(timezone.utc).astimezone(
            ZoneInfo("America/New_York")).date():
        raise ValueError("cannot inspect a future Friday")
    return day


def summarize(*, friday: date, desks, records, draft, selected):
    """Aggregate without embedding any record bodies, URLs, or source titles."""
    offered = {e["record_id"]: e for e in draft["source_trail"]}
    records_by_desk = Counter(row["desk_id"] for row in records)
    offers_by_desk = Counter(e["desk"] for e in draft["source_trail"])
    fulltext_by_desk = Counter()
    for row in records:
        ref = offered.get(row["id"])
        if ref is None or ref != trail_entry(row):
            continue
        body = (row["text_english"] or row["text_original"] or "").strip()
        if len(body) >= 250:
            fulltext_by_desk[row["desk_id"]] += 1
    selected_by_desk = Counter(row["desk_id"] for row, _ in selected)
    covered = [d for d in desks if selected_by_desk[d]]
    return {
        "friday_cutoff": friday.isoformat(),
        "sunday_start": (friday - timedelta(days=5)).isoformat(),
        "saturday_identity": (friday + timedelta(days=1)).isoformat(),
        "total_source_records": len(records),
        "offered_source_candidates": len(draft["source_trail"]),
        "selected_fulltext_records": len(selected),
        "selected_desk_count": len(covered),
        "maximum_model_records": MAX_RECORDS,
        "maximum_body_chars_per_record": MAX_BODY_CHARS,
        "by_desk": {
            desk: {
                "stored": records_by_desk[desk],
                "offered": offers_by_desk[desk],
                "usable_fulltext": fulltext_by_desk[desk],
                "chosen_for_model": selected_by_desk[desk],
            }
            for desk in desks
        },
        "ready": len(covered) >= 2,
        "status": ("ELIGIBLE_FOR_PROVISIONAL_DRAFT"
                   if len(covered) >= 2 else "BLOCKED_INSUFFICIENT_DESKS"),
        "approved_or_published": False,
    }


def collect_report(friday: str, *, db=DB_PATH):
    target = _valid_friday(friday)
    desks = live_editorial_desks()
    if len(desks) < 2:
        raise ValueError("fewer than two production-backed desks are live")
    start = (target - timedelta(days=5)).isoformat()
    with read_only(Path(db)) as conn:
        records = get_articles_for_desks(start, target.isoformat(),
                                         desks, conn=conn)
    draft = build_draft(records, desks=desks, week_start=start,
                        week_ending=(target + timedelta(days=1)).isoformat())
    try:
        selected = choose_evidence(draft, as_of=target.isoformat(), db=db)
    except ValueError as exc:
        # Only the known evidence coverage gate becomes a blocked audit result.
        # Any other source integrity problem should still surface as a failure.
        if "fewer than two desks with full-text evidence" not in str(exc):
            raise
        selected = []
    return summarize(friday=target, desks=desks, records=records,
                     draft=draft, selected=selected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--friday", required=True, help="YYYY-MM-DD past/current Friday")
    args = parser.parse_args(argv)
    try:
        report = collect_report(args.friday)
    except ValueError as exc:
        parser.exit(2, "REFUSED: " + str(exc) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Read-only source check. No model call, email, approval or publication.")
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
