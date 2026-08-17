"""
Reading the tracked database must work on a fresh clone, on any platform.

The tracked database is WAL-mode, and a fresh `git clone` has no `-wal`/`-shm`
beside it because the sidecars are gitignored. What a direct
`file:…?mode=ro` URI does in that state is **not fixed**: it depends on the
SQLite build, the VFS and the filesystem. SQLite's rule since 3.22.0 is that a
read-only WAL database can be opened when the `-wal`/`-shm` files already
exist, when they *can be created*, or when the database is immutable
(https://www.sqlite.org/wal.html#read_only_databases).

So the same call can go either way. Where the directory is not writable or the
required WAL state cannot be established, it fails — that is what broke both
consumers here:

  * `check_source_liveness.py` raised an unhandled `OperationalError`. It is the
    last step of the daily workflow.
  * `validate_output.py` caught the error and downgraded it to a warning, so
    check 8 — the analyzed-but-unrendered gate, added because output once lagged
    the database by 117 articles across four deploys — silently did not run.

Where the directory *is* writable, SQLite may create and use the sidecars and
open perfectly well — which is why the daily workflow never showed either
failure, and why asserting a specific `OperationalError` is asserting a
property of one machine rather than of this project.

The contract this project actually needs is stronger than "it opens": reads of
the tracked database must be reliable everywhere, must not mutate it, and must
leave no sidecar residue in its directory. Direct `mode=ro` guarantees none of
those. `reconcile_db.read_only` does, by copying the database and any sidecars
to a scratch directory and reading the copy, so every recovery and sidecar
effect lands there instead.

These tests therefore pin what the project controls — that the governed
consumers go through the helper, and that the helper behaves — using a
sidecar-less copy in a temporary directory. Nothing here touches the tracked
database.
"""

from __future__ import annotations

import ast
import hashlib
import shutil
import sqlite3
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.reconcile_db import read_only                        # noqa: E402

TRACKED = REPO_ROOT / "pla_watch.db"


def sidecars(db: Path):
    return sorted(p.name for p in db.parent.glob(db.name + "-*"))


