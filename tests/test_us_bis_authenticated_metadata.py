"""BIS independently attested official metadata -> isolated SQLite contracts."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from core.us_bis_authenticated_metadata import (
    BISLiveAdmissionHold, admit_attested, load_public_links, validate)
from scripts import admit_us_bis_scheduled_metadata as cli
from tests.test_us_bis_homepage_receipt import packet

DAY="2026-10-15"

def proof():
    p=packet()
    return {
        "status":"PASS_GENUINE_SCHEDULED_SOURCE_METADATA_RECEIPT",
        "source_branch_head":"a"*40,
        "source_commit":"b"*40,
        "source_run_id":38823500001,
        "source_run_attempt":1,
        "receipt_day":DAY,
        "official_listing_sha256":p["official_listing_sha256"],
        "verified_official_link_rows":len(p["rows"]),
        "source_html_independently_rehashed":False,
        "qualified_clean_day_streak":False,
        "live_sqlite_admission_authorized":False,
        "public_site_publishing_authorized":False,
    }

class TestBISAuthenticatedAdmission(unittest.TestCase):
    def test_typed_separate_tables_and_idempotency(self):
        with tempfile.TemporaryDirectory() as temp:
            db=Path(temp)/"candidate.sqlite"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE unrelated(v TEXT)")
                con.execute("INSERT INTO unrelated VALUES ('preserved')")
                self.assertEqual(admit_attested(con,packet(),proof()),2)
                self.assertEqual(admit_attested(con,packet(),proof()),0)
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM bis_authenticated_official_observations").fetchone()[0],1)
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM bis_authenticated_official_source_records").fetchone()[0],2)
                self.assertEqual(con.execute("SELECT v FROM unrelated").fetchone()[0],"preserved")
            rows=load_public_links(db)
            self.assertEqual(len(rows),2)
            self.assertTrue(all(r["source_url"].startswith("https://www.bis.gov/press-release/")
                                for r in rows))
            self.assertTrue(all("official press reference" in r["neutral_label"]
                                for r in rows))
            self.assertNotIn("title_original",str(rows))
            self.assertNotIn("text_original",str(rows))

    def test_never_trust_arbitrary_proof_fields(self):
        for field,value in [
            ("status","PASS_FAKE"),
            ("source_commit","corrupt"),
            ("source_branch_head","corrupt"),
            ("source_run_id",False),
            ("source_run_id",-1),
            ("source_run_attempt",0),
            ("receipt_day","2026-10-14"),
            ("official_listing_sha256","c"*64),
            ("verified_official_link_rows",0),
            ("source_html_independently_rehashed",True),
            ("qualified_clean_day_streak",True),
            ("live_sqlite_admission_authorized",True),
            ("public_site_publishing_authorized",True),
        ]:
            with self.subTest(field=field,value=value):
                p=proof();p[field]=value
                with self.assertRaises(BISLiveAdmissionHold):
                    validate(packet(),p)

    def test_metadata_only_source_contract_is_strict(self):
        for mutation,value in [
            ("issuer","other"),
            ("original_titles_copied",True),
            ("bodies_copied",True),
            ("analysis_performed",True),
            ("production_records_written",1),
            ("visible_dated_rows",99),
            ("observed_on_utc","2026-10-14"),
        ]:
            with self.subTest(mutation=mutation):
                pkt=packet();pkt[mutation]=value
                with self.assertRaises(BISLiveAdmissionHold):
                    validate(pkt,proof())
        pkt=packet();pkt["rows"][0]["headline"]="unapproved"
        with self.assertRaises(BISLiveAdmissionHold):
            validate(pkt,proof())

    def test_conflicting_same_day_digest_rolls_back(self):
        with sqlite3.connect(":memory:") as con:
            admit_attested(con,packet(),proof())
            p=packet();p["official_listing_sha256"]="f"*64
            a=proof();a["official_listing_sha256"]="f"*64
            with self.assertRaises(BISLiveAdmissionHold):
                admit_attested(con,p,a)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM bis_authenticated_official_observations").fetchone()[0],1)
            self.assertEqual(con.execute(
                "SELECT official_listing_sha256 FROM bis_authenticated_official_observations").fetchone()[0],
                packet()["official_listing_sha256"])

    def test_changed_identity_on_later_day_rolls_back_whole_day(self):
        with sqlite3.connect(":memory:") as con:
            admit_attested(con,packet(),proof())
            p=packet();p["observed_on_utc"]="2026-10-16"
            p["rows"][0]["publisher_posted_date"]="2026-10-14"
            p["rows"]=sorted(p["rows"],key=lambda row:
                             (row["publisher_posted_date"],row["source_identity"]),
                             reverse=True)
            a=proof();a["receipt_day"]="2026-10-16"
            a["source_run_id"]+=1;a["source_commit"]="c"*40
            with self.assertRaises(BISLiveAdmissionHold):
                admit_attested(con,p,a)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM bis_authenticated_official_observations").fetchone()[0],1)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM bis_authenticated_official_source_records").fetchone()[0],2)

    def test_next_day_same_entries_append_observation_without_new_links(self):
        with sqlite3.connect(":memory:") as con:
            admit_attested(con,packet(),proof())
            p=packet();p["observed_on_utc"]="2026-10-16"
            a=proof();a["receipt_day"]="2026-10-16"
            a["source_run_id"]+=1;a["source_commit"]="c"*40
            self.assertEqual(admit_attested(con,p,a),0)
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM bis_authenticated_official_observations").fetchone()[0],2)

    def test_reader_refuses_manually_corrupted_official_url(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"scratch.sqlite"
            with sqlite3.connect(db) as con:
                admit_attested(con,packet(),proof())
                con.execute("UPDATE bis_authenticated_official_source_records "
                            "SET canonical_official_url='https://malicious.invalid/article' "
                            "WHERE rowid=1")
            with self.assertRaises(BISLiveAdmissionHold):
                load_public_links(db)

    def test_unadmitted_schema_means_no_live_bis_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"empty.sqlite"
            with sqlite3.connect(db) as con:
                con.execute("CREATE TABLE unrelated(key TEXT)")
            self.assertEqual(load_public_links(db),[])

    def test_command_requires_explicit_metadata_only_owner_permission(self):
        with self.assertRaises(SystemExit) as caught:
            cli.main(["--source-checkout","/tmp/nonexistent",
                      "--authenticated-run-json","/tmp/nonexistent.json",
                      "--expected-remote-head","f"*40,
                      "--database","/tmp/nonexistent.sqlite"])
        self.assertIn("no standing metadata-only owner approval",str(caught.exception))

if __name__=="__main__":
    unittest.main()
