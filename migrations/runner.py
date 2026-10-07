"""
Migration framework.

Why this exists rather than one-off scripts
-------------------------------------------
`scripts/reconcile_db.py` resolves a diverged `pla_watch.db` by copying the
*published* side's file and then merging rows into it. That is correct for row
identity and wrong for schema: if origin's file predates a schema change, the
merged database silently comes back with the older shape, no conflict and no
warning. It has already happened once — the 2026-08-09 `'degraded'` migration
was reverted by a rebase and only found by hand (DECISION_LOG 2026-08-09 §7),
and Phase 0 found it reverted a second time.

The standing rule that came out of that ("re-apply and re-verify AFTER the final
rebase") is a human instruction, and this is the mechanism that stops it from
depending on anyone remembering. Two properties do the work:

  * **Every migration is idempotent and re-runnable.** Applying them to a
    database that already has the change is a no-op that records itself.
  * **Everything a migration creates is either DDL or reconstructible from
    tracked configuration.** Desk, institution and source metadata are synced
    from `desks/*/manifest.json`, so a reconcile that reverts the schema loses
    nothing that the next `apply()` cannot rebuild from git.

The one thing that is NOT reconstructible is observed data: `source_run_results`
rows written locally between a reconcile and the next push. That limitation is
real, is documented in docs/SCHEMA_AND_MIGRATIONS.md, and is a Phase 3 decision
(CI ordering), deliberately not papered over here.

Python 3.9 / stdlib only. This runs on the CI runner and inside the collection
path, so it must not pull in a dependency.
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import pkgutil
import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("migrations")

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_PACKAGE = "migrations.versions"

SCHEMA_MIGRATIONS_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now')),
    checksum    TEXT,
    note        TEXT
)
"""


class MigrationError(RuntimeError):
    """Raised when a migration fails. The transaction is already rolled back."""


class Migration:
    """One discovered migration module, normalized."""

    def __init__(self, module) -> None:
        self.module = module
        try:
            self.version: str = module.VERSION
            self.name: str = module.NAME
            self.up: Callable[[sqlite3.Connection], None] = module.up
        except AttributeError as exc:
            raise MigrationError(
                "%s is not a valid migration module (needs VERSION, NAME, up): %s"
                % (getattr(module, "__name__", module), exc)
            )
        # Optional predicate: "this change is already present in the database,
        # even though schema_migrations has no record of it." Needed because the
        # 'degraded' constraint was applied by hand before this framework
        # existed, and because a reverted-then-partially-restored database must
        # not be double-applied.
        self.is_already_applied: Optional[Callable[[sqlite3.Connection], bool]] = (
            getattr(module, "is_already_applied", None)
        )

    @property
    def checksum(self) -> str:
        source = Path(self.module.__file__).read_bytes()
        return hashlib.sha256(source).hexdigest()[:16]

    def __repr__(self) -> str:
        return "<Migration %s %s>" % (self.version, self.name)


def discover() -> List[Migration]:
    """Return every migration module, ordered by version string."""
    package = importlib.import_module(VERSIONS_PACKAGE)
    found: List[Migration] = []
    for mod_info in pkgutil.iter_modules(package.__path__):
        if mod_info.name.startswith("_"):
            continue
        module = importlib.import_module("%s.%s" % (VERSIONS_PACKAGE, mod_info.name))
        found.append(Migration(module))

    found.sort(key=lambda m: m.version)

    seen: Dict[str, str] = {}
    for m in found:
        if m.version in seen:
            raise MigrationError(
                "duplicate migration version %s (%s and %s)"
                % (m.version, seen[m.version], m.name)
            )
        seen[m.version] = m.name
    return found


def ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(SCHEMA_MIGRATIONS_DDL)


def applied_versions(conn: sqlite3.Connection) -> Dict[str, str]:
    ensure_migrations_table(conn)
    return {
        row[0]: row[1]
        for row in conn.execute("SELECT version, name FROM schema_migrations")
    }


def _record(conn: sqlite3.Connection, migration: Migration, note: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO schema_migrations (version, name, checksum, note) "
        "VALUES (?, ?, ?, ?)",
        (migration.version, migration.name, migration.checksum, note),
    )


