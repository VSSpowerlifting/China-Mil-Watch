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
import re
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

FRAMING_LINE = (
    "DVIDS USINDOPACOM-tagged reference stream -- a Tier B DoD media-service "
    "feed. Unit tagging does not imply command authorship or comprehensive "
    "Indo-Pacific relevance. Not a complete USINDOPACOM command-release wire, "
    "and not presently a peer of the China Desk. The public US Indo-Pacific "
    "Reference Desk remains access_blocked; shadow collection evaluates "
    "whether this source can support that desk later.")

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
            " published_date, published_at_utc, source_slug,"
            " location, units"
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
    stats["_rows"] = rows
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


def check_rates(entries, stats):
    """Duplicate and media-only rates, as fractions of what the feed offered."""
    findings = []
    offered = sum(e.get("discovered", 0) for e in entries)
    dupes = sum(e.get("duplicates", 0) for e in entries)
    media = sum((e.get("rejections") or {}).get("not_news_media", 0)
                for e in entries)
    seen = offered + sum((e.get("rejections") or {}).get(r, 0)
                         for e in entries for r in REJECTION_REASONS)
    findings.append("     duplicate rate: %d of %d selected item(s)%s"
                    % (dupes, offered,
                       " (%.1f%%)" % (100.0 * dupes / offered) if offered
                       else ""))
    findings.append("     media-only rate: %d of %d feed item(s)%s -- image, "
                    "video and audio, counted and rejected"
                    % (media, seen,
                       " (%.1f%%)" % (100.0 * media / seen) if seen else ""))
    return findings, {"duplicates": dupes, "selected": offered,
                      "media_only": media, "feed_items_seen": seen}


def check_distributions(stats):
    """Publication geography and submitting-unit spread, where extractable."""
    findings = []
    rows = stats.get("_rows") or []
    if not rows:
        return ["     no records to describe"], {}
    locs = Counter((r[7] or "unrecorded") for r in rows)
    # DVIDS records some items at country granularity only ("US", "IN", "PR").
    # Reporting those beside full placenames would read as a single dominant
    # location when it is really an absence of detail.
    countries = Counter((r[7] or "unrecorded").rsplit(",", 1)[-1].strip()
                        for r in rows)
    coarse = {k: v for k, v in locs.items()
              if k != "unrecorded" and "," not in k}
    specific = {k: v for k, v in locs.items() if "," in k}
    units = Counter(u for r in rows
                    for u in (r[8] or "").split(",") if u)
    missing_loc = locs.get("unrecorded", 0)
    findings.append("     publication country: %s"
                    % "; ".join("%s=%d" % kv for kv in countries.most_common(8)))
    findings.append("     publication place (top 8 of %d specific): %s"
                    % (len(specific),
                       "; ".join("%s=%d" % kv for kv in
                                 Counter(specific).most_common(8)) or "none"))
    if coarse:
        findings.append(
            "     %d record(s) carry a country only, with no place: %s"
            % (sum(coarse.values()),
               "; ".join("%s=%d" % kv for kv in
                         Counter(coarse).most_common(6))))
    if missing_loc:
        findings.append("     %d record(s) carry no extractable location"
                        % missing_loc)
    findings.append("     submitting units (top 8 of %d): %s"
                    % (len(units), "; ".join("%s=%d" % kv
                                             for kv in units.most_common(8))
                       or "none extractable"))
    return findings, {"locations": dict(locs.most_common(20)),
                      "countries": dict(countries.most_common(20)),
                      "country_only": sum(coarse.values()),
                      "units": dict(units.most_common(20))}


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


# ── Scope-fitness reporting ───────────────────────────────────────────────────
# Everything below MEASURES the stream. None of it filters, and none of it
# decides. The editorial decision recorded on 2026-09-19 was to collect the
# complete eligible /news/ stream so its usefulness could be measured rather
# than predetermined; a reviewer that quietly applied the keyword list as a
# gate would undo that decision while appearing to honour it.

#: Deliberately generous: `alaska`, `pacific` and `hawaii` all score as hits,
#: which OVERSTATES Indo-Pacific presence rather than understating it. A count
#: built from it is a DIAGNOSTIC INDICATOR, never a disposition.
INDICATOR_TERMS = (
    # Command and theatre
    "indo-pacific", "indopacific", "indopacom", "pacific", "pacaf",
    "usarpac", "marforpac", "7th fleet", "3rd fleet", "pacific fleet",
    # States and territories in the AOR
    "japan", "korea", "china", "chinese", "taiwan", "india", "australia",
    "new zealand", "philippine", "indonesia", "malaysia", "singapore",
    "thailand", "vietnam", "mongolia", "bangladesh", "sri lanka", "nepal",
    "maldives", "brunei", "cambodia", "laos", "timor", "papua", "fiji",
    "tonga", "samoa", "palau", "micronesia", "marshall islands", "kiribati",
    "vanuatu", "solomon islands",
    # US territory and installations in or facing the AOR
    "hawaii", "guam", "alaska", "marianas", "okinawa", "yokosuka", "sasebo",
    "kadena", "andersen", "misawa", "iwakuni", "osan", "kunsan",
    "camp humphreys", "diego garcia", "darwin", "subic", "luzon",
    # Bodies of water
    "south china sea", "east china sea", "philippine sea", "taiwan strait",
    "bering sea", "sea of japan", "yellow sea", "malacca",
)

