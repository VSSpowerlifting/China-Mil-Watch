"""No-network contracts for the zero-row regional source-index migration."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from migrations.runner import apply_all, connect, discover
from migrations.versions import m0010_regional_official_source_links as migration


def row(*, family="ph_afp_articles", desk="philippines",
        url="https://www.afp.mil.ph/news/synthetic-release",
        issuer="ph_afp", publisher="ph_afp",
        source_id="afp:1234", proof="b"*64):
    return (family, source_id, desk, url, "2026-10-15",
            issuer, publisher, None, "a"*40, "c"*64, "123456-1",
            "official_link_only", proof, "2026-10-16T18:00:00Z")


FIELDS = (
    "source_family,source_identity,desk,canonical_official_url,"
    "publisher_posted_date,official_issuer,official_publisher,"
    "official_republisher,source_git_commit,metadata_version_sha256,"
    "first_seen_run,release_scope,release_proof_sha256,released_at_utc"
)


class RegionalSourceIndexMigration(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)

    def insert(self, values):
        self.conn.execute(
            "INSERT INTO regional_official_source_links ("+FIELDS+") "
            "VALUES (" + ",".join("?" for _ in range(14)) + ")", values
        )

    def test_version_is_unique_in_real_discovery(self):
        found = [m for m in discover() if m.version == "0010"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].name, migration.NAME)

    def test_creates_empty_index_and_idempotently_replays(self):
        self.assertFalse(migration.is_already_applied(self.conn))
        migration.up(self.conn)
        self.assertTrue(migration.is_already_applied(self.conn))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM regional_official_source_links"
        ).fetchone()[0], 0)
        self.assertEqual(set(r[1] for r in self.conn.execute(
            "PRAGMA table_info(regional_official_source_links)"
        )), migration.COLUMNS)
        migration.up(self.conn)
        self.assertTrue(migration.is_already_applied(self.conn))

    def test_valid_metadata_only_rows_can_be_stored(self):
        migration.up(self.conn)
        self.insert(row())
        self.insert(row(
            family="id_kemhan_news", desk="indonesia",
            source_id="kemhan:/2026/10/15/synthetic-notice.html",
            url="https://www.kemhan.go.id/2026/10/15/synthetic-notice.html",
            issuer=None, publisher="id_kemhan"
        ))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM regional_official_source_links"
        ).fetchone()[0], 2)

    def test_cross_desk_and_foreign_urls_fail_closed(self):
        migration.up(self.conn)
        invalid = (
            row(desk="indonesia"),
            row(url="https://example.invalid/news/synthetic"),
            row(issuer=None),
            row(publisher="third_party"),
            row(proof="invalid"),
        )
        for values in invalid:
            with self.subTest(invalid=values):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.insert(values)

    def test_no_source_body_or_review_authority_columns(self):
        migration.up(self.conn)
        self.assertEqual(migration.COLUMNS, {
            r[1] for r in self.conn.execute(
                "PRAGMA table_info(regional_official_source_links)"
            )
        })
        self.assertTrue(set((
            "original_title", "original_text", "capture_body",
            "pdf", "translation", "analysis", "review_approved",
            "collection_enabled",
        )).isdisjoint(migration.COLUMNS))

    def test_existing_bad_shape_is_refused_without_repair_or_data_loss(self):
        self.conn.execute(
            "CREATE TABLE regional_official_source_links (source_identity TEXT)"
        )
        self.conn.execute(
            "INSERT INTO regional_official_source_links VALUES ('sentinel')"
        )
        with self.assertRaisesRegex(ValueError, "schema drift"):
            migration.is_already_applied(self.conn)
        with self.assertRaisesRegex(ValueError, "schema drift"):
            migration.up(self.conn)
        self.assertEqual(self.conn.execute(
            "SELECT source_identity FROM regional_official_source_links"
        ).fetchone()[0], "sentinel")

    def test_full_versioned_migration_preserves_existing_corpus_and_tombstones(self):
        # Exercise real migration discovery and ledger on disposable legacy
        # schema, rather than relying solely on direct m0010.up() unit tests.
        from tests.test_migrations import build_legacy_db
        with tempfile.TemporaryDirectory(prefix="regional-index-migration-") as d:
            db_path = Path(d) / "legacy.sqlite"
            original = build_legacy_db(db_path)
            cx = connect(db_path)
            try:
                apply_all(cx)
                from migrations.runner import applied_versions
                self.assertIn("0010", applied_versions(cx))
                self.assertEqual(cx.execute(
                    "SELECT COUNT(*) FROM regional_official_source_links"
                ).fetchone()[0], 0)
                self.assertEqual(cx.execute(
                    "SELECT COUNT(*) FROM retired_article_urls"
                ).fetchone()[0], 0)
                self.assertEqual([
                    row[0] for row in cx.execute(
                        "SELECT id FROM articles ORDER BY id"
                    )
                ], original["article_ids"])
                self.assertEqual([
                    row[0] for row in cx.execute(
                        "SELECT url FROM articles ORDER BY id"
                    )
                ], original["article_urls"])
            finally:
                cx.close()

    def test_missing_index_can_be_repaired_without_changing_rows(self):
        migration.up(self.conn)
        self.insert(row())
        self.conn.execute("DROP INDEX idx_regional_official_source_family_day")
        self.assertFalse(migration.is_already_applied(self.conn))
        migration.up(self.conn)
        self.assertTrue(migration.is_already_applied(self.conn))
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) FROM regional_official_source_links"
        ).fetchone()[0], 1)


    def test_real_writer_and_public_reader_round_trip(self):
        # Check the actual production writer and renderer against migration
        # 0010, not just a hand-made INSERT into a synthetic schema. Every
        # reviewer/Actions authentication used here is FICTIONAL test data.
        from unittest.mock import patch
        from core import regional_official_link_release as release
        from core.regional_official_link_render import read_live_links
        from tests.test_regional_official_link_release import data

        migration.up(self.conn)
        self.assertEqual(migration.COLUMNS, release.EXPECTED_TABLE_COLUMNS)
        policy, packet, receipt = data("id_kemhan_news", with_hold=True)
        with patch.object(release, "load_owner_policy", return_value=policy):
            with self.assertRaisesRegex(
                release.RegionalLinkHold,
                "trusted_release_evidence_validator_missing",
            ):
                release.admit(
                    self.conn, packet, policy, receipt,
                    as_of_utc="2026-10-17T18:00:00Z",
                )
            self.assertEqual(read_live_links(self.conn, "indonesia"), [])
            # Only synthetic tests may substitute the independent reviewer.
            first = release.admit(
                self.conn, packet, policy, receipt,
                as_of_utc="2026-10-17T18:00:00Z",
                trusted_validator=lambda *_: True,
            )
            repeated = release.admit(
                self.conn, packet, policy, receipt,
                as_of_utc="2026-10-17T18:00:00Z",
                trusted_validator=lambda *_: True,
            )
        self.assertEqual(first["new_official_links"], 1)
        self.assertEqual(first["held_semantic_exceptions"], 1)
        self.assertEqual(repeated["new_official_links"], 0)
        self.assertEqual(repeated["unchanged_official_links"], 1)
        indonesia = read_live_links(self.conn, "indonesia")
        self.assertEqual(len(indonesia), 1)
        self.assertEqual(indonesia[0]["source_identity"],
                         packet["records"][0]["source_identity"]
                         if not packet["records"][0]["semantic_exception_hold"]
                         else packet["records"][1]["source_identity"])
        self.assertEqual(read_live_links(self.conn, "philippines"), [])
        self.assertNotIn("kunker-ke-kaltara",
                         indonesia[0]["canonical_official_url"])


if __name__ == "__main__":
    unittest.main()
