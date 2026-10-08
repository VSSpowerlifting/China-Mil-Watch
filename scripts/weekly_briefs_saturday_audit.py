"""Audit Saturday additions and Friday-packet drift before Briefs editorial approval.

This command is read-only: it reads the tracked corpus and, optionally, the
owner's private original Friday .txt attachment. It never generates a Brief,
changes the corpus, calls an LLM, emails Dylan, or approves anything.

Usage (after Saturday ends in New York):
    python -m scripts.weekly_briefs_saturday_audit --saturday 2026-10-10
    python -m scripts.weekly_briefs_saturday_audit --saturday 2026-10-10 \
        --friday-packet /private/IPR-Briefs-Provisional-2026-10-10.txt

The first command is appropriate for manual GitHub Actions execution, with
only aggregate counts printed. The second is local/private: source IDs from
the original packet are compared to current full-week candidates.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from config import DB_PATH
from scripts.author_brief import build_draft
from scripts.reconcile_db import read_only
from scripts.weekly_briefs_auto_writer import live_editorial_desks
from storage.db import get_articles_for_desks

NEW_YORK = ZoneInfo("America/New_York")
MAX_PACKET_BYTES = 2_000_000
APPENDIX_MARKER = "=== SOURCE APPENDIX — DO NOT EDIT ==="
END_APPENDIX = "END OF SOURCE APPENDIX"
RECORD_LINE = re.compile(
    r"^Record ([1-9][0-9]*) \| ([a-z0-9_-]+) \| ([0-9]{4}-[0-9]{2}-[0-9]{2}) \| .+$",
    re.MULTILINE,
)


def parse_saturday(value: str, *, now=None) -> date:
    """Refuse incomplete weeks, malformed dates and non-Saturday identities."""
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Saturday must be a YYYY-MM-DD date") from exc
    if parsed.isoformat() != value or parsed.weekday() != 5:
        raise ValueError("week ending must be a Saturday in YYYY-MM-DD format")
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("clock must include a timezone")
    today = now.astimezone(NEW_YORK).date()
    if parsed >= today:
        raise ValueError("cannot audit an incomplete Saturday; wait until Sunday in New York")
    return parsed


def parse_original_packet(path: Path, *, saturday: date) -> dict:
    """Read only the immutable source appendix of the originally sent packet.

    This detects candidate ID drift, not editorial truth or record mutation.
    No model-authored prose or recipient information is logged.
    """
    if not path.is_file() or path.stat().st_size > MAX_PACKET_BYTES:
        raise ValueError("original Friday packet missing or larger than 2 MB")
    try:
        txt = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("original Friday packet must be UTF-8") from exc
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    if txt.count(APPENDIX_MARKER) != 1 or txt.count(END_APPENDIX) != 1:
        raise ValueError("original Friday packet has invalid appendix markers")
    if "Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED" not in txt:
        raise ValueError("packet must be an unapproved editorial worksheet")
    if "Packet: IPR-" + saturday.isoformat() not in txt.split(APPENDIX_MARKER, 1)[0].splitlines():
        raise ValueError("Friday packet does not match requested Saturday edition")
    cutoff = saturday - timedelta(days=1)
    as_of = "AS-OF CUT-OFF: " + cutoff.isoformat() + " (FRIDAY PROVISIONAL; SATURDAY NOT INCLUDED)"
    if as_of not in txt.split(APPENDIX_MARKER, 1)[0].splitlines():
        raise ValueError("packet is not the Friday provisional cutoff")
    appendix = txt.split(APPENDIX_MARKER, 1)[1].split(END_APPENDIX, 1)[0]
    entries = RECORD_LINE.findall(appendix)
    if not entries:
        raise ValueError("original packet has no source record listings")
    ids = [int(rid) for rid, _, _ in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("original packet has duplicate source IDs")
    beginning = saturday - timedelta(days=6)
    for _rid, _desk, value in entries:
        try:
            pub = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("original packet contains malformed publication dates") from exc
        if not beginning <= pub <= cutoff:
            raise ValueError("original Friday appendix includes out-of-window records")
    return {"records": {int(rid): desk for rid, desk, _ in entries}}


def summarize(*, saturday: date, desks, friday_rows, saturday_rows,
              friday_draft, full_draft, original=None):
    """All public outputs are aggregate; optional private IDs are never printed."""
    fri_by_desk = Counter(e["desk"] for e in friday_draft["source_trail"])
    fri_stored_by_desk = Counter(r["desk_id"] for r in friday_rows)
    sat_stored_by_desk = Counter(r["desk_id"] for r in saturday_rows)
    sat_offered = [
        e for e in full_draft["source_trail"] if e["date"] == saturday.isoformat()
    ]
    sat_by_desk = Counter(e["desk"] for e in sat_offered)
    friday_ids = {e["record_id"]: e["desk"] for e in friday_draft["source_trail"]}
    sat_ids = {e["record_id"]: e["desk"] for e in sat_offered}
    if set(friday_ids).intersection(sat_ids):
        raise ValueError("source appears as both Friday and Saturday candidate")

    result = {
        "status": "FULL_WEEK_SOURCE_REVIEW_REQUIRED",
        "saturday_identity": saturday.isoformat(),
        "friday_cutoff": (saturday - timedelta(days=1)).isoformat(),
        "sunday_start": (saturday - timedelta(days=6)).isoformat(),
        "saturday_stored_records": len(saturday_rows),
        "saturday_offered_candidates": len(sat_offered),
        "saturday_records_require_editorial_review": bool(sat_offered),
        "by_desk": {
            desk: {
                "friday_stored": fri_stored_by_desk[desk],
                "friday_candidates_current": fri_by_desk[desk],
                "saturday_stored": sat_stored_by_desk[desk],
                "saturday_candidates": sat_by_desk[desk],
            }
            for desk in desks
        },
        "friday_packet_comparison": "not supplied",
        "approval_or_publication_authorized": False,
        "warning": (
            "This reports only the repository's current stored publication dates; "
            "missing Saturday records do not establish institutional silence. "
            "Late-collected earlier-dated records, source changes and external "
            "publication completeness require separate human verification."
        ),
    }
    if original is not None:
        baseline = original["records"]
        if any(desk not in desks for desk in baseline.values()):
            raise ValueError("original packet names an unrecognized current desk")
        new = set(friday_ids) - set(baseline)
        missing = set(baseline) - set(friday_ids)
        mismatched = [rid for rid in baseline.keys() & friday_ids.keys()
                      if baseline[rid] != friday_ids[rid]]
        result["friday_packet_comparison"] = {
            "original_friday_candidates": len(baseline),
            "current_friday_candidates": len(friday_ids),
            "new_candidate_ids_since_packet": len(new),
            "missing_or_no_longer_offered_ids": len(missing),
            "changed_desk_assignments": len(mismatched),
            "needs_friday_reconciliation": bool(new or missing or mismatched),
            "note": ("Counts reflect current eligible candidates, not proof of "
                     "new publication or deleted records. A record can change "
                     "screening state between the Friday packet and this audit."),
        }
    return result


def collect_report(saturday: str, *, original_path=None, db=DB_PATH, now=None):
    target = parse_saturday(saturday, now=now)
    original = (parse_original_packet(Path(original_path), saturday=target)
                if original_path is not None else None)
    desks = live_editorial_desks()
    if len(desks) < 2:
        raise ValueError("fewer than two production-backed desks are live")
    start = (target - timedelta(days=6)).isoformat()
    cutoff = (target - timedelta(days=1)).isoformat()
    with read_only(Path(db)) as conn:
        rows = get_articles_for_desks(start, target.isoformat(), desks, conn=conn)
    friday_rows = [r for r in rows if r["published_date"] <= cutoff]
    saturday_rows = [r for r in rows if r["published_date"] == target.isoformat()]
    friday_draft = build_draft(friday_rows, desks=desks, week_start=start,
                               week_ending=target.isoformat())
    full_draft = build_draft(rows, desks=desks, week_start=start,
                             week_ending=target.isoformat())
    return summarize(saturday=target, desks=desks, friday_rows=friday_rows,
                     saturday_rows=saturday_rows, friday_draft=friday_draft,
                     full_draft=full_draft, original=original)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saturday", required=True, help="week-ending Saturday YYYY-MM-DD")
    parser.add_argument("--friday-packet", type=Path,
                        help="optional original private Friday .txt sent to Dylan")
    args = parser.parse_args(argv)
    try:
        report = collect_report(args.saturday, original_path=args.friday_packet)
    except ValueError as exc:
        parser.exit(2, "REFUSED: " + str(exc) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Unapproved source audit only; human editor must review records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
