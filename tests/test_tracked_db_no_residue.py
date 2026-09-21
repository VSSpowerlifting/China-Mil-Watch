"""
A read-only tool must be read-only on the file system too.

The defect (measured 2026-09-21). `scripts/verify_db_current.py` is documented
"Read-only by default" and `scripts/source_health_report.py` says "Read-only.
Performs no network I/O and no model calls, so it is safe to run anywhere and
cheap to run often." Both opened the tracked database with a plain
`sqlite3.connect()`. On a WAL database that creates `-wal` and `-shm` beside
the file, and — measured, not assumed — `close()` does **not** remove them.
They outlive the process.

The consequence was not theoretical. Running either script in a checkout and
then running the test suite produced six failures, every time, in the four
modules that assert no sidecar sits beside the tracked database. They looked
like an intermittent race for as long as nobody noticed which command had been
run first. The suite was right and the scripts were wrong.

`scripts.reconcile_db.read_only()` already exists for exactly this, and its
docstring already describes this failure mode (DECISION_LOG 2026-08-17). These
two callers simply were not using it.

Offline: no network, no model calls. Each script runs as a subprocess so the
check is on the real command line, not on an import.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKED = REPO_ROOT / "pla_watch.db"
SIDECARS = ("-wal", "-shm")

#: Every tool that claims to read the tracked database without changing it.
#: A new one belongs here on the day it is written, not after it has left
#: residue in somebody's checkout.
READ_ONLY_COMMANDS = (
    ("verify_db_current", ["scripts/verify_db_current.py", "--quiet"]),
    ("source_health_report", ["scripts/source_health_report.py"]),
    ("check_source_liveness", ["scripts/check_source_liveness.py"]),
)


def sidecars_present():
    return [s for s in SIDECARS if (REPO_ROOT / (TRACKED.name + s)).exists()]


class ReadOnlyToolsLeaveNothingBehind(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not TRACKED.exists():
            raise unittest.SkipTest("tracked database not present")
        if sidecars_present():
            raise unittest.SkipTest(
                "a sidecar already sits beside the tracked database, so this "
                "test cannot attribute one: %s" % sidecars_present())
        cls.before = hashlib.sha256(TRACKED.read_bytes()).hexdigest()

    def setUp(self):
        # Whatever this test provokes, it removes. setUpClass has already
        # established that nothing was there to begin with, so anything found
        # afterwards was created here and deleting it restores the checkout
        # rather than destroying someone else's state.
        self.addCleanup(self.sweep)

    @staticmethod
    def sweep():
        for s in SIDECARS:
            path = REPO_ROOT / (TRACKED.name + s)
            if path.exists():
                path.unlink()

    def run_script(self, argv):
        return subprocess.run([sys.executable, *argv], cwd=str(REPO_ROOT),
                              capture_output=True, text=True, timeout=600)

    def test_no_read_only_tool_creates_a_sidecar(self):
        for name, argv in READ_ONLY_COMMANDS:
            with self.subTest(tool=name):
                # Blame only what this tool created. Without the sweep the
                # second tool inherits the first one's residue and the failure
                # names the wrong script.
                self.sweep()
                proc = self.run_script(argv)
                self.assertEqual(
                    0, proc.returncode,
                    "%s exited %d:\n%s" % (name, proc.returncode,
                                           proc.stderr[-2000:]))
                left = sidecars_present()
                self.assertEqual(
                    [], left,
                    "%s left %s beside the tracked database. Read it through "
                    "scripts.reconcile_db.read_only(), which copies."
                    % (name, left))

    def test_no_read_only_tool_changes_the_database(self):
        for name, argv in READ_ONLY_COMMANDS:
            with self.subTest(tool=name):
                self.sweep()
                self.run_script(argv)
                self.assertEqual(
                    self.before,
                    hashlib.sha256(TRACKED.read_bytes()).hexdigest(),
                    "%s changed the tracked database" % name)


class TheMechanismIsWhatWeThinkItIs(unittest.TestCase):
    """Pins *why*, on a throwaway copy — never on the tracked file."""

    def setUp(self):
        if not TRACKED.exists():
            self.skipTest("tracked database not present")
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = self.tmp / "copy.db"
        shutil.copy(TRACKED, self.db)

    def sides(self):
        return [s for s in SIDECARS if (self.tmp / (self.db.name + s)).exists()]

    def test_the_database_really_is_in_wal_mode(self):
        """Bytes 18 and 19 of the header are the write and read versions;
        2 means WAL. If this ever stops being true the rest is moot."""
        with open(self.db, "rb") as fh:
            header = fh.read(20)
        self.assertEqual(2, header[18])
        self.assertEqual(2, header[19])

    def test_a_plain_connect_and_read_creates_the_sidecars(self):
        """The portable half of the premise. A plain read of a WAL database
        writes two files next to it, everywhere, on every build."""
        con = sqlite3.connect(str(self.db))
        self.addCleanup(con.close)
        con.execute("SELECT count(*) FROM articles").fetchone()
        self.assertEqual(sorted(SIDECARS), sorted(self.sides()),
                         "a plain read did not create the sidecars, so the "
                         "premise of the fix has changed")

    def test_whether_close_removes_them_is_a_property_of_the_build(self):
        """Not portable, and the reason the fix is not 'just close it'.

        SQLite deletes the -wal and -shm when the last connection closes
        cleanly — on the Linux CI runner it does. On the macOS builds this
        project is developed against they survive the close and the process,
        and that residue is what fails six assertions in the next suite run
        in that checkout.

        So this pins the two legitimate outcomes and rejects a third: a
        half-state, one sidecar without the other, would mean something
        stranger than a missed cleanup. Either way the database itself must
        come back byte-identical, because this was only ever a read."""
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        con = sqlite3.connect(str(self.db))
        con.execute("SELECT count(*) FROM articles").fetchone()
        con.close()
        left = sorted(self.sides())
        self.assertIn(left, ([], sorted(SIDECARS)),
                      "close() left %s — half a sidecar pair is neither "
                      "cleanup nor residue" % (left,))
        self.assertEqual(before,
                         hashlib.sha256(self.db.read_bytes()).hexdigest(),
                         "a read changed the database")

    def test_the_read_only_helper_creates_nothing(self):
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.reconcile_db import read_only
        with read_only(self.db) as con:
            con.execute("SELECT count(*) FROM articles").fetchone()
        self.assertEqual([], self.sides())


if __name__ == "__main__":
    unittest.main()
