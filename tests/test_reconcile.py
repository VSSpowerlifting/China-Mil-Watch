"""
Reconciliation tests against the PRODUCTION `scripts/reconcile_db.py`.

These invoke the real `reconcile()` and `gates()`, not a simulation. The
previous suite simulated schema reversion by rebuilding a legacy database, which
is why it could not catch either reconciliation blocker: the merge driver was
never executed by a test at all.

Every database is a temporary file. No git, no merge-driver registration, no
network, no model calls; base/origin/local inputs are asserted unmodified.
"""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from migrations.runner import apply_all, connect, discover      # noqa: E402
from tests.test_migrations import build_legacy_db               # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "reconcile_db_under_test", REPO_ROOT / "scripts" / "reconcile_db.py"
)
rdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rdb)


# ── helpers ───────────────────────────────────────────────────────────────────

def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tables(path: Path) -> set:
    con = sqlite3.connect(str(path))
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def query(path: Path, sql: str, args=()):
    con = sqlite3.connect(str(path))
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def scrape_runs_sql(path: Path) -> str:
    return query(path, "SELECT sql FROM sqlite_master WHERE name='scrape_runs'")[0][0]


def migrate(path: Path) -> None:
    con = connect(path)
    try:
        apply_all(con)
    finally:
        con.close()


def add_run(path: Path, run_id: int, status: str = "completed") -> None:
    con = sqlite3.connect(str(path))
    con.execute(
        "INSERT INTO scrape_runs (id, status, started_at) "
        "VALUES (?, ?, datetime('now'))", (run_id, status))
    con.commit()
    con.close()


def add_article(path: Path, article_id: int, run_id: int, tag: str) -> None:
    con = sqlite3.connect(str(path))
    src = con.execute("SELECT id FROM sources WHERE slug='pla_daily'").fetchone()[0]
    con.execute(
        "INSERT INTO articles (id, url, content_hash, source_id, scrape_run_id, "
        "title_original, text_original, published_date) "
        "VALUES (?,?,?,?,?,?,?,'2026-08-01')",
        (article_id, "http://www.81.cn/x/%s.html" % tag, "hash-%s" % tag,
         src, run_id, "title %s" % tag, "body %s" % tag))
    con.commit()
    con.close()


def add_srr(path: Path, run_id: int, slug: str, status: str,
            is_failure: int = 0, new_documents: int = 0,
            error_detail=None, discovered: int = 0) -> None:
    con = sqlite3.connect(str(path))
    con.execute(
        "INSERT INTO source_run_results (scrape_run_id, source_slug, desk_id, "
        "status, is_failure, new_documents, references_discovered, "
        "error_detail, started_at, completed_at) "
        "VALUES (?,?,'china',?,?,?,?,?,datetime('now'),datetime('now'))",
        (run_id, slug, status, is_failure, new_documents, discovered,
         error_detail))
    con.commit()
    con.close()


def srr_rows(path: Path):
    if "source_run_results" not in tables(path):
        return None
    return query(
        path,
        "SELECT scrape_run_id, source_slug, status, is_failure, new_documents "
        "FROM source_run_results ORDER BY scrape_run_id, source_slug")


