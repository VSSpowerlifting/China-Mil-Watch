"""Independent BIS live readback contracts, entirely synthetic and offline."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.us_bis_authenticated_metadata import admit_attested, load_public_links
from scripts.verify_us_bis_deployed_metadata import (
    BISReadbackHold, verify, verified_html)
from tests.test_us_bis_authenticated_metadata import packet, proof
from tests.test_us_bis_public_metadata_bridge import render


def html(rows):
    items=render(rows)
    pacom="".join('<li data-us-pacom-link="p%d"><a href="https://www.pacom.mil/">PACOM</a></li>'%i for i in range(9))
    uscc="".join('<li data-uscc-official-link="u%d"><a href="https://www.uscc.gov/">USCC</a></li>'%i for i in range(10))
    treasury="".join('<li data-us-treasury-official-link="t%d"><a href="https://home.treasury.gov/">Treasury</a></li>'%i for i in range(10))
    return ('<!doctype html><html><body><p>PACOM remains access-blocked; DVIDS paused</p>'
            +items+pacom+uscc+treasury+'</body></html>').encode("utf-8")


class DeployedBISReadback(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        folder=Path(self.tmp.name)
        self.db=folder/"test.sqlite"
        with sqlite3.connect(self.db) as con:
            admit_attested(con,packet(),proof())
        self.rows=load_public_links(self.db)
        content=html(self.rows)
        self.a=folder/"main.html"
        self.b=folder/"pages.html"
        self.c=folder/"http.html"
        for p in (self.a,self.b,self.c):
            p.write_bytes(content)

    def check(self):
        return verify(self.db,self.a,self.b,self.c)

    def test_matches_exact_three_sources(self):
        result=self.check()
        self.assertEqual(result["status"],"PASS_BIS_INDEPENDENT_DEPLOYED_READBACK")
        self.assertEqual(result["records"],2)
        self.assertTrue(result["main_matches_pages_git"])
        self.assertTrue(result["pages_git_matches_public_http"])
        self.assertFalse(result["original_bis_text_rehosted"])

    def test_cdn_mismatch_is_not_success(self):
        self.c.write_bytes(self.c.read_bytes()+b"\n")
        with self.assertRaisesRegex(BISReadbackHold,"cdn"):
            self.check()

    def test_pages_git_mismatch_is_not_success(self):
        self.b.write_bytes(self.b.read_bytes()+b"<!-- pending deployment -->")
        with self.assertRaisesRegex(BISReadbackHold,"github_pages"):
            self.check()

    def test_corrupt_date_or_identity_not_readback(self):
        altered=self.a.read_bytes().replace(self.rows[0]["published_date"].encode(),b"2024-10-15",1)
        with self.assertRaises(BISReadbackHold):
            verified_html(altered,self.rows)
        altered=self.a.read_bytes().replace(
            self.rows[0]["source_identity"].encode(),b"us-bis-homepage-press:fake",1)
        with self.assertRaises(BISReadbackHold):
            verified_html(altered,self.rows)

    def test_missing_pacom_uscc_or_treasury_is_hold(self):
        for key in (b"data-us-pacom-link",b"data-uscc-official-link",
                    b"data-us-treasury-official-link"):
            with self.subTest(key=key):
                broken=self.a.read_bytes().replace(key,b"removed",1)
                with self.assertRaises(BISReadbackHold):
                    verified_html(broken,self.rows)

    def test_unapproved_rehosted_publisher_body_is_hold(self):
        altered=self.a.read_bytes()+b" title_original"
        with self.assertRaisesRegex(BISReadbackHold,"original_publisher"):
            verified_html(altered,self.rows)

    def test_missing_authentication_table_cannot_prove_live(self):
        empty=Path(self.tmp.name)/"empty.sqlite"
        with sqlite3.connect(empty) as c:
            c.execute("CREATE TABLE other(v TEXT)")
        with self.assertRaisesRegex(BISReadbackHold,"no_authenticated"):
            verify(empty,self.a,self.b,self.c)

    def test_empty_or_oversized_http_response_is_hold(self):
        for raw in (b"",b"x"*1000001):
            with self.subTest(size=len(raw)):
                self.c.write_bytes(raw)
                with self.assertRaisesRegex(BISReadbackHold,"invalid_page"):
                    self.check()


if __name__=="__main__":
    unittest.main()
