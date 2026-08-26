"""
A logical no-op must be a byte-level no-op.

`test_migrations.py` already proves the migration runner is idempotent by
LOGICAL fingerprint: run it twice, the data is the same. That is necessary and
it is not sufficient, and the gap is exactly the class of defect this project
has been bitten by before.

The failure a fingerprint cannot see is an unconditional
`INSERT ... ON CONFLICT DO UPDATE` that writes the values already stored. Every
logical check passes — same rows, same values, same fingerprint — while the
file on disk changes. In a repository that TRACKS its database, that produces a
database diff on a morning when nothing was collected: a commit asserting the
corpus moved when it did not.

Whether it changes the file turns out to depend on the journal mode, which is
exactly why relying on the pager is not a plan:

  * In WAL mode — production's mode — SQLite is forgiving. Rewriting a row with
    the values it already holds leaves the page image identical, no page is
    dirtied, and the header change counter does not advance. The hazard is
    latent rather than absent.
  * In rollback-journal mode, the same no-op write DOES advance the change
    counter and the file moves.

`sync_desk_config()` was unconditional, and `apply_all()` calls it. It now
compares before writing, so the property holds by construction in either mode
rather than by pager luck — and the tests below assert it in BOTH, because a
guard that only holds in the mode you happen to run is not a guard.

Mutation-proved: removing the `_unchanged` guard from `_sync_one_desk` fails
`test_a_no_op_sync_is_byte_stable_under_a_rollback_journal` and
`test_a_second_config_sync_changes_no_bytes`, while every logical assertion in
`test_migrations.py` keeps passing.

Everything here runs against a disposable copy. The tracked database is read,
hashed and asserted about; it is never opened for writing.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.registry import sync_desk_config                       # noqa: E402
from migrations.runner import apply_all, discover                # noqa: E402

TRACKED_DB = REPO_ROOT / "pla_watch.db"
SIDECAR_SUFFIXES = ("-wal", "-shm")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checkpoint(path: Path) -> None:  # noqa: D401
    """
    Fold the write-ahead log into the main file before measuring it.

    Without this the tests would be weaker than they look. In WAL mode a commit
    lands in `-wal` and does not touch the main database until a checkpoint, so
    an unconditional upsert can rewrite every row while the main file's bytes
    sit still — right up until the checkpoint that the commit step performs
    anyway. Measuring the checkpointed file is measuring what actually gets
    committed to the repository.
    """
    conn = sqlite3.connect(str(path))
    try:
        if conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal":
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def sidecars(path: Path):
    return [Path(str(path) + suffix) for suffix in SIDECAR_SUFFIXES]


class ByteStabilityCase(unittest.TestCase):
    """Each test gets its own copy of the tracked database."""

    @classmethod
    def setUpClass(cls):
        if not TRACKED_DB.exists():
            raise unittest.SkipTest("production database not present")

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="byte-stability-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = self.tmp / "copy.db"
        shutil.copy(TRACKED_DB, self.db)
        # A pristine copy of the tracked file carries no sidecar, which is what
        # makes "did this run leave one" answerable at all.
        self.assertEqual(self.stray_sidecars(), [])

    def stray_sidecars(self):
        return [p for p in sidecars(self.db) if p.exists()]

    def clear_sidecars(self):
        for path in self.stray_sidecars():
            path.unlink()

    def open(self):
        """
        Open exactly as the daily workflow does — no journal-mode coercion.

        Forcing `journal_mode=DELETE` would make these tests measure a
        configuration the pipeline never uses. The copy is WAL, as production
        is, and the assertions below have to hold there.
        """
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def run_migrations(self):
        conn = self.open()
        try:
            return apply_all(conn)
        finally:
            conn.commit()
            conn.close()
            checkpoint(self.db)

    def run_config_sync(self):
        conn = self.open()
        try:
            return sync_desk_config(conn)
        finally:
            conn.commit()
            conn.close()
            checkpoint(self.db)


class TestMigrationsAreByteStable(ByteStabilityCase):

    def test_the_tracked_database_reaches_full_currency_in_one_pass(self):
        """
        The premise of every test below, stated so a pending migration does not
        break it.

        The tracked database is normally fully migrated, and between a
        migration merging and the first production run that applies it, it is
        legitimately behind by exactly that migration. Asserting "nothing to
        apply" would fail for the whole of that window and would push whoever
        hit it toward migrating the tracked file — which is the one thing this
        repository must not do casually.

        What actually has to hold is weaker and more useful: one pass brings it
        current, and a second pass then finds nothing left. Everything below
        runs its own pass first, so they measure an already-current database
        either way.
        """
        first = self.run_migrations()
        second = self.run_migrations()

        self.assertEqual(
            second["applied"], [],
            "a second pass still had migrations to apply: %s"
            % second["applied"])
        self.assertEqual(sorted(second["skipped"]),
                         sorted(m.version for m in discover()))

        if first["applied"]:
            # Visible, not silent. A pending migration is a fact about the
            # working tree that a reader of this suite should see named.
            print("\n    tracked database was behind by: %s"
                  % ", ".join(first["applied"]))

    def test_a_second_migration_run_changes_no_bytes(self):
        self.run_migrations()
        before = digest(self.db)
        self.run_migrations()
        self.assertEqual(digest(self.db), before,
                         "a no-op migration run rewrote the database")

    def test_a_second_config_sync_changes_no_bytes(self):
        """
        The specific hazard. `sync_desk_config()` covers one desk, four
        institutions and five sources on every run; if any of those writes
        unconditionally, the file moves while the data does not.
        """
        self.run_config_sync()
        before = digest(self.db)
        report = self.run_config_sync()
        self.assertEqual(digest(self.db), before,
                         "a no-op config sync rewrote the database")
        # Nothing written, and everything checked. Silence would be a different
        # defect: a sync that examined nothing also writes nothing.
        self.assertEqual(report["desks"], 0)
        self.assertEqual(report["institutions"], 0)
        self.assertEqual(report["sources_updated"], 0)
        self.assertEqual(report["sources_inserted"], 0)
        self.assertGreater(report["desks_unchanged"], 0)
        self.assertGreater(report["institutions_unchanged"], 0)
        self.assertGreater(report["sources_unchanged"], 0)

    def test_ten_consecutive_no_op_runs_are_byte_stable(self):
        """
        Once is luck. The daily workflow runs migrations on every collection,
        so the property has to hold repeatedly or the tracked file drifts a
        little every morning.
        """
        self.run_migrations()
        self.run_config_sync()
        before = digest(self.db)
        for attempt in range(10):
            self.run_migrations()
            self.run_config_sync()
            with self.subTest(attempt=attempt):
                self.assertEqual(digest(self.db), before)

    def test_the_change_counter_does_not_advance_on_a_no_op(self):
        """
        The mechanism, asserted directly. Bytes 24-27 of the header are
        SQLite's file change counter, and it is what a byte comparison is
        really watching.
        """
        self.run_migrations()
        before = int.from_bytes(self.db.read_bytes()[24:28], "big")
        self.run_migrations()
        self.run_config_sync()
        self.assertEqual(int.from_bytes(self.db.read_bytes()[24:28], "big"),
                         before)

    def test_a_real_change_does_move_the_bytes(self):
        """
        The control. If the comparison could not detect a genuine write, every
        assertion above would pass vacuously.
        """
        self.run_migrations()
        before = digest(self.db)
        conn = self.open()
        conn.execute(
            "UPDATE sources SET notes = COALESCE(notes,'') || ' x' "
            "WHERE slug = 'pla_daily'")
        conn.commit()
        conn.close()
        checkpoint(self.db)
        self.assertNotEqual(digest(self.db), before)

    def test_a_changed_manifest_value_is_still_written(self):
        """
        The other control, and the one that matters more: the guard must skip
        writes, not skip work. A source whose stored metadata drifts from the
        manifest has to be corrected.
        """
        self.run_config_sync()
        conn = self.open()
        conn.execute("UPDATE sources SET authority_tier = 'D' "
                     "WHERE slug = 'pla_daily'")
        conn.commit()
        conn.close()
        checkpoint(self.db)
        report = self.run_config_sync()
        self.assertEqual(report["sources_updated"], 1)
        conn = self.open()
        tier = conn.execute("SELECT authority_tier FROM sources "
                            "WHERE slug = 'pla_daily'").fetchone()[0]
        conn.close()
        self.assertEqual(tier, "B")


class TestByteStabilityUnderARollbackJournal(ByteStabilityCase):
    """
    The same property, in the journal mode where the hazard actually bites.

    Production runs WAL, where a no-op write happens to leave the page image
    untouched. That is a property of the pager, not of our code, and it is not
    something to build a guarantee on: any tool that opens the database with a
    rollback journal — a manual `sqlite3` session, a backup script, a future
    change of `journal_mode` — gets the other behaviour. If the guard in
    `sync_desk_config()` is ever removed, this is the test that says so.
    """

    def setUp(self):
        super().setUp()
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.commit()
        conn.close()
        # Converting out of WAL leaves a `-shm` behind. It carries nothing
        # once the journal mode has changed, and removing it here is what makes
        # the byte comparisons below about the database rather than about the
        # conversion that set them up.
        self.clear_sidecars()

    def open(self):
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def test_the_copy_really_is_using_a_rollback_journal(self):
        conn = sqlite3.connect(str(self.db))
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(mode, "delete")

    def test_a_no_op_sync_is_byte_stable_under_a_rollback_journal(self):
        self.run_config_sync()
        before = digest(self.db)
        self.run_config_sync()
        self.assertEqual(
            digest(self.db), before,
            "a no-op config sync rewrote the database under a rollback "
            "journal — the upsert guard has been removed")

    def test_a_no_op_migration_is_byte_stable_under_a_rollback_journal(self):
        self.run_migrations()
        self.run_config_sync()
        before = digest(self.db)
        for attempt in range(5):
            self.run_migrations()
            self.run_config_sync()
            with self.subTest(attempt=attempt):
                self.assertEqual(digest(self.db), before)

    def test_a_real_change_still_moves_the_bytes_here_too(self):
        self.run_config_sync()
        before = digest(self.db)
        conn = self.open()
        conn.execute("UPDATE sources SET authority_tier = 'D' "
                     "WHERE slug = 'pla_daily'")
        conn.commit()
        conn.close()
        self.assertNotEqual(digest(self.db), before)


class TestSidecarsCarryNoUnwrittenData(ByteStabilityCase):
    """
    The run-475 defect, one level down.

    A WAL-mode open leaves `-wal` and `-shm` beside the database and they
    survive a clean close — that is current, documented behaviour of the
    read-write path, and asserting they never appear would be asserting
    something false. What must be true is that they hold nothing the main file
    does not: a `-wal` carrying uncommitted pages means the tracked file alone
    is not the database, and a commit of it would publish a partial corpus.
    """

    def test_the_main_file_alone_is_a_complete_database_after_a_run(self):
        self.run_migrations()
        self.run_config_sync()
        alone = self.tmp / "alone.db"
        shutil.copy(self.db, alone)          # main file only, no sidecars
        conn = sqlite3.connect(str(alone))
        try:
            self.assertEqual(
                conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertGreater(
                conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM desks").fetchone()[0], 1)
        finally:
            conn.close()

    def test_the_tracked_database_gains_no_sidecar_from_this_suite(self):
        for sidecar in sidecars(TRACKED_DB):
            with self.subTest(sidecar=sidecar.suffix):
                self.assertFalse(sidecar.exists())


class TestTheTrackedDatabaseIsNeverWritten(ByteStabilityCase):

    def test_running_everything_leaves_the_tracked_file_untouched(self):
        before = digest(TRACKED_DB)
        self.run_migrations()
        self.run_config_sync()
        self.assertEqual(digest(TRACKED_DB), before,
                         "the tracked database was modified")


if __name__ == "__main__":
    unittest.main()
