#!/usr/bin/env python3
"""Read-only account of which official records the Sunday model would see.

Reuses the production Sunday writer's *unchanged* choose_evidence selector.
This diagnostic never calls a model, writes a Brief, sends mail, signs a source
review, changes a record's screening state or authorizes publication.

The audit does not prove that the producer's selected sources are true, that
their original-language texts are complete, or that a manuscript is worthwhile.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

from config import DB_PATH
from core.brief_contract import (
    SCREENING_NOT_SELECTED, eligible_desks, screening_state, trail_entry,
)
from core.desk_registry import load_registry
from scripts.author_brief import build_draft
from scripts.reconcile_db import read_only
from scripts.sunday_briefs_auto_writer import choose_evidence
from scripts.sunday_corpus_readiness import ReadinessError, inspect, iso_day
from storage.db import get_articles_for_desks

SCHEMA = "ipr-sunday-source-offer-audit/1"
MIN_BODY_CHARS = 250
MAX_WATCH_IDS = 25


def parse_watch_ids(value):
    """Only bounded numeric production identities; never accept search text."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("--watch-ids requires one or more numeric record IDs")
    tokens = value.split(",")
    if len(tokens) > MAX_WATCH_IDS or any(not re.fullmatch(r"[1-9][0-9]*", x)
                                         for x in tokens):
        raise ValueError("--watch-ids must be 1–25 comma-separated positive IDs")
    result = [int(x) for x in tokens]
    if len(set(result)) != len(result):
        raise ValueError("--watch-ids cannot contain duplicates")
    return result


def explain_offer(*, rows, sidecar, chosen, watched_ids):
    """Classify a watched ID without reproducing or modifying the ranker.

    chosen must be the *actual* output of choose_evidence, not a guessed ID set.
    Omit source bodies, titles, URLs, per-source digests and editorial assertions.
    """
    selected = [r["id"] for r, _body in chosen]
    if len(selected) != len(set(selected)):
        raise ValueError("selection contains duplicate record IDs")
    selected_set = set(selected)
    by_id = {}
    for row in rows:
        ident = row["id"]
        if ident in by_id:
            raise ValueError("duplicate production ID in read-only corpus")
        by_id[ident] = row
    trail = {r["record_id"]: r for r in sidecar["source_trail"]}
    if len(trail) != len(sidecar["source_trail"]):
        raise ValueError("duplicate source trail ID")
    results = []
    for ident in watched_ids:
        row = by_id.get(ident)
        if row is None:
            results.append({"record_id": ident, "desk": None,
                            "screening": None, "outcome": "not_in_week_corpus"})
            continue
        state = screening_state(row)
        reference = trail.get(ident)
        body = (row["text_english"] or row["text_original"] or "").strip()
        if reference is None:
            outcome = ("screened_not_selected" if state == SCREENING_NOT_SELECTED
                       else "missing_from_source_trail")
        elif trail_entry(row) != reference:
            outcome = "source_trail_mismatch"
        elif len(body) < MIN_BODY_CHARS:
            outcome = "insufficient_full_text"
        elif ident in selected_set:
            outcome = "selected_for_default_model_offer"
        else:
            outcome = "eligible_but_omitted_by_default_ranking"
        results.append({"record_id": ident, "desk": row["desk_id"],
                        "screening": state, "outcome": outcome})
    return {
        "selected_numeric_record_ids": selected,
        "selected_desk_counts": dict(sorted(Counter(
            row["desk_id"] for row, _body in chosen).items())),
        "watched_records": results,
    }


def inspect_offer(*, week_ending, as_of, review_local_day, watched_ids,
                  database=DB_PATH,
                  marker_path=Path(".github/state/last_daily_run_date.txt")):
    """Read one corpus snapshot, apply the exact writer selector, then preflight.

    Sunday health is reported separately from editorial quality and permissions.
    A source trail is constructed in memory; no output artifact is written.
    """
    saturday = iso_day(week_ending)
    cutoff = iso_day(as_of)
    observed = iso_day(review_local_day)
    if saturday.weekday() != 5 or cutoff not in (
            saturday - timedelta(days=1), saturday):
        raise ValueError("selector requires Friday or Saturday cutoff")
    if cutoff > observed:
        raise ValueError("cannot audit a future source cutoff")
    desks = eligible_desks(load_registry())
    if len(desks) < 2:
        raise ValueError("fewer than two live production-backed desks")
    with read_only(Path(database)) as conn:
        rows = list(get_articles_for_desks(
            (saturday - timedelta(days=6)).isoformat(), as_of,
            desks, conn=conn))
    sidecar = build_draft(
        rows, desks=desks,
        week_start=(saturday - timedelta(days=6)).isoformat(),
        week_ending=week_ending)
    # Critical: call the real default chooser, with no selected IDs or pins.
    # It reopens the database in read-only mode and verifies source trails.
    chosen = choose_evidence(sidecar, as_of=as_of, db=database)
    offer = explain_offer(
        rows=rows, sidecar=sidecar, chosen=chosen, watched_ids=watched_ids)
    readiness = inspect(
        week_ending=week_ending, as_of=as_of,
        review_day=review_local_day, database=database,
        marker_path=marker_path)
    return {
        "schema": SCHEMA,
        "reporting_week_start": sidecar["week_start"],
        "reporting_saturday": week_ending,
        "source_as_of": as_of,
        "evaluated_local_date": review_local_day,
        "source_trail_record_count": len(sidecar["source_trail"]),
        "source_offer_count": len(offer["selected_numeric_record_ids"]),
        **offer,
        "sunday_corpus_readiness": readiness["machine_preflight_verdict"],
        "unmet_sunday_gates": readiness["unmet_gates"],
        "model_called": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "archive_modified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--review-local-day", required=True)
    parser.add_argument("--watch-ids", required=True,
                        help="1–25 numeric IDs, comma-separated; never URLs")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--marker", type=Path,
                        default=Path(".github/state/last_daily_run_date.txt"))
    args = parser.parse_args(argv)
    try:
        watched = parse_watch_ids(args.watch_ids)
        report = inspect_offer(
            week_ending=args.week_ending, as_of=args.as_of,
            review_local_day=args.review_local_day, watched_ids=watched,
            database=args.db, marker_path=args.marker)
    except (ValueError, ReadinessError, OSError, KeyError) as exc:
        parser.error("read-only audit refused: " + str(exc))
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
