"""Strict independent regional index readback checks, entirely synthetic."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.regional_official_link_release import SCHEMA_SQL
from scripts.verify_regional_source_index_readback import (
    ReadbackHold, main, validate_page, verify,
)
from tests.test_regional_live_site_wiring import html_for
from tests.test_regional_official_link_render import insert
from core.regional_official_link_render import load_admitted_links


class RegionalReadbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "db.sqlite"
        self.site = self.root / "committed"
        self.pages = self.root / "deployed"
        self.site.mkdir()
        self.pages.mkdir()
        con = sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE scratch (id INTEGER)")
        con.commit()
        con.close()
        self.make_pages()

    def make_pages(self):
        for desk in ("philippines", "indonesia"):
            (self.site / (desk + ".html")).write_text(
                html_for(desk, []), encoding="utf-8")

    def migrate(self):
        con=sqlite3.connect(str(self.db))
        con.execute(SCHEMA_SQL)
        con.commit()
        return con

    def admit_afp(self):
        con = self.migrate()
        insert(con)
        con.commit()
        con.close()
        self.make_pages_with_admitted()

    def make_pages_with_admitted(self):
        for desk in ("philippines", "indonesia"):
            rows = load_admitted_links(self.db, desk)
            (self.site / (desk + ".html")).write_text(
                html_for(desk, rows), encoding="utf-8")

    def digest(self):
        return hashlib.sha256(self.db.read_bytes()).hexdigest()

    def test_no_migration_has_zero_and_not_live(self):
        before=self.digest()
        packet=verify(self.db,self.site)
        self.assertEqual(packet["source_families"]["ph_afp_articles"][
            "admitted_official_link_count"],0)
        self.assertEqual(packet["source_families"]["id_kemhan_news"][
            "admitted_official_link_count"],0)
        self.assertEqual(self.digest(),before)
        self.assertFalse(Path(str(self.db)+"-wal").exists())
        self.assertFalse(Path(str(self.db)+"-shm").exists())

    def test_empty_source_index_cannot_masquerade_as_live(self):
        con=self.migrate()
        con.close()
        with self.assertRaisesRegex(ReadbackHold, "claimed_live_desk"):
            verify(self.db,self.site,require_records=True)

    def test_exact_rendered_record_matches_sqlite(self):
        self.admit_afp()
        before=self.digest()
        result=verify(self.db,self.site)
        self.assertEqual(result["source_families"]["ph_afp_articles"][
            "admitted_official_link_count"],1)
        self.assertEqual(result["source_families"]["id_kemhan_news"][
            "admitted_official_link_count"],0)
        self.assertEqual(self.digest(),before)

    def test_new_admitted_row_missing_from_rendered_page_holds(self):
        con=self.migrate()
        insert(con)
        con.commit()
        con.close()
        with self.assertRaisesRegex(ReadbackHold,
                                    "regional_source_section_presence_disagrees_with_db"):
            verify(self.db,self.site)

    def test_forged_unadmitted_extra_html_row_holds(self):
        con=self.migrate()
        con.close()
        fake=html_for("philippines", [{
            "source_identity":"afp:1499",
            "canonical_official_url":"https://www.afp.mil.ph/news/fake",
            "publisher_posted_date":"2026-10-15",
            "label":"AFP official source"}])
        (self.site/"philippines.html").write_text(fake,encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "presence_disagrees_with_db"):
            verify(self.db,self.site)

    def test_tampered_official_url_rejected_against_db(self):
        self.admit_afp()
        page=self.site/"philippines.html"
        original=page.read_text(encoding="utf-8")
        page.write_text(original.replace(
            "https://www.afp.mil.ph/news/fictional-exercise",
            "https://www.afp.mil.ph/news/other-source"),
            encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold,
                                    "html_link_date_or_neutral_label_differs_from_db"):
            verify(self.db,self.site)

    def test_tampered_publisher_date_rejected_against_db(self):
        self.admit_afp()
        page=self.site/"philippines.html"
        page.write_text(page.read_text(encoding="utf-8").replace(
            'datetime="2026-10-15"','datetime="2026-10-14"'),
            encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold, "html_link_date_or_neutral_label"):
            verify(self.db,self.site)

    def test_duplicate_row_rejected_even_with_same_source_id(self):
        self.admit_afp()
        page=self.site/"philippines.html"
        original=page.read_text(encoding="utf-8")
        start=original.index('    <li data-regional-official-source-id="afp:1499"')
        end=original.index("</li>",start)+5
        page.write_text(original[:end]+original[start:end]+original[end:],
                        encoding="utf-8")
        with self.assertRaisesRegex(ReadbackHold,"rendered_official_source_count"):
            verify(self.db,self.site)

    def test_two_claimed_live_desks_require_two_eligible_source_rows(self):
        self.admit_afp()
        with self.assertRaisesRegex(ReadbackHold, "claimed_live_desk"):
            verify(self.db,self.site,require_records=True)

    def test_pages_byte_parity_succeeds_if_equal(self):
        self.admit_afp()
        for page in self.site.glob("*.html"):
            shutil.copyfile(page,self.pages/page.name)
        receipt=verify(self.db,self.site,pages_dir=self.pages)
        self.assertTrue(receipt["site_bytes_match_deployed_checkout"])
        self.assertFalse(receipt["actual_pages_deployed_by_this_check"])

    def test_changed_deployed_page_fails_even_with_same_number_of_links(self):
        self.admit_afp()
        for page in self.site.glob("*.html"):
            shutil.copyfile(page,self.pages/page.name)
        page=self.pages/"philippines.html"
        page.write_bytes(page.read_bytes()+b"\n<!-- injected stale edit -->\n")
        with self.assertRaisesRegex(ReadbackHold,"deployed_pages_route_differs"):
            verify(self.db,self.site,pages_dir=self.pages)

    def test_missing_published_page_always_fails(self):
        self.admit_afp()
        (self.site/"indonesia.html").unlink()
        with self.assertRaisesRegex(ReadbackHold,"committed_regional_desk_page_missing"):
            verify(self.db,self.site)

    def test_schema_present_but_corrupt_is_hard_hold(self):
        con=sqlite3.connect(str(self.db))
        con.execute("CREATE TABLE regional_official_source_links(id INTEGER)")
        con.commit()
        con.close()
        with self.assertRaises(Exception):
            verify(self.db,self.site)

    def test_no_original_text_in_receipt(self):
        self.admit_afp()
        packet=verify(self.db,self.site)
        blob=json.dumps(packet)
        self.assertNotIn("original_title",blob)
        self.assertNotIn("publisher_body",blob)
        self.assertIn("source_families",packet)


if __name__ == "__main__":
    unittest.main()
