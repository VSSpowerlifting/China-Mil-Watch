"""
`scripts/backfill_sidecar_bodies.py` must read the tracked database the way
every other consumer does.

The script enriches each source-trail entry with `title_zh`, taken from
`articles.title_original` on an exact URL match. It used to open the tracked
database itself with a `file:…?mode=ro` URI. That is the idiom DECISION_LOG
2026-08-14 (corrected 2026-08-17) rules out: the tracked database is WAL-mode
and a fresh `git clone` has no `-wal`/`-shm` beside it, because the sidecars are
gitignored. In that state SQLite's behaviour is not fixed — since 3.22.0 a
read-only WAL database opens when those files exist, when they *can be created*,
or when the database is immutable
(https://www.sqlite.org/wal.html#read_only_databases) — so the same call either
fails outright or succeeds by creating sidecars next to the tracked file.

Both outcomes are wrong here, and the failing one is the quiet one: the script
catches it, prints a warning, and backfills every sidecar with no `title_zh` at
all. The result is stored, committed data that differs by machine.

The standing rule is that no consumer reads the tracked database directly
(DECISION_LOG 2026-08-17). `scripts.reconcile_db.read_only` is how that rule is
kept: it copies the database and any sidecars to a scratch directory and reads
the copy, so recovery and sidecar effects land there instead.

A read that fails is also not the same answer as a database with no Chinese
titles, and the two must not produce the same file. `_load_zh_titles` therefore
raises on every failure — missing, invalid, unreadable, a failed copy, a failed
connect, a failed query — and `main()` turns that into one ERROR and a nonzero
exit before any sidecar is opened for writing. An empty mapping is a fact about
the database, never a report of not having read it.

These tests pin what this project controls — that the script goes through the
helper, that the read is dependable on a sidecar-less fixture, that it fails
closed when it is not, and that the script's selection, output and CLI contract
are untouched by the change. They
deliberately assert nothing about what a direct `mode=ro` open does on any
particular machine: that is a property of the SQLite build, the VFS and the
filesystem, and the two tests that once asserted it were removed for exactly
that reason. Nothing here touches the tracked database.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import os
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

from scripts.reconcile_db import read_only                          # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "backfill_sidecar_bodies.py"
TRACKED = REPO_ROOT / "pla_watch.db"
SCRATCH_PREFIX = "dbread-"


def sidecars(db: Path):
    return sorted(p.name for p in db.parent.glob(db.name + "-*"))


def scratch_dirs():
    """The helper's scratch directories currently on disk."""
    return {n for n in os.listdir(tempfile.gettempdir())
            if n.startswith(SCRATCH_PREFIX)}


@contextlib.contextmanager
def captured_stdout():
    buf, real = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = real


@contextlib.contextmanager
def captured_output():
    """Both channels: the report goes to stdout, the ERROR to stderr."""
    out, err = io.StringIO(), io.StringIO()
    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        yield out, err
    finally:
        sys.stdout, sys.stderr = real_out, real_err


