"""
Destructive-cleanup contract tests.

scripts/cleanup_duplicates.py deletes rows. It must therefore agree exactly
with the pipeline about which copy is canonical, and must refuse to guess.

Until 2026-08-17 it ranked by `source_priority(url)` alone. Once the pipeline
began preferring the Tier A ministry copy, that left the destructive tool
scoring a MOD China URL at 50 against PLA Daily's 要闻 at 100 — it would have
deleted precisely the copy the pipeline had chosen to keep. Both now rank
through `processing.dedup.canonical_sort_key`.

Offline: no network, no model calls. Every database is a temporary file; the
tracked pla_watch.db is never opened.
"""

from __future__ import annotations

import io
import itertools
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from processing.dedup import (                                   # noqa: E402
    canonical_sort_key, dedup_articles, select_canonical, unresolved_authority,
)
from scripts.cleanup_duplicates import (                          # noqa: E402
    find_duplicate_groups, main, rank_group,
)

TITLE = "国防部：“台独”死局演不赢、改不了"

MOD_URL = "http://www.mod.gov.cn/gfbw/xwfyr/yzxwfb/16479365.html"
PLA_MAIN_URL = "http://www.81.cn/yw_208727/16479366.html"
PLA_NAVY_URL = "http://www.81.cn/hj_208557/16479367.html"


class _TempDB:
    """A disposable database with the columns cleanup actually reads."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "cleanup.db"
        conn = sqlite3.connect(self.path)
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL
            );
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                url TEXT UNIQUE,
                title_original TEXT,
                source_id INTEGER REFERENCES sources(id)
            );
            CREATE TABLE article_categories (
                article_id INTEGER NOT NULL
                    REFERENCES articles(id) ON DELETE CASCADE,
                category TEXT NOT NULL
            );
            """
        )
        conn.commit()
        conn.close()

    def add_source(self, slug, sid):
        self._exec("INSERT INTO sources (id, slug) VALUES (?, ?)", (sid, slug))

    def add_article(self, aid, url, title, source_id, categories=()):
        self._exec(
            "INSERT INTO articles (id, url, title_original, source_id) "
            "VALUES (?, ?, ?, ?)", (aid, url, title, source_id),
        )
        for c in categories:
            self._exec(
                "INSERT INTO article_categories (article_id, category) "
                "VALUES (?, ?)", (aid, c),
            )

    def _exec(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(sql, params)
        conn.commit()
        conn.close()

    def query(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return rows

    def article_ids(self):
        return [r[0] for r in self.query("SELECT id FROM articles ORDER BY id")]

    def cleanup(self):
        self._tmp.cleanup()


def run_cli(db_path, *flags):
    """Invoke the script's main() and capture stdout."""
    argv = sys.argv
    sys.argv = ["cleanup_duplicates.py", "--db", str(db_path), *flags]
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = main()
    finally:
        sys.argv = argv
    return code, buf.getvalue()


class _DBTest(unittest.TestCase):
    def setUp(self):
        self.db = _TempDB()
        self.addCleanup(self.db.cleanup)
        self.db.add_source("mod_china", 1)
        self.db.add_source("pla_daily", 2)
        self.db.add_source("china_mil_online", 3)


class TestPipelineAndCleanupAgree(_DBTest):
    """Requirement 1: both select the same winner for every fixture."""

    FIXTURES = [
        # (name, [(id, url, slug)])
        ("mod vs pla main",
         [(1, MOD_URL, "mod_china"), (2, PLA_MAIN_URL, "pla_daily")]),
        ("pla main vs pla navy",
         [(1, PLA_MAIN_URL, "pla_daily"), (2, PLA_NAVY_URL, "pla_daily")]),
        ("mod vs pla navy",
         [(1, MOD_URL, "mod_china"), (2, PLA_NAVY_URL, "pla_daily")]),
        ("mod vs english mirror",
         [(1, MOD_URL, "mod_china"),
          (2, "http://english.chinamil.com.cn/view/1.html", "china_mil_online")]),
        ("three-way",
         [(1, MOD_URL, "mod_china"), (2, PLA_MAIN_URL, "pla_daily"),
          (3, PLA_NAVY_URL, "pla_daily")]),
        ("same source, url length tie-break",
         [(1, "http://www.81.cn/yw_208727/1234567890.html", "pla_daily"),
          (2, "http://www.81.cn/yw_208727/1.html", "pla_daily")]),
    ]

    def test_same_winner_for_every_fixture(self):
        slug_to_id = {"mod_china": 1, "pla_daily": 2, "china_mil_online": 3}
        for name, members in self.FIXTURES:
            with self.subTest(name):
                db = _TempDB()
                self.addCleanup(db.cleanup)
                for slug, sid in slug_to_id.items():
                    db.add_source(slug, sid)
                for aid, url, slug in members:
                    db.add_article(aid, url, TITLE, slug_to_id[slug])

                # cleanup's view
                conn = sqlite3.connect(db.path)
                groups = find_duplicate_groups(conn)
                conn.close()
                self.assertEqual(len(groups), 1, name)
                cleanup_winner = rank_group(groups[0])[0]["url"]

                # pipeline's view
                articles = [
                    {"url": url, "source_slug": slug, "title_original": TITLE}
                    for _, url, slug in members
                ]
                kept = dedup_articles(articles)
                self.assertEqual(len(kept), 1, name)
                pipeline_winner = kept[0]["url"]

                self.assertEqual(
                    cleanup_winner, pipeline_winner,
                    "cleanup and pipeline disagree for fixture %r" % name,
                )
                self.assertEqual(
                    cleanup_winner, select_canonical(articles)["url"], name,
                )


class TestWinnerRules(_DBTest):
    """Requirements 2 and 3."""

    def test_mod_beats_pla_daily(self):
        self.db.add_article(1, PLA_MAIN_URL, TITLE, 2)
        self.db.add_article(2, MOD_URL, TITLE, 1)
        conn = sqlite3.connect(self.db.path)
        winner = rank_group(find_duplicate_groups(conn)[0])[0]
        conn.close()
        self.assertEqual(winner["source_slug"], "mod_china")
        self.assertEqual(winner["url"], MOD_URL)

    def test_pla_main_news_still_beats_its_own_service_section(self):
        self.db.add_article(1, PLA_NAVY_URL, TITLE, 2)
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2)
        conn = sqlite3.connect(self.db.path)
        winner = rank_group(find_duplicate_groups(conn)[0])[0]
        conn.close()
        self.assertEqual(winner["url"], PLA_MAIN_URL)

    def test_source_slug_comes_from_the_join_not_the_url(self):
        """The slug must be read through articles->sources, not guessed."""
        self.db.add_article(1, MOD_URL, TITLE, 1)
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2)
        conn = sqlite3.connect(self.db.path)
        rows = find_duplicate_groups(conn)[0]
        conn.close()
        self.assertEqual(
            {r["url"]: r["source_slug"] for r in rows},
            {MOD_URL: "mod_china", PLA_MAIN_URL: "pla_daily"},
        )