class ReconcileCase(unittest.TestCase):
    """Builds base/origin/local fixtures and runs the real reconciler."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.base = self.tmp / "base.db"
        build_legacy_db(self.base)
        self.origin = self.tmp / "origin.db"
        self.local = self.tmp / "local.db"
        shutil.copyfile(self.base, self.origin)
        shutil.copyfile(self.base, self.local)

    def tearDown(self):
        self._tmp.cleanup()

    def run_reconcile(self, out_name="out.db"):
        """Run reconcile()+gates(); assert inputs were not mutated."""
        before = (digest(self.base), digest(self.origin), digest(self.local))
        out = self.tmp / out_name
        con, report = rdb.reconcile(
            str(self.base), str(self.origin), str(self.local), str(out))
        problems = rdb.gates(con, str(self.origin), str(self.local), str(out))
        con.close()
        after = (digest(self.base), digest(self.origin), digest(self.local))
        self.assertEqual(before, after,
                         "reconcile() must never mutate its input databases")
        return out, report, problems


# ── 1. legacy origin + current local carrying source results ─────────────────

class TestLegacyOriginCurrentLocal(ReconcileCase):
    def setUp(self):
        super().setUp()
        add_run(self.origin, 3)
        add_article(self.origin, 4000, 3, "origin4000")
        migrate(self.local)
        add_run(self.local, 100)
        add_article(self.local, 4001, 100, "local4001")
        add_srr(self.local, 100, "pla_daily", "ok", 0, 1)
        add_srr(self.local, 100, "mod_china", "listing_failure", 1, 0,
                "listing unreachable")

    def test_output_schema_is_current_not_legacy(self):
        out, _, problems = self.run_reconcile()
        self.assertIn("source_run_results", tables(out))
        self.assertIn("schema_migrations", tables(out))
        self.assertIn("desks", tables(out))
        self.assertIn("'degraded'", scrape_runs_sql(out))
        self.assertEqual(problems, [])

    def test_migration_ledger_is_complete(self):
        out, _, _ = self.run_reconcile()
        have = {r[0] for r in query(out, "SELECT version FROM schema_migrations")}
        self.assertEqual(have, {m.version for m in discover()})

    def test_local_source_results_survive(self):
        out, report, problems = self.run_reconcile()
        rows = srr_rows(out)
        slugs = {r[1] for r in rows}
        self.assertEqual(slugs, {"pla_daily", "mod_china"})
        self.assertEqual(report["source_results_merged"], 2)
        self.assertEqual(problems, [])

    def test_structured_status_and_counts_preserved(self):
        out, _, _ = self.run_reconcile()
        row = query(out, "SELECT status, is_failure, new_documents, error_detail "
                         "FROM source_run_results WHERE source_slug='mod_china'")[0]
        self.assertEqual(row[0], "listing_failure")
        self.assertEqual(row[1], 1)
        self.assertEqual(row[2], 0)
        self.assertEqual(row[3], "listing unreachable")

    def test_articles_from_both_sides_survive(self):
        out, _, _ = self.run_reconcile()
        urls = {r[0] for r in query(out, "SELECT url FROM articles")}
        self.assertIn("http://www.81.cn/x/origin4000.html", urls)
        self.assertIn("http://www.81.cn/x/local4001.html", urls)

    def test_origin_article_ids_do_not_drift(self):
        out, _, _ = self.run_reconcile()
        got = query(out, "SELECT id FROM articles WHERE url=?",
                    ("http://www.81.cn/x/origin4000.html",))[0][0]
        self.assertEqual(got, 4000)


# ── 2. legacy origin + local carrying a 'degraded' run ───────────────────────

class TestDegradedRunAgainstPreHotfixOrigin(ReconcileCase):
    def setUp(self):
        super().setUp()
        add_run(self.origin, 3)
        migrate(self.local)
        add_run(self.local, 100, "degraded")
        add_article(self.local, 4001, 100, "local4001")
        add_srr(self.local, 100, "pla_daily", "ok", 0, 1)

    def test_degraded_run_merges_without_raising(self):
        """Previously raised IntegrityError → binary conflict in unattended CI."""
        out, _, problems = self.run_reconcile()
        statuses = {r[0] for r in query(out, "SELECT status FROM scrape_runs")}
        self.assertIn("degraded", statuses)
        self.assertEqual(problems, [])

    def test_merged_constraint_accepts_degraded(self):
        out, _, _ = self.run_reconcile()
        self.assertIn("'degraded'", scrape_runs_sql(out))


# ── 3. current origin + legacy local ─────────────────────────────────────────

class TestCurrentOriginLegacyLocal(ReconcileCase):
    def setUp(self):
        super().setUp()
        migrate(self.origin)
        add_run(self.origin, 3)
        add_article(self.origin, 4000, 3, "origin4000")
        add_srr(self.origin, 3, "pla_daily", "ok", 0, 1)
        add_run(self.local, 4)
        add_article(self.local, 4001, 4, "local4001")

    def test_origin_results_preserved_and_schema_stays_current(self):
        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        self.assertIn("'degraded'", scrape_runs_sql(out))
        self.assertEqual([r[1] for r in srr_rows(out)], ["pla_daily"])

    def test_legacy_local_article_still_merges(self):
        out, _, _ = self.run_reconcile()
        urls = {r[0] for r in query(out, "SELECT url FROM articles")}
        self.assertIn("http://www.81.cn/x/local4001.html", urls)


# ── 4 & 5. both current, unique results, colliding run ids ───────────────────

class TestBothCurrentWithCollidingRunIds(ReconcileCase):
    def setUp(self):
        super().setUp()
        migrate(self.origin)
        migrate(self.local)
        # Both sides independently allocated run id 3 — the 2026-07-30 shape.
        add_run(self.origin, 3)
        add_article(self.origin, 4000, 3, "origin4000")
        add_srr(self.origin, 3, "pla_daily", "ok", 0, 34)
        add_run(self.local, 3)
        add_article(self.local, 4001, 3, "local4001")
        add_srr(self.local, 3, "mod_china", "listing_failure", 1, 0)
        add_srr(self.local, 3, "china_mil_online", "ok_no_publications", 0, 0)

    def test_results_from_both_sides_survive(self):
        out, report, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        slugs = sorted(r[1] for r in srr_rows(out))
        self.assertEqual(slugs, ["china_mil_online", "mod_china", "pla_daily"])
        self.assertEqual(report["source_results_merged"], 2)

    def test_local_results_follow_the_run_remap(self):
        """A renumbered local run must carry its results to the new id."""
        out, _, _ = self.run_reconcile()
        local_run = query(
            out, "SELECT scrape_run_id FROM articles WHERE url=?",
            ("http://www.81.cn/x/local4001.html",))[0][0]
        self.assertNotEqual(local_run, 3, "local run should have been remapped")
        for slug in ("mod_china", "china_mil_online"):
            got = query(out, "SELECT scrape_run_id FROM source_run_results "
                             "WHERE source_slug=?", (slug,))[0][0]
            self.assertEqual(got, local_run)

    def test_origin_results_keep_their_run_id(self):
        out, _, _ = self.run_reconcile()
        got = query(out, "SELECT scrape_run_id FROM source_run_results "
                         "WHERE source_slug='pla_daily'")[0][0]
        self.assertEqual(got, 3)

    def test_no_orphaned_results(self):
        out, _, _ = self.run_reconcile()
        orphans = query(out, "SELECT COUNT(*) FROM source_run_results r "
                             "LEFT JOIN scrape_runs s ON s.id=r.scrape_run_id "
                             "WHERE s.id IS NULL")[0][0]
        self.assertEqual(orphans, 0)


# ── 6. true natural-key conflict ─────────────────────────────────────────────

class TestNaturalKeyConflict(ReconcileCase):
    def setUp(self):
        super().setUp()
        # Run 1 exists in base, so it is shared: both sides kept id 1 and each
        # recorded a result for the same source. This is the only way a genuine
        # (run, source) collision can arise.
        migrate(self.origin)
        migrate(self.local)
        add_srr(self.origin, 1, "pla_daily", "ok", 0, 34)
        add_srr(self.local, 1, "pla_daily", "listing_failure", 1, 0)
        add_srr(self.local, 1, "mod_china", "ok_no_publications", 0, 0)

    def test_origin_wins_the_conflict(self):
        out, report, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        row = query(out, "SELECT status, new_documents FROM source_run_results "
                         "WHERE scrape_run_id=1 AND source_slug='pla_daily'")
        self.assertEqual(len(row), 1, "conflict must not duplicate the key")
        self.assertEqual(row[0][0], "ok", "published/origin must win")
        self.assertEqual(row[0][1], 34)
        self.assertEqual(report["source_results_origin_won"], 1)

    def test_nonconflicting_local_row_still_merges(self):
        out, _, _ = self.run_reconcile()
        self.assertTrue(query(out, "SELECT 1 FROM source_run_results "
                                   "WHERE source_slug='mod_china'"))

    def test_no_duplicate_natural_keys(self):
        out, _, _ = self.run_reconcile()
        dupes = query(out, "SELECT COUNT(*) FROM (SELECT scrape_run_id, "
                           "source_slug FROM source_run_results "
                           "GROUP BY 1,2 HAVING COUNT(*)>1)")[0][0]
        self.assertEqual(dupes, 0)


# ── 7 & 8. pre-hotfix and ledgerless inputs ──────────────────────────────────

class TestPreHotfixAndLedgerless(ReconcileCase):
    def test_pre_hotfix_origin_against_current_local(self):
        migrate(self.local)
        add_run(self.local, 100, "degraded")
        add_srr(self.local, 100, "pla_daily", "ok", 0, 1)
        self.assertNotIn("'degraded'", scrape_runs_sql(self.origin))
        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        self.assertIn("'degraded'", scrape_runs_sql(out))

    def test_degraded_capable_origin_without_ledger(self):
        """Production's exact shape after the 2026-08-09 hand migration."""
        import migrations.versions.m0001_scrape_run_status_degraded as m1
        con = connect(self.origin)
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("BEGIN")
        m1.up(con)
        con.execute("COMMIT")
        con.close()
        self.assertNotIn("schema_migrations", tables(self.origin))

        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        have = {r[0] for r in query(out, "SELECT version FROM schema_migrations")}
        self.assertEqual(have, {m.version for m in discover()})
        self.assertEqual(
            query(out, "SELECT note FROM schema_migrations WHERE version='0001'")[0][0],
            "detected as already applied",
        )


