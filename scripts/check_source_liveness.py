#!/usr/bin/env python3
"""Report sources that have gone quiet.

Background (2026-08-09). MOD China (国防部) last produced an article on
2026-07-10 and nothing noticed for four weeks: PLA Daily supplies ~87% of all
articles, so a dead secondary source does not dent the daily totals and the
pipeline stays green. This check makes that visible.

A source is UNHEALTHY when it is expected to collect and its most recent
article is older than its own silence threshold. Sources that have never
produced anything are unhealthy immediately unless they are not expected to
collect at all.

Where the expectations come from (2026-09-20)
---------------------------------------------
Nowhere in this file. Both the "this source is allowed to be silent" list and
the per-source thresholds used to be hand-maintained dictionaries here, and
both drifted: Xinhua Military was rewritten into a working adapter on
2026-09-16 and delivered four new articles on 2026-09-20, while this script
still carried the stub's obituary and reported it INERT. An INERT source is
exempt from every recency threshold, so Xinhua could have died the next day and
this gate would have said nothing.

A second copy of a fact is a second chance to be wrong about it. Both
dictionaries are gone. Expectations are now derived:

  * whether a source can collect at all — from the adapter's own offline
    `healthcheck()`, which reports NOT_IMPLEMENTED for a class declaring
    `IS_STUB` and SKIPPED_DISABLED for one the desk manifest disables. A
    source becomes exempt by being a declared stub, not by being named here.
  * how long it may stay quiet — from `silence_threshold_days` in the desk
    manifest, the same field `core.collection.health.silence_verdict` reads.

A source whose adapter will not even import is UNHEALTHY, not INERT. That is
the failure this gate exists for, and it must never be reachable by accident.

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
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                       # noqa: E402
from core.registry import get_registry                         # noqa: E402
from scripts.reconcile_db import read_only                     # noqa: E402

DEFAULT_DB = REPO_ROOT / "pla_watch.db"

#: Configuration states in which a source is not expected to produce anything,
#: and its silence is therefore not a defect. Both are declarations made
#: elsewhere and merely read here: `IS_STUB` on the adapter class, `enabled`
#: in the desk manifest. Neither is a failure, and neither is a judgement this
#: file is entitled to make on its own.
INERT_STATUSES = {
    st.NOT_IMPLEMENTED: "declared stub — no working collection path",
    st.SKIPPED_DISABLED: "disabled in its desk manifest",
}


@dataclass(frozen=True)
class Expectation:
    """What configuration says this source should be doing.

    `threshold` of None means the manifest states no cadence for this source
    and the run-wide `--max-silent-days` applies.
    """

    inert: bool = False
    broken: bool = False
    reason: Optional[str] = None
    threshold: Optional[int] = None


#: The expectation for a slug no desk manifest declares. Deliberately not
#: inert: a source in the database that configuration has forgotten is still
#: expected to produce, and the generic threshold applies. Exemption is
#: something a manifest grants, never something absence produces.
UNDECLARED = Expectation()


def expectations(registry=None) -> Dict[str, Expectation]:
    """Derive per-source expectations from adapters and desk manifests.

    Offline: `healthcheck()` is specified to perform no network I/O, which is
    what lets this run inside the test suite and on a fresh clone.
    """
    registry = registry or get_registry()
    out: Dict[str, Expectation] = {}
    for result in registry.healthcheck_all():
        source = registry.get_source(result.source_slug)
        threshold = getattr(source, "silence_threshold_days", None)
        if result.status in INERT_STATUSES:
            out[result.source_slug] = Expectation(
                inert=True,
                reason=result.detail or INERT_STATUSES[result.status],
                threshold=threshold,
            )
        elif st.is_failure(result.status):
            # An adapter that cannot be imported or resolved. Silence from it
            # is guaranteed and meaningless, so recency would report HEALTHY
            # for as long as the corpus stayed warm.
            out[result.source_slug] = Expectation(
                broken=True,
                reason="adapter unusable (%s): %s"
                % (result.status, result.detail or "no detail"),
                threshold=threshold,
            )
        else:
            out[result.source_slug] = Expectation(threshold=threshold)
    return out


def rows(db_path: Path, today: date):
    # Reads a scratch copy, not the tracked file. A direct `mode=ro` URI on a
    # sidecar-less WAL database is not portable: depending on SQLite, the VFS
    # and the filesystem it either fails to open or creates the sidecars beside
    # the input (DECISION_LOG 2026-08-17). Where it failed, running this on a
    # fresh clone died with an unhandled OperationalError — the health gate is
    # the last step of the daily run, and it survived there only because an
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
             today: date, max_silent: int,
             expectation: Expectation = UNDECLARED):
    """Return (state, days_silent, detail)."""
    if expectation.broken:
        return "UNHEALTHY", None, expectation.reason

    if expectation.inert:
        return "INERT", None, expectation.reason

    if total == 0 or last_seen is None:
        return "UNHEALTHY", None, "no articles have ever been collected"

    threshold = expectation.threshold or max_silent
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

    expected = expectations()
    unhealthy: list[tuple[str, str]] = []
    lines: list[str] = []

    for slug, name, total, last_seen in rows(args.db, args.today):
        state, _days, detail = classify(
            slug, total, last_seen, args.today, args.max_silent_days,
            expected.get(slug, UNDECLARED),
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
