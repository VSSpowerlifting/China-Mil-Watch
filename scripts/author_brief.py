"""
Scaffold an Indo-Pacific Record Brief draft, or check one against the contract.

    .venv/bin/python scripts/author_brief.py scaffold --desks china,singapore \\
        --week-ending 2026-09-19 [--out PATH]
    .venv/bin/python scripts/author_brief.py check PATH

`scaffold` selects candidate records by the brief's named desks and writes a
draft: identity recorded explicitly, every candidate as a source-trail entry
that keeps its own desk and language, per-desk coverage, empty analyst fields
and no issue number. It is deterministic and read-only on disk: no model API,
no network, and the database is read through a scratch copy
(`scripts.reconcile_db.read_only`), so nothing is left beside the tracked file.
Without `--out` the draft goes to stdout. It never writes inside `output/`,
which is generated: a brief's sidecar is source, kept in `briefs/` at the
repository root, where `core/brief_collection.py` reads it (drafts are withheld).

The candidate trail is a starting list, not a citation list. The analyst keeps
the entries the brief cites, removes the rest, writes the prose, and runs
`check` until it passes.

A single-desk brief is refused unless the exception is recorded with who
approved it, when, and why. Issue numbers are not assigned here: a number is
assigned at approval (`core.brief_contract.approve`), and none can be while
No. 14's publication status is unreconciled.

`check` holds that line for a number written by hand. It reads the existing
issues' sidecars under `output/the-pla-watch/posts/` (read only) and reports a
brief that carries an issue number while No. 14 is unreconciled, or a number an
existing issue already holds, as breaking the contract. An unnumbered draft is
unaffected.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import DB_PATH                                     # noqa: E402
from core.brief_contract import (                              # noqa: E402
    BRIEF_SCHEMA, MIN_DESKS, SCREENING_NOT_SELECTED, STATUS_DRAFT,
    coverage_by_desk, eligible_desks, screening_state, trail_entry,
    validate_brief)
from core.desk_registry import load_registry                   # noqa: E402
from core.edition_identity import (                            # noqa: E402
    TIMING_REGULAR, TIMING_RETROSPECTIVE, brief_identity_fields)
from scripts.reconcile_db import read_only                     # noqa: E402
from storage.db import get_articles_for_desks                  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "output"
POSTS_DIR = OUTPUT_DIR / "the-pla-watch" / "posts"


def existing_issues() -> list:
    """The existing issues' sidecars, read only, for `check`'s number rules."""
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(POSTS_DIR.glob("*.json"))]


def build_draft(records, *, desks, week_start: str, week_ending: str,
                timing: str = TIMING_REGULAR, exception=None,
                include_not_selected: bool = False) -> dict:
    """
    The draft sidecar for `records`. No I/O; every analyst field empty.

    Coverage counts every record the desks hold in the window. The candidate
    trail leaves out records that were screened and not selected — a judgement
    was made about those — unless `include_not_selected`; records never
    screened stay in, because no judgement was made about them, and leaving
    them out would silently drop a desk whose records are not screened yet.
    """
    candidates = [r for r in records if include_not_selected
                  or screening_state(r) != SCREENING_NOT_SELECTED]
    draft = brief_identity_fields(timing)
    draft.update({
        "brief_schema": BRIEF_SCHEMA,
        "editorial_status": STATUS_DRAFT,
        "issue_number": None,
        "desks": list(desks),
        "week_start": week_start,
        "week_ending": week_ending,
        "development": {"summary": "", "citations": []},
        "title": "",
        "dek": "",
        "signal": "",
        "edition_type": "",
        "opening_note": "",
        "what_stood_out": "",
        "why_it_matters": "",
        "what_was_routine": "",
        "term_to_know_term": "",
        "term_to_know_lang": "",
        "term_to_know_explanation": "",
        "what_im_watching_next": "",
        "cross_desk_claims": [],
        "coverage_by_desk": coverage_by_desk(records, desks),
        "source_trail": [trail_entry(r) for r in candidates],
    })
    if exception:
        draft["single_desk_exception"] = exception
    return draft


def _refuse(message: str) -> int:
    print("REFUSED: " + message, file=sys.stderr)
    return 2


def _iso(value, flag):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise SystemExit("REFUSED: %s must be YYYY-MM-DD, got %r" % (flag, value))


def cmd_scaffold(args) -> int:
    registry = load_registry()
    desks = list(dict.fromkeys(d.strip() for d in args.desks.split(",")
                               if d.strip()))
    live = sorted(eligible_desks(registry))
    not_live = [d for d in desks if d not in live]
    if not desks or not_live:
        return _refuse("%s. Live desks with production records: %s." % (
            "not live: " + ", ".join(not_live) if not_live else "no desk named",
            ", ".join(live)))

    exception = None
    if len(desks) < MIN_DESKS:
        given = (args.exception_approved_by, args.exception_approved_on,
                 args.exception_reason)
        if not all(v and v.strip() for v in given):
            return _refuse(
                "a brief draws on at least %d live desks. A single-desk brief "
                "needs its approved exception recorded: --exception-approved-by, "
                "--exception-approved-on and --exception-reason." % MIN_DESKS)
        exception = {
            "approved_by": args.exception_approved_by.strip(),
            "approved_on": _iso(args.exception_approved_on,
                                "--exception-approved-on").isoformat(),
            "reason": args.exception_reason.strip(),
        }

    week_ending = _iso(args.week_ending, "--week-ending")
    week_start = (_iso(args.week_start, "--week-start") if args.week_start
                  else week_ending - timedelta(days=6))
    if week_start > week_ending:
        return _refuse("--week-start is after --week-ending")

    out = Path(args.out).resolve() if args.out else None
    if out is not None and (out == OUTPUT_DIR or OUTPUT_DIR in out.parents):
        return _refuse("never write inside output/: it is generated, and a "
                       "brief sidecar is source, kept in briefs/")

    with read_only(Path(args.db)) as conn:
        records = get_articles_for_desks(week_start.isoformat(),
                                         week_ending.isoformat(), desks,
                                         conn=conn)
    draft = build_draft(
        records, desks=desks, week_start=week_start.isoformat(),
        week_ending=week_ending.isoformat(),
        timing=TIMING_RETROSPECTIVE if args.retrospective else TIMING_REGULAR,
        exception=exception, include_not_selected=args.include_not_selected)

    text = json.dumps(draft, ensure_ascii=False, indent=2) + "\n"
    if out is None:
        sys.stdout.write(text)
    else:
        out.write_text(text, encoding="utf-8")
        print("Wrote %s" % out, file=sys.stderr)
    for desk, cov in draft["coverage_by_desk"].items():
        states = ", ".join("%s %d" % kv for kv in cov["by_screening"].items())
        offered = sum(1 for e in draft["source_trail"] if e["desk"] == desk)
        print("  %-12s %4d record(s) in window%s; %d offered as candidates" % (
            desk, cov["records"], " (%s)" % states if states else "", offered),
            file=sys.stderr)
    print("Draft only: no issue number. Keep the trail entries the brief "
          "cites, write the prose, then run `check`.", file=sys.stderr)
    return 0


def cmd_check(args) -> int:
    path = Path(args.path)
    sidecar = json.loads(path.read_text(encoding="utf-8"))
    issues = existing_issues()
    if sidecar.get("issue_number") is not None and not issues:
        # A number cannot be checked against issues that cannot be read; say so
        # rather than pass it. An unnumbered draft never needs them.
        return _refuse("%s carries an issue number, but no existing issue "
                       "sidecar was found under %s to check it against."
                       % (path, POSTS_DIR))
    problems = validate_brief(sidecar, load_registry(), collection=issues)
    if problems:
        print("%s breaks the brief contract:" % path)
        for problem in problems:
            print("  - " + problem)
        return 1
    print("%s satisfies the brief contract (%s)."
          % (path, sidecar.get("editorial_status")))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold or check an Indo-Pacific Record Brief.")
    sub = parser.add_subparsers(dest="command", required=True)

    scaffold = sub.add_parser(
        "scaffold", help="draft a brief from the named desks' records")
    scaffold.add_argument("--desks", required=True,
                          help="comma-separated live desks, e.g. china,singapore")
    scaffold.add_argument("--week-ending", required=True, help="YYYY-MM-DD")
    scaffold.add_argument("--week-start",
                          help="YYYY-MM-DD; default six days before --week-ending")
    scaffold.add_argument("--retrospective", action="store_true",
                          help="the brief is prepared after its week")
    scaffold.add_argument("--include-not-selected", action="store_true",
                          help="also offer records screened and not selected")
    scaffold.add_argument("--exception-approved-by",
                          help="single-desk brief only: who approved it")
    scaffold.add_argument("--exception-approved-on",
                          help="single-desk brief only: YYYY-MM-DD")
    scaffold.add_argument("--exception-reason",
                          help="single-desk brief only: why one desk suffices")
    scaffold.add_argument("--out",
                          help="write the draft here, never inside output/ "
                               "(default: stdout)")
    scaffold.add_argument("--db", default=str(DB_PATH),
                          help="database to read, through a scratch copy")

    check = sub.add_parser("check", help="validate a brief against the contract")
    check.add_argument("path")

    args = parser.parse_args(argv)
    if args.command == "scaffold":
        return cmd_scaffold(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
