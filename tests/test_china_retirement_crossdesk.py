"""No China cull may mutate independent live U.S. metadata records."""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.verify_china_retirement_crossdesk import validate, verify_us_public_link_parity


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


class USPublisherLinkReadback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.before = base / "before"
        self.after = base / "after"
        self.before.mkdir()
        self.after.mkdir()
        html = """<main><h2>PACOM collection blocked</h2>
        <li data-uscc-official-link="uscc:1">
          <a href="https://www.uscc.gov/a">USCC</a>
          <time datetime="2026-10-15">Oct 15</time>Issuer: USCC
        </li>
        <li data-us-treasury-official-link="treasury:2">
          <a href="https://home.treasury.gov/b">Treasury</a>
          <time datetime="2026-10-14">Oct 14</time>Issuer: Treasury
        </li></main>"""
        for root in (self.before, self.after):
            (root / "us-indopacific.html").write_text(html, encoding="utf-8")
        self.db_receipt = {
            "official_source_rows": {
                "uscc_official_source_records": 1,
                "treasury_official_source_records": 1,
            }
        }

    def test_identical_official_links_survive(self):
        result = verify_us_public_link_parity(
            self.before, self.after, self.db_receipt
        )
        self.assertEqual(list(result.values()), [1, 1])

    def test_changed_official_date_refused(self):
        page = self.after / "us-indopacific.html"
        page.write_text(page.read_text().replace("2026-10-15", "2026-10-16"))
        with self.assertRaisesRegex(ValueError, "date/issuer changed"):
            verify_us_public_link_parity(self.before, self.after, self.db_receipt)

    def test_missing_treasury_reference_refused(self):
        page = self.after / "us-indopacific.html"
        page.write_text(page.read_text().replace(
            'data-us-treasury-official-link="treasury:2"', 'data-wrong="treasury:2"'))
        with self.assertRaisesRegex(ValueError, "changed or vanished"):
            verify_us_public_link_parity(self.before, self.after, self.db_receipt)

    def test_live_sqlite_without_any_rendered_uscc_ref_refused(self):
        for root in (self.before, self.after):
            page = root / "us-indopacific.html"
            page.write_text(page.read_text().replace(
                'data-uscc-official-link="uscc:1"', 'data-wrong="uscc:1"'))
        with self.assertRaisesRegex(ValueError, "not rendered"):
            verify_us_public_link_parity(self.before, self.after, self.db_receipt)

    def test_unblocked_pacom_description_refused(self):
        page = self.after / "us-indopacific.html"
        page.write_text(page.read_text().replace(
            "PACOM collection blocked", "PACOM now live"))
        with self.assertRaisesRegex(ValueError, "must not promote"):
            verify_us_public_link_parity(self.before, self.after, self.db_receipt)


if __name__ == "__main__":
    unittest.main()
