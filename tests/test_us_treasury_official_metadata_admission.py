"""Treasury strict source admission: no real network and no publisher content."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from core.us_treasury_official_metadata import (
    admit, validate_observation, TreasuryAdmissionHold, load_public_links,
)
from scripts.collect_us_treasury_press_metadata import (
    SCHEMA, INDEX, HOST,
)

def packet():
    day="2026-10-15"
    return dict(
        schema=SCHEMA, source_host=HOST, source_family="us_treasury_press_releases",
        publisher="U.S. Department of the Treasury",
        issuer="us_department_treasury",
        collection_mode="bounded_official_listing_metadata_only",
        observed_on_utc=day, official_listing_url=INDEX,
        official_listing_sha256="a"*64, visible_dated_rows=1,
        original_titles_copied=False,bodies_copied=False,
        document_media_copied=False,analysis_performed=False,
        publication_authorized_by_collector=False,
        production_records_written=0, complete_publisher_history_claimed=False,
        rows=[dict(source_identity="us-treasury-press:sb0661",
            canonical_official_url=INDEX+"/sb0661",
            publisher_posted_date="2026-09-22",
            official_issuer="us_department_treasury",
            official_publisher=HOST,publisher_listing_url=INDEX)]
    )

class TreasuryAdmissionTests(unittest.TestCase):
    def test_repeated_observation_is_idempotent_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"test.sqlite"
            with sqlite3.connect(path) as con:
                con.execute("CREATE TABLE unrelated (unchanged TEXT)")
                con.execute("INSERT INTO unrelated VALUES ('kept')")
                self.assertEqual(admit(con,packet(),receipt_day="2026-10-15",
                                       source_sha="b"*40),1)
                self.assertEqual(admit(con,packet(),receipt_day="2026-10-15",
                                       source_sha="b"*40),0)
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM treasury_official_source_records").fetchone()[0],1)
                self.assertEqual(con.execute(
                    "SELECT * FROM unrelated").fetchone()[0],"kept")
            rows=load_public_links(path)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["published_date"],"2026-09-22")
            self.assertNotIn("article",rows[0])
            self.assertNotIn("title_original",str(rows))
            self.assertNotIn("analysis",str(rows))
    def test_date_changes_and_wrong_publisher_hold(self):
        for mutation in ("date","host","key","flags","day","count","foreign_url"):
            with self.subTest(mutation=mutation):
                p=packet()
                if mutation=="date": p["rows"][0]["publisher_posted_date"]="2026-10-16"
                if mutation=="host": p["rows"][0]["official_publisher"]="evil.invalid"
                if mutation=="key": p["rows"][0]["headline"]="Not approved"
                if mutation=="flags": p["bodies_copied"]=True
                if mutation=="day": p["observed_on_utc"]="2026-10-14"
                if mutation=="count": p["visible_dated_rows"]=2
                if mutation=="foreign_url": p["rows"][0]["canonical_official_url"]="https://example.org/press-releases/sb0661"
                with self.assertRaises(TreasuryAdmissionHold):
                    validate_observation(p,receipt_day="2026-10-15")
    def test_existing_record_collision_refuses_mutation(self):
        with sqlite3.connect(":memory:") as con:
            admit(con,packet(),receipt_day="2026-10-15",source_sha="c"*40)
            p=packet()
            p["observed_on_utc"]="2026-10-16"
            p["rows"][0]["publisher_posted_date"]="2026-09-21"
            with self.assertRaises(TreasuryAdmissionHold):
                admit(con,p,receipt_day="2026-10-16",source_sha="d"*40)
            self.assertEqual(con.execute(
                "SELECT publisher_posted_date FROM treasury_official_source_records"
            ).fetchone()[0],"2026-09-22")

if __name__=="__main__":
    unittest.main()
