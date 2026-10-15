"""Strict read-only BIS official source-shape probe offline contracts."""
import unittest
from scripts import probe_us_bis_html_shape as p
from tests.test_us_navy_first_party_access import FakeResponse,FakeOpener

class BISShapeTests(unittest.TestCase):
    def test_disallowed_robots_never_touch_listing(self):
        fake=FakeOpener({p.ROBOTS:FakeResponse(p.ROBOTS,b"User-agent: *\nDisallow: /\n")})
        result=p.run(fake)
        self.assertEqual(fake.calls,[p.ROBOTS])
        self.assertFalse(result["production_written"])
        self.assertFalse(result["collection_authorized"])
    def test_bounded_only_fixed_routes_no_source_copies(self):
        urls=["https://"+p.HOST+path for path in p.ROUTES]
        fake=FakeOpener({p.ROBOTS:FakeResponse(p.ROBOTS,b"User-agent: *\nAllow: /\n"),
         urls[0]:FakeResponse(urls[0],b'<!doctype html><html><a href="/press-release/test"></a></html>'),
         urls[1]:FakeResponse(urls[1],b'<!doctype html><html></html>')})
        result=p.run(fake)
        self.assertEqual(fake.calls,[p.ROBOTS,*urls])
        self.assertEqual(result["records_collected"],0)
        self.assertFalse(result["source_originals_stored"])
        self.assertFalse(result["publisher_content_reproduced"])
        self.assertEqual(len(result["routes"]),2)

if __name__=="__main__":
    unittest.main()