class FreshCloneCase(unittest.TestCase):
    """A copy of the tracked database with no -wal/-shm beside it."""

    def setUp(self):
        if not TRACKED.exists():
            self.skipTest("production database not present")
        self.tmp = Path(tempfile.mkdtemp(prefix="freshclone-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db = self.tmp / "pla_watch.db"
        shutil.copyfile(TRACKED, self.db)          # deliberately no sidecars
        self.assertEqual(sidecars(self.db), [],
                         "fixture must start with no sidecars")

    def digest(self):
        return hashlib.sha256(self.db.read_bytes()).hexdigest()


class TestTheTrackedDatabaseIsStillWalMode(FreshCloneCase):
    """The premise the rest of this module rests on."""

    def test_the_tracked_database_really_is_wal_mode(self):
        header = self.db.read_bytes()[:100]
        self.assertEqual((header[18], header[19]), (2, 2),
                         "write/read version 2 == WAL; if this ever changes, "
                         "the reasoning below needs revisiting")


class TestGovernedConsumersReadThroughTheHelper(unittest.TestCase):
    """
    The contract the project controls, in place of one platform's error.

    Whether a direct `mode=ro` open succeeds is a property of SQLite, the VFS
    and the filesystem — it can fail, or it can create the sidecars and work.
    Neither outcome is something this project can assert on every machine, and
    a test that accepted both would assert nothing at all.

    What *is* ours to guarantee is the call site: the two scripts a human runs
    against the tracked database must go through `reconcile_db.read_only`, and
    must not open it directly. That holds identically everywhere.

    Structural, not textual: the module is parsed with `ast`, so the corrected
    explanations in those files' own comments cannot satisfy the guard, and an
    aliased import cannot evade it. The alias resolution is the scanner already
    governed by `tests/test_workflow_failure_paths.py`, which carries its own
    fixtures for every import spelling it claims to cover.
    """

    CONSUMERS = ("scripts/validate_output.py",
                 "scripts/check_source_liveness.py")

    def tree(self, relative):
        path = REPO_ROOT / relative
        self.assertTrue(path.is_file(), "%s is missing" % relative)
        return ast.parse(path.read_text(encoding="utf-8"))

    def test_both_governed_consumers_call_the_canonical_helper(self):
        for relative in self.CONSUMERS:
            with self.subTest(consumer=relative):
                tree = self.tree(relative)
                bound = {alias.asname or alias.name
                         for node in ast.walk(tree)
                         if isinstance(node, ast.ImportFrom)
                         and (node.module or "").endswith("reconcile_db")
                         for alias in node.names if alias.name == "read_only"}
                self.assertTrue(
                    bound,
                    "%s does not import read_only from reconcile_db" % relative)
                called = {node.func.id for node in ast.walk(tree)
                          if isinstance(node, ast.Call)
                          and isinstance(node.func, ast.Name)}
                called |= {node.func.attr for node in ast.walk(tree)
                           if isinstance(node, ast.Call)
                           and isinstance(node.func, ast.Attribute)}
                self.assertTrue(
                    bound & called,
                    "%s imports read_only but never calls it" % relative)

    def test_no_governed_consumer_opens_sqlite_directly(self):
        from tests.test_workflow_failure_paths import _sqlite_connect_names
        for relative in self.CONSUMERS:
            with self.subTest(consumer=relative):
                tree = self.tree(relative)
                modules, funcs = _sqlite_connect_names(tree)
                offenders = []
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "connect" \
                            and isinstance(func.value, ast.Name) \
                            and func.value.id in modules:
                        offenders.append("%s.connect line %d"
                                         % (func.value.id, node.lineno))
                    elif isinstance(func, ast.Name) and func.id in funcs:
                        offenders.append("%s() line %d" % (func.id, node.lineno))
                self.assertEqual(
                    offenders, [],
                    "%s opens the database directly; read through "
                    "reconcile_db.read_only instead: %s" % (relative, offenders))


class TestCanonicalHelper(FreshCloneCase):

    def test_opens_a_sidecar_less_database(self):
        with read_only(self.db) as con:
            n = con.execute("SELECT count(*) FROM sources").fetchone()[0]
        self.assertGreater(n, 0)

    def test_accepts_a_path_or_a_string(self):
        for arg in (self.db, str(self.db)):
            with self.subTest(arg=type(arg).__name__):
                with read_only(arg) as con:
                    con.execute("SELECT 1").fetchone()

    def test_leaves_the_input_byte_identical(self):
        before = self.digest()
        for _ in range(3):
            with read_only(self.db) as con:
                con.execute("SELECT count(*) FROM articles").fetchone()
        self.assertEqual(self.digest(), before)

    def test_leaves_no_sidecars_beside_the_input(self):
        with read_only(self.db) as con:
            con.execute("SELECT 1").fetchone()
        self.assertEqual(sidecars(self.db), [])

    def test_a_hot_wal_is_recovered_rather_than_ignored(self):
        """
        Dropping the `-wal` would silently hide committed rows. The helper
        copies it, so a reader sees the same rows a writer just committed.
        """
        con = sqlite3.connect(str(self.db))
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("INSERT INTO scrape_runs (status) VALUES ('completed')")
        con.commit()
        expected = con.execute("SELECT count(*) FROM scrape_runs").fetchone()[0]
        # leave the connection open so the WAL is not checkpointed away
        with read_only(self.db) as probe:
            seen = probe.execute("SELECT count(*) FROM scrape_runs").fetchone()[0]
        con.close()
        self.assertEqual(seen, expected)

    def test_errors_are_not_swallowed(self):
        missing = self.tmp / "nope.db"
        with self.assertRaises((OSError, sqlite3.Error)):
            with read_only(missing) as con:
                con.execute("SELECT 1")

    def test_read_only_is_the_public_name_of_the_historical_helper(self):
        from scripts.reconcile_db import _read_only
        self.assertIs(_read_only, read_only)


class TestConsumersUseTheHelper(FreshCloneCase):
    """The two scripts a human runs on a clean checkout."""

    def test_source_liveness_runs_without_a_traceback(self):
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_source_liveness.py"),
             "--db", str(self.db)],
            capture_output=True, text=True)
        self.assertNotIn("Traceback", proc.stderr,
                         "check_source_liveness crashed on a fresh clone")
        self.assertIn("Source liveness", proc.stdout)
        self.assertEqual(sidecars(self.db), [])

    def test_coverage_check_runs_rather_than_degrading_to_a_warning(self):
        """
        Check 8 must execute. Previously an unreadable database produced a
        warning and the check vanished; the gate has to be loud either way.
        """
        import scripts.validate_output as vo
        errors, warnings = [], []
        with read_only(self.db) as con:
            ids = {str(r[0]) for r in con.execute(
                "SELECT id FROM articles "
                " WHERE analyzed_at IS NOT NULL AND passed_relevance = 1")}
        self.assertGreater(len(ids), 0, "the fixture should have analyzed rows")
        # and the real function still finds no fault against the real tree
        vo._validate_db_coverage(
            (REPO_ROOT / "output").resolve(), errors, warnings)
        # Neither channel may carry a read failure. Asserting only on `errors`
        # would still pass under the old behaviour, which put the message in
        # `warnings` — the exact regression this file exists to prevent.
        self.assertEqual(
            [e for e in errors if "could not read" in e], [],
            "the coverage check reported the database as unreadable")
        self.assertEqual(
            [w for w in warnings if "could not read" in w], [],
            "the coverage check was downgraded to a warning instead of running")

    def test_an_unreadable_database_is_an_error_not_a_warning(self):
        import scripts.validate_output as vo
        errors, warnings = [], []
        broken = self.tmp / "broken.db"
        broken.write_bytes(b"this is not a database")
        with unittest.mock.patch.object(vo, "read_only",
                                        side_effect=sqlite3.DatabaseError("boom")):
            vo._validate_db_coverage(
                (REPO_ROOT / "output").resolve(), errors, warnings)
        self.assertTrue(any("could not read" in e for e in errors),
                        "an unreadable database must fail the gate")
        self.assertFalse(any("could not read" in w for w in warnings),
                         "it must not be downgraded to a warning")