# ── 9. idempotency ───────────────────────────────────────────────────────────

class TestIdempotency(ReconcileCase):
    def setUp(self):
        super().setUp()
        migrate(self.origin)
        migrate(self.local)
        add_run(self.origin, 3)
        add_article(self.origin, 4000, 3, "origin4000")
        add_srr(self.origin, 3, "pla_daily", "ok", 0, 34)
        add_run(self.local, 3)
        add_article(self.local, 4001, 3, "local4001")
        add_srr(self.local, 3, "mod_china", "listing_failure", 1, 0)

    def test_repeated_reconciliation_is_identical(self):
        first, _, p1 = self.run_reconcile("out1.db")
        second, _, p2 = self.run_reconcile("out2.db")
        self.assertEqual(p1, [])
        self.assertEqual(p2, [])

        def dump(path):
            con = sqlite3.connect(str(path))
            try:
                # applied_at timestamps are wall-clock; compare structure+rows.
                return "\n".join(
                    line for line in con.iterdump()
                    if "schema_migrations" not in line
                )
            finally:
                con.close()

        self.assertEqual(dump(first), dump(second))

    def test_repeated_reconciliation_does_not_duplicate_results(self):
        for name in ("out1.db", "out2.db", "out3.db"):
            out, _, _ = self.run_reconcile(name)
            self.assertEqual(len(srr_rows(out)), 2)


