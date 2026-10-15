"""Synthetic tests for metadata-only Korea production schema; no live DB writes."""
import sqlite3
import unittest

from migrations.versions import m0008_korea_official_source_metadata as schema

SHA = "a" * 64
SID = "156799901"
IDENTITY = "korea-policy:" + SID
URL = "https://www.korea.kr/briefing/pressReleaseView.do?newsId=" + SID


def fields(**override):
    row = dict(
        source_identity=IDENTITY,
        canonical_official_url=URL,
        publisher_posted_date="2026-10-15",
        source_git_commit="b" * 40,
        source_db_sha256=SHA,
        candidate_version_sha256=SHA,
        original_title_sha256=SHA,
        original_text_sha256=SHA,
        publisher_html_sha256=SHA,
        original_hwpx_sha256=SHA,
        official_issuer="kr_mnd",
        official_republisher="kr_policy_briefing",
        source_language="ko",
        authority_tier="B",
        originality="syndicated",
        public_scope="held",
        admitted_at_utc=None,
        released_at_utc=None,
    )
    row.update(override)
    return row


def insert(conn, row):
    names = list(row)
    conn.execute(
        "INSERT INTO korea_official_source_records (%s) VALUES (%s)" %
        (", ".join(names), ", ".join("?" for _ in names)),
        tuple(row.values()),
    )


class KoreaOfficialSourceSchemaTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute(
            "CREATE TABLE articles (id INTEGER PRIMARY KEY, url TEXT)"
        )
        self.db.execute(
            "INSERT INTO articles VALUES (2806, 'https://existing.example/2806')"
        )
        schema.up(self.db)

    def test_no_existing_article_changed_and_no_korea_rows_invented(self):
        self.assertEqual(
            self.db.execute("SELECT id,url FROM articles").fetchall(),
            [(2806, "https://existing.example/2806")],
        )
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM korea_official_source_records"
        ).fetchone()[0], 0)
        self.assertTrue(schema.is_already_applied(self.db))
        schema.up(self.db)
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM korea_official_source_records"
        ).fetchone()[0], 0)

    def test_no_unreviewed_body_title_media_or_model_fields(self):
        actual = {x[1] for x in self.db.execute(
            "PRAGMA table_info(korea_official_source_records)"
        )}
        self.assertEqual(actual, schema.EXPECTED_COLUMNS)
        for field in (
            "title_original", "text_original", "summary_english",
            "body_original", "title_english", "text_english", "image",
            "document_blob", "model_id", "permission_granted",
            "reviewer_name",
        ):
            self.assertNotIn(field, actual)

    def test_official_link_identity_and_default_hold(self):
        insert(self.db, fields())
        stored = self.db.execute(
            "SELECT public_scope, canonical_official_url, source_language "
            "FROM korea_official_source_records"
        ).fetchone()
        self.assertEqual(stored, ("held", URL, "ko"))
        with self.assertRaises(sqlite3.IntegrityError):
            insert(self.db, fields())
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM korea_official_source_records"
        ).fetchone()[0], 1)

    def test_reject_unapproved_release_wrong_institution_or_fake_url(self):
        bad_rows = (
            fields(public_scope="official_link_only"),
            fields(public_scope="official_link_only",
                   admitted_at_utc="2026-10-15T18:00:00Z"),
            fields(official_issuer="kr_dapa"),
            fields(canonical_official_url="https://attacker.example/123"),
            fields(source_identity="korea-policy:156799901x"),
            fields(source_language="en"),
            fields(original_text_sha256="wrong"),
            fields(publisher_posted_date="20261015"),
        )
        for value in bad_rows:
            with self.subTest(value=value), self.assertRaises(sqlite3.IntegrityError):
                insert(self.db, value)

    def test_explicit_release_can_be_represented_but_not_invented_by_migration(self):
        insert(self.db, fields(
            public_scope="official_link_only",
            admitted_at_utc="2026-10-15T18:00:00Z",
            released_at_utc="2026-10-15T18:05:00Z",
        ))
        self.assertEqual(self.db.execute(
            "SELECT COUNT(*) FROM korea_official_source_records "
            "WHERE public_scope='official_link_only'"
        ).fetchone()[0], 1)
        self.assertEqual(self.db.execute(
            "SELECT id,url FROM articles"
        ).fetchall(), [(2806, "https://existing.example/2806")])


if __name__ == "__main__":
    unittest.main()
