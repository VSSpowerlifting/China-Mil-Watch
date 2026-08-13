#!/usr/bin/env python3
"""
Verify that `pla_watch.db` is schema-current and structurally sound.

Read-only by default. Used in two places in the daily workflow:

  * **Before the pipeline**, after `--apply`, to confirm the migration actually
    landed.
  * **After every rebase that precedes a push**, to prove the reconciler's
    output is current before it reaches origin.

The post-rebase use is a fail-closed check, not a repair step. The reconciler
now migrates its output before merging rows, so a rebase should never produce a
regressed database — this exists to make that guarantee observable rather than
assumed, and to stop a regressed file from being pushed if it ever is violated.

`--repair` is offered for the one path that legitimately commits the database,
and even there the workflow must prove the repair is inside the pushed commit.
Never use `--repair` on a marker-only path: it would put database changes into a
commit whose documented responsibility is a state file.

Exit codes
    0  database is current and clean
    1  verification failed (or, with --repair, could not be made current)
    2  database not found
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from migrations.runner import (                                   # noqa: E402
    apply_all, applied_versions, connect, discover, verify,
)

DEFAULT_DB = REPO_ROOT / "pla_watch.db"

REQUIRED_TABLES = (
    "articles", "sources", "categories", "article_categories", "scrape_runs",
    "schema_migrations", "desks", "institutions", "source_run_results",
)

# Statuses pipeline.py can write. The merged/committed database must be able to
# represent all of them or a degraded day fails at the last step.
REQUIRED_RUN_STATUSES = ("running", "completed", "degraded", "failed")


def classify(conn) -> str:
    """
    Distinguish the states that need different responses.

    fully_current           — ledger complete, tables present
    ledger_absent           — schema looks current but nothing recorded it
    partially_applied       — some migrations recorded, others pending
    structurally_incompatible — a core legacy table is missing entirely
    """
    present = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for core_table in ("articles", "sources", "scrape_runs"):
        if core_table not in present:
            return "structurally_incompatible"

    expected = {m.version for m in discover()}
    if "schema_migrations" not in present:
        return "ledger_absent"

    have = set(applied_versions(conn))
    if not have:
        return "ledger_absent"
    if expected - have:
        return "partially_applied"
    return "fully_current"


def check(conn) -> list:
    problems = []

    present = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for table in REQUIRED_TABLES:
        if table not in present:
            problems.append("required table missing: %s" % table)

    expected = {m.version for m in discover()}
    have = set(applied_versions(conn)) if "schema_migrations" in present else set()
    missing = sorted(expected - have)
    if missing:
        problems.append("migration ledger incomplete: missing %s" % missing)

    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='scrape_runs'"
    ).fetchone()
    if row:
        for status in REQUIRED_RUN_STATUSES:
            if "'%s'" % status not in row[0]:
                problems.append(
                    "scrape_runs CHECK does not accept status '%s'" % status
                )

    report = verify(conn)
    if report["integrity_check"] != "ok":
        problems.append("integrity_check: %s" % report["integrity_check"])
    if report["foreign_key_violations"]:
        problems.append(
            "%d foreign key violation(s)" % report["foreign_key_violations"]
        )
    for name, count in sorted(report["orphans"].items()):
        if count:
            problems.append("orphan check %s: %d" % (name, count))

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument(
        "--repair", action="store_true",
        help="apply pending migrations instead of failing. Only for a path that "
             "commits pla_watch.db AND can prove the repair is in the push.",
    )
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print("database not found: %s" % db_path, file=sys.stderr)
        return 2

    conn = connect(db_path)
    try:
        state = classify(conn)
        if not args.quiet:
            print("database state: %s" % state)

        if state != "fully_current":
            if not args.repair:
                print(
                    "FAIL: database is '%s', not fully current.\n"
                    "  The reconciler migrates its output before merging, so a "
                    "rebase should never produce this.\n"
                    "  Failing closed rather than pushing a regressed database. "
                    "Run: python -m migrations.cli --apply" % state,
                    file=sys.stderr,
                )
                return 1
            report = apply_all(conn)
            print("repaired: applied=%s already_present=%s"
                  % (report["applied"], report["already_present"]))

        problems = check(conn)
        if problems:
            print("FAIL: %d problem(s)" % len(problems), file=sys.stderr)
            for p in problems:
                print("  - %s" % p, file=sys.stderr)
            return 1

        if not args.quiet:
            print("OK: schema current, ledger complete, integrity and foreign "
                  "keys clean.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
