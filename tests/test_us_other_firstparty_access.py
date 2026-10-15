"""Seven immutable policy-first official site access tests (offline)."""
import unittest
from scripts import probe_us_other_firstparty_access as p
from tests.test_us_navy_first_party_access import FakeOpener, FakeResponse

class Canaries(unittest.TestCase):
    def test_fixed_hosts(self):
        self.assertEqual(len(p.check_targets()), 7)
        with self.assertRaises(ValueError):
            p.check_targets([("evil", "host.invalid", "/")])
    def test_no_policy_never_requests_listing(self):
        fake=FakeOpener({})
        report=p.run(fake)
        self.assertEqual(len(fake.calls), 7)
        self.assertTrue(all(x.endswith("/robots.txt") for x in fake.calls))
        self.assertEqual(report["records_collected"],0)
        self.assertEqual(report["qualified_collection_days"],0)
        self.assertFalse(report["website_changed"])
    def test_single_permitted_listing_and_explicit_non_authorization(self):
        name,host,path=next(x for x in p.SOURCES if x[0]=="us_treasury")
        robots="https://"+host+"/robots.txt"
        listing="https://"+host+path
        fake=FakeOpener({
            robots:FakeResponse(robots,b"User-agent: *\\nAllow: /\\n".replace(b"\\n",b"\n")),
            listing:FakeResponse(listing,b"<!doctype html><html><body></body></html>"),
        })
        result=p.probe_one(name,host,path,fake)
        self.assertEqual(fake.calls,[robots,listing])
        self.assertTrue(result["listing_reachable"])
        self.assertFalse(result["source_day_qualified"])
        self.assertFalse(result["collection_authorized"])

if __name__ == "__main__":
    unittest.main()