class TestCheckEightGatesOnAFreshClone(FreshCloneCase):
    """
    Check 8 against an isolated tree, not the repository's own.

    Running it against the real `output/` only proves it found no fault there;
    it cannot distinguish a gate that ran and passed from one that never ran.
    `_validate_db_coverage` derives the repo root from its module's `__file__`,
    so pointing that at a scratch tree gives the check a database and an
    `output/` this test fully controls, and lets it assert the gate *fires*.

    The fixture database has no sidecars — the fresh-clone condition, where a
    direct `mode=ro` open is only as reliable as the filesystem allows, and
    where its failure is what made the gate vanish into a warning. The fixture
    reproduces that condition; the helper is what makes reading it dependable.
    """

    def _fake_repo(self):
        """A scratch repo whose output/ renders every analyzed article."""
        root = self.tmp / "repo"
        (root / "scripts").mkdir(parents=True)
        (root / "output" / "article").mkdir(parents=True)
        shutil.copyfile(self.db, root / "pla_watch.db")   # still no sidecars
        self.assertEqual(sidecars(root / "pla_watch.db"), [],
                         "the fixture must reproduce the fresh-clone condition")
        with read_only(root / "pla_watch.db") as con:
            ids = sorted(
                (str(r[0]) for r in con.execute(
                    "SELECT id FROM articles "
                    " WHERE analyzed_at IS NOT NULL AND passed_relevance = 1")),
                key=lambda s: int(s) if s.isdigit() else 0)
        self.assertGreater(len(ids), 1, "the fixture needs analyzed articles")
        for aid in ids:
            (root / "output" / "article" / f"{aid}.html").write_text(
                "<html></html>", encoding="utf-8")
        return root, ids

    def _coverage(self, root):
        import scripts.validate_output as vo
        errors, warnings = [], []
        with unittest.mock.patch.object(
                vo, "__file__", str(root / "scripts" / "validate_output.py")):
            vo._validate_db_coverage(
                (root / "output").resolve(), errors, warnings)
        return errors, warnings

    def test_a_complete_tree_produces_no_fault_and_no_read_warning(self):
        root, _ = self._fake_repo()
        errors, warnings = self._coverage(root)
        self.assertEqual(errors, [], "a complete tree must not fail check 8")
        self.assertEqual([w for w in warnings if "could not read" in w], [],
                         "the database was not read on a fresh clone")
        self.assertEqual(sidecars(root / "pla_watch.db"), [],
                         "check 8 left sidecars beside the database")

    def test_an_analyzed_but_unrendered_article_fails_check_8(self):
        """
        The 2026-08-03 defect, reproduced: the database holds an analyzed
        article that `output/` never rendered. Nothing links to the missing
        page, so no link-integrity check can fire — only check 8 sees it.
        """
        root, ids = self._fake_repo()
        victim = ids[len(ids) // 2]
        (root / "output" / "article" / f"{victim}.html").unlink()
        before = hashlib.sha256(
            (root / "pla_watch.db").read_bytes()).hexdigest()

        errors, warnings = self._coverage(root)

        unrendered = [e for e in errors if "have no rendered page" in e]
        self.assertEqual(len(unrendered), 1,
                         f"check 8 did not fire; errors={errors}")
        self.assertIn("1 analyzed article(s)", unrendered[0])
        self.assertIn(victim, unrendered[0])
        # The failure must arrive as an error, and not alongside a read warning
        # that would mean the gate had actually been skipped.
        self.assertEqual([w for w in warnings if "could not read" in w], [],
                         "the database was not read; check 8 did not run")
        self.assertEqual([e for e in errors if "could not read" in e], [],
                         "check 8 reported the database as unreadable")
        self.assertEqual(sidecars(root / "pla_watch.db"), [])
        self.assertEqual(
            hashlib.sha256((root / "pla_watch.db").read_bytes()).hexdigest(),
            before, "check 8 modified the database it was reading")


if __name__ == "__main__":
    unittest.main(verbosity=2)
