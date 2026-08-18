"""
One-shot cleanup for syndicated reposts that slipped into the DB before
title-based dedup existed.

Groups articles by Chinese-title hash, keeps the canonical copy from each
group, deletes the rest.

Ranking is NOT defined here. It comes from
`processing.dedup.canonical_sort_key`, the same function the pipeline uses to
decide which copy to store. That sharing is load-bearing: until 2026-08-17
this script ranked by `source_priority(url)` alone, so once the pipeline
started preferring the Tier A ministry copy, an unchanged cleanup would have
scored a MOD China URL at 50 against PLA Daily's 要闻 at 100 and deleted
exactly the copy the pipeline had chosen to keep.

Because this deletes rows it fails closed. Any group containing a row whose
source identity cannot be resolved at all is refused outright — an empty
identity is the absence of an answer, never evidence that two rows share a
source — as is any group whose identities differ and include an ungoverned one.
A group in which every row carries the same explicit slug stays rankable even
if that source is not yet in the tier table.

`--dry-run` reads through `reconcile_db.read_only()`, which copies the database
and its sidecars to scratch and reads the copy, so a dry run cannot check-point
a WAL input or leave sidecars beside it. `--apply` opens the database directly,
because it is meant to write.

Usage:
    python scripts/cleanup_duplicates.py --dry-run
    python scripts/cleanup_duplicates.py --apply
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# Allow running from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from processing.dedup import (
    canonical_sort_key,
    rank_canonical,
    title_hash,
    unresolved_authority,
)
from scripts.reconcile_db import read_only


def find_duplicate_groups(conn: sqlite3.Connection) -> list[list[sqlite3.Row]]:
    """
    Return groups (lists of >1 row) sharing the same normalized title hash.

    The source slug is joined in rather than inferred from the URL: canonical
    ranking is an authority judgement about the *source*, and the database
    already records which source each article came from. LEFT JOIN so an
    article with a dangling or missing source still appears — it must reach the
    fail-closed guard, not vanish from the report.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT a.id, a.url, a.title_original, s.slug AS source_slug "
        "FROM articles a "
        "LEFT JOIN sources s ON a.source_id = s.id "
        "WHERE a.title_original IS NOT NULL AND a.title_original != ''"
    ).fetchall()

    groups: dict[str, list[sqlite3.Row]] = {}
    for r in rows:
        h = title_hash(r["title_original"])
        if not h:
            continue
        groups.setdefault(h, []).append(r)

    return [g for g in groups.values() if len(g) > 1]


def rank_group(group: list[sqlite3.Row]) -> list[sqlite3.Row]:
    """Sort so the winner is first, using the shared canonical key."""
    return rank_canonical(group)


def _describe(row: sqlite3.Row) -> str:
    """
    The complete ranking key, every component, in precedence order.

    Printing a subset would misreport why a row won: the first three components
    tie on most real duplicate groups, so the decision is usually made by the
    last two.
    """
    auth, slug, section, neg_len, url = canonical_sort_key(row)
    return (
        "key=(auth=%-3d identity=%-17s section=%-3d urllen=%-3d url=%s)"
        % (auth, slug or "<unresolved>", section, -neg_len, url)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="pla_watch.db",
                        help="Path to SQLite DB (default: pla_watch.db)")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true",
                      help="Report only; do not delete")
    mode.add_argument("--apply", action="store_true",
                      help="Delete duplicate rows")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}", file=sys.stderr)
        return 2

    if args.dry_run:
        # A dry run must be incapable of touching its input, not merely
        # uninterested in doing so. A plain sqlite3.connect() writes to a
        # database just by opening it when there is WAL state to recover, and
        # every database this project produces is in WAL mode — so the old
        # dry-run path could check-point the tracked database, or leave -wal and
        # -shm files beside it, while reporting that it changed nothing.
        # read_only() copies the database and any sidecars to a scratch
        # directory and reads the copy, so every such effect lands on the copy.
        with read_only(db_path) as conn:
            return _report(conn, apply=False)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")  # honor ON DELETE CASCADE
    try:
        return _report(conn, apply=True)
    finally:
        conn.close()


def _report(conn: sqlite3.Connection, apply: bool) -> int:
    """Rank every duplicate group and, when applying, delete the losers."""
    groups = find_duplicate_groups(conn)

    if not groups:
        print("No duplicate title groups found. Nothing to do.")
        return 0

    print(f"Found {len(groups)} duplicate title group(s):\n")
    to_delete: list[int] = []
    refused = 0

    for i, grp in enumerate(groups):
        reason = unresolved_authority(grp)
        if reason is not None:
            refused += 1
            print(f"── Group {i+1} ── REFUSED")
            print(f"  {reason}")
            print("  No row in this group will be deleted. Resolve the "
                  "source identity, then re-run.")
            for r in grp:
                print(f"  SKIP  id={r['id']:<5} {_describe(r)}")
                print(f"        url={r['url']}")
            print()
            continue

        g = rank_group(grp)
        keeper, losers = g[0], g[1:]
        print(f"── Group {i+1} ──")
        print(f"  KEEP  id={keeper['id']:<5} {_describe(keeper)}")
        print(f"        url={keeper['url']}")
        print(f"        title={keeper['title_original']}")
        for r in losers:
            print(f"  DROP  id={r['id']:<5} {_describe(r)}")
            print(f"        url={r['url']}")
            print(f"        title={r['title_original']}")
            to_delete.append(r["id"])
        print()

    print(f"Summary: {len(to_delete)} row(s) would be deleted; "
          f"{refused} group(s) refused as unresolved.")

    if not apply:
        print("Dry run — no changes made "
              "(read through a scratch copy; the input was never opened "
              "for writing).")
        return 0

    # Apply
    # article_categories has ON DELETE CASCADE on article_id, so a
    # single DELETE on articles suffices.
    conn.executemany(
        "DELETE FROM articles WHERE id = ?",
        [(aid,) for aid in to_delete],
    )
    conn.commit()
    print(f"Deleted {len(to_delete)} row(s).")
    if refused:
        print(f"{refused} group(s) left untouched pending source "
              f"identity resolution.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
