"""Synthetic, no-network negative and positive checks for US Navy access canary."""
import unittest
from unittest.mock import patch
import urllib.error

from scripts import probe_us_navy_first_party_access as canary

class FakeResponse:
    def __init__(self, url, body, code=200, actual=None):
        self.url=url
        self.body=body
        self.code=code
        self.actual=actual or url
    def getcode(self): return self.code
    def geturl(self): return self.actual
    def read(self, n): return self.body[:n]
    def __enter__(self): return self
    def __exit__(self, *args): return None

class FakeOpener:
    def __init__(self, payload):
        self.payload=payload
        self.calls=[]
    def open(self, req, timeout):
        self.calls.append(req.full_url)
        value=self.payload.get(req.full_url)
        if value is None:
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
        if isinstance(value,Exception): raise value
        return value

def target(which="seventh_fleet"):
    return next(x for x in canary.SOURCES if x[0]==which)

class CanaryContracts(unittest.TestCase):
    def test_fixed_hosts_and_no_submission_to_any_corpus(self):
        self.assertEqual(len(canary.validate_targets()), 3)
        with self.assertRaises(canary.AccessHold):
            canary.validate_targets([("other","attacker.invalid","/x")])
        opener=FakeOpener({})
        receipt=canary.run(opener)
        self.assertEqual(receipt["records_collected"],0)
        self.assertEqual(receipt["production_records_written"],0)
        self.assertIs(receipt["website_changed"],False)
        self.assertIs(receipt["new_source_day_claimed"],False)
        self.assertEqual(len(opener.calls),3)
        self.assertTrue(all(p.endswith("/robots.txt") for p in opener.calls))
        self.assertEqual({row["robots_policy"] for row in receipt["results"]},
                         {"http_403"})

    def test_uscc_is_distinct_official_source_family(self):
        name,host,path=target("us_china_commission")
        self.assertEqual(name, "us_china_commission")
        self.assertEqual(host, "www.uscc.gov")
        self.assertEqual(path, "/press-releases")
        self.assertNotIn("navy.mil", host)

    def test_unreadable_and_disallowed_policy_never_requests_article_listing(self):
        name,host,path=target()
        robot="https://"+host+"/robots.txt"
        for policy,expected in [
            (b"<html><script>captcha()</script></html>","not_a_usable_robots_policy"),
            (b"User-agent: *\nDisallow: /Media/News/\n","disallows_listings"),
            (b"", "empty_response")
        ]:
            opener=FakeOpener({robot:FakeResponse(robot,policy)})
            report=canary.probe_one(name,host,path,opener)
            self.assertEqual(report["robots_policy"],expected)
            self.assertFalse(report["listing_reachable"])
            self.assertEqual(opener.calls,[robot])

    def test_allowed_valid_listing_still_not_authorized_for_collection(self):
        name,host,path=target()
        robots="https://"+host+"/robots.txt"
        listing="https://"+host+path
        opener=FakeOpener({
            robots:FakeResponse(robots,b"User-agent: *\nAllow: /\n"),
            listing:FakeResponse(listing,b"<!doctype html><html><h1>News</h1></html>")
        })
        row=canary.probe_one(name,host,path,opener)
        self.assertEqual(opener.calls,[robots,listing])
        self.assertTrue(row["listing_reachable"])
        self.assertFalse(row["collection_authorized"])
        self.assertFalse(row["source_day_qualified"])

    def test_redirect_or_cross_origin_denied_without_retry(self):
        name,host,path=target()
        robots="https://"+host+"/robots.txt"
        opener=FakeOpener({robots:FakeResponse(robots,
            b"User-agent: *\nAllow: /\n",actual="https://other.invalid/robots.txt")})
        row=canary.probe_one(name,host,path,opener)
        self.assertEqual(row["robots_policy"],"unexpected_http_or_redirect")
        self.assertEqual(len(opener.calls),1)

    def test_unapproved_run_gated(self):
        with patch("sys.argv",["probe_us_navy_first_party_access.py"]):
            with self.assertRaises(SystemExit):
                canary.main([])

if __name__=="__main__":
    unittest.main()
