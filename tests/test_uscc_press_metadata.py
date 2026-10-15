"""Strict no-network fixtures for USCC first-party listing metadata only."""
import copy
import json
import unittest
import urllib.error
from scripts import collect_uscc_press_metadata as uscc

POLICY=b"User-agent: *\nAllow: /\n"
HTML=b"""<!doctype html><html><body>
<div class="views-row">
  <div class="views-field-created"><span>09/22/2026</span></div>
  <a href="/press-releases/press-release-new-report-chinas-gray-zone-threats-trans-pacific-undersea-cables">Official release one</a>
  <a href="/press-releases/press-release-new-report-chinas-gray-zone-threats-trans-pacific-undersea-cables"><img src="/a.png"></a>
</div>
<div class="views-row">
  <div class="views-field-created">09/21/2026</div>
  <a href="/press-releases/press-release-new-reports-detail-china-russia-military-cooperation">Release two</a>
</div></body></html>"""

class FakeResponse:
    def __init__(self,url,body): self.url,self.body=url,body
    def getcode(self): return 200
    def geturl(self): return self.url
    def read(self,n): return self.body[:n]
    def __enter__(self): return self
    def __exit__(self,*args): return None

class FakeOpener:
    def __init__(self,allow=True,listing=HTML):
        self.calls=[]
        self.mapping={
            uscc.ROBOTS:FakeResponse(uscc.ROBOTS,POLICY if allow else
                                       b"User-agent: *\nDisallow: /\n"),
            uscc.INDEX:FakeResponse(uscc.INDEX,listing),
        }
    def open(self,req,timeout):
        self.calls.append(req.full_url)
        return self.mapping[req.full_url]

class USCCTest(unittest.TestCase):
    def test_two_verifiable_official_dates_and_no_content(self):
        rows=uscc.extract(HTML,as_of="2026-10-15")
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["publisher_posted_date"],"2026-09-22")
        self.assertEqual(rows[1]["publisher_posted_date"],"2026-09-21")
        self.assertTrue(all(x["canonical_official_url"].startswith(
                            "https://www.uscc.gov/press-releases/")
                            and set(x)=={
                              "source_identity","canonical_official_url",
                              "publisher_posted_date","official_issuer",
                              "official_publisher","publisher_listing_url"}
                            for x in rows))
        self.assertNotIn("Official release one",json.dumps(rows))

    def test_exact_robots_then_one_listing_and_no_corpus_use(self):
        op=FakeOpener()
        record=uscc.collect(opener=op,as_of="2026-10-15")
        self.assertEqual(op.calls,[uscc.ROBOTS,uscc.INDEX])
        self.assertEqual(record["visible_dated_rows"],2)
        self.assertFalse(record["publication_authorized_by_collector"])
        self.assertFalse(record["bodies_copied"])
        self.assertFalse(record["complete_publisher_history_claimed"])
        self.assertEqual(record["production_records_written"],0)

    def test_disallowed_source_never_contacts_listing(self):
        op=FakeOpener(allow=False)
        with self.assertRaises(uscc.USCCHold):
            uscc.collect(opener=op,as_of="2026-10-15")
        self.assertEqual(op.calls,[uscc.ROBOTS])

    def test_query_different_host_and_unsafe_slug_never_admitted(self):
        for ref in (
           "https://evil.invalid/press-releases/press-release-foo",
           "https://www.uscc.gov/press-releases/press-release-foo?download=1",
           "https://www.uscc.gov/press-releases/../something",
           "http://www.uscc.gov/press-releases/press-release-foo",
           "https://www.uscc.gov/press-releases?page=2",
           "/press-releases/press-release-foo#body",
        ):
            with self.subTest(ref=ref):
                self.assertIsNone(uscc.canonical(ref))

    def test_non_dated_card_not_independent_date_evidence(self):
        page=b"""<!doctype html><html><body><div class="views-row">
        <a href="/press-releases/press-release-example">A title</a>
        </div><div class="views-row">09/22/2026</div></body></html>"""
        with self.assertRaises(uscc.USCCHold):
            uscc.extract(page,as_of="2026-10-15")

    def test_wrong_chronology_or_bad_date_holds(self):
        for value in (b"09/31/2026",b"10/16/2026"):
            with self.subTest(value=value):
                page=HTML.replace(b"09/22/2026",value)
                with self.assertRaises(uscc.USCCHold):
                    uscc.extract(page,as_of="2026-10-15")

if __name__=="__main__":
    unittest.main()