#: Matched on a leading word boundary plus an optional inflection, never as a
#: bare substring. Three cases had to work at once:
#:
#:   * "india" must NOT fire on "Indiana", and "laos" must not fire on "chaos"
#:     -- which a bare substring match got wrong;
#:   * "philippine" MUST fire on "Philippines" and "korea" on "Korean" --
#:     which a strict \b...\b match got wrong;
#:   * "japan" must fire on "Japanese".
#:
#: So: boundary, term, an optional suffix from a closed list, boundary.
#: "Indiana" fails because "na" is not in that list. The result is still a
#: CEILING on Indo-Pacific presence, deliberately; generosity is not the same
#: as being wrong about which word is on the page.
_INFLECTIONS = "s|n|ns|se|ese|ian|ians"
_INDICATOR_RE = re.compile(
    r"\b(?:%s)(?:%s)?\b" % ("|".join(re.escape(x) for x in INDICATOR_TERMS),
                             _INFLECTIONS),
    re.IGNORECASE)


#: Themes seen repeatedly in the measured feed that are not command activity in
#: the Indo-Pacific. Named so a reviewer can see WHAT the off-scope volume is,
#: not merely how much of it there is.
OFF_SCOPE_THEMES = (
    ("ceremonial / recognition",
     ("pinning", "retiree", "appreciation", "award", "ceremony",
      "promotion", "commemorat", "remembrance", "anniversary", "honoring",
      "memorial", "induct")),
    ("human interest / community",
     ("pen pal", "youth", "family", "school", "volunteer", "outreach",
      "hometown", "spouse", "heritage month")),
    ("domestic installation life",
     ("fort ", "base life", "dining facility", "housing", "commissary",
      "gym", "clinic opens")),
    ("obituary / interment",
     ("interment", "laid to rest", "funeral", "accounted for", "remains")),
    ("sports / fitness",
     ("run", "marathon", "tournament", "competition", "fitness")),
)


def indicator_count(titles):
    """How many titles carry ANY Indo-Pacific term. Diagnostic, not a verdict."""
    hits = [t for t in titles if _INDICATOR_RE.search(t or "")]
    return len(hits), hits


def off_scope_themes(titles):
    """Recurring themes among titles carrying no Indo-Pacific indicator."""
    misses = [t for t in titles if not _INDICATOR_RE.search(t or "")]
    counts = []
    for label, markers in OFF_SCOPE_THEMES:
        n = sum(1 for t in misses
                if any(m in (t or "").lower() for m in markers))
        if n:
            counts.append((label, n))
    counts.sort(key=lambda kv: -kv[1])
    unmatched = [t for t in misses
                 if not any(m in (t or "").lower()
                            for _, ms in OFF_SCOPE_THEMES for m in ms)]
    return counts, len(misses), unmatched


def representative_titles(rows, limit=10):
    """
    A spread across the corpus, not the newest ten.

    Evenly spaced by index over titles sorted by date then identity, so the
    sample cannot be dominated by one busy day -- and so nobody can read the
    first screenful and believe they have seen the stream.
    """
    ordered = sorted(rows, key=lambda r: (r[4] or "", r[1] or ""))
    if len(ordered) <= limit:
        return [r[2] for r in ordered]
    step = len(ordered) / float(limit)
    return [ordered[int(i * step)][2] for i in range(limit)]


def daily_volume(rows):
    """Records per publication day, and the retention pressure that implies."""
    per_day = Counter((r[4] or "")[:10] for r in rows if r[4])
    if not per_day:
        return {}
    counts = sorted(per_day.values())
    mid = len(counts) // 2
    median = (counts[mid] if len(counts) % 2
              else (counts[mid - 1] + counts[mid]) / 2.0)
    return {
        "days": len(per_day),
        "total": sum(per_day.values()),
        "median_per_day": median,
        "max_per_day": max(counts),
        "min_per_day": min(counts),
        "busiest_day": per_day.most_common(1)[0][0],
    }


