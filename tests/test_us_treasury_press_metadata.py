"""Treasury publisher release-card provenance, robots, and limits (offline)."""
import unittest
import json
from scripts import collect_us_treasury_press_metadata as t
from tests.test_us_navy_first_party_access import FakeOpener, FakeResponse

HTML=b"""<!doctype html><html><body>
<div class="featured-stories content--2col">
 <time datetime="2026-10-15">October 15, 2026</time>
 <div class="content--2col__body"><h3 class="featured-stories__headline">
 <a href="/news/press-releases/sb0661/">Release A</a></h3></div></div>
<div class="featured-stories content--2col">
 <time datetime="2026-10-14">October 14, 2026</time>
 <div class="content--2col__body"><h3 class="featured-stories__headline">
 <a href="/news/press-releases/sb0660/">Release B</a></h3></div></div>
</body></html>"""
class TreasuryContracts(unittest.TestCase):
    def test_valid_exact_card_date_and_metadata_only(self):
        rows=t.extract(HTML,as_of="2026-10-15")
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]["source_identity"],"us-treasury-press:sb0661")
        self.assertEqual(rows[1]["publisher_posted_date"],"2026-10-14")
        self.assertNotIn("Release A",json.dumps(rows))
        self.assertEqual({x["official_issuer"] for x in rows},{"us_department_treasury"})
    def test_robots_first_listing_once_and_no_originals(self):
        fake=FakeOpener({
            t.ROBOTS:FakeResponse(t.ROBOTS,b"User-agent: *\nAllow: /\n"),
            t.INDEX:FakeResponse(t.INDEX,HTML)
        })
        packet=t.collect(opener=fake,as_of="2026-10-15")
        self.assertEqual(fake.calls,[t.ROBOTS,t.INDEX])
        self.assertEqual(packet["visible_dated_rows"],2)
        self.assertFalse(packet["bodies_copied"])
        self.assertFalse(packet["publication_authorized_by_collector"])
    def test_robots_disallow_prevents_fetch(self):
        fake=FakeOpener({t.ROBOTS:FakeResponse(
            t.ROBOTS,b"User-agent: *\nDisallow: /\n")})
        with self.assertRaises(t.TreasuryHold):
            t.collect(opener=fake,as_of="2026-10-15")
        self.assertEqual(fake.calls,[t.ROBOTS])
    def test_malformed_date_cross_card_and_future_hold(self):
        for html in (
           HTML.replace(b'2026-10-15',b'2026-10-16'),
           HTML.replace(b'<time datetime="2026-10-15">October 15, 2026</time>',b''),
           HTML.replace(b'</h3></div></div>',b'<a href="/news/press-releases/sb0662">Other</a></h3></div></div>',1),
        ):
            with self.subTest(html=html[:50]):
                with self.assertRaises(t.TreasuryHold):
                    t.extract(html,as_of="2026-10-15")
    def test_wrong_host_query_and_non_release_slug_hold(self):
        for bad in ("https://evil.invalid/news/press-releases/sb0661",
                    "/news/press-releases/sb0661?download=1",
                    "/news/press-releases/statements-remarks",
                    "http://home.treasury.gov/news/press-releases/sb0661",
                    "/news/press-releases/sb0661#x"):
            with self.subTest(bad=bad):
                self.assertIsNone(t.canonical(bad))

if __name__=="__main__":unittest.main()
