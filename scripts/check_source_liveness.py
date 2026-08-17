#!/usr/bin/env python3
"""Report sources that have gone quiet.

Background (2026-08-09). MOD China (国防部) last produced an article on
2026-07-10 and nothing noticed for four weeks: PLA Daily supplies ~87% of all
articles, so a dead secondary source does not dent the daily totals and the
pipeline stays green. This check makes that visible.

A source is UNHEALTHY when it is active, is not a documented stub, and its most
recent article is older than --max-silent-days (default 7). Sources that have
never produced anything are unhealthy immediately unless they are documented
stubs.

KNOWN_INERT sources are reported as INERT, never UNHEALTHY. Keep this list in
sync with the scraper docstrings — an entry here is a promise that the silence
is understood and tracked somewhere.

Exit codes:
    0  all sources healthy (or only inert ones are quiet)
    1  at least one source is unhealthy

Usage:
    .venv/bin/python scripts/check_source_liveness.py
    .venv/bin/python scripts/check_source_liveness.py --max-silent-days 14
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.reconcile_db import read_only                      # noqa: E402

DEFAULT_DB = REPO_ROOT / "pla_watch.db"

# Sources whose silence is deliberate and documented. The value is the reason,
# and it is printed in the report so nobody has to go spelunking for it.
KNOWN_INERT = {
    "xinhua_mil": (
        "documented stub — listing page requires JS rendering; returns [] by "
        "design (see scraper/sources/xinhua_mil.py, v2 roadmap P3)"
    ),
}

# Per-source silence thresholds in days, overriding --max-silent-days. A source
# that genuinely publishes twice a month is not sick after seven quiet days, and
# alarming on it teaches everyone to ignore the alarm. Measured 2026-08-09 from
# the sources' own listing pages, not from our collection (which is what we are
# trying to check).
SILENCE_THRESHOLD_DAYS = {
    # MOD's six tracked sections carried 28 distinct publish dates across three
    # months — roughly one every three days, in bursts. 21d flags real death
    # while tolerating a normal quiet fortnight.
    "mod_china": 21,
}


def rows(db_path: Path, today: date):
    # Reads a scratch copy, not the tracked file. The previous `mode=ro` URI
    # could not open a WAL-mode database with no `-shm` beside it, so running
    # this on a fresh clone died with an unhandled OperationalError — the health
    # gate is the last step of the daily run and only survived because an
    # earlier step had already created the sidecars.
    with read_only(db_path) as conn:
        return conn.execute(
            """
            SELECT s.slug,
                   s.display_name,
                   COUNT(a.id)             AS total,
                   MAX(date(a.scraped_at)) AS last_seen
              FROM sources s
              LEFT JOIN articles a ON a.source_id = s.id
             WHERE s.is_active = 1
             GROUP BY s.id
             ORDER BY total DESC
            """
        ).fetchall()


def classify(slug: str, total: int, last_seen: str | None,
             today: date, max_silent: int):
    """Return (state, days_silent, detail)."""
    if slug in KNOWN_INERT:
        return "INERT", None, KNOWN_INERT[slug]

    if total == 0 or last_seen is None:
        return "UNHEALTHY", None, "no articles have ever been collected"

    threshold = SILENCE_THRESHOLD_DAYS.get(slug, max_silent)
    days = (today - datetime.strptime(last_seen, "%Y-%m-%d").date()).days
    detail = f"last article {last_seen} ({days}d ago, threshold {threshold}d)"
    if days > threshold:
        return "UNHEALTHY", days, detail
    return "HEALTHY", days, detail


def emit_github(unhealthy: list[tuple[str, str]], lines: list[str]) -> None:
    """Annotate the Actions run and write a step summary, when running in CI."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return

    for name, detail in unhealthy:
        print(f"::warning title=Source silent::{name}: {detail}")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("### Source liveness\n\n```\n")
            fh.write("\n".join(lines))
            fh.write("\n```\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--max-silent-days", type=int, default=7)
    parser.add_argument(
        "--today", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date(),
        default=date.today(), help="override today's date (testing)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        sys.exit(f"ERROR: database not found: {args.db}")

    unhealthy: list[tuple[str, str]] = []
    lines: list[str] = []

    for slug, name, total, last_seen in rows(args.db, args.today):
        state, _days, detail = classify(
            slug, total, last_seen, args.today, args.max_silent_days
        )
        lines.append(f"{state:<10} {name:<28} {total:>5} article(s)  {detail}")
        if state == "UNHEALTHY":
            unhealthy.append((name, detail))

    print(f"Source liveness — threshold {args.max_silent_days}d, as of {args.today}")
    print("-" * 78)
    for line in lines:
        print(line)
    print("-" * 78)

    emit_github(unhealthy, lines)

    if unhealthy:
        print(f"\n{len(unhealthy)} source(s) need attention.")
        return 1

    print("\nAll non-inert sources are producing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