# ── 10. gates must reject defective output ───────────────────────────────────

class TestGatesRejectDefects(ReconcileCase):
    """
    A green gate result must be worth something. Each case below produces a
    database that the OLD gates accepted and asserts the new ones reject it.
    """

    def setUp(self):
        super().setUp()
        migrate(self.origin)
        migrate(self.local)
        add_run(self.origin, 3)
        add_srr(self.origin, 3, "pla_daily", "ok", 0, 34)
        add_run(self.local, 4)
        add_srr(self.local, 4, "mod_china", "listing_failure", 1, 0)

    def _gates_on(self, out):
        con = sqlite3.connect(str(out))
        con.row_factory = sqlite3.Row
        con.execute("ATTACH ? AS loc", (str(self.local),))
        con.execute("ATTACH ? AS bse", (str(self.base),))
        try:
            return rdb.gates(con, str(self.origin), str(self.local), str(out))
        finally:
            con.close()

    def test_baseline_output_passes(self):
        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])

    def test_missing_source_run_results_table_fails(self):
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute("DROP TABLE source_run_results")
        con.commit()
        con.close()
        problems = self._gates_on(out)
        self.assertTrue(any("source_run_results" in p for p in problems))

    def test_incomplete_migration_ledger_fails(self):
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute("DELETE FROM schema_migrations WHERE version='0004'")
        con.commit()
        con.close()
        problems = self._gates_on(out)
        self.assertTrue(any("ledger incomplete" in p for p in problems))

    def test_lost_local_result_fails(self):
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute("DELETE FROM source_run_results WHERE source_slug='mod_china'")
        con.commit()
        con.close()
        problems = self._gates_on(out)
        self.assertTrue(any("local source_run_result" in p for p in problems))

    def test_lost_origin_result_fails(self):
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute("DELETE FROM source_run_results WHERE source_slug='pla_daily'")
        con.commit()
        con.close()
        problems = self._gates_on(out)
        self.assertTrue(any("origin source_run_result" in p for p in problems))

    def test_unsupported_run_status_fails(self):
        """
        A merged CHECK that cannot represent a status present in an input must
        fail — the exact schema regression a legacy origin used to produce.
        """
        add_run(self.local, 5, "degraded")
        out, _, _ = self.run_reconcile()

        # Rebuild the merged scrape_runs with the pre-hotfix CHECK, dropping the
        # degraded row so the copy is accepted. The input still carries it.
        con = sqlite3.connect(str(out))
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("PRAGMA legacy_alter_table=ON")
        con.execute("DELETE FROM scrape_runs WHERE status='degraded'")
        con.execute(
            "CREATE TABLE runs_old (id INTEGER PRIMARY KEY, started_at TEXT, "
            "completed_at TEXT, articles_scraped INTEGER, articles_new INTEGER, "
            "articles_analyzed INTEGER, errors TEXT, status TEXT NOT NULL "
            "CHECK (status IN ('running','completed','failed')))")
        con.execute(
            "INSERT INTO runs_old SELECT id, started_at, completed_at, "
            "articles_scraped, articles_new, articles_analyzed, errors, status "
            "FROM scrape_runs")
        con.execute("DROP TABLE scrape_runs")
        con.execute("ALTER TABLE runs_old RENAME TO scrape_runs")
        con.commit()
        con.close()

        problems = self._gates_on(out)
        self.assertTrue(
            any("does not accept status 'degraded'" in p for p in problems),
            "gates missed a CHECK that cannot represent an input status: %s"
            % problems,
        )

    def test_schema_prevents_duplicate_natural_keys(self):
        """The table's UNIQUE constraint is the first line of defence."""
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        try:
            run_id = con.execute(
                "SELECT scrape_run_id FROM source_run_results "
                "WHERE source_slug='pla_daily'").fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute(
                    "INSERT INTO source_run_results (scrape_run_id, source_slug, "
                    "status, is_failure) VALUES (?, 'pla_daily', 'ok', 0)",
                    (run_id,))
        finally:
            con.close()

    def test_duplicate_natural_key_fails_gates(self):
        """
        Defence in depth: if the UNIQUE constraint were ever absent, the gate
        must still catch a duplicated (run, source) observation.
        """
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute("PRAGMA legacy_alter_table=ON")
        con.execute(
            "CREATE TABLE srr_nouniq (id INTEGER PRIMARY KEY, "
            "scrape_run_id INTEGER NOT NULL REFERENCES scrape_runs(id) "
            "ON DELETE CASCADE, source_slug TEXT NOT NULL, desk_id TEXT, "
            "status TEXT NOT NULL, is_failure INTEGER NOT NULL DEFAULT 0, "
            "started_at TEXT, completed_at TEXT, "
            "references_discovered INTEGER NOT NULL DEFAULT 0, "
            "fetched INTEGER NOT NULL DEFAULT 0, "
            "extracted INTEGER NOT NULL DEFAULT 0, "
            "duplicates INTEGER NOT NULL DEFAULT 0, "
            "new_documents INTEGER NOT NULL DEFAULT 0, "
            "relevance_rejected INTEGER NOT NULL DEFAULT 0, "
            "failed_fetches INTEGER NOT NULL DEFAULT 0, error_detail TEXT)")
        cols = ("scrape_run_id, source_slug, desk_id, status, is_failure, "
                "started_at, completed_at, references_discovered, fetched, "
                "extracted, duplicates, new_documents, relevance_rejected, "
                "failed_fetches, error_detail")
        con.execute("INSERT INTO srr_nouniq (%s) SELECT %s FROM source_run_results"
                    % (cols, cols))
        con.execute("DROP TABLE source_run_results")
        con.execute("ALTER TABLE srr_nouniq RENAME TO source_run_results")
        con.execute(
            "INSERT INTO source_run_results (scrape_run_id, source_slug, status, "
            "is_failure) VALUES ((SELECT scrape_run_id FROM source_run_results "
            "WHERE source_slug='pla_daily'), 'pla_daily', 'ok', 0)")
        con.commit()
        con.close()
        problems = self._gates_on(out)
        self.assertTrue(any("duplicate source_run_result" in p for p in problems))

    def test_missing_desks_table_fails(self):
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute("DROP TABLE institutions")
        con.execute("DROP TABLE desks")
        con.commit()
        con.close()
        problems = self._gates_on(out)
        self.assertTrue(any("'desks' is missing" in p for p in problems))


