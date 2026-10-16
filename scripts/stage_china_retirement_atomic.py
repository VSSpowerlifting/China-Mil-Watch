"""Atomic URL tombstoning plus physical deletion on a disposable SQLite copy.

This deliberately has no command-line interface and will refuse to operate on
any database in the Git checkout. The caller must create a separately named,
verified scratch copy and supply the exact frozen retirement planner output.
Production replacement, backups and public rendering are different phases.
"""
from datetime import date
from hashlib import sha256
from pathlib import Path
import sqlite3

from core.retired_article_urls import (
    has_retired_table, url_sha256, verify_no_active_retired_urls,
)

ROOT = Path(__file__).resolve().parents[1]
CHINA_SOURCES = frozenset({
    "pla_daily", "mod_china", "china_mil_online", "xinhua_mil",
    "global_times_mil",
})


def rehearse_on_new_scratch_copy(source_db, scratch_db, plan_data, retired_at,
                                 *, minimum_retire=4300, maximum_retire=4500):
    """Read source without touching its WAL and retire in a NEW outside-repo DB.

    Source bytes are never modified, copied database is never placed in the
    checkout, and no live output changes. The caller must still independently
    verify backup restoration and render a complete new site before release.
    """
    from scripts.reconcile_db import read_only

    source_db = Path(source_db).resolve(strict=True)
    scratch_db = Path(scratch_db)
    if not scratch_db.is_absolute() or scratch_db.exists():
        raise ValueError("scratch destination must be a new absolute path")
    if (not scratch_db.parent.is_dir() or scratch_db.parent.is_symlink()):
        raise ValueError("scratch directory must exist and not be a symlink")
    scratch_db = scratch_db.resolve()
    if (scratch_db == ROOT or ROOT in scratch_db.parents
            or scratch_db == source_db):
        raise ValueError("scratch copy cannot be inside repository or source")
    if any(Path(str(scratch_db) + suffix).exists()
           for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("scratch SQLite journal path is already occupied")

    with read_only(source_db) as original:
        # The production database may legitimately predate migration 0009.
        # Migrate only the disposable copy. SQLite's migration runner owns
        # explicit BEGIN/COMMIT, so open in autocommit mode.
        target = sqlite3.connect(str(scratch_db), isolation_level=None)
        try:
            original.backup(target)
            target.execute("PRAGMA journal_mode=DELETE")
            if not has_retired_table(target):
                from migrations.runner import apply_all
                apply_all(target, sync_config=False)
            target.execute("PRAGMA foreign_keys=ON")
            result = stage_atomic_retirement(
                target, plan_data, retired_at, minimum_retire=minimum_retire,
                maximum_retire=maximum_retire)
        except BaseException:
            target.close()
            scratch_db.unlink(missing_ok=True)
            for suffix in ("-wal", "-shm", "-journal"):
                Path(str(scratch_db) + suffix).unlink(missing_ok=True)
            raise
        else:
            target.close()
    return dict(result, scratch_db=str(scratch_db),
                original_db_unchanged=True)


def _checked_scratch_connection(conn):
    files = [r[2] for r in conn.execute("PRAGMA database_list")
             if r[1] == "main"]
    if len(files) != 1:
        raise ValueError("scratch main database unresolved")
    if files[0]:
        destination = Path(files[0]).resolve()
        if destination == ROOT or ROOT in destination.parents:
            raise ValueError("production repository database is forbidden")
    if conn.in_transaction:
        raise ValueError("caller has an active transaction")
    if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise ValueError("foreign keys must be enabled before retirement")
    if not has_retired_table(conn):
        raise ValueError("retirement migration is missing")
    # The current migration needs BOTH the hash ledger and ID trigger.
    verify_no_active_retired_urls(conn)


def _dependent_cascade_check(conn):
    for (table,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'"
    ):
        ident = table.replace('"', '""')
        for fk in conn.execute('PRAGMA foreign_key_list("%s")' % ident):
            if fk[2] == "articles" and fk[6].upper() != "CASCADE":
                raise ValueError("unsafe foreign-key dependency: " + table)


def stage_atomic_retirement(conn, plan_data, retired_at, *,
                            minimum_retire=4300, maximum_retire=4500):
    """Commit the exact deletion and its tombstones together on scratch ONLY.

    Expected planner fields: retired_ids, kept_ids, total_before, total_after,
    retirement_id_sha256. Fail closed for duplicates, stale DB, non-China
    sources, foreign-key hazards, citation holds and inconsistent IDs.
    """
    _checked_scratch_connection(conn)
    _dependent_cascade_check(conn)
    try:
        date.fromisoformat(retired_at)
    except (TypeError, ValueError) as exc:
        raise ValueError("retirement date must be YYYY-MM-DD") from exc
    if type(minimum_retire) is not int or type(maximum_retire) is not int:
        raise ValueError("retirement bounds must be integers")
    retired = tuple(plan_data["retired_ids"])
    kept = tuple(plan_data["kept_ids"])
    if (any(type(i) is not int or i <= 0 for i in retired + kept)
            or len(retired) != len(set(retired))
            or len(kept) != len(set(kept))
            or set(retired) & set(kept)):
        raise ValueError("retired and protected identities overlap or repeat")
    if not minimum_retire <= len(retired) <= maximum_retire:
        raise ValueError("outside approved China retirement range")
    fingerprint = sha256(",".join(map(str, sorted(retired))).encode()).hexdigest()
    if fingerprint != plan_data["retirement_id_sha256"]:
        raise ValueError("retirement selection fingerprint changed")
    if plan_data["total_before"] != len(retired) + len(kept):
        raise ValueError("reviewed corpus is internally inconsistent")
    if plan_data["total_after"] != len(kept):
        raise ValueError("reviewed retained count is inconsistent")

    conn.execute("BEGIN IMMEDIATE")
    try:
        if conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] != plan_data["total_before"]:
            raise ValueError("database advanced after review")
        current = {r[0] for r in conn.execute("SELECT id FROM articles")}
        if current != set(retired) | set(kept):
            raise ValueError("database identities differ from reviewed selection")
        selected_rows = []
        for start in range(0, len(retired), 400):
            chunk = retired[start:start + 400]
            sql = ("SELECT a.id, a.url, s.slug FROM articles a "
                   "JOIN sources s ON s.id=a.source_id "
                   "WHERE a.id IN (%s)" % ",".join("?" for _ in chunk))
            selected_rows.extend(conn.execute(sql, chunk))
        if len(selected_rows) != len(retired):
            raise ValueError("retired rows cannot all be attributed")
        if any(slug not in CHINA_SOURCES for _, _, slug in selected_rows):
            raise ValueError("non-China record targeted for retirement")
        if any(not isinstance(url, str) or not url for _, url, _ in selected_rows):
            raise ValueError("invalid stored canonical URL")
        hashes = [url_sha256(url) for _, url, _ in selected_rows]
        if len(hashes) != len(set(hashes)):
            raise ValueError("duplicate stored canonical URL")

        before_ledger = conn.execute(
            "SELECT COUNT(*) FROM retired_article_urls").fetchone()[0]
        conn.executemany(
            "INSERT INTO retired_article_urls "
            "(url_sha256, original_article_id, source_slug, retired_at, selection_sha256) "
            "VALUES (?, ?, ?, ?, ?)",
            [(url_sha256(url), ident, slug, retired_at, fingerprint)
             for ident, url, slug in selected_rows],
        )
        for start in range(0, len(retired), 400):
            chunk = retired[start:start + 400]
            conn.execute("DELETE FROM articles WHERE id IN (%s)" %
                         ",".join("?" for _ in chunk), chunk)
        remaining = {r[0] for r in conn.execute("SELECT id FROM articles")}
        if remaining != set(kept):
            raise ValueError("retained article identities changed")
        after_ledger = verify_no_active_retired_urls(conn)
        if after_ledger != before_ledger + len(retired):
            raise ValueError("retirement ledger and deletion are not one-to-one")
        if conn.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("foreign-key integrity changed")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity verification failed")
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
        return {
            "retired": len(retired),
            "retained": len(kept),
            "ledger_added": len(retired),
            "retirement_id_sha256": fingerprint,
            "scratch_only": True,
        }
