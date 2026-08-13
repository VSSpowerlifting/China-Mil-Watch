"""
Migration tests.

Every test builds its own throwaway database from
`tests/fixtures/legacy_schema.sql` — which is not a hand-written approximation
of the old schema but the real `storage/schema.sql` as it stood at the commit
before `'degraded'` was introduced, extracted from git history. Nothing here
touches the production database or the network.

The property under test throughout: **a migration must preserve every existing
record and identifier.** Article ids are published as `output/article/<id>.html`
and referenced by the sitemap and feed, so a migration that renumbers them
breaks live URLs.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from migrations.runner import (            # noqa: E402
    MigrationError, apply_all, applied_versions, connect, discover, verify,
)

LEGACY_SCHEMA = REPO_ROOT / "tests" / "fixtures" / "legacy_schema.sql"


def build_legacy_db(path: Path, articles: int = 12) -> dict:
    """
    Create a database with the pre-migration schema and representative rows.

    Returns a fingerprint of what was written, so tests can assert preservation
    rather than merely "it did not crash".
    """
    conn = sqlite3.connect(str(path))
    conn.executescript(LEGACY_SCHEMA.read_text(encoding="utf-8"))

    conn.execute(
        "INSERT INTO scrape_runs (id, started_at, completed_at, "
        "articles_scraped, articles_new, articles_analyzed, status) "
        "VALUES (1, '2026-05-07 12:00:00', '2026-05-07 12:30:00', 30, 30, 10, "
        "'completed')"
    )
    conn.execute(
        "INSERT INTO scrape_runs (id, started_at, status) "
        "VALUES (2, '2026-05-08 12:00:00', 'failed')"
    )

    src = conn.execute(
        "SELECT id FROM sources WHERE slug = 'pla_daily'"
    ).fetchone()[0]

    # Non-contiguous ids on purpose: production has gaps (deleted duplicates,
    # reconciler renumbering), and a migration that "tidies" them would break
    # every published article URL.
    ids = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 2806][:articles]
    for i, aid in enumerate(ids):
        conn.execute(
            "INSERT INTO articles (id, url, content_hash, source_id, "
            "scrape_run_id, title_original, text_original, published_date, "
            "passed_relevance, analyzed_at, model_id, prompt_version) "
            "VALUES (?, ?, ?, ?, 1, ?, ?, '2026-05-07', ?, ?, ?, ?)",
            (aid, "http://www.81.cn/article/%d.html" % aid, "hash%d" % aid, src,
             "标题 %d" % aid, "正文内容 %d" % aid,
             1 if i % 2 == 0 else 0,
             "2026-05-07 13:00:00" if i % 2 == 0 else None,
             "claude-sonnet-4-6" if i % 2 == 0 else None,
             "v1" if i % 2 == 0 else None),
        )
        cat = conn.execute(
            "SELECT id FROM categories WHERE slug = 'taiwan'"
        ).fetchone()[0]
        if i % 3 == 0:
            conn.execute(
                "INSERT INTO article_categories (article_id, category_id) "
                "VALUES (?, ?)", (aid, cat),
            )

    conn.commit()
    fp = fingerprint(conn)
    conn.close()
    return fp


def fingerprint(conn: sqlite3.Connection) -> dict:
    """Everything a migration must not change."""
    return {
        "article_ids": [r[0] for r in conn.execute(
            "SELECT id FROM articles ORDER BY id")],
        "article_urls": [r[0] for r in conn.execute(
            "SELECT url FROM articles ORDER BY id")],
        "article_count": conn.execute(
            "SELECT COUNT(*) FROM articles").fetchone()[0],
        "run_ids": [r[0] for r in conn.execute(
            "SELECT id FROM scrape_runs ORDER BY id")],
        "run_statuses": [r[0] for r in conn.execute(
            "SELECT status FROM scrape_runs ORDER BY id")],
        "source_slugs": [r[0] for r in conn.execute(
            "SELECT slug FROM sources ORDER BY slug")],
        "category_slugs": [r[0] for r in conn.execute(
            "SELECT slug FROM categories ORDER BY slug")],
        "article_categories": conn.execute(
            "SELECT COUNT(*) FROM article_categories").fetchone()[0],
        "provenance": [tuple(r) for r in conn.execute(
            "SELECT id, model_id, prompt_version, passed_relevance, analyzed_at "
            "FROM articles ORDER BY id")],
    }


class MigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmp.name) / "test.db"
        self.before = build_legacy_db(self.db_path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def open(self) -> sqlite3.Connection:
        return connect(self.db_path)


class TestLegacyFixture(MigrationTestCase):
    def test_fixture_really_is_the_legacy_schema(self):
        """The fixture must lack 'degraded' — otherwise 0001 tests nothing."""
        conn = self.open()
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='scrape_runs'"
        ).fetchone()[0]
        self.assertNotIn("degraded", sql)
        self.assertIsNone(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='schema_migrations'"
            ).fetchone(),
            "legacy fixture must not already have a migrations table",
        )
        conn.close()

    def test_legacy_db_rejects_degraded(self):
        conn = self.open()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO scrape_runs (status) VALUES ('degraded')")
        conn.close()


class TestApply(MigrationTestCase):
    def test_migrates_successfully(self):
        conn = self.open()
        report = apply_all(conn)
        self.assertTrue(report["applied"], "expected migrations to be applied")
        self.assertEqual(report["skipped"], [])
        conn.close()

    def test_all_discovered_migrations_are_applied(self):
        conn = self.open()
        apply_all(conn)
        applied = set(applied_versions(conn))
        expected = {m.version for m in discover()}
        self.assertEqual(applied, expected)
        conn.close()

    def test_degraded_accepted_after_migration(self):
        conn = self.open()
        apply_all(conn)
        conn.execute("BEGIN")
        conn.execute("INSERT INTO scrape_runs (status) VALUES ('degraded')")
        conn.execute("ROLLBACK")
        conn.close()

    def test_invalid_status_still_rejected_after_migration(self):
        conn = self.open()
        apply_all(conn)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO scrape_runs (status) VALUES ('nonsense')")
        conn.close()

    def test_records_preserved(self):
        """Article, source, category and run rows all survive unchanged."""
        conn = self.open()
        apply_all(conn)
        after = fingerprint(conn)
        conn.close()

        self.assertEqual(after["article_ids"], self.before["article_ids"])
        self.assertEqual(after["article_urls"], self.before["article_urls"])
        self.assertEqual(after["article_count"], self.before["article_count"])
        self.assertEqual(after["run_ids"], self.before["run_ids"])
        self.assertEqual(after["run_statuses"], self.before["run_statuses"])
        self.assertEqual(after["category_slugs"], self.before["category_slugs"])
        self.assertEqual(
            after["article_categories"], self.before["article_categories"]
        )

    def test_article_ids_and_urls_are_identical(self):
        """Published URLs are derived from article ids; renumbering breaks them."""
        conn = self.open()
        apply_all(conn)
        rows = conn.execute("SELECT id, url FROM articles ORDER BY id").fetchall()
        conn.close()
        self.assertEqual([r[0] for r in rows], self.before["article_ids"])
        self.assertEqual([r[1] for r in rows], self.before["article_urls"])

    def test_model_and_prompt_provenance_retained(self):
        conn = self.open()
        apply_all(conn)
        after = fingerprint(conn)
        conn.close()
        self.assertEqual(after["provenance"], self.before["provenance"])

    def test_all_sources_assigned_to_china_desk(self):
        conn = self.open()
        apply_all(conn)
        rows = conn.execute("SELECT slug, desk_id FROM sources ORDER BY slug").fetchall()
        unassigned = [slug for slug, desk in rows if desk is None]
        conn.close()
        self.assertEqual(unassigned, [], "every legacy source must get a desk")
        self.assertTrue(all(desk == "china" for _, desk in rows))

    def test_language_tags_backfilled_without_dropping_legacy_column(self):
        conn = self.open()
        apply_all(conn)
        rows = conn.execute(
            "SELECT slug, language, language_tag FROM sources ORDER BY slug"
        ).fetchall()
        conn.close()
        for slug, legacy, tag in rows:
            self.assertIsNotNone(legacy, "%s lost its legacy language" % slug)
            self.assertIsNotNone(tag, "%s has no BCP 47 tag" % slug)
            self.assertIn(tag, ("zh-Hans", "en"))
            self.assertTrue(tag.startswith(legacy))

    def test_no_orphans_and_integrity_ok(self):
        conn = self.open()
        apply_all(conn)
        report = verify(conn)
        conn.close()
        self.assertEqual(report["integrity_check"], "ok")
        self.assertEqual(report["foreign_key_violations"], 0)
        for name, count in report["orphans"].items():
            self.assertEqual(count, 0, "orphan check %s found %d" % (name, count))
        self.assertTrue(report["ok"])

    def test_new_tables_created(self):
        conn = self.open()
        apply_all(conn)
        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        for expected in ("desks", "institutions", "source_run_results",
                         "schema_migrations"):
            self.assertIn(expected, names)

    def test_desk_and_institutions_populated_from_manifest(self):
        conn = self.open()
        apply_all(conn)
        desks = conn.execute("SELECT desk_id, public_status FROM desks").fetchall()
        insts = conn.execute("SELECT COUNT(*) FROM institutions").fetchone()[0]
        conn.close()
        self.assertEqual(desks, [("china", "legacy")])
        self.assertGreaterEqual(insts, 4)


class TestIdempotency(MigrationTestCase):
    def test_second_run_is_detected_as_applied(self):
        conn = self.open()
        apply_all(conn)
        second = apply_all(conn)
        conn.close()
        self.assertEqual(second["applied"], [])
        self.assertEqual(
            sorted(second["skipped"]), sorted(m.version for m in discover())
        )

    def test_second_run_changes_no_data(self):
        conn = self.open()
        apply_all(conn)
        after_first = fingerprint(conn)
        apply_all(conn)
        after_second = fingerprint(conn)
        conn.close()
        self.assertEqual(after_first, after_second)

    def test_already_migrated_db_is_detected_without_reapplying(self):
        """
        A database that already has the change but no schema_migrations row —
        exactly the production state after the 2026-08-09 hand migration — must
        be recorded, not rebuilt.
        """
        conn = self.open()
        apply_all(conn)
        conn.execute("DELETE FROM schema_migrations")
        report = apply_all(conn)
        conn.close()
        self.assertEqual(report["applied"], [])
        self.assertEqual(
            sorted(report["already_present"]),
            sorted(m.version for m in discover()),
        )


class TestReconcileReversion(MigrationTestCase):
    """
    The failure mode this framework exists for.

    `scripts/reconcile_db.py` resolves a diverged database by copying the
    *published* side's file, so a rebase onto an origin that predates a schema
    change silently restores the older shape (DECISION_LOG 2026-08-09 §7).
    Re-running migrations must fully restore the schema and all config-derived
    state, with the article corpus untouched.
    """

    def test_schema_reversion_is_fully_recoverable(self):
        conn = self.open()
        apply_all(conn)
        migrated = fingerprint(conn)
        conn.close()

        # Simulate the reconcile: origin's older file wins wholesale.
        reverted = self.db_path.parent / "reverted.db"
        build_legacy_db(reverted)

        conn = connect(reverted)
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='scrape_runs'"
        ).fetchone()[0]
        self.assertNotIn("degraded", sql, "precondition: schema is reverted")

        report = apply_all(conn)
        self.assertTrue(report["applied"], "re-migration must reapply the schema")

        restored = fingerprint(conn)
        v = verify(conn)
        desks = conn.execute("SELECT COUNT(*) FROM desks").fetchone()[0]
        sources_with_desk = conn.execute(
            "SELECT COUNT(*) FROM sources WHERE desk_id IS NOT NULL"
        ).fetchone()[0]
        conn.close()

        self.assertEqual(restored["article_ids"], migrated["article_ids"])
        self.assertEqual(restored["article_urls"], migrated["article_urls"])
        self.assertTrue(v["ok"])
        self.assertEqual(desks, 1)
        self.assertEqual(sources_with_desk, 5)


class TestRollback(MigrationTestCase):
    """A failing migration must leave no partial state behind."""

    def test_failed_migration_rolls_back_and_is_not_recorded(self):
        import types

        from migrations import runner

        boom = types.SimpleNamespace(
            VERSION="9999",
            NAME="deliberately_failing",
            __file__=str(REPO_ROOT / "migrations" / "runner.py"),
        )

        def bad_up(conn):
            conn.execute("CREATE TABLE half_created (x INTEGER)")
            raise RuntimeError("simulated failure partway through")

        boom.up = bad_up
        real_discover = runner.discover

        def patched():
            return real_discover() + [runner.Migration(boom)]

        runner.discover = patched
        try:
            conn = self.open()
            with self.assertRaises(MigrationError):
                apply_all(conn)

            leftover = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='half_created'"
            ).fetchone()
            recorded = "9999" in applied_versions(conn)
            corpus_intact = fingerprint(conn)["article_ids"]
            conn.close()
        finally:
            runner.discover = real_discover

        self.assertIsNone(leftover, "partial table survived a rolled-back migration")
        self.assertFalse(recorded, "a failed migration must not be recorded")
        self.assertEqual(corpus_intact, self.before["article_ids"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