if __name__ == "__main__":
    unittest.main(verbosity=2)


# ── Orphan lineage: the review's exact failing variants ──────────────────────

class TestOrphanLineageFailsLoudly(ReconcileCase):
    """
    A local `source_run_results` row whose run lineage cannot be proven must
    abort reconciliation.

    Previously these were dropped with a log line and the merge continued. Two
    of the three variants below then passed every gate: the local-loss check
    asked only whether the slug appeared *somewhere* in the output, so any
    dropped row whose slug existed elsewhere was invisible. The third was worse
    than loss — the row attached to an unrelated origin run that happened to
    share the dangling numeric id, misfiling analytical provenance.
    """

    def setUp(self):
        super().setUp()
        migrate(self.origin)
        migrate(self.local)

    def _dangle(self, run_id, slug, status="ok"):
        """Write an srr row referencing a run that does not exist locally."""
        con = sqlite3.connect(str(self.local))
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute(
            "INSERT INTO source_run_results (scrape_run_id, source_slug, "
            "desk_id, status, is_failure) VALUES (?,?, 'china', ?, 0)",
            (run_id, slug, status))
        con.commit()
        con.close()

    def _reconcile_without_preflight(self, out_name="out.db"):
        """
        Reach the lineage guard with input validation disabled.

        A dangling result IS a foreign-key violation, so the preflight added
        alongside this guard catches these inputs first (asserted separately
        below). Bypassing it here proves the second line of defence in its own
        right, rather than leaving it untested behind the first.
        """
        out = self.tmp / out_name
        original = rdb.validate_inputs
        rdb.validate_inputs = lambda *a, **k: None
        try:
            return rdb.reconcile(str(self.base), str(self.origin),
                                 str(self.local), str(out)), out
        finally:
            rdb.validate_inputs = original

    def test_A_dangling_run_slug_absent_elsewhere(self):
        self._dangle(999, "china_mil_online")
        with self.assertRaises(SystemExit) as ctx:
            self._reconcile_without_preflight()
        self.assertIn("lineage", str(ctx.exception).lower())

    def test_B_dangling_run_slug_present_on_unrelated_origin_run(self):
        """Slug presence elsewhere must not conceal the loss."""
        add_run(self.origin, 3)
        add_srr(self.origin, 3, "pla_daily", "ok", 0, 34)
        self._dangle(999, "pla_daily", "listing_failure")
        with self.assertRaises(SystemExit) as ctx:
            self._reconcile_without_preflight()
        self.assertIn("lineage", str(ctx.exception).lower())

    def test_C_dangling_run_id_collides_with_real_origin_run(self):
        """Must not attach to the unrelated origin run that shares the id."""
        add_run(self.origin, 500)
        self._dangle(500, "mod_china", "listing_failure")
        with self.assertRaises(SystemExit) as ctx:
            self._reconcile_without_preflight()
        self.assertIn("lineage", str(ctx.exception).lower())

    def test_C_does_not_misattribute_before_aborting(self):
        add_run(self.origin, 500)
        self._dangle(500, "mod_china", "listing_failure")
        with self.assertRaises(SystemExit):
            (_, out) = self._reconcile_without_preflight("never.db")
        out = self.tmp / "never.db"
        if out.exists() and "source_run_results" in tables(out):
            rows = query(out, "SELECT scrape_run_id, source_slug FROM "
                              "source_run_results WHERE scrape_run_id=500")
            self.assertEqual(rows, [], "observation attached to an unrelated run")

    def test_preflight_also_rejects_these_inputs(self):
        """A dangling result is an FK violation; validation catches it first."""
        self._dangle(999, "china_mil_online")
        with self.assertRaises(SystemExit) as ctx:
            self.run_reconcile()
        self.assertIn("foreign key", str(ctx.exception).lower())

    def test_D_valid_local_only_run_succeeds_and_follows_remap(self):
        add_run(self.origin, 3)
        add_run(self.local, 3)                 # colliding id -> remapped
        add_srr(self.local, 3, "mod_china", "listing_failure", 1, 0)
        out, report, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        row = query(out, "SELECT scrape_run_id FROM source_run_results "
                         "WHERE source_slug='mod_china'")
        self.assertNotEqual(row[0][0], 3, "local run should have been remapped")

    def test_E_base_authored_shared_run_succeeds(self):
        """Run 1 exists in base: both sides keep it; origin wins a conflict."""
        add_srr(self.origin, 1, "pla_daily", "ok", 0, 34)
        add_srr(self.local, 1, "pla_daily", "listing_failure", 1, 0)
        add_srr(self.local, 1, "mod_china", "ok_no_publications", 0, 0)
        out, report, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        got = dict(query(out, "SELECT source_slug, status FROM source_run_results"))
        self.assertEqual(got["pla_daily"], "ok", "origin must win the conflict")
        self.assertEqual(got["mod_china"], "ok_no_publications")


