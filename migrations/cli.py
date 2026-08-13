#!/usr/bin/env python3
"""
Migration CLI.

    .venv/bin/python -m migrations.cli --status
    .venv/bin/python -m migrations.cli --apply
    .venv/bin/python -m migrations.cli --verify
    .venv/bin/python -m migrations.cli --apply --db /path/to/copy.db

Read-only by default: with no flags it prints status and exits 0 without
touching the database. Only `--apply` writes.

`--verify` exits non-zero when integrity, foreign keys or orphan checks fail, so
it is usable as a gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import DB_PATH                                       # noqa: E402
from migrations.runner import (                                  # noqa: E402
    apply_all, applied_versions, connect, discover, verify,
)


def cmd_status(conn) -> int:
    done = applied_versions(conn)
    print("Migrations — %s" % ("applied" if done else "none applied yet"))
    print("-" * 62)
    for m in discover():
        mark = "applied" if m.version in done else "PENDING"
        print("  %-6s %-34s %s" % (m.version, m.name, mark))
    print("-" * 62)
    pending = [m.version for m in discover() if m.version not in done]
    print("%d applied, %d pending" % (len(done), len(pending)))
    return 0


def cmd_apply(conn, dry_run: bool) -> int:
    report = apply_all(conn, dry_run=dry_run)
    print("applied            : %s" % (report["applied"] or "none"))
    print("already present    : %s" % (report["already_present"] or "none"))
    print("skipped (recorded) : %s" % (report["skipped"] or "none"))
    if report["synced"]:
        print("desk config synced : %s" % json.dumps(report["synced"]))
    if dry_run:
        print("\n--dry-run: nothing was written.")
    return 0


def cmd_verify(conn) -> int:
    report = verify(conn)
    print("Verification")
    print("-" * 62)
    for key, value in sorted(report["counts"].items()):
        print("  %-26s %s" % (key, "n/a" if value is None else value))
    print("  %-26s %s" % ("max_article_id", report["max_article_id"]))
    print("  %-26s %s" % ("integrity_check", report["integrity_check"]))
    print("  %-26s %s" % ("foreign_key_violations",
                          report["foreign_key_violations"]))
    print("  orphans:")
    for key, value in sorted(report["orphans"].items()):
        print("      %-22s %s" % (key, value))
    print("  applied: %s" % ", ".join(report["applied_migrations"]))
    print("-" * 62)
    print("RESULT: %s" % ("OK" if report["ok"] else "PROBLEMS FOUND"))
    return 0 if report["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--apply", action="store_true", help="apply pending migrations")
    ap.add_argument("--verify", action="store_true", help="run verification checks")
    ap.add_argument("--status", action="store_true", help="list migration state")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --apply, report without writing")
    args = ap.parse_args()

    if not Path(args.db).exists():
        print("database not found: %s" % args.db, file=sys.stderr)
        return 2

    conn = connect(args.db)
    try:
        if args.apply:
            return cmd_apply(conn, args.dry_run)
        if args.verify:
            return cmd_verify(conn)
        return cmd_status(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