class FreshCloneCase(unittest.TestCase):
    """A copy of the tracked database with no -wal/-shm beside it."""

    def setUp(self):
        if not TRACKED.exists():
            self.skipTest("production database not present")
        self.tmp = Path(tempfile.mkdtemp(prefix="backfill-freshclone-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.db = self.tmp / "pla_watch.db"
        shutil.copyfile(TRACKED, self.db)          # deliberately no sidecars
        self.assertEqual(sidecars(self.db), [],
                         "fixture must start with no sidecars")
        self.module = self._module_pointed_at(self.db)

    def _module_pointed_at(self, db):
        """The script with DB_PATH aimed at the fixture, restored afterwards."""
        import scripts.backfill_sidecar_bodies as mod
        original = mod.DB_PATH
        self.addCleanup(setattr, mod, "DB_PATH", original)
        mod.DB_PATH = db
        return mod

    def digest(self):
        return hashlib.sha256(self.db.read_bytes()).hexdigest()


class TestTheFreshCloneRead(FreshCloneCase):
    """The defect, at the call site that had it."""

    def test_a_sidecar_less_database_yields_the_chinese_titles(self):
        """
        The regression itself. Before the fix this returned an empty mapping on
        any machine where the direct open failed, and every `title_zh` was
        dropped from the source trail without the backfill failing.
        """
        with captured_stdout() as out:
            titles = self.module._load_zh_titles()
        self.assertGreater(len(titles), 0,
                           "no Chinese titles were read from a fresh clone")
        self.assertNotIn("could not read DB", out.getvalue())
        self.assertTrue(all(isinstance(k, str) and isinstance(v, str)
                            for k, v in titles.items()))

    def test_the_input_database_is_byte_identical_afterwards(self):
        before = self.digest()
        for _ in range(3):
            self.module._load_zh_titles()
        self.assertEqual(self.digest(), before,
                         "the backfill's read modified the database")

    def test_no_sidecar_appears_beside_the_input(self):
        self.module._load_zh_titles()
        self.assertEqual(sidecars(self.db), [],
                         "the read left -wal/-shm residue beside the database")

    def test_a_hot_wal_commit_is_visible_rather_than_dropped(self):
        """
        A `-wal` that is copied rather than ignored is the difference between
        seeing a committed row and silently missing it. The writer connection
        stays open so the WAL is not checkpointed away first.
        """
        url = "https://example.invalid/hot-wal-probe"
        title = "热更新条目"
        con = sqlite3.connect(str(self.db))
        try:
            con.execute("PRAGMA journal_mode=WAL")
            source_id = con.execute("SELECT id FROM sources LIMIT 1").fetchone()[0]
            con.execute(
                "INSERT INTO articles (url, content_hash, source_id, title_original)"
                " VALUES (?, ?, ?, ?)",
                (url, "hot-wal-probe-hash", source_id, title))
            con.commit()
            titles = self.module._load_zh_titles()
        finally:
            con.close()
        self.assertEqual(titles.get(url), title,
                         "a committed row in the hot WAL was not visible")

    def test_the_scratch_directory_is_removed_after_a_successful_read(self):
        before = scratch_dirs()
        self.module._load_zh_titles()
        self.assertEqual(scratch_dirs() - before, set(),
                         "the read leaked a scratch directory")


class TestFailuresAreLoud(FreshCloneCase):
    """
    Nothing may fail into a silently empty result.

    The helper raises; the script turns that into a visible warning and carries
    on, because `title_zh` enrichment is optional and always was. What must not
    happen is an empty mapping with nothing said about it, or a traceback where
    a warning used to be.
    """

    def _unreadable(self):
        path = self.tmp / "unreadable.db"
        shutil.copyfile(self.db, path)
        os.chmod(path, 0o000)
        self.addCleanup(os.chmod, path, 0o600)
        if os.access(path, os.R_OK):
            self.skipTest("this environment can read a mode-000 file")
        return path

    def _invalid(self):
        path = self.tmp / "invalid.db"
        path.write_bytes(b"this is not a database")
        return path

    def _missing(self):
        return self.tmp / "nope.db"

    # -- the helper --------------------------------------------------------

    def test_the_helper_raises_on_a_missing_database(self):
        with self.assertRaises((OSError, sqlite3.Error)):
            with read_only(self._missing()) as con:
                con.execute("SELECT 1").fetchone()

    def test_the_helper_raises_on_an_invalid_database(self):
        with self.assertRaises((OSError, sqlite3.Error)):
            with read_only(self._invalid()) as con:
                con.execute("SELECT count(*) FROM articles").fetchone()

    def test_the_helper_raises_on_an_unreadable_database(self):
        with self.assertRaises((OSError, sqlite3.Error)):
            with read_only(self._unreadable()) as con:
                con.execute("SELECT 1").fetchone()

    # -- the script's own read ---------------------------------------------

    def test_the_read_raises_on_an_invalid_database(self):
        self.module.DB_PATH = self._invalid()
        with self.assertRaises((OSError, sqlite3.Error)):
            self.module._load_zh_titles()

    def test_the_read_raises_on_an_unreadable_database(self):
        self.module.DB_PATH = self._unreadable()
        with self.assertRaises((OSError, sqlite3.Error)):
            self.module._load_zh_titles()

    def test_the_read_raises_on_a_missing_database(self):
        """
        A missing database is a failure, not a quiet no-op. It used to return
        `{}` through an explicit `DB_PATH.exists()` check, which is the same
        value a successful read of a database with no Chinese titles returns —
        so the backfill could not tell the two apart and rewrote every sidecar
        without `title_zh` either way.
        """
        self.module.DB_PATH = self._missing()
        with self.assertRaises(FileNotFoundError):
            self.module._load_zh_titles()

    def test_no_failure_mode_returns_an_empty_mapping(self):
        """The property behind all of the above, stated once."""
        for label, path in (("missing", self._missing()),
                            ("invalid", self._invalid())):
            with self.subTest(case=label):
                self.module.DB_PATH = path
                with self.assertRaises((OSError, sqlite3.Error)):
                    result = self.module._load_zh_titles()
                    self.fail("returned %r instead of raising" % (result,))

    # -- scratch hygiene on the failing paths ------------------------------

    def test_the_scratch_directory_is_removed_after_an_exception(self):
        before = scratch_dirs()
        boom = RuntimeError("raised inside the read")
        with self.assertRaises(RuntimeError):
            with read_only(self.db) as con:
                con.execute("SELECT 1").fetchone()
                raise boom
        self.assertEqual(scratch_dirs() - before, set(),
                         "an exception inside the read leaked a scratch "
                         "directory")

    def test_a_failed_script_read_leaves_no_scratch_directory(self):
        before = scratch_dirs()
        self.module.DB_PATH = self._invalid()
        with self.assertRaises((OSError, sqlite3.Error)):
            self.module._load_zh_titles()
        self.assertEqual(scratch_dirs() - before, set(),
                         "a failed read leaked a scratch directory")


class TestTheScriptReadsThroughTheHelper(unittest.TestCase):
    """
    The call site, asserted structurally.

    Whether a direct `mode=ro` open succeeds is a property of one machine, so
    it is not assertable here. What is ours to guarantee is that the script
    imports and calls `reconcile_db.read_only`, and opens nothing itself. That
    holds identically everywhere, and `ast` means the file's own corrected
    comments — which still mention `mode=ro` — cannot satisfy or trip the
    guard, and an aliased import cannot evade it.
    """

    def tree(self):
        self.assertTrue(SCRIPT.is_file(), "%s is missing" % SCRIPT)
        return ast.parse(SCRIPT.read_text(encoding="utf-8"))

    def test_it_imports_the_shared_helper_from_reconcile_db(self):
        bound = {alias.asname or alias.name
                 for node in ast.walk(self.tree())
                 if isinstance(node, ast.ImportFrom)
                 and (node.module or "").endswith("reconcile_db")
                 for alias in node.names
                 if alias.name in ("read_only", "_read_only")}
        self.assertTrue(
            bound, "the script does not import read_only from reconcile_db")

    def test_it_actually_calls_the_helper(self):
        tree = self.tree()
        bound = {alias.asname or alias.name
                 for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom)
                 and (node.module or "").endswith("reconcile_db")
                 for alias in node.names
                 if alias.name in ("read_only", "_read_only")}
        called = {node.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)}
        called |= {node.func.attr for node in ast.walk(tree)
                   if isinstance(node, ast.Call)
                   and isinstance(node.func, ast.Attribute)}
        self.assertTrue(bound & called,
                        "the script imports read_only but never calls it")

    def test_it_never_opens_sqlite_itself(self):
        from tests.test_workflow_failure_paths import _sqlite_connect_names
        tree = self.tree()
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
            "the script opens the database directly; read through "
            "reconcile_db.read_only instead: %s" % offenders)

    def test_it_never_connects_to_the_governed_database(self):
        """
        The repository's own resolver, pointed at this script. It follows
        `DB_PATH = ROOT / "pla_watch.db"` through assignment and through the
        f-string URI form, so it recognises the exact pre-fix line.
        """
        from tests.test_workflow_failure_paths import tracked_db_connections
        hits = tracked_db_connections(SCRIPT.read_text(encoding="utf-8"))
        self.assertEqual(
            [line for line, _ in hits], [],
            "the script connects to the tracked database at %s" % (hits,))