class TestGatesDetectTamperedOutput(ReconcileCase):
    """
    Gates must catch an incorrect final result independently of reconcile().
    Each case mutates a correctly merged database and re-runs gates.
    """

    def setUp(self):
        super().setUp()
        migrate(self.origin)
        migrate(self.local)
        add_run(self.origin, 3)
        add_srr(self.origin, 3, "pla_daily", "ok", 0, 34)
        add_run(self.local, 4)
        add_srr(self.local, 4, "mod_china", "listing_failure", 1, 0)

    def _gates_on(self, out):
        con = sqlite3.connect(str(out))
        con.row_factory = sqlite3.Row
        con.execute("ATTACH ? AS loc", (str(self.local),))
        con.execute("ATTACH ? AS bse", (str(self.base),))
        try:
            return rdb.gates(con, str(self.origin), str(self.local), str(out))
        finally:
            con.close()

    def test_F_removing_a_merged_result_is_detected(self):
        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        con = sqlite3.connect(str(out))
        con.execute("DELETE FROM source_run_results WHERE source_slug='mod_china'")
        con.commit()
        con.close()
        found = self._gates_on(out)
        self.assertTrue(any("local source_run_result" in p for p in found), found)

    def test_G_altering_a_payload_is_detected(self):
        """Same natural key, corrupted substance."""
        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        con = sqlite3.connect(str(out))
        con.execute("UPDATE source_run_results SET status='ok', is_failure=0 "
                    "WHERE source_slug='mod_china'")
        con.commit()
        con.close()
        found = self._gates_on(out)
        self.assertTrue(any("unaccounted" in p or "altered" in p for p in found),
                        found)

    def test_G_altering_an_origin_payload_is_detected(self):
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute("UPDATE source_run_results SET new_documents=999 "
                    "WHERE source_slug='pla_daily'")
        con.commit()
        con.close()
        found = self._gates_on(out)
        self.assertTrue(any("altered" in p for p in found), found)

    def test_H_an_unexpected_extra_result_is_rejected(self):
        out, _, _ = self.run_reconcile()
        con = sqlite3.connect(str(out))
        con.execute(
            "INSERT INTO source_run_results (scrape_run_id, source_slug, status, "
            "is_failure) VALUES (3, 'global_times_mil', 'ok', 0)")
        con.commit()
        con.close()
        found = self._gates_on(out)
        self.assertTrue(any("neither input" in p for p in found), found)


