"""No China cull may mutate independent live U.S. metadata records."""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.verify_china_retirement_crossdesk import validate


class LiveUSMetadataSurvivors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old = Path(self.tmp.name) / "before.db"
        self.new = Path(self.tmp.name) / "after.db"
        with sqlite3.connect(self.old) as db:
            db.executescript("""
                CREATE TABLE sources(id INTEGER PRIMARY KEY, slug TEXT NOT NULL);
                INSERT INTO sources VALUES (1, 'mod_china');
                INSERT INTO sources VALUES (2, 'uscc_press');
                CREATE TABLE uscc_official_source_records(
                    source_identity TEXT PRIMARY KEY, source_url TEXT NOT NULL,
                    issuer TEXT NOT NULL);
                CREATE TABLE uscc_official_observations(
                    observed_on_utc TEXT NOT NULL, source_identity TEXT NOT NULL);
                CREATE TABLE treasury_official_source_records(
                    source_identity TEXT PRIMARY KEY, source_url TEXT NOT NULL,
                    issuer TEXT NOT NULL);
                CREATE TABLE treasury_official_observations(
                    observed_on_utc TEXT NOT NULL, source_identity TEXT NOT NULL);
                INSERT INTO uscc_official_source_records VALUES
                    ('uscc:a','https://www.uscc.gov/a','USCC');
                INSERT INTO uscc_official_observations VALUES
                    ('2026-10-15','uscc:a');
                INSERT INTO treasury_official_source_records VALUES
                    ('treasury:b','https://home.treasury.gov/b','Treasury');
                INSERT INTO treasury_official_observations VALUES
                    ('2026-10-15','treasury:b');
                CREATE TABLE articles(id INTEGER PRIMARY KEY, source_id INTEGER);
                INSERT INTO articles VALUES (1, 1);
                INSERT INTO articles VALUES (2, 2);
            """)
        shutil.copyfile(self.old, self.new)
        with sqlite3.connect(self.new) as db:
            db.execute("DELETE FROM articles WHERE id=1")

    def test_real_china_article_removal_preserves_all_others(self):
        receipt = validate(self.old, self.new)
        self.assertEqual(receipt["official_source_rows"],
                         {"uscc_official_source_records": 1,
                          "treasury_official_source_records": 1})
        self.assertEqual(len(receipt["preserved_tables"]), 5)

    def test_uscc_record_loss_fails(self):
        with sqlite3.connect(self.new) as db:
            db.execute("DELETE FROM uscc_official_source_records")
        with self.assertRaisesRegex(ValueError, "uscc_official_source_records"):
            validate(self.old, self.new)

    def test_treasury_observation_loss_fails(self):
        with sqlite3.connect(self.new) as db:
            db.execute("DELETE FROM treasury_official_observations")
        with self.assertRaisesRegex(ValueError, "treasury_official_observations"):
            validate(self.old, self.new)

    def test_source_registry_tampering_fails(self):
        with sqlite3.connect(self.new) as db:
            db.execute("UPDATE sources SET slug='wrong' WHERE id=2")
        with self.assertRaisesRegex(ValueError, "sources"):
            validate(self.old, self.new)

    def test_dropped_treasury_table_fails(self):
        with sqlite3.connect(self.new) as db:
            db.execute("DROP TABLE treasury_official_source_records")
        with self.assertRaisesRegex(ValueError, "treasury_official_source_records"):
            validate(self.old, self.new)

    def test_changed_metadata_schema_fails(self):
        with sqlite3.connect(self.new) as db:
            db.execute("CREATE INDEX ix_uscc_issuer ON uscc_official_source_records(issuer)")
        with self.assertRaisesRegex(ValueError, "uscc_official_source_records"):
            validate(self.old, self.new)

    def test_original_incomplete_metadata_pair_fails(self):
        with sqlite3.connect(self.old) as db:
            db.execute("DROP TABLE treasury_official_observations")
        with self.assertRaisesRegex(ValueError, "partial official metadata family"):
            validate(self.old, self.new)

    def test_both_older_schemas_without_us_metadata_are_supported(self):
        with sqlite3.connect(self.old) as orig, sqlite3.connect(self.new) as newer:
            for table in ("uscc_official_source_records", "uscc_official_observations",
                          "treasury_official_source_records", "treasury_official_observations"):
                orig.execute("DROP TABLE " + table)
                newer.execute("DROP TABLE " + table)
        receipt = validate(self.old, self.new)
        self.assertEqual(receipt["official_source_rows"],
                         {"uscc_official_source_records": None,
                          "treasury_official_source_records": None})


if __name__ == "__main__":
    unittest.main()
