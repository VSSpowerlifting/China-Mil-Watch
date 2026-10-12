"""Daily Indonesia operational canary against immutable shadow Git and Pages.

Provides collection continuity and public-link *navigation* checks only. It does
not enumerate every Actions attempt, authenticate editorial reviews, qualify
the 30-day source or authorize copied content/production admission.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
import re

from bs4 import BeautifulSoup
from pathlib import Path

from core.indonesia_official_index import load as load_official_links
from core.indonesia_press_index import load as load_official_press_links
from core.shadow_schedule import scheduled_slot_date
from scripts.audit_indonesia_shadow_provenance import (
    DESK, GOOD_RESULTS, RUN_ID, SHA, SHA256, pinned_state, utc,
)

FIRST_SCHEDULED = date(2026, 10, 7)
MONITOR_CRON = "03:17"


class HealthError(ValueError):
    """Bad collection evidence or unsafe public page."""


def check(ok, reason):
    if not ok:
        raise HealthError(reason)


def monitor_day(at=None):
    """Use nominal 03:17 UTC health slot, even if GitHub runs after midnight."""
    at = at or datetime.now(timezone.utc)
    check(at.tzinfo is not None and at.utcoffset() == timedelta(0),
          "monitor start must be UTC")
    return scheduled_slot_date(at, MONITOR_CRON) - timedelta(days=1)


def evaluate(clock, ledgers, db_digest, expected_day, commit):
    """Strict append-only hash and daily-slot check, without source bodies."""
    check(isinstance(expected_day, date), "expected UTC date required")
    check(type(commit) is str and SHA.fullmatch(commit), "literal state pin required")
    check(type(db_digest) is str and SHA256.fullmatch(db_digest), "invalid DB digest")
    check(clock.get("desk") == DESK and
          clock.get("day_zero_run_id") == "local-native-20261006-indonesia",
          "Indonesia initial clock changed")
    check(expected_day >= FIRST_SCHEDULED, "monitor precedes start of schedule")
    check(type(ledgers) is list and bool(ledgers), "no successful state ledgers")
    previous, previous_end, dates, latest, stored = None, None, set(), None, None
    for number, ledger in enumerate(ledgers):
        check(type(ledger) is dict and ledger.get("desk") == "indonesia",
              "unexpected state ledger")
        started, ended = utc(ledger.get("started_utc")), utc(ledger.get("finished_utc"))
        check(started <= ended and (previous_end is None or started >= previous_end),
              "ledgers overlap or are not chronological")
        previous_end = ended
        check(ledger.get("health") == "ok" and ledger.get("result") in GOOD_RESULTS
              and all(type(ledger.get(x)) is int and ledger[x] == 0 for x in
                      ("fetch_failures", "extraction_failures", "access_failures")),
              "collector reported unhealthy result")
        prev_hash, new_hash = ledger.get("state_sha256_before"), ledger.get("state_sha256_after")
        check(type(new_hash) is str and SHA256.fullmatch(new_hash), "invalid ledger state digest")
        if number == 0:
            check(prev_hash is None and
                  ledger.get("run_id") == clock.get("day_zero_run_id") and
                  ended == utc(clock.get("day_zero_utc")),
                  "initial ledger/clock mismatch")
        else:
            check(prev_hash == previous, "broken adjacent shadow database hash chain")
        previous = new_hash
        try:
            logical = date.fromisoformat(ledger["target_date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HealthError("invalid collection logical date") from exc
        check(logical.isoformat() == ledger["target_date"], "noncanonical logical date")
        if ledger.get("target_date_source") == "schedule-slot":
            check(RUN_ID.fullmatch(str(ledger.get("run_id"))) is not None,
                  "scheduled ledger lacks Actions run identity")
            check(scheduled_slot_date(started, "17:17") == logical,
                  "scheduled ledger assigned to wrong nominal date")
            check(logical not in dates, "duplicate scheduled logical date")
            dates.add(logical)
        count = ledger.get("stored_total")
        check(type(count) is int and count >= 0 and (stored is None or count >= stored),
              "stored original record count regressed")
        stored = count
        latest = logical
    check(previous == db_digest, "pinned DB bytes disagree with last successful ledger")
    expected_dates = set()
    d = FIRST_SCHEDULED
    while d <= expected_day:
        expected_dates.add(d)
        d += timedelta(days=1)
    absent = sorted(expected_dates - dates)
    lag = (expected_day - max(dates)).days if dates else len(expected_dates)
    return {
        "schema": "ipr-indonesia-readonly-operational-canary/1",
        "as_of_logical_day": expected_day.isoformat(),
        "pinned_state_commit": commit,
        "source_family": "id_kemhan_news",
        "stored_private_originals": stored,
        "successful_ledgers": len(ledgers),
        "successful_scheduled_dates": len(dates),
        "latest_scheduled_day": max(dates).isoformat() if dates else None,
        "missing_scheduled_dates": [x.isoformat() for x in absent],
        "days_lagging": max(0, lag),
        "collection_status": "LEDGERS_CURRENT" if not absent else "HOLD_MISSING_SCHEDULED_SLOT",
        "all_actions_attempts_independently_audited": False,
        "independent_source_review_completed": False,
        "source_rights_approved": False,
        "production_admitted": False,
    }


def published_entries(document, label, *, press=False):
    """Read each source's *local* title/date/number as a bound list item.

    Static publication check only: no link dereference, source fetch or rights
    decision. A correct URL is not sufficient if its surrounding metadata lies.
    """
    groups = document.select('ol[aria-label="' + label + '"]')
    check(len(groups) == 1, "expected exactly one " + label)
    result = []
    for item in groups[0].find_all("li", recursive=False):
        anchors, dates = item.find_all("a"), item.find_all("time")
        check(len(anchors) == 1 and len(dates) == 1,
              "publisher item must bind one link, heading and date")
        link, published = anchors[0], dates[0]
        entry = (link.get("href"), link.get("lang"),
                 link.get_text(" ", strip=True),
                 published.get("datetime"),
                 published.get_text(" ", strip=True))
        if press:
            numbers = re.findall(
                r"\bPress statement\s+(SP/[1-9][0-9]*/[IVX]+/20[0-9]{2}/ROINFOHAN)\b",
                item.get_text(" ", strip=True))
            check(len(numbers) == 1,
                  "missing or duplicated local publisher press identifier")
            entry += (numbers[0],)
        result.append(entry)
    return result


def check_public_page(path, approved_links=None, approved_press_links=None):
    """Read a local copy from exact gh-pages Git commit, never fetch publisher."""
    path = Path(path)
    check(path.is_file() and not path.is_symlink() and
          path.stat().st_size <= 250_000, "published page missing or oversized")
    page = path.read_text(encoding="utf-8")
    document = BeautifulSoup(page, "html.parser")
    known = approved_links if approved_links is not None else load_official_links()
    press = approved_press_links if approved_press_links is not None else load_official_press_links()
    news_entries = published_entries(
        document, "Four external ministry news links")
    press_entries = published_entries(
        document, "Two external ministry press release links", press=True)
    expected_news = [
        (ref["source_url"], "id", ref["title_original"],
         ref["published_date"], ref["published_date"])
        for ref in known
    ]
    expected_press = [
        (ref["source_url"], "id", ref["title_original"],
         ref["published_date"], ref["published_date"], ref["press_number"])
        for ref in press
    ]
    check(news_entries == expected_news,
          "Pages news links, headlines or dates disagree with frozen source metadata")
    check(press_entries == expected_press,
          "Pages press links, headlines, dates or numbered releases disagree with frozen source metadata")
    check(len({entry[0] for entry in news_entries + press_entries}) ==
          len(news_entries) + len(press_entries),
          "published ministry links are not unique")
    for phrase in ("Shadow evaluation — no public corpus records",
                   "No individual source references have completed",
                   "Explore official Indonesian defense publications",
                   "Kemhan press releases (Siaran Pers)"):
        check(phrase in page, "public source-scope explanation missing")
    for forbidden in ("text_original", "body_original", "state/shadow.db",
                      "data-reference-list", "NOT APPROVED FOR PUBLICATION"):
        check(forbidden not in page, "unapproved source or review material in public page")
    return len(news_entries) + len(press_entries)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--published-page", type=Path, required=True)
    p.add_argument("--as-of", help="explicit expected scheduled UTC date for audit/replay")
    p.add_argument("--receipt", type=Path, required=True)
    args = p.parse_args(argv)
    expected = date.fromisoformat(args.as_of) if args.as_of else monitor_day()
    clock, ledgers, db_hash = pinned_state(args.state_repo, args.state_commit)
    report = evaluate(clock, ledgers, db_hash, expected, args.state_commit)
    report["published_external_links"] = check_public_page(args.published_page)
    report["status"] = "PASS" if report["collection_status"] == "LEDGERS_CURRENT" else "HOLD"
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
