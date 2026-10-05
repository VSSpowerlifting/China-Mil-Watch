"""Author an Indo-Pacific Record Brief without API calls.

scaffold: source candidates and per-desk coverage from a read-only corpus copy.
check: schema/collection validity; empty drafts may pass and remain withheld.
ready: complete prose, citations, chronology and parity with preserved records.
approve: record explicit human authorization and assign the next collection
number, atomically under a local lock. Repeating the same approval is a no-op;
a different approval, conflicting collection or existing scaffold is refused.

Canonical source is briefs/<slug>.json. Nothing here writes generated output,
merges, deploys, or establishes editorial approval on the owner's behalf.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import DB_PATH                                     # noqa: E402
from core.brief_contract import (                              # noqa: E402
    BRIEF_SCHEMA, MIN_DESKS, SCREENING_NOT_SELECTED, STATUS_DRAFT,
    coverage_by_desk, eligible_desks, screening_state, trail_entry,
    validate_brief, validate_readiness, approve, NumberingBlocked)
from core.brief_collection import load_briefs, SLUG_RE, RESERVED_SLUGS
from core.desk_registry import load_registry                   # noqa: E402
from core.edition_identity import (                            # noqa: E402
    TIMING_REGULAR, TIMING_RETROSPECTIVE, brief_identity_fields)
from scripts.reconcile_db import read_only                     # noqa: E402
from storage.db import get_articles_for_desks                  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "output"
POSTS_DIR = OUTPUT_DIR / "the-pla-watch" / "posts"
BRIEFS_DIR = REPO_ROOT / "briefs"


def existing_issues(exclude=None) -> list:
    """Validate/read the whole collection; exclude the file being checked."""
    historical = [json.loads(p.read_text(encoding="utf-8"))
                  for p in sorted(POSTS_DIR.glob("*.json"))]
    published, _ = load_briefs(BRIEFS_DIR, load_registry(), historical_numbers=[
        s["issue_number"] for s in historical])
    return historical + [s for slug, s in published
                         if exclude is None or (BRIEFS_DIR / (slug + ".json")).resolve() != exclude]


def readiness_problems(sidecar, issues, db):
    problems = validate_readiness(sidecar, load_registry(), collection=issues)
    with read_only(Path(db)) as conn:
        records = get_articles_for_desks(sidecar["week_start"], sidecar["week_ending"],
                                         sidecar["desks"], conn=conn)
    current = {r["id"]: trail_entry(r) for r in records}
    for entry in sidecar.get("source_trail") or []:
        rid = entry.get("record_id")
        if rid not in current:
            problems.append("record %s is absent from this corpus/window" % rid)
        elif entry != current[rid]:
            changed = sorted(k for k in current[rid] if entry.get(k) != current[rid][k])
            problems.append("record %s conflicts with stored source state (%s); review a fresh scaffold" % (rid, ", ".join(changed)))
    if sidecar.get("coverage_by_desk") != coverage_by_desk(records, sidecar["desks"]):
        problems.append("coverage_by_desk conflicts with this corpus; review a fresh scaffold")
    return problems


def _report(path, problems):
    if problems:
        print("%s is not ready:" % path, file=sys.stderr)
        for problem in problems:
            print("  - " + problem, file=sys.stderr)
        return 1
    return 0


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
        with out.open("x", encoding="utf-8") as stream:
            stream.write(text)
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
    issues = existing_issues(path.resolve())
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
    print("Schema validity is not release readiness or editorial approval.")
    return 0


def cmd_ready(args):
    path = Path(args.path).resolve()
    sidecar = json.loads(path.read_text(encoding="utf-8"))
    if _report(path, readiness_problems(sidecar, existing_issues(path), args.db)):
        return 1
    print("%s passes release readiness. Editorial approval and rendered review remain separate." % path)
    return 0


def cmd_approve(args):
    path = Path(args.path).resolve()
    if not args.approved_by.strip() or not args.approval_reference.strip():
        return _refuse("name the approving human and the actual approval reference")
    if path.parent != BRIEFS_DIR.resolve() or not SLUG_RE.fullmatch(path.stem) or path.stem in RESERVED_SLUGS:
        return _refuse("approve a canonical briefs/<slug>.json source, never output/ or another directory")
    # ponytail: one local publication lock; distributed publishers need a shared transaction.
    with (BRIEFS_DIR / ".approval.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        sidecar = json.loads(path.read_text(encoding="utf-8"))
        issues = existing_issues(path)
        if sidecar.get("editorial_status") == "approved":
            if sidecar.get("approval") != {"approved_by": args.approved_by, "approved_on": args.approved_on,
                                          "reference": args.approval_reference}:
                return _refuse("already approved; approval evidence and number cannot be overwritten")
            print("Already approved as No. %s; unchanged." % sidecar["issue_number"])
            return 0
        if _report(path, readiness_problems(sidecar, issues, args.db)):
            return 1
        result = approve(sidecar, collection=issues, registry=load_registry(),
                         approved_by=args.approved_by, approved_on=args.approved_on)
        result["approval"]["reference"] = args.approval_reference
        pending = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".approval-", delete=False) as stream:
                pending = Path(stream.name)
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, path)
        finally:
            if pending and pending.exists():
                pending.unlink()
        print("Approved No. %s in %s. Render and validate before release." % (result["issue_number"], path))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold, check, review readiness, or record authorized Brief approval.")
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

    ready = sub.add_parser("ready", help="check complete prose, citations and stored source state; no approval")
    ready.add_argument("path")
    ready.add_argument("--db", default=str(DB_PATH))
    approval = sub.add_parser("approve", help="record explicit owner approval and assign the next collection number")
    approval.add_argument("path")
    approval.add_argument("--approved-by", required=True)
    approval.add_argument("--approved-on", required=True, type=lambda v: _iso(v, "--approved-on").isoformat())
    approval.add_argument("--approval-reference", required=True, help="location of the actual human approval")
    approval.add_argument("--db", default=str(DB_PATH))

    args = parser.parse_args(argv)
    try:
        return {"scaffold": cmd_scaffold, "check": cmd_check, "ready": cmd_ready,
                "approve": cmd_approve}[args.command](args)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, NumberingBlocked) as exc:
        return _refuse(str(exc))


if __name__ == "__main__":
    sys.exit(main())
