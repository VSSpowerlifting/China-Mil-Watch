"""Read-only Sunday Briefs source/corpus readiness, not an AI or SMTP run.

This report deliberately cannot approve articles, infer national silence, or
assert readiness from a Saturday archive snapshot before the actual Sunday
production success marker has been committed. No source bodies are output.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from config import DB_PATH
from core.brief_contract import SCREENING_NOT_SELECTED, eligible_desks, screening_state
from core.desk_registry import load_registry
from scripts.reconcile_db import read_only
from storage.db import get_articles_for_desks

MIN_FULL_TEXT = 250
SCHEMA = "ipr-sunday-corpus-readiness/1"


class ReadinessError(ValueError):
    pass


def iso_day(value):
    if not isinstance(value, str):
        raise ReadinessError("date must be YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ReadinessError("invalid date") from exc
    if result.isoformat() != value:
        raise ReadinessError("date must be exact YYYY-MM-DD")
    return result


def evaluate(*, rows, desks, week_ending, as_of, review_day, marker):
    saturday = iso_day(week_ending)
    cutoff = iso_day(as_of)
    observed = iso_day(review_day)
    if saturday.weekday() != 5:
        raise ReadinessError("week ending must be Saturday")
    start = saturday - timedelta(days=6)
    sunday = saturday + timedelta(days=1)
    if not start <= cutoff <= saturday:
        raise ReadinessError("as-of outside reporting week or after Saturday")
    if cutoff > observed:
        raise ReadinessError("cannot inspect records from a future calendar day")
    if observed < start or observed > sunday + timedelta(days=91):
        raise ReadinessError("review date outside permitted calendar window")
    if marker and iso_day(marker) > observed:
        raise ReadinessError("success marker is dated after review date")
    chosen = list(dict.fromkeys(desks))
    if len(chosen) != len(desks) or len(chosen) < 2:
        raise ReadinessError("at least two distinct production-backed desks required")

    per_desk = {name: {"stored": 0, "offered": 0, "usable_text": 0,
                        "latest_published": None} for name in chosen}
    ids = set()
    usable_desk_ids = set()
    nonselected = 0
    for row in rows:
        desk = row["desk_id"]
        ident = row["id"]
        published = iso_day(row["published_date"])
        if desk not in per_desk or not start <= published <= cutoff:
            raise ReadinessError("record escaped declared desk/date selection")
        if ident in ids:
            raise ReadinessError("duplicate production record in archive selection")
        ids.add(ident)
        stats = per_desk[desk]
        stats["stored"] += 1
        stats["latest_published"] = max(
            stats["latest_published"] or published.isoformat(), published.isoformat())
        if screening_state(row) == SCREENING_NOT_SELECTED:
            nonselected += 1
            continue
        stats["offered"] += 1
        body = (row["text_english"] or row["text_original"] or "").strip()
        if len(body) >= MIN_FULL_TEXT:
            stats["usable_text"] += 1
            usable_desk_ids.add(desk)

    issues = []
    if cutoff < saturday:
        issues.append("reporting_week_not_complete")
    if observed < sunday:
        issues.append("sunday_production_update_not_due")
    elif marker != sunday.isoformat():
        issues.append("same_sunday_success_marker_missing_or_stale")
    if len(usable_desk_ids) < 2:
        issues.append("fewer_than_two_desks_with_usable_source_text")
    if sum(stats["offered"] for stats in per_desk.values()) == 0:
        issues.append("no_unscreened_or_selected_production_records")

    # This is necessary evidence, not approval of draft quality, source rights,
    # scheduled send, model token budget or cross-institutional narrative.
    verdict = ("candidate_for_no_send_model_preview_not_approved"
               if not issues else "hold_before_model_or_email")
    return {
        "schema": SCHEMA,
        "reporting_week_start": start.isoformat(),
        "reporting_saturday": saturday.isoformat(),
        "source_as_of": cutoff.isoformat(),
        "evaluated_local_date": observed.isoformat(),
        "required_sunday_marker": sunday.isoformat(),
        "observed_sunday_marker": marker or None,
        "production_desks": chosen,
        "production_desk_counts": per_desk,
        "stored_records": len(ids),
        "offered_records": sum(x["offered"] for x in per_desk.values()),
        "usable_text_records": sum(x["usable_text"] for x in per_desk.values()),
        "desks_with_usable_text": sorted(usable_desk_ids),
        "screened_not_selected_records": nonselected,
        "unmet_gates": issues,
        "machine_preflight_verdict": verdict,
        "actual_model_draft_reviewed": False,
        "external_research_source_review_completed": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "changes_production_archive": False,
    }


def inspect(*, week_ending, as_of, review_day, database=DB_PATH,
            marker_path=Path(".github/state/last_daily_run_date.txt")):
    saturday, cutoff = iso_day(week_ending), iso_day(as_of)
    desks = eligible_desks(load_registry())
    # Validate window BEFORE querying tracked production data.
    if saturday.weekday() != 5 or not saturday - timedelta(days=6) <= cutoff <= saturday:
        raise ReadinessError("invalid Saturday reporting window")
    marker_file = Path(marker_path)
    marker = marker_file.read_text(encoding="utf-8").strip() if marker_file.is_file() else ""
    with read_only(Path(database)) as conn:
        rows = get_articles_for_desks(
            (saturday - timedelta(days=6)).isoformat(), cutoff.isoformat(),
            desks, conn=conn)
    return evaluate(rows=rows, desks=desks, week_ending=week_ending,
                    as_of=as_of, review_day=review_day, marker=marker)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--week-ending", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--review-local-day", required=True)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--marker", type=Path, default=Path(".github/state/last_daily_run_date.txt"))
    p.add_argument("--output", type=Path)
    args = p.parse_args(argv)
    if args.output is not None and args.output.exists():
        p.error("refusing to overwrite an existing report")
    try:
        result = inspect(week_ending=args.week_ending, as_of=args.as_of,
                         review_day=args.review_local_day, database=args.db,
                         marker_path=args.marker)
    except (ReadinessError, OSError, ValueError) as exc:
        p.error(str(exc))
    serial = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(serial, encoding="utf-8")
    else:
        print(serial, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