# ── Article source attribution ───────────────────────────────────────────────

class TestArticleSourceAttribution(ReconcileCase):
    def setUp(self):
        super().setUp()
        migrate(self.origin)
        migrate(self.local)

    def _renumber_local_source(self, slug, new_id):
        con = sqlite3.connect(str(self.local))
        con.execute("PRAGMA foreign_keys=OFF")
        old = con.execute("SELECT id FROM sources WHERE slug=?", (slug,)).fetchone()[0]
        con.execute("UPDATE sources SET id=? WHERE slug=?", (new_id, slug))
        con.execute("UPDATE articles SET source_id=? WHERE source_id=?",
                    (new_id, old))
        con.commit()
        con.close()

    def test_same_slug_different_numeric_ids_maps_correctly(self):
        self._renumber_local_source("pla_daily", 77)
        add_run(self.local, 50)
        add_article(self.local, 6000, 50, "sid6000")
        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        row = query(out, "SELECT s.slug FROM articles a JOIN sources s "
                         "ON s.id=a.source_id WHERE a.url LIKE '%sid6000%'")
        self.assertEqual(row[0][0], "pla_daily")

    def test_colliding_numeric_ids_do_not_cross_attribute(self):
        """
        Local `pla_daily` renumbered onto origin's `mod_china` id. Carrying the
        numeric id verbatim used to file the article under mod_china silently.
        The local database stays internally consistent throughout — this is a
        legitimate divergence, not a corrupt input.
        """
        mod_id = query(self.origin,
                       "SELECT id FROM sources WHERE slug='mod_china'")[0][0]
        pd_id = query(self.origin,
                      "SELECT id FROM sources WHERE slug='pla_daily'")[0][0]
        con = sqlite3.connect(str(self.local))
        con.execute("PRAGMA foreign_keys=OFF")
        # mod_china out of the way, then pla_daily onto mod_china's old id,
        # moving that source's articles with it so no FK dangles.
        con.execute("UPDATE sources SET id=900 WHERE slug='mod_china'")
        con.execute("UPDATE articles SET source_id=900 WHERE source_id=?", (mod_id,))
        con.execute("UPDATE sources SET id=? WHERE slug='pla_daily'", (mod_id,))
        con.execute("UPDATE articles SET source_id=? WHERE source_id=?",
                    (mod_id, pd_id))
        con.execute("INSERT INTO scrape_runs (id,status) VALUES (51,'completed')")
        con.execute(
            "INSERT INTO articles (id,url,content_hash,source_id,scrape_run_id,"
            "title_original,text_original,published_date) VALUES "
            "(6001,'http://www.81.cn/x/collide.html','hc',?,51,'t','b','2026-08-01')",
            (mod_id,))
        con.commit()
        con.close()

        out, _, problems = self.run_reconcile()
        self.assertEqual(problems, [])
        row = query(out, "SELECT s.slug FROM articles a JOIN sources s "
                         "ON s.id=a.source_id WHERE a.url LIKE '%collide%'")
        self.assertEqual(row[0][0], "pla_daily",
                         "article must follow its slug, not a numeric id")

    def test_local_only_article_gets_the_output_id_for_its_slug(self):
        add_run(self.local, 52)
        add_article(self.local, 6002, 52, "localonly")
        out, _, _ = self.run_reconcile()
        expected = query(out, "SELECT id FROM sources WHERE slug='pla_daily'")[0][0]
        got = query(out, "SELECT source_id FROM articles WHERE url LIKE "
                         "'%localonly%'")[0][0]
        self.assertEqual(got, expected)

    def test_missing_output_slug_fails_loudly(self):
        con = sqlite3.connect(str(self.local))
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("INSERT INTO sources (id, slug, display_name, base_url, "
                    "language) VALUES (300, 'unknown_local_src', 'X', "
                    "'https://x.invalid', 'zh')")
        con.execute("INSERT INTO scrape_runs (id,status) VALUES (53,'completed')")
        con.execute(
            "INSERT INTO articles (id,url,content_hash,source_id,scrape_run_id,"
            "title_original,text_original,published_date) VALUES "
            "(6003,'http://www.81.cn/x/unknownsrc.html','hu',300,53,'t','b','2026-08-01')")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit) as ctx:
            self.run_reconcile()
        self.assertIn("does not exist in the merged database", str(ctx.exception))

    def test_shared_url_with_conflicting_slug_fails_loudly(self):
        url = "http://www.81.cn/article/1.html"      # exists in both from base
        con = sqlite3.connect(str(self.local))
        con.execute("PRAGMA foreign_keys=OFF")
        other = con.execute(
            "SELECT id FROM sources WHERE slug='global_times_mil'").fetchone()[0]
        con.execute("UPDATE articles SET source_id=? WHERE url=?", (other, url))
        con.commit()
        con.close()
        with self.assertRaises(SystemExit) as ctx:
            self.run_reconcile()
        self.assertIn("conflicting", str(ctx.exception).lower())

    def test_existing_attribution_is_unchanged(self):
        before = dict(query(self.origin,
                            "SELECT a.url, s.slug FROM articles a JOIN sources s "
                            "ON s.id=a.source_id"))
        out, _, problems = self.run_reconcile()
        after = dict(query(out, "SELECT a.url, s.slug FROM articles a JOIN "
                                "sources s ON s.id=a.source_id"))
        self.assertEqual(problems, [])
        for url, slug in before.items():
            self.assertEqual(after[url], slug)