class TestTheChangeIsConfinedToTheDatabaseOpen(unittest.TestCase):
    """
    Everything the script does apart from opening the database is unchanged:
    which sidecars it selects, the numbering it assigns, what it extracts, how
    it writes, and the CLI it exposes. Exercised against a synthetic tree — the
    real `output/` is never touched and the real backfill is never run.
    """

    HTML = """<html>
      <div class="mod-heading brand">Opening Note</div>
      <div class="section-text"><p>First para.</p><p>Second para.</p></div>
      </div>
      <div class="mod-heading brand">Why It Matters</div>
      <div class="section-text"><p>It matters &amp; then some.</p></div>
      </div>
      <div class="term-word">&#31995;&#32479;</div>
      <div class="term-explanation"><p>A system.</p></div>
      <div class="signal-text">A quiet signal.</div>
    </html>"""

    URL = "https://example.invalid/zh-probe"
    ZH = "中文标题"

    def setUp(self):
        import scripts.backfill_sidecar_bodies as mod
        self.mod = mod
        self.tmp = Path(tempfile.mkdtemp(prefix="backfill-cli-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.posts = self.tmp / "posts"
        self.posts.mkdir()
        for original, attr in (("POSTS_DIR", "POSTS_DIR"), ("DB_PATH", "DB_PATH")):
            self.addCleanup(setattr, mod, attr, getattr(mod, attr))
        mod.POSTS_DIR = self.posts
        mod.DB_PATH = self._mini_db()

    def _mini_db(self):
        """A tiny purpose-built database — never the tracked one."""
        path = self.tmp / "mini.db"
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE articles (url TEXT, title_original TEXT)")
        con.execute("INSERT INTO articles VALUES (?, ?)", (self.URL, self.ZH))
        con.execute("INSERT INTO articles VALUES (?, ?)", ("https://x.invalid", ""))
        con.commit()
        con.close()
        return path

    def _sidecar(self, name, **extra):
        payload = {
            "date": name,
            "title": "Edition " + name,
            "author_title": self.mod.OLD_TITLE,
            "author_bio": "She is the founder of China Mil Watch.",
            "sources_seen": ["PLA Daily (81.cn)"],
            "source_trail": [{"label": "A headline", "url": self.URL}],
        }
        payload.update(extra)
        path = self.posts / (name + ".json")
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        (self.posts / (name + ".html")).write_text(self.HTML, encoding="utf-8")
        return path

    def _run(self, *argv):
        original = sys.argv
        sys.argv = ["backfill_sidecar_bodies.py", *argv]
        try:
            with captured_stdout() as out:
                code = self.mod.main()
        finally:
            sys.argv = original
        return code, out.getvalue()

    def test_dry_run_writes_nothing(self):
        path = self._sidecar("2026-05-09")
        before = path.read_bytes()
        code, out = self._run("--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(path.read_bytes(), before,
                         "--dry-run modified a sidecar")
        self.assertIn("Would update", out)

    def test_selection_is_every_json_sidecar_numbered_in_filename_order(self):
        for name in ("2026-05-23", "2026-05-09", "2026-05-16"):
            self._sidecar(name)
        code, _ = self._run()
        self.assertEqual(code, 0)
        numbers = {p.stem: json.loads(p.read_text(encoding="utf-8"))["issue_number"]
                   for p in self.posts.glob("*.json")}
        self.assertEqual(numbers,
                         {"2026-05-09": 1, "2026-05-16": 2, "2026-05-23": 3})

    def test_it_extracts_bodies_normalises_identity_and_fills_title_zh(self):
        path = self._sidecar("2026-05-09")
        self._run()
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["opening_note"], "First para.\n\nSecond para.")
        self.assertEqual(data["why_it_matters"], "It matters & then some.")
        self.assertEqual(data["term_to_know_term"], "系统")
        self.assertEqual(data["signal"], "A quiet signal.")
        self.assertEqual(data["author_title"], self.mod.AUTHOR_TITLE)
        self.assertIn("is the principal analyst at China Mil Watch",
                      data["author_bio"])
        entry = data["source_trail"][0]
        self.assertEqual(entry["title"], "A headline")
        self.assertNotIn("label", entry)
        self.assertEqual(entry["source"], "PLA Daily (81.cn)")
        self.assertEqual(entry["title_zh"], self.ZH)

    def test_an_existing_body_field_is_never_overwritten(self):
        path = self._sidecar("2026-05-09", opening_note="Kept verbatim.")
        self._run()
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["opening_note"], "Kept verbatim.")

    def test_the_written_format_is_two_space_json_with_unescaped_unicode(self):
        path = self._sidecar("2026-05-09")
        self._run()
        text = path.read_text(encoding="utf-8")
        self.assertIn('\n  "date"', text, "sidecars must stay indent=2")
        self.assertIn(self.ZH, text, "unicode must not be \\u-escaped")

    def test_an_empty_posts_directory_exits_one(self):
        code, out = self._run()
        self.assertEqual(code, 1)
        self.assertIn("No sidecars found", out)

    def test_the_cli_still_accepts_only_dry_run(self):
        parser_flags = set()
        for node in ast.walk(ast.parse(SCRIPT.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "add_argument":
                parser_flags |= {a.value for a in node.args
                                 if isinstance(a, ast.Constant)}
        self.assertEqual(parser_flags, {"--dry-run"},
                         "the CLI contract changed")

    def test_a_missing_html_file_warns_and_continues(self):
        path = self._sidecar("2026-05-09")
        (self.posts / "2026-05-09.html").unlink()
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn("cannot backfill body", out)
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8"))["issue_number"], 1)


class TestTheBackfillFailsClosed(unittest.TestCase):
    """
    End to end, against synthetic sidecars: no read failure reaches the write
    loop.

    This is the defect the helper alone did not close. Routing the read through
    `read_only` made it portable, but the caller still caught every failure and
    carried on with an empty mapping — so on any machine where the read failed,
    `main()` rewrote every sidecar with `title_zh` absent from the source trail
    and reported success. That is the same incomplete, machine-dependent stored
    output, produced one layer up.

    So each failure mode is driven through `main()` and required to leave the
    sidecars untouched. Two of them — a failed copy and a failed connect — are
    injected rather than provoked, because provoking them portably is not
    possible: `chmod 000` is readable to a privileged user, and whether a given
    filesystem refuses a copy is not this project's property. Injection makes
    them deterministic everywhere.
    """

    HTML = """<html>
      <div class="mod-heading brand">Opening Note</div>
      <div class="section-text"><p>Body that a successful run would store.</p></div>
      </div>
      <div class="signal-text">A quiet signal.</div>
    </html>"""

    URL = "https://example.invalid/zh-probe"
    ZH = "中文标题"
    NAMES = ("2026-05-09", "2026-05-16")

    def setUp(self):
        import scripts.backfill_sidecar_bodies as mod
        self.mod = mod
        self.tmp = Path(tempfile.mkdtemp(prefix="backfill-failclosed-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.posts = self.tmp / "posts"
        self.posts.mkdir()
        for attr in ("POSTS_DIR", "DB_PATH"):
            self.addCleanup(setattr, mod, attr, getattr(mod, attr))
        mod.POSTS_DIR = self.posts

        self.db = self._good_db()
        mod.DB_PATH = self.db
        for name in self.NAMES:
            self._sidecar(name)

    # -- fixtures ----------------------------------------------------------

    def _good_db(self):
        path = self.tmp / "good.db"
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE articles (url TEXT, title_original TEXT)")
        con.execute("INSERT INTO articles VALUES (?, ?)", (self.URL, self.ZH))
        con.commit()
        con.close()
        return path

    def _sidecar(self, name):
        payload = {
            "date": name,
            "title": "Edition " + name,
            "author_title": self.mod.OLD_TITLE,
            "author_bio": "She is the founder of China Mil Watch.",
            "sources_seen": ["PLA Daily (81.cn)"],
            "source_trail": [{"label": "A headline", "url": self.URL}],
        }
        (self.posts / (name + ".json")).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        (self.posts / (name + ".html")).write_text(self.HTML, encoding="utf-8")

    def _digests(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.posts.iterdir())}

    def _run(self, *argv):
        original = sys.argv
        sys.argv = ["backfill_sidecar_bodies.py", *argv]
        try:
            with captured_output() as (out, err):
                code = self.mod.main()
        finally:
            sys.argv = original
        return code, out.getvalue(), err.getvalue()

    # -- the shared contract -----------------------------------------------

    def _assert_failed_closed(self, code, out, err, before, leaked_before):
        self.assertNotEqual(code, 0, "a failed read returned success")
        self.assertIn("ERROR:", err,
                      "no ERROR: message on the failure channel")
        self.assertEqual(err.count("ERROR:"), 1,
                         "the failure must be reported once, not repeatedly")
        self.assertNotIn("Traceback", err, "the failure escaped as a traceback")
        self.assertEqual(self._digests(), before,
                         "a sidecar changed despite the read failing")
        self.assertEqual(sidecars(self.db), [],
                         "the failed read left -wal/-shm beside the input")
        self.assertEqual(scratch_dirs() - leaked_before, set(),
                         "the failed read leaked a scratch directory")
        # No silent empty-title continuation: the write loop never ran, so none
        # of its per-sidecar report lines and neither summary line can appear.
        self.assertNotIn(".json:", out,
                         "the write loop ran after the read failed")
        self.assertNotIn("Would update", out)
        self.assertNotIn("Updated", out)

    def _failure_case(self, argv=(), patch=None, db=None):
        before, leaked_before = self._digests(), scratch_dirs()
        if db is not None:
            self.mod.DB_PATH = db
        ctx = patch if patch is not None else contextlib.nullcontext()
        with ctx:
            code, out, err = self._run(*argv)
        self._assert_failed_closed(code, out, err, before, leaked_before)
        return code, out, err

    # -- the positive control ----------------------------------------------

    def test_a_readable_database_still_backfills_title_zh(self):
        """Everything below is only meaningful because this passes."""
        code, out, err = self._run()
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        for name in self.NAMES:
            data = json.loads((self.posts / (name + ".json")).read_text("utf-8"))
            self.assertEqual(data["source_trail"][0]["title_zh"], self.ZH)
            self.assertEqual(data["opening_note"],
                             "Body that a successful run would store.")

    # -- the failure modes -------------------------------------------------

    def test_a_missing_database_fails_closed(self):
        self._failure_case(db=self.tmp / "nope.db")

    def test_an_invalid_database_fails_closed(self):
        broken = self.tmp / "invalid.db"
        broken.write_bytes(b"this is not a database")
        self._failure_case(db=broken)

    def test_a_query_failure_fails_closed(self):
        """A real database that simply has no `articles` table."""
        empty = self.tmp / "no-articles.db"
        con = sqlite3.connect(str(empty))
        con.execute("CREATE TABLE unrelated (x TEXT)")
        con.commit()
        con.close()
        _, _, err = self._failure_case(db=empty)
        self.assertIn("articles", err)

    def test_a_copy_failure_fails_closed(self):
        """
        Injected inside the helper, where the copy happens. Deterministic on
        every platform, unlike a permission bit.
        """
        import scripts.reconcile_db as rd
        patch = unittest.mock.patch.object(
            rd.shutil, "copyfile",
            side_effect=OSError(28, "No space left on device"))
        self._failure_case(patch=patch)

    def test_a_connect_failure_fails_closed(self):
        import scripts.reconcile_db as rd
        patch = unittest.mock.patch.object(
            rd.sqlite3, "connect",
            side_effect=sqlite3.OperationalError("unable to open database file"))
        self._failure_case(patch=patch)

    def test_an_unreadable_database_fails_closed(self):
        """
        Supplementary to the injected cases, not a substitute for them: a
        privileged environment can read a mode-000 file, so this skips rather
        than asserting a permission model this project does not own.
        """
        path = self.tmp / "unreadable.db"
        shutil.copyfile(self.db, path)
        os.chmod(path, 0o000)
        self.addCleanup(os.chmod, path, 0o600)
        if os.access(path, os.R_OK):
            self.skipTest("this environment can read a mode-000 file")
        self._failure_case(db=path)

    # -- the dry run is not an exception -----------------------------------

    def test_dry_run_also_fails_closed_on_a_missing_database(self):
        self._failure_case(argv=("--dry-run",), db=self.tmp / "nope.db")

    def test_dry_run_also_fails_closed_on_an_injected_copy_failure(self):
        import scripts.reconcile_db as rd
        patch = unittest.mock.patch.object(
            rd.shutil, "copyfile", side_effect=OSError(5, "I/O error"))
        self._failure_case(argv=("--dry-run",), patch=patch)

    # -- the exit status actually reaches the shell -------------------------

    def test_the_entry_point_exits_with_mains_return_value(self):
        """
        `main()` returned its failure codes into nothing: the module ended in a
        bare `main()` call, so every documented failure exited 0. A gate that
        cannot be observed by a caller is not a gate.
        """
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        guarded = [n for n in tree.body if isinstance(n, ast.If)]
        self.assertTrue(guarded, "the __main__ guard is missing")
        calls = [n for n in ast.walk(guarded[-1])
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "exit"
                 and isinstance(n.func.value, ast.Name)
                 and n.func.value.id == "sys"]
        self.assertTrue(
            calls, "the entry point does not pass main()'s return to sys.exit")
        self.assertTrue(
            any(isinstance(a, ast.Call) and isinstance(a.func, ast.Name)
                and a.func.id == "main" for c in calls for a in c.args),
            "sys.exit() is not called with main()'s return value")

    def test_a_missing_database_is_reported_on_stderr_not_stdout(self):
        _, out, err = self._failure_case(db=self.tmp / "nope.db")
        self.assertNotIn("ERROR:", out,
                         "the error was also written to the report channel")
        self.assertIn("no sidecar was modified", err)


class TestThisModuleAssertsNoPlatformSpecificSqliteBehaviour(unittest.TestCase):
    """
    The guard on the guard.

    Two earlier tests asserted that a direct `mode=ro` open raises
    `OperationalError` on a sidecar-less WAL database. A hosted Ubuntu runner
    disproved them (DECISION_LOG 2026-08-17): that outcome belongs to the
    SQLite build, the VFS and the filesystem, not to this project. Asserting
    either branch asserts one machine, and accepting both asserts nothing. This
    parses the present module and refuses to let such an assertion return.
    """

    PLATFORM_DEPENDENT = ("OperationalError", "DatabaseError", "NotSupportedError")

    def test_no_test_here_asserts_a_platform_dependent_sqlite_error(self):
        """
        The rule is about what is *asserted*, not what is mentioned. Raising a
        concrete `OperationalError` as an injected failure is fine — the
        injection is what makes the test deterministic. Requiring one to come
        back is what pins a machine, so only `assertRaises` arguments are
        scanned. `sqlite3.Error`, the base class, is always a legitimate
        expectation: it says "the read failed", which is the project's
        property, not the platform's.
        """
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        named = []
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr.startswith("assertRaises")):
                continue
            for arg in node.args:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.Attribute) \
                            and sub.attr in self.PLATFORM_DEPENDENT \
                            and isinstance(sub.value, ast.Name) \
                            and sub.value.id == "sqlite3":
                        named.append(node.lineno)
        self.assertEqual(
            named, [],
            "this module requires a platform-dependent SQLite error at lines "
            "%s; expect sqlite3.Error instead" % named)

    def test_no_test_here_opens_a_database_through_a_uri(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        offenders = [node.lineno for node in ast.walk(tree)
                     if isinstance(node, ast.Call)
                     and any(kw.arg == "uri" for kw in node.keywords)]
        self.assertEqual(
            offenders, [],
            "this module opens a database through a URI at lines %s — the "
            "behaviour of that form is not a property of this project"
            % offenders)

    def test_it_never_connects_to_the_tracked_database(self):
        from tests.test_workflow_failure_paths import tracked_db_connections
        hits = tracked_db_connections(
            Path(__file__).read_text(encoding="utf-8"))
        self.assertEqual([line for line, _ in hits], [],
                         "this module connects to the tracked database at %s"
                         % (hits,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
