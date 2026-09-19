#!/usr/bin/env python3
"""
US Indo-Pacific (DVIDS) shadow checkpoint review.

WHAT THIS SOURCE IS
-------------------
**DVIDS USINDOPACOM-tagged reference stream.**

  * a **Tier B DoD media-service feed** -- the publisher is Defense Media
    Activity, a DoD field activity, not U.S. Pacific Command
  * **unit tagging does not imply command authorship or comprehensive
    Indo-Pacific relevance**; the tag is applied by the submitting unit
  * it is **not a complete USINDOPACOM command-release wire**
  * it is **not presently a peer of the China Desk**
  * **the public US Indo-Pacific Reference Desk remains `access_blocked`**
  * **shadow collection evaluates whether this source can support that desk
    later** -- it does not presuppose that it can

No record may be called Indo-Pacific-relevant merely because DVIDS tagged it
to the unit. Measured 2026-09-17: 428 items, 171 of them `/news/`, and 15 of
those 171 titles carry any Indo-Pacific keyword at all. The complete eligible
`/news/` stream is collected and **no relevance filter is applied**: filtering
at collection would predetermine the usefulness question this shadow phase
exists to measure.

Reads an explicit COPY of the `shadow/us-indopacom` state and reports what the
ledger and the shadow corpus actually show. It answers a reviewer's questions
with measurements, and it does not promote anything: there is no code path here
that writes to the repository, the production database, `output/`, or any
remote branch.

This is deliberately NOT `scripts/review_shadow_state.py`. That tool is bound
to Singapore -- its desk identity, its state branch, its release-URL pattern and
its source slug are constants inside it. Pointing it at a different desk would
mean either rewriting those constants (making it two tools in one file with a
flag) or letting the US desk be judged against Singapore's rules. The checks
that differ here are not cosmetic:

  * identity is a DVIDS numeric id, not a ministry release URL
  * a record's date comes from a per-item UTC offset, not a slug
  * the corpus has a REJECTION TAXONOMY to reconcile, which Singapore has no
    equivalent of
  * the retention window is a fixed item count, so a collection gap is
    permanent and must be reported as unrecoverable rather than as lateness

Usage:

    python3 scripts/review_us_shadow_state.py --state-repo /tmp/us-state-copy
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from scraper.sources.us_dvids import (                          # noqa: E402
    MIN_BODY_CHARS, REJECTION_REASONS, canonical_url, url_identity)

DESK_IDENTITY = "us-indopacom"
STATE_BRANCH = "shadow/us-indopacom"
SOURCE_SLUG = "us_dvids_indopacom"

#: A shadow desk is eligible to be CONSIDERED after this many collecting days.
#: Reaching it is necessary and never sufficient; this tool never says promote.
REQUIRED_COLLECTING_DAYS = 30

TERMINAL_OK = (st.OK, st.OK_NO_PUBLICATIONS, st.OK_ALL_DUPLICATES,
               st.OK_ALL_FILTERED)


class ReviewError(RuntimeError):
    """The state handed to this tool cannot be reviewed as given."""


def assert_is_a_copy(state_repo: Path) -> None:
    """
    Refuse to review the live working tree.

    A review that can reach the repository is a review that can change what it
    is reporting on. The reviewer passes an explicit copy.
    """
    state_repo = state_repo.resolve()
    if state_repo == REPO_ROOT or REPO_ROOT in state_repo.parents \
            or state_repo in REPO_ROOT.parents:
        raise ReviewError(
            "refusing to review state inside or above the repository working "
            "tree: %s\nCheck %s out somewhere else and pass that copy."
            % (state_repo, STATE_BRANCH))


def load_ledger(state_repo: Path):
    """Every ledger entry, oldest first. A malformed entry is an error."""
    ledger_dir = state_repo / "ledger"
    if not ledger_dir.is_dir():
        raise ReviewError("no ledger directory in %s" % state_repo)
    entries = []
    for path in sorted(ledger_dir.glob("*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ReviewError("ledger entry %s is not readable JSON: %s"
                              % (path.name, exc))
        entry["_file"] = path.name
        entries.append(entry)
    if not entries:
        raise ReviewError("ledger is empty; nothing has been collected")
    entries.sort(key=lambda e: e.get("finished_utc") or "")
    return entries


def check_desk_identity(entries):
    """Every entry must name this desk. A foreign entry is not reviewed."""
    findings = []
    foreign = sorted({e.get("desk") for e in entries
                      if e.get("desk") != DESK_IDENTITY})
    if foreign:
        findings.append(
            "FAIL ledger contains entries for another desk: %s"
            % ", ".join(str(f) for f in foreign))
    else:
        findings.append("ok   every ledger entry names %s" % DESK_IDENTITY)
    return findings


def check_clock(state_repo: Path, entries):
    """Day zero must be the first terminal-successful run, and immutable."""
    findings = []
    clock_path = state_repo / "clock.json"
    successes = [e for e in entries if e.get("result") in TERMINAL_OK]
    if not clock_path.exists():
        findings.append(
            "FAIL no clock.json" if successes
            else "ok   no clock.json and no successful run: the clock has "
                 "not started, which is correct")
        return findings, None
    clock = json.loads(clock_path.read_text(encoding="utf-8"))
    if not successes:
        findings.append("FAIL clock.json exists but no run succeeded")
        return findings, clock
    first = successes[0]
    if clock.get("day_zero_run_id") != first.get("run_id"):
        findings.append(
            "FAIL day zero names run %s but the first successful run is %s"
            % (clock.get("day_zero_run_id"), first.get("run_id")))
    else:
        findings.append("ok   day zero is the first successful run (%s)"
                        % clock.get("day_zero_run_id"))
    return findings, clock


def collecting_days(entries):
    """
    Distinct UTC days on which a run finished successfully.

    Runs, not days, are what the ledger records, and two runs on one day are
    one collecting day. A failed run is not a collecting day at all.
    """
    return sorted({(e.get("finished_utc") or "")[:10]
                   for e in entries if e.get("result") in TERMINAL_OK
                   and e.get("finished_utc")})


def check_continuity(days):
    """Gaps matter more here than elsewhere: this feed cannot be backfilled."""
    findings = []
    if len(days) < 2:
        findings.append("ok   too few collecting days to have a gap yet")
        return findings, []
    gaps = []
    for earlier, later in zip(days, days[1:]):
        d0 = date.fromisoformat(earlier)
        d1 = date.fromisoformat(later)
        missing = (d1 - d0).days - 1
        if missing > 0:
            gaps.append((earlier, later, missing))
    if gaps:
        for earlier, later, missing in gaps:
            findings.append(
                "FAIL %d day(s) missing between %s and %s -- the DVIDS window "
                "is a fixed item count, so those documents are UNRECOVERABLE "
                "from this route" % (missing, earlier, later))
    else:
        findings.append("ok   no gap between collecting days")
    return findings, gaps


def check_corpus(state_repo: Path):
    """Identity, bodies and dates in the shadow database."""
    findings = []
    db = state_repo / "shadow.db"
    if not db.exists():
        return ["FAIL no shadow.db in the state copy"], {}
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    try:
        rows = con.execute(
            "SELECT url, source_identity, title_original, text_original,"
            " published_date, published_at_utc, source_slug"
            " FROM shadow_records").fetchall()
    finally:
        con.close()

    stats = {"records": len(rows)}
    if not rows:
        return ["FAIL shadow.db holds no records"], stats

    urls = [r[0] for r in rows]
    idents = [r[1] for r in rows]
    stats["distinct_urls"] = len(set(urls))
    stats["distinct_identities"] = len(set(idents))

    findings.append(
        ("ok   " if len(set(urls)) == len(urls) else "FAIL ")
        + "%d records, %d distinct URLs" % (len(urls), len(set(urls))))
    findings.append(
        ("ok   " if len(set(idents)) == len(idents) else "FAIL ")
        + "%d records, %d distinct DVIDS identities"
        % (len(idents), len(set(idents))))

    empty = [r[0] for r in rows if not (r[3] or "").strip()]
    short = [r[0] for r in rows
             if (r[3] or "").strip() and len((r[3]).strip()) < MIN_BODY_CHARS]
    stats["empty_bodies"] = len(empty)
    findings.append(
        ("ok   " if not empty else "FAIL ")
        + "%d record(s) with an empty body" % len(empty))
    findings.append(
        ("ok   " if not short else "FAIL ")
        + "%d record(s) below the %d-character floor" % (len(short),
                                                         MIN_BODY_CHARS))

    bad_url = [u for u in urls if canonical_url(u) != u]
    findings.append(
        ("ok   " if not bad_url else "FAIL ")
        + "%d record(s) whose URL is not canonical" % len(bad_url))

    mismatched = [r[0] for r in rows if url_identity(r[0]) != r[1]]
    findings.append(
        ("ok   " if not mismatched else "FAIL ")
        + "%d record(s) whose identity disagrees with its URL"
        % len(mismatched))

    untitled = [r[0] for r in rows if not (r[2] or "").strip()]
    findings.append(
        ("ok   " if not untitled else "FAIL ")
        + "%d record(s) with no title" % len(untitled))

    undated = [r[0] for r in rows if not (r[4] or "").strip()]
    findings.append(
        ("ok   " if not undated else "FAIL ")
        + "%d record(s) with no publication date" % len(undated))

    no_instant = [r[0] for r in rows if not (r[5] or "").strip()]
    findings.append(
        ("ok   " if not no_instant else "FAIL ")
        + "%d record(s) with no preserved UTC instant" % len(no_instant))

    foreign_slug = sorted({r[6] for r in rows if r[6] != SOURCE_SLUG})
    findings.append(
        ("ok   " if not foreign_slug else "FAIL ")
        + "source slugs present: %s"
        % ", ".join(sorted({r[6] for r in rows})))

    dates = sorted(r[4] for r in rows if r[4])
    stats["range"] = [dates[0], dates[-1]] if dates else [None, None]
    return findings, stats


def check_rejections(entries):
    """
    Reconcile what the feed offered against what was kept.

    A collector that reports only its successes cannot be audited, and a
    taxonomy that never fires is a taxonomy nobody has tested.
    """
    findings = []
    totals = Counter()
    for entry in entries:
        for reason, count in (entry.get("rejections") or {}).items():
            totals[reason] += count
    unknown = sorted(set(totals) - set(REJECTION_REASONS))
    if unknown:
        findings.append("FAIL ledger uses rejection reasons the collector "
                        "does not declare: %s" % ", ".join(unknown))
    else:
        findings.append("ok   every rejection reason is a declared one")
    findings.append("     rejections across all runs: %s"
                    % (", ".join("%s=%d" % kv for kv in sorted(totals.items())
                                 if kv[1]) or "none"))
    return findings, dict(totals)


def check_health(entries):
    findings = []
    results = Counter(e.get("result") for e in entries)
    failures = [e for e in entries if e.get("health") != "ok"]
    findings.append("     run results: %s"
                    % ", ".join("%s=%d" % kv for kv in sorted(results.items())))
    findings.append(
        ("ok   " if not failures else "note ")
        + "%d of %d run(s) failed" % (len(failures), len(entries)))
    streak = worst = 0
    for entry in entries:
        streak = streak + 1 if entry.get("health") != "ok" else 0
        worst = max(worst, streak)
    findings.append(
        ("ok   " if worst < 2 else "FAIL ")
        + "longest consecutive failure streak: %d" % worst)
    return findings


def verdict(days, findings):
    """
    What the evidence supports. Never a promotion.

    Two separate things have to be true, and this tool only ever reports on
    them: the desk must have collected for long enough to have a record, and
    nothing in that record may be broken. Neither makes promotion automatic.
    """
    failed = [f for f in findings if f.startswith("FAIL")]
    lines = []
    lines.append("collecting days: %d of %d required"
                 % (len(days), REQUIRED_COLLECTING_DAYS))
    if failed:
        lines.append("VERDICT: NOT READY -- %d check(s) failed" % len(failed))
    elif len(days) < REQUIRED_COLLECTING_DAYS:
        lines.append("VERDICT: NOT READY -- checks pass, but the desk has "
                     "collected for %d day(s); %d are required"
                     % (len(days), REQUIRED_COLLECTING_DAYS))
    else:
        lines.append(
            "VERDICT: ELIGIBLE FOR REVIEW -- every check passes and %d "
            "collecting days have elapsed. This is a NECESSARY condition and "
            "never a sufficient one. Promotion is a human editorial decision "
            "and this tool does not make it, least of all for a source whose "
            "measured scope is unit-tagged public affairs." % len(days))
    return lines


def review(state_repo: Path):
    assert_is_a_copy(state_repo)
    entries = load_ledger(state_repo)
    findings = []
    findings += check_desk_identity(entries)
    clock_findings, _clock = check_clock(state_repo, entries)
    findings += clock_findings
    days = collecting_days(entries)
    cont_findings, _gaps = check_continuity(days)
    findings += cont_findings
    corpus_findings, stats = check_corpus(state_repo)
    findings += corpus_findings
    rej_findings, rejections = check_rejections(entries)
    findings += rej_findings
    findings += check_health(entries)
    return {
        "desk": DESK_IDENTITY,
        "state_branch": STATE_BRANCH,
        "runs": len(entries),
        "collecting_days": days,
        "corpus": stats,
        "rejections": rejections,
        "findings": findings,
        "verdict": verdict(days, findings),
        "passed": not any(f.startswith("FAIL") for f in findings),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--state-repo", required=True,
                    help="a COPY of the %s branch. Never the working tree."
                         % STATE_BRANCH)
    ap.add_argument("--json", action="store_true",
                    help="emit the report as JSON instead of text")
    args = ap.parse_args(argv)
    try:
        report = review(Path(args.state_repo))
    except ReviewError as exc:
        print("review refused: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    else:
        print("US Indo-Pacific shadow review (%s)" % report["state_branch"])
        print("runs: %d   collecting days: %d"
              % (report["runs"], len(report["collecting_days"])))
        print("")
        for line in report["findings"]:
            print("  " + line)
        print("")
        for line in report["verdict"]:
            print("  " + line)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
