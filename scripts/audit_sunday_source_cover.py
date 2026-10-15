"""Read-only Sunday default-selection coverage audit; NEVER changes the writer.

For a validated source-trail sidecar, report which specific numeric production
source IDs would be selected by the ordinary ten-record algorithm. The only
output is bounded identity/count metadata, never source text or prompt content.
No model, SMTP, publication, collector, artifact or database writes.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from config import DB_PATH
from core.brief_contract import trail_entry
from scripts.reconcile_db import read_only
from scripts.sunday_briefs_auto_writer import MAX_RECORDS, choose_evidence
from storage.db import get_articles_for_desks


class SourceCoverageError(ValueError):
    """Unreviewed candidate or malformed source-trail audit request."""


def audit(sidecar, *, as_of, required_ids, db=DB_PATH):
    if (not isinstance(sidecar, dict) or
            not isinstance(required_ids, (tuple, list)) or
            not 1 <= len(required_ids) <= MAX_RECORDS or
            any(type(x) is not int or x <= 0 for x in required_ids) or
            len(set(required_ids)) != len(required_ids)):
        raise SourceCoverageError("1–10 distinct positive numeric source IDs required")
    # Use the actual production selection function, never an independent ranking
    # replica. Its date cutoff, original/English text minimum and trail digest
    # gates remain the source of truth.
    try:
        chosen = choose_evidence(sidecar, as_of=as_of, db=db)
        start = date.fromisoformat(sidecar["week_start"])
        cutoff = date.fromisoformat(as_of)
        with read_only(Path(db)) as conn:
            rows = get_articles_for_desks(
                start.isoformat(), cutoff.isoformat(), sidecar["desks"], conn=conn)
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceCoverageError("invalid or blocked default Sunday input") from exc
    selected = {row["id"] for row, _body in chosen}
    sources = {entry["record_id"]: entry for entry in sidecar["source_trail"]}
    by_id = {row["id"]: row for row in rows}
    result = []
    for ident in required_ids:
        row = by_id.get(ident)
        if row is None:
            status = "absent_from_reporting_window_or_production"
        elif ident not in sources:
            status = "not_in_exact_source_trail"
        elif trail_entry(row) != sources[ident]:
            status = "source_trail_mismatch"
        elif len((row["text_english"] or row["text_original"] or "").strip()) < 250:
            status = "stored_body_shorter_than_minimum"
        elif ident in selected:
            status = "selected_by_default"
        else:
            status = "eligible_but_ranked_out"
        result.append({
            "record_id": ident,
            "desk": row["desk_id"] if row is not None else None,
            "status": status,
            "selected_by_default": status == "selected_by_default",
        })
    return {
        "schema": "ipr-sunday-source-cover-audit/1",
        "week_ending": sidecar["week_ending"],
        "as_of": as_of,
        "selection_cap_unchanged": MAX_RECORDS,
        "default_selected_ids": [row["id"] for row, _body in chosen],
        "reviewed_anchors": result,
        "all_required_anchors_selected": all(
            x["selected_by_default"] for x in result),
        "theme_override": False,
        "model_called": False,
        "email_sent": False,
        "production_or_review_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--required-id", type=int, action="append", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if (args.sidecar.is_symlink() or not args.sidecar.is_file()
            or args.sidecar.stat().st_size > 1000000):
        parser.error("missing, symlinked or oversized source-trail sidecar")
    try:
        sidecar = json.loads(args.sidecar.read_text(encoding="utf-8"))
        receipt = audit(
            sidecar, as_of=args.as_of, required_ids=args.required_id, db=args.db)
    except (SourceCoverageError, OSError, UnicodeError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    serialized = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    if args.report is None:
        print(serialized, end="")
    else:
        # This remains operator-local and identity-only, never a public article.
        if args.report.is_symlink() or args.report.exists():
            parser.error("existing report may not be overwritten")
        args.report.open("x", encoding="utf-8").write(serialized)
        print("Source-cover metadata-only report written:", args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