# ── Malformed input preflight ────────────────────────────────────────────────

class TestInputValidation(ReconcileCase):
    def test_legacy_input_is_valid(self):
        """Missing newer tables must NOT fail preflight."""
        rdb.validate_inputs(str(self.base), str(self.origin), str(self.local))

    def test_missing_legacy_table_fails(self):
        con = sqlite3.connect(str(self.local))
        con.execute("DROP TABLE article_categories")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit) as ctx:
            rdb.validate_inputs(str(self.base), str(self.origin), str(self.local))
        self.assertIn("article_categories", str(ctx.exception))

    def test_dangling_foreign_key_fails(self):
        con = sqlite3.connect(str(self.local))
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute("INSERT INTO articles (id,url,content_hash,source_id,"
                    "scrape_run_id,title_original,text_original,published_date) "
                    "VALUES (7777,'http://x/y','h',424242,1,'t','b','2026-08-01')")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit) as ctx:
            rdb.validate_inputs(str(self.base), str(self.origin), str(self.local))
        self.assertIn("foreign key", str(ctx.exception).lower())

    def test_structurally_unreadable_newer_table_fails(self):
        con = sqlite3.connect(str(self.local))
        con.execute("CREATE TABLE source_run_results (id INTEGER PRIMARY KEY)")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit) as ctx:
            rdb.validate_inputs(str(self.base), str(self.origin), str(self.local))
        self.assertIn("lacks", str(ctx.exception))

    def test_validation_does_not_modify_inputs(self):
        migrate(self.local)     # leaves a WAL beside the file
        before = (digest(self.base), digest(self.origin), digest(self.local))
        rdb.validate_inputs(str(self.base), str(self.origin), str(self.local))
        after = (digest(self.base), digest(self.origin), digest(self.local))
        self.assertEqual(before, after)

    def test_reconcile_refuses_a_malformed_input(self):
        con = sqlite3.connect(str(self.local))
        con.execute("DROP TABLE categories")
        con.commit()
        con.close()
        with self.assertRaises(SystemExit):
            self.run_reconcile()


# ── Merge-driver failure behaviour ───────────────────────────────────────────

class TestMergeDriverFailureCleanup(unittest.TestCase):
    """
    A failed merge must leave git's conflict exactly as it was, and must not
    leave a temporary reconciled database behind.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.ancestor = self.tmp / "anc.db"
        self.current = self.tmp / "cur.db"
        self.other = self.tmp / "oth.db"
        build_legacy_db(self.ancestor)
        shutil.copyfile(self.ancestor, self.current)
        shutil.copyfile(self.ancestor, self.other)

    def tearDown(self):
        self._tmp.cleanup()

    def test_malformed_input_exits_nonzero_and_cleans_up(self):
        # Break `other` so validation refuses.
        con = sqlite3.connect(str(self.other))
        con.execute("DROP TABLE sources")
        con.commit()
        con.close()

        current_before = digest(self.current)
        other_before = digest(self.other)

        # Identify `current` as the published side without touching git.
        original = rdb._published_side
        rdb._published_side = lambda a, b: a
        try:
            rc = rdb.merge_driver(str(self.ancestor), str(self.current),
                                  str(self.other))
        finally:
            rdb._published_side = original

        self.assertEqual(rc, 1, "merge driver must fail on a malformed input")
        self.assertEqual(digest(self.current), current_before,
                         "the git merge target must be left untouched")
        self.assertEqual(digest(self.other), other_before)
        tmp_db = Path(str(self.current) + ".reconciled")
        self.assertFalse(tmp_db.exists(), "temporary reconciled DB left behind")
        for suffix in ("-wal", "-shm"):
            self.assertFalse(Path(str(tmp_db) + suffix).exists())

    def test_successful_driver_run_replaces_the_target(self):
        original = rdb._published_side
        rdb._published_side = lambda a, b: a
        try:
            rc = rdb.merge_driver(str(self.ancestor), str(self.current),
                                  str(self.other))
        finally:
            rdb._published_side = original
        self.assertEqual(rc, 0)
        self.assertFalse(Path(str(self.current) + ".reconciled").exists())
        self.assertIn("schema_migrations", tables(self.current))