class TestFailClosed(_DBTest):
    """Requirement 4: an unresolved cross-source identity cannot be deleted."""

    def _mixed_group(self):
        # id=3 has a dangling source_id: the LEFT JOIN yields source_slug NULL.
        self.db.add_article(1, MOD_URL, TITLE, 1)
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2)
        self.db._exec(
            "INSERT INTO articles (id, url, title_original, source_id) "
            "VALUES (?, ?, ?, ?)",
            (3, "https://unknown.example/whatever/1.html", TITLE, None),
        )

    def test_guard_reports_the_group_as_unresolved(self):
        self._mixed_group()
        conn = sqlite3.connect(self.db.path)
        group = find_duplicate_groups(conn)[0]
        conn.close()
        reason = unresolved_authority(group)
        self.assertIsNotNone(reason)
        self.assertIn("no resolvable source identity", reason)

    def test_mixed_governed_and_named_ungoverned_is_still_refused(self):
        """Rule 3: identities differ and one is not governed — still a guess."""
        self.db.add_source("brand_new_source", 9)
        self.db.add_article(1, MOD_URL, TITLE, 1)
        self.db.add_article(2, "https://new.example/a/1.html", TITLE, 9)
        conn = sqlite3.connect(self.db.path)
        group = find_duplicate_groups(conn)[0]
        conn.close()
        reason = unresolved_authority(group)
        self.assertIsNotNone(reason)
        self.assertIn("ungoverned", reason)

    def test_apply_deletes_nothing_from_an_unresolved_group(self):
        self._mixed_group()
        before = self.db.article_ids()
        code, out = run_cli(self.db.path, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("REFUSED", out)
        self.assertIn("1 group(s) refused", out)
        self.assertEqual(self.db.article_ids(), before,
                         "a refused group must lose no rows under --apply")

    def test_same_source_group_with_unknown_slug_is_still_rankable(self):
        """
        Authority cannot decide a group whose members share one identity, so an
        unrecognised slug there is not a guess — ordering falls to the
        unchanged URL rules.
        """
        self.db.add_source("brand_new_source", 9)
        self.db.add_article(1, "https://new.example/a/1234.html", TITLE, 9)
        self.db.add_article(2, "https://new.example/a/1.html", TITLE, 9)
        conn = sqlite3.connect(self.db.path)
        group = find_duplicate_groups(conn)[0]
        conn.close()
        self.assertIsNone(unresolved_authority(group))
        self.assertEqual(rank_group(group)[0]["url"], "https://new.example/a/1.html")


class TestDryRunIsInert(_DBTest):
    """Requirement 5: --dry-run performs zero mutations."""

    def test_dry_run_changes_nothing(self):
        self.db.add_article(1, MOD_URL, TITLE, 1)
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2, categories=("naval",))
        before_ids = self.db.article_ids()
        before_cats = self.db.query("SELECT * FROM article_categories")
        before_bytes = self.db.path.read_bytes()

        code, out = run_cli(self.db.path, "--dry-run")

        self.assertEqual(code, 0)
        self.assertIn("Dry run — no changes made", out)
        self.assertEqual(self.db.article_ids(), before_ids)
        self.assertEqual(self.db.query("SELECT * FROM article_categories"), before_cats)
        self.assertEqual(self.db.path.read_bytes(), before_bytes,
                         "dry run must not write a single byte")

    def test_dry_run_reports_the_complete_key_not_just_the_url_score(self):
        self.db.add_article(1, MOD_URL, TITLE, 1)
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2)
        _, out = run_cli(self.db.path, "--dry-run")
        for component in ("auth=", "identity=", "section=", "urllen=", "url="):
            self.assertIn(component, out,
                          "every key component must be printed, not a subset")
        self.assertIn("identity=mod_china", out)
        # The winner line must be the MOD row.
        keep_line = next(l for l in out.splitlines() if "KEEP" in l)
        self.assertIn("auth=400", keep_line)