def apply_all(
    conn: sqlite3.Connection,
    dry_run: bool = False,
    sync_config: bool = True,
) -> Dict[str, object]:
    """
    Apply every pending migration, then sync desk configuration.

    Each migration runs inside its own transaction: a failure rolls that
    migration back entirely and leaves `schema_migrations` without a record of
    it, so the next run retries from a consistent state. Earlier migrations that
    already committed are not rolled back — they are independent, versioned
    steps, not one giant transaction.

    Returns a report dict suitable for logging or a verification document.
    """
    report: Dict[str, object] = {
        "applied": [], "already_present": [], "skipped": [], "synced": None,
    }

    ensure_migrations_table(conn)
    done = applied_versions(conn)

    # SQLite cannot ALTER a CHECK constraint, so some migrations rebuild a table
    # (create-copy-drop-rename). The official "Making Other Kinds Of Table Schema
    # Changes" procedure requires foreign_keys OFF for that, and the pragma is a
    # no-op inside a transaction — so it has to be set out here, before BEGIN.
    # Safety is not lost: every migration runs `PRAGMA foreign_key_check` inside
    # its own transaction below and aborts if it introduced a violation.
    fk_was_on = bool(conn.execute("PRAGMA foreign_keys").fetchone()[0])
    if not dry_run:
        conn.execute("PRAGMA foreign_keys = OFF")

    try:
        for migration in discover():
            if migration.version in done:
                report["skipped"].append(migration.version)
                continue

            if dry_run:
                report["applied"].append(migration.version + " (dry-run)")
                continue

            pre_existing = False
            if migration.is_already_applied is not None:
                try:
                    pre_existing = bool(migration.is_already_applied(conn))
                except Exception as exc:
                    raise MigrationError(
                        "%s: is_already_applied() raised: %s"
                        % (migration.version, exc)
                    )

            try:
                conn.execute("BEGIN")
                if pre_existing:
                    # The change is in the database but predates this framework
                    # (or survived a partial revert). Record it, do not redo it.
                    _record(conn, migration, "detected as already applied")
                    conn.execute("COMMIT")
                    report["already_present"].append(migration.version)
                    logger.info("migration %s already present — recorded",
                                migration.version)
                    continue

                migration.up(conn)

                violations = conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise MigrationError(
                        "introduced %d foreign key violation(s): %r"
                        % (len(violations), violations[:3])
                    )

                _record(conn, migration, "applied")
                conn.execute("COMMIT")
                report["applied"].append(migration.version)
                logger.info("migration %s (%s) applied",
                            migration.version, migration.name)
            except Exception as exc:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise MigrationError(
                    "migration %s (%s) failed and was rolled back: %s"
                    % (migration.version, migration.name, exc)
                )
    finally:
        if fk_was_on:
            conn.execute("PRAGMA foreign_keys = ON")

    if sync_config and not dry_run:
        # Imported here, not at module scope: migrations must be importable in a
        # bare test harness that has no desk configuration on disk.
        from core.registry import sync_desk_config
        report["synced"] = sync_desk_config(conn)

    return report


def verify(conn: sqlite3.Connection) -> Dict[str, object]:
    """
    Post-migration verification: row counts, orphan checks, integrity.

    Read-only. Everything here is something a reviewer should be able to check
    themselves with one SQL statement.
    """
    def scalar(sql: str) -> int:
        try:
            return conn.execute(sql).fetchone()[0]
        except sqlite3.Error:
            return -1

    def table_exists(name: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None

    out: Dict[str, object] = {
        "counts": {
            "articles": scalar("SELECT COUNT(*) FROM articles"),
            "distinct_article_urls": scalar("SELECT COUNT(DISTINCT url) FROM articles"),
            "sources": scalar("SELECT COUNT(*) FROM sources"),
            "categories": scalar("SELECT COUNT(*) FROM categories"),
            "article_categories": scalar("SELECT COUNT(*) FROM article_categories"),
            "scrape_runs": scalar("SELECT COUNT(*) FROM scrape_runs"),
        },
        "max_article_id": scalar("SELECT IFNULL(MAX(id), 0) FROM articles"),
        "max_run_id": scalar("SELECT IFNULL(MAX(id), 0) FROM scrape_runs"),
    }

    for extra in ("desks", "institutions", "source_run_results", "schema_migrations"):
        out["counts"][extra] = (
            scalar("SELECT COUNT(*) FROM %s" % extra) if table_exists(extra) else None
        )

    orphans: Dict[str, int] = {
        "articles_without_source":
            scalar("SELECT COUNT(*) FROM articles a "
                   "LEFT JOIN sources s ON s.id = a.source_id WHERE s.id IS NULL"),
        "article_categories_without_article":
            scalar("SELECT COUNT(*) FROM article_categories ac "
                   "LEFT JOIN articles a ON a.id = ac.article_id WHERE a.id IS NULL"),
    }
    if table_exists("desks"):
        orphans["sources_without_desk"] = scalar(
            "SELECT COUNT(*) FROM sources s LEFT JOIN desks d "
            "ON d.desk_id = s.desk_id WHERE s.desk_id IS NOT NULL AND d.desk_id IS NULL"
        )
        orphans["sources_with_null_desk"] = scalar(
            "SELECT COUNT(*) FROM sources WHERE desk_id IS NULL"
        )
    if table_exists("institutions"):
        orphans["institutions_without_desk"] = scalar(
            "SELECT COUNT(*) FROM institutions i LEFT JOIN desks d "
            "ON d.desk_id = i.desk_id WHERE d.desk_id IS NULL"
        )
    out["orphans"] = orphans

    out["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
    out["foreign_key_violations"] = len(
        conn.execute("PRAGMA foreign_key_check").fetchall()
    )
    out["applied_migrations"] = sorted(applied_versions(conn).keys())
    out["ok"] = (
        out["integrity_check"] == "ok"
        and out["foreign_key_violations"] == 0
        and all(v == 0 for v in orphans.values())
    )
    return out


def connect(db_path) -> sqlite3.Connection:
    """
    Open a connection suitable for migrations.

    `isolation_level=None` turns off the driver's implicit transaction handling
    so the explicit BEGIN/COMMIT above are the only transactions in play —
    otherwise sqlite3 opens one for us and the DDL commit boundaries stop being
    the ones written here.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