def scope_fitness(stats, indicator, total, themes, missing):
    """
    An explicit verdict on whether the stream fits the desk it is proposed for.

    Separate from the checkpoint verdict on purpose. A collector can be
    flawless and the source still be a poor fit, and merging the two would let
    a clean run argue for a source that does not carry the material.
    """
    if not total:
        return ["SCOPE FITNESS: UNMEASURED -- no accepted records yet"]
    pct = 100.0 * indicator / total
    lines = ["scope indicator: %d of %d accepted titles (%.1f%%) carry any "
             "Indo-Pacific term" % (indicator, total, pct),
             "   this is a DIAGNOSTIC INDICATOR, not a disposition: the term "
             "list is deliberately generous and scores alaska, pacific and "
             "hawaii as hits, so it OVERSTATES presence"]
    if themes:
        lines.append("   recurring off-scope themes: %s"
                     % ", ".join("%s=%d" % kv for kv in themes))
    if pct < 25:
        lines.append(
            "SCOPE FITNESS: POOR -- on the most favourable reading available, "
            "the large majority of this stream does not announce Indo-Pacific "
            "content. It may still serve as a reference stream; it does not "
            "on this evidence support a desk presented as Indo-Pacific "
            "coverage. This is an editorial judgement for a human.")
    elif pct < 60:
        lines.append(
            "SCOPE FITNESS: MIXED -- a substantial minority of the stream "
            "carries Indo-Pacific indicators. Whether that is sufficient is "
            "an editorial judgement for a human.")
    else:
        lines.append(
            "SCOPE FITNESS: STRONG on this indicator. The indicator is a "
            "keyword count over titles and is not a substitute for reading "
            "the corpus.")
    return lines


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
            "VERDICT: ELIGIBLE FOR HUMAN REVIEW -- every check passes and %d "
            "collecting days have elapsed. This is a NECESSARY condition and "
            "never a sufficient one, and it is the strongest result this tool "
            "can return. Promotion is a human editorial decision; nothing "
            "here makes it, least of all for a DVIDS USINDOPACOM-tagged "
            "reference stream, which is a Tier B DoD media-service feed and "
            "not presently a peer of the China Desk. The public US "
            "Indo-Pacific Reference Desk remains access_blocked until a human "
            "decides otherwise." % len(days))
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
    rate_findings, rates = check_rates(entries, stats)
    findings += rate_findings
    dist_findings, distributions = check_distributions(stats)
    findings += dist_findings
    findings += check_health(entries)

    rows = stats.get("_rows") or []
    titles = [r[2] for r in rows]
    indicator, _hits = indicator_count(titles)
    themes, off_total, unmatched = off_scope_themes(titles)
    volume = daily_volume(rows)
    sample = representative_titles(rows)

    findings.append("     daily volume: %s" % (
        "%d record(s) over %d publication day(s); median %.1f/day, "
        "range %d-%d" % (volume["total"], volume["days"],
                         volume["median_per_day"], volume["min_per_day"],
                         volume["max_per_day"]) if volume else "no dated records"))
    findings.append(
        "     retention pressure: the DVIDS window is a fixed item count "
        "across ALL media, not a date range. At the measured mix it held ~16 "
        "days of news; a busier period shortens it, and anything that falls "
        "out is unrecoverable from this route.")

    stats.pop("_rows", None)
    report = {
        "desk": DESK_IDENTITY,
        "state_branch": STATE_BRANCH,
        "framing": FRAMING_LINE,
        "runs": len(entries),
        "collecting_days": days,
        "corpus": stats,
        "eligible_news_records": len(rows),
        "indicator": {"matched": indicator, "total": len(titles),
                      "kind": "diagnostic indicator, not dispositive"},
        "off_scope_themes": dict(themes),
        "off_scope_untyped": len(unmatched),
        "daily_volume": volume,
        "distributions": distributions,
        "rates": rates,
        "representative_titles": sample,
        "rejections": rejections,
        "findings": findings,
        "scope_fitness": scope_fitness(stats, indicator, len(titles), themes,
                                       off_total),
        "verdict": verdict(days, findings),
        "passed": not any(f.startswith("FAIL") for f in findings),
    }
    return report


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
        print("")
        print("  " + FRAMING_LINE.replace(". ", ".\n  "))
        print("")
        print("runs: %d   collecting days: %d"
              % (report["runs"], len(report["collecting_days"])))
        print("")
        for line in report["findings"]:
            print("  " + line)
        print("")
        print("  eligible news records: %d" % report["eligible_news_records"])
        print("  representative sample of accepted titles:")
        for title in report["representative_titles"]:
            print("    - %s" % title[:96])
        print("")
        for line in report["scope_fitness"]:
            print("  " + line)
        print("")
        for line in report["verdict"]:
            print("  " + line)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