class TestApplyOnDisposableFixture(_DBTest):
    """Requirement 6: --apply deletes only governed losers, integrity intact."""

    def test_apply_deletes_losers_and_cascades(self):
        self.db.add_article(1, MOD_URL, TITLE, 1, categories=("spokesperson",))
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2, categories=("reprint",))
        self.db.add_article(3, PLA_NAVY_URL, TITLE, 2, categories=("reprint2",))
        # An unrelated article that must survive untouched.
        self.db.add_article(4, "http://www.81.cn/yw_208727/999.html",
                            "另一个完全不同的标题", 2, categories=("other",))

        code, out = run_cli(self.db.path, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Deleted 2 row(s).", out)

        self.assertEqual(self.db.article_ids(), [1, 4],
                         "only the Tier A winner and the unrelated row remain")

        # Dependent rows for deleted articles are gone; survivors' rows remain.
        cats = {r[0] for r in self.db.query("SELECT article_id FROM article_categories")}
        self.assertEqual(cats, {1, 4})

        # No orphans, foreign keys clean.
        conn = sqlite3.connect(self.db.path)
        conn.execute("PRAGMA foreign_keys = ON")
        self.assertEqual(conn.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        conn.close()

    def test_apply_never_touches_the_tracked_database(self):
        self.assertNotEqual(self.db.path, REPO_ROOT / "pla_watch.db")
        self.assertFalse(str(self.db.path).startswith(str(REPO_ROOT)))


class TestOrderIndependence(_DBTest):
    """
    Cleanup and the pipeline must agree on the winner for EVERY input order.

    Row order out of SQLite is not guaranteed, so an order-dependent key could
    delete a different row on a different day against the same data.
    """

    EQUAL = [
        "http://www.81.cn/yw_208727/16463738.html",
        "http://www.81.cn/yw_208727/16468666.html",
        "http://www.81.cn/yw_208727/16470502.html",
    ]

    def test_cleanup_picks_the_same_winner_for_every_permutation(self):
        winners = set()
        for perm in itertools.permutations(self.EQUAL):
            rows = [{"url": u, "source_slug": "pla_daily", "title_original": TITLE}
                    for u in perm]
            winners.add(rank_group(rows)[0]["url"])
        self.assertEqual(len(winners), 1,
                         "cleanup ranking is order-dependent: %s" % sorted(winners))

    def test_cleanup_and_pipeline_agree_for_every_permutation(self):
        for perm in itertools.permutations(self.EQUAL):
            rows = [{"url": u, "source_slug": "pla_daily", "title_original": TITLE}
                    for u in perm]
            self.assertEqual(rank_group(rows)[0]["url"],
                             dedup_articles(list(rows))[0]["url"])
            self.assertEqual(rank_group(rows)[0]["url"],
                             select_canonical(rows)["url"])

    def test_database_row_order_cannot_change_the_outcome(self):
        """The same rows, inserted in two different id orders, keep one winner."""
        winners = set()
        for perm in itertools.permutations(self.EQUAL):
            db = _TempDB()
            self.addCleanup(db.cleanup)
            db.add_source("pla_daily", 2)
            for i, u in enumerate(perm, start=1):
                db.add_article(i, u, TITLE, 2)
            conn = sqlite3.connect(db.path)
            winners.add(rank_group(find_duplicate_groups(conn)[0])[0]["url"])
            conn.close()
        self.assertEqual(len(winners), 1, sorted(winners))


class TestUnresolvedIdentitiesAreNeverPaired(_DBTest):
    """
    Two rows whose identity cannot be resolved are two unknowns, not a pair.

    The earlier guard tested `len(set(slugs)) <= 1` first. Two rows from
    different unknown hosts both resolved to "", collapsed to a one-element set,
    and were ranked and deleted as confirmed same-source duplicates. An empty
    identity is the absence of an answer.
    """

    def _two_unknowns(self):
        for aid, url in (
            (1, "https://unknown-a.example/x/1.html"),
            (2, "https://unknown-b.example/y/2.html"),
        ):
            self.db._exec(
                "INSERT INTO articles (id, url, title_original, source_id) "
                "VALUES (?, ?, ?, ?)", (aid, url, TITLE, None))

    def test_two_empty_identities_are_refused(self):
        self._two_unknowns()
        conn = sqlite3.connect(self.db.path)
        group = find_duplicate_groups(conn)[0]
        conn.close()
        self.assertEqual([r["source_slug"] for r in group], [None, None])
        reason = unresolved_authority(group)
        self.assertIsNotNone(reason, "two unknowns must not be treated as a pair")
        self.assertIn("no resolvable source identity", reason)

    def test_apply_deletes_nothing_for_two_empty_identities(self):
        self._two_unknowns()
        before = self.db.article_ids()
        code, out = run_cli(self.db.path, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("REFUSED", out)
        self.assertIn("Deleted 0 row(s).", out)
        self.assertEqual(self.db.article_ids(), before)

    def test_one_empty_identity_among_governed_rows_refuses_the_group(self):
        self.db.add_article(1, MOD_URL, TITLE, 1)
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2)
        self.db._exec(
            "INSERT INTO articles (id, url, title_original, source_id) "
            "VALUES (?, ?, ?, ?)", (3, "https://unknown.example/z/3.html", TITLE, None))
        before = self.db.article_ids()
        code, out = run_cli(self.db.path, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("REFUSED", out)
        self.assertEqual(self.db.article_ids(), before,
                         "one unresolved row protects the whole group")

    def test_one_shared_explicit_ungoverned_slug_stays_rankable(self):
        """Rule 2 is preserved: same named slug, not yet in the tier table."""
        self.db.add_source("brand_new_source", 9)
        self.db.add_article(1, "https://new.example/a/1234567.html", TITLE, 9)
        self.db.add_article(2, "https://new.example/a/1.html", TITLE, 9)
        conn = sqlite3.connect(self.db.path)
        group = find_duplicate_groups(conn)[0]
        conn.close()
        self.assertIsNone(unresolved_authority(group))
        code, out = run_cli(self.db.path, "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Deleted 1 row(s).", out)
        self.assertEqual(self.db.article_ids(), [2],
                         "shorter URL wins within one identity")


class TestDryRunLeavesNoResidueOnWalInput(_DBTest):
    """
    A dry run must be incapable of touching its input.

    A plain sqlite3.connect() writes to a WAL database just by opening it, and
    every database this project produces is in WAL mode. --dry-run now reads
    through reconcile_db.read_only(), which copies the database and sidecars to
    scratch and reads the copy.
    """

    def _make_wal_input(self):
        conn = sqlite3.connect(self.db.path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            "INSERT INTO articles (id, url, title_original, source_id) "
            "VALUES (99, 'http://www.81.cn/yw_208727/99.html', ?, 2)", (TITLE,))
        conn.commit()
        conn.close()
        self.db.add_article(1, MOD_URL, TITLE, 1)
        self.db.add_article(2, PLA_MAIN_URL, TITLE, 2)

    def _sidecars(self):
        return [p.name for p in self.db.path.parent.iterdir()
                if p.name.startswith(self.db.path.name) and p != self.db.path]

    def test_wal_input_is_byte_identical_and_gains_no_sidecar(self):
        self._make_wal_input()
        before_bytes = self.db.path.read_bytes()
        before_sidecars = sorted(self._sidecars())

        code, out = run_cli(self.db.path, "--dry-run")

        self.assertEqual(code, 0)
        self.assertIn("Dry run — no changes made", out)
        self.assertEqual(self.db.path.read_bytes(), before_bytes,
                         "dry run altered its WAL input")
        self.assertEqual(sorted(self._sidecars()), before_sidecars,
                         "dry run left sidecars beside its input")

    def test_journal_mode_of_the_input_is_unchanged(self):
        self._make_wal_input()
        conn = sqlite3.connect(self.db.path)
        mode_before = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        run_cli(self.db.path, "--dry-run")
        conn = sqlite3.connect(self.db.path)
        mode_after = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        self.assertEqual(mode_before, "wal")
        self.assertEqual(mode_after, "wal", "dry run check-pointed its input")

    def test_dry_run_succeeds_when_the_input_cannot_be_written(self):
        """
        The decisive proof. Make the database file and its directory read-only:
        a plain sqlite3.connect() on a WAL database then fails outright, because
        SQLite cannot create the -wal/-shm state it needs. read_only() copies the
        database to scratch first, so the report still works.

        Byte-comparison alone cannot catch this — a read-write connection that
        happens to read cleanly also leaves the bytes intact — which is why this
        test exists alongside the residue checks.
        """
        self._make_wal_input()
        d = self.db.path.parent
        original_dir_mode = d.stat().st_mode
        original_db_mode = self.db.path.stat().st_mode
        # Sidecars must be gone, or SQLite can reuse them and never need to write.
        for suffix in ("-wal", "-shm"):
            side = Path(str(self.db.path) + suffix)
            if side.exists():
                side.unlink()
        self.db.path.chmod(0o444)
        d.chmod(0o555)
        self.addCleanup(lambda: (d.chmod(original_dir_mode),
                                 self.db.path.chmod(original_db_mode)))

        code, out = run_cli(self.db.path, "--dry-run")

        self.assertEqual(code, 0, "dry run must not need write access to its input")
        self.assertIn("Dry run — no changes made", out)

    def test_dry_run_goes_through_read_only(self):
        """Structural: the dry-run path must use the copying helper, not connect()."""
        self._make_wal_input()
        import scripts.cleanup_duplicates as cd
        with mock.patch.object(cd, "read_only", wraps=cd.read_only) as spy:
            code, _ = run_cli(self.db.path, "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(spy.call_count, 1,
                         "--dry-run must read through reconcile_db.read_only()")

    def test_apply_still_opens_the_database_directly(self):
        """--apply is meant to write; it must not read a throwaway copy."""
        self._make_wal_input()
        import scripts.cleanup_duplicates as cd
        with mock.patch.object(cd, "read_only", wraps=cd.read_only) as spy:
            code, _ = run_cli(self.db.path, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(spy.call_count, 0, "--apply must not go through read_only()")

    def test_no_residue_even_when_the_report_raises(self):
        """read_only() is a context manager; an exception must still clean up."""
        self._make_wal_input()
        before_bytes = self.db.path.read_bytes()
        before_sidecars = sorted(self._sidecars())

        import scripts.cleanup_duplicates as cd
        with mock.patch.object(cd, "_report", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                run_cli(self.db.path, "--dry-run")

        self.assertEqual(self.db.path.read_bytes(), before_bytes)
        self.assertEqual(sorted(self._sidecars()), before_sidecars)


class TestSharedKeyIsTheOnlyDefinition(unittest.TestCase):
    """The ordering must not be re-implemented in the script."""

    def test_cleanup_does_not_define_its_own_ordering(self):
        import ast
        src = (REPO_ROOT / "scripts" / "cleanup_duplicates.py").read_text()
        tree = ast.parse(src)
        called = {
            n.func.id for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        self.assertNotIn("sorted", called,
                         "cleanup must delegate ordering to rank_canonical()")
        self.assertNotIn("source_priority", called,
                         "cleanup must not rank by the subordinate URL score")

    def test_rank_group_is_the_shared_key(self):
        rows = [
            {"url": PLA_MAIN_URL, "source_slug": "pla_daily", "title_original": TITLE},
            {"url": MOD_URL, "source_slug": "mod_china", "title_original": TITLE},
        ]
        self.assertEqual(rank_group(rows)[0], max(rows, key=canonical_sort_key))


if __name__ == "__main__":
    unittest.main()
