"""BIS URL/date/issuer-only SQLite staging, offline adversarial contracts."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.us_bis_official_metadata import (
    BISAdmissionHold, admit_scratch, load_staged_links, validate)
from scripts import collect_us_bis_homepage_metadata as bis
from scripts import stage_us_bis_official_metadata as runner
from tests.test_us_bis_homepage_metadata import html

SHA = "a" * 40
DAY = "2026-10-15"


def packet(day=DAY):
    rows = bis.extract(html(), as_of=day)
    return {
        "schema": bis.SCHEMA, "source_host": bis.HOST,
        "source_family": bis.FAMILY,
        "publisher": "U.S. Department of Commerce, Bureau of Industry and Security",
        "issuer": bis.ISSUER,
        "collection_mode": "bounded_exact_homepage_metadata_only",
        "observed_on_utc": day, "official_listing_url": bis.INDEX,
        "official_listing_sha256": "b"*64,
        "rows": rows, "visible_dated_rows": len(rows),
        "original_titles_copied": False, "bodies_copied": False,
        "document_media_copied": False, "analysis_performed": False,
        "publication_authorized_by_collector": False,
        "production_records_written": 0,
        "complete_publisher_history_claimed": False,
    }


class BISAdmission(unittest.TestCase):
    def test_staging_is_idempotent_and_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "scratch.db"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE unrelated(v TEXT NOT NULL)")
                con.execute("INSERT INTO unrelated VALUES ('untouched')")
                self.assertEqual(admit_scratch(con, packet(), receipt_day=DAY,
                                               input_reference_sha=SHA), 2)
                self.assertEqual(admit_scratch(con, packet(), receipt_day=DAY,
                                               input_reference_sha=SHA), 0)
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM bis_official_source_records").fetchone()[0], 2)
                self.assertEqual(con.execute(
                    "SELECT provenance_status FROM bis_official_observations").fetchone()[0],
                    "unverified_scratch_rehearsal")
                self.assertEqual(con.execute("SELECT v FROM unrelated").fetchone()[0],
                                 "untouched")
            links = load_staged_links(db)
            self.assertEqual(len(links), 2)
            self.assertEqual([x["source_url"] for x in links],
                             [x["canonical_official_url"] for x in packet()["rows"]])
            self.assertTrue(all("source_identity" in x for x in links))
            self.assertNotIn("text_original", str(links))
            self.assertNotIn("title_original", str(links))

    def test_content_and_provenance_tampering_holds(self):
        changes = (
            ("original_titles_copied", True),
            ("bodies_copied", True),
            ("publication_authorized_by_collector", True),
            ("official_listing_sha256", "not-a-hash"),
            ("issuer", "us_department_treasury"),
            ("observed_on_utc", "2026-10-14"),
            ("visible_dated_rows", 0),
        )
        for name, value in changes:
            with self.subTest(name=name):
                p = packet()
                p[name] = value
                with self.assertRaises(BISAdmissionHold):
                    validate(p, receipt_day=DAY)
        p = packet()
        p["rows"][0]["headline"] = "Unapproved publisher title"
        with self.assertRaises(BISAdmissionHold):
            validate(p, receipt_day=DAY)

    def test_url_identity_date_and_duplicate_holds(self):
        for name, value in (
            ("official_publisher", "www.uscc.gov"),
            ("publisher_posted_date", "2026-10-16"),
            ("source_identity", "us-bis-homepage-press:wrong"),
            ("canonical_official_url", "https://evil.example/press-release/abc"),
        ):
            with self.subTest(name=name):
                p = packet()
                p["rows"][0][name] = value
                with self.assertRaises(BISAdmissionHold):
                    validate(p, receipt_day=DAY)
        p = packet()
        p["rows"][1]["canonical_official_url"] = p["rows"][0]["canonical_official_url"]
        with self.assertRaises(BISAdmissionHold):
            validate(p, receipt_day=DAY)

    def test_changed_same_day_digest_is_rejected_without_partial_write(self):
        with sqlite3.connect(":memory:") as con:
            admit_scratch(con, packet(), receipt_day=DAY, input_reference_sha=SHA)
            p = packet()
            p["official_listing_sha256"] = "c"*64
            with self.assertRaises(BISAdmissionHold):
                admit_scratch(con, p, receipt_day=DAY, input_reference_sha=SHA)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM bis_official_observations").fetchone()[0],1)
            self.assertEqual(con.execute("SELECT official_listing_sha256 FROM bis_official_observations").fetchone()[0], "b"*64)

    def test_next_day_identity_change_rejects_all_that_days_writes(self):
        with sqlite3.connect(":memory:") as con:
            admit_scratch(con, packet(), receipt_day=DAY, input_reference_sha=SHA)
            p = packet("2026-10-16")
            p["rows"][0]["publisher_posted_date"] = "2026-10-15"
            with self.assertRaises(BISAdmissionHold):
                admit_scratch(con,p,receipt_day="2026-10-16",input_reference_sha="d"*40)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM bis_official_observations").fetchone()[0],1)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM bis_official_source_records").fetchone()[0],2)

    def test_invalid_commit_reference_and_reader_corruption_hold(self):
        with sqlite3.connect(":memory:") as con:
            with self.assertRaises(BISAdmissionHold):
                admit_scratch(con,packet(),receipt_day=DAY,input_reference_sha="fake")
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/"scratch.db"
            with sqlite3.connect(db) as con:
                admit_scratch(con,packet(),receipt_day=DAY,input_reference_sha=SHA)
                con.execute("UPDATE bis_official_source_records SET publisher_listing_url='https://evil.invalid' WHERE rowid=1")
            with self.assertRaises(BISAdmissionHold):
                load_staged_links(db)

    def test_scratch_cli_rejects_repository_and_existing_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            receipt=folder/"2026-10-15.json"
            receipt.write_text(json.dumps(packet()),encoding="utf-8")
            with self.assertRaises(BISAdmissionHold):
                runner.stage(receipt,runner.REPO_ROOT/"pla_watch.db",input_reference_sha=SHA)
            existing=folder/"existing.db"
            existing.write_bytes(b"not a DB")
            with self.assertRaises(BISAdmissionHold):
                runner.stage(receipt,existing,input_reference_sha=SHA)
            staged=folder/"scratch.db"
            result=runner.stage(receipt,staged,input_reference_sha=SHA)
            self.assertEqual(result["typed_links_staged"],2)
            self.assertFalse(result["approved_for_live_admission"])
            self.assertEqual(result["live_records_written"],0)
            self.assertEqual(len(load_staged_links(staged)),2)

    def test_absent_staged_table_is_not_source_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"empty.db"
            with sqlite3.connect(path) as con:
                con.execute("CREATE TABLE unrelated(k INTEGER)")
            self.assertEqual(load_staged_links(path),[])


if __name__=="__main__":
    unittest.main()
