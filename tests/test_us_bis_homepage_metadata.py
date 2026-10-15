"""Adversarial source-free BIS homepage date/issuer contracts."""
import json
import unittest
from scripts import collect_us_bis_homepage_metadata as bis
from tests.test_us_navy_first_party_access import FakeOpener, FakeResponse

CARD1 = """<li class="p-4"><div class="py-6"><span>October 2, 2026</span>
<a href="/press-release/official-first-case">Publisher-owned headline must vanish</a>
</div></li>"""
CARD2 = """<li class="p-4"><div class="py-6"><span>July 27, 2026</span>
<a href="/press-release/official-second-case">Another copyrighted headline</a>
</div></li>"""

def html(cards=CARD1 + CARD2, extra=""):
    return ("""<!doctype html><html><body><main><section class="py-8">
<ul class="grid auto-rows-max grid-cols-1 text-left">""" + cards
            + "</ul></section></main>" + extra + "</body></html>").encode()

class BISHomepageContracts(unittest.TestCase):
    def test_exact_card_provenance_metadata_only(self):
        rows = bis.extract(html(), as_of="2026-10-15")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["publisher_posted_date"], "2026-10-02")
        self.assertEqual(rows[1]["publisher_posted_date"], "2026-07-27")
        self.assertEqual(rows[0]["official_issuer"], bis.ISSUER)
        self.assertEqual(set(rows[0]), {
            "source_identity", "canonical_official_url", "publisher_posted_date",
            "official_issuer", "official_publisher", "publisher_listing_url",
        })
        self.assertNotIn("headline", json.dumps(rows).lower())
        self.assertNotIn("copyrighted", json.dumps(rows).lower())

    def test_robots_first_then_one_homepage_no_originals(self):
        fake = FakeOpener({
            bis.ROBOTS: FakeResponse(bis.ROBOTS, b"User-agent: *\nAllow: /\n"),
            bis.INDEX: FakeResponse(bis.INDEX, html()),
        })
        p = bis.collect(opener=fake, as_of="2026-10-15")
        self.assertEqual(fake.calls, [bis.ROBOTS, bis.INDEX])
        self.assertEqual(p["visible_dated_rows"], 2)
        self.assertEqual(len(p["official_listing_sha256"]), 64)
        for name in ("original_titles_copied", "bodies_copied",
                     "document_media_copied", "analysis_performed",
                     "publication_authorized_by_collector",
                     "complete_publisher_history_claimed"):
            self.assertIs(p[name], False)
        self.assertEqual(p["production_records_written"], 0)
        self.assertNotIn("Publisher-owned", json.dumps(p))

    def test_robots_denial_blocks_listing(self):
        fake = FakeOpener({bis.ROBOTS: FakeResponse(
            bis.ROBOTS, b"User-agent: *\nDisallow: /\n")})
        with self.assertRaisesRegex(bis.BISHold, "robots_disallow"):
            bis.collect(opener=fake, as_of="2026-10-15")
        self.assertEqual(fake.calls, [bis.ROBOTS])

    def test_challenge_and_invalid_robots_block_listing(self):
        for raw in (b"<html>Challenge</html>", b"Allow: /\n"):
            with self.subTest(raw=raw):
                fake = FakeOpener({bis.ROBOTS: FakeResponse(bis.ROBOTS, raw)})
                with self.assertRaises(bis.BISHold):
                    bis.collect(opener=fake, as_of="2026-10-15")
                self.assertEqual(fake.calls, [bis.ROBOTS])

    def test_wrong_host_scheme_query_fragment_encoded_path_rejected(self):
        for raw in ("https://evil.invalid/press-release/official-first-case",
                    "http://www.bis.gov/press-release/official-first-case",
                    "//evil.invalid/press-release/official-first-case",
                    "/press-release/official-first-case?download=1",
                    "/press-release/official-first-case#reference",
                    "/press-release/official%2ffirst-case",
                    "/press-release/official_first_case",
                    "/news-updates/official-first-case",
                    "/press-release/official-first-case/extra",
                    "https://www.bis.gov:443/press-release/official-first-case"):
            with self.subTest(raw=raw):
                self.assertIsNone(bis.canonical(raw))

    def test_global_date_cannot_supply_missing_card_date(self):
        broken = CARD1.replace("October 2, 2026", "No date")
        with self.assertRaisesRegex(bis.BISHold, "non_unique_or_missing"):
            bis.extract(html(broken, "<footer>October 2, 2026</footer>"),
                        as_of="2026-10-15")

    def test_neighbor_date_cannot_supply_missing_card_date(self):
        broken = CARD2.replace("July 27, 2026", "No date")
        with self.assertRaisesRegex(bis.BISHold, "non_unique_or_missing"):
            bis.extract(html(CARD1 + broken), as_of="2026-10-15")

    def test_multiple_card_dates_hold(self):
        broken = CARD1.replace("October 2, 2026",
                               "October 2, 2026 and July 27, 2026")
        with self.assertRaisesRegex(bis.BISHold, "non_unique_or_missing"):
            bis.extract(html(broken), as_of="2026-10-15")

    def test_multiple_card_release_links_hold(self):
        broken = CARD1.replace("</div></li>",
            '<a href="/press-release/different">Other</a></div></li>')
        with self.assertRaisesRegex(bis.BISHold, "multiple_press_links"):
            bis.extract(html(broken), as_of="2026-10-15")

    def test_future_invalid_and_stale_dates_hold(self):
        for wrong in ("October 16, 2026", "February 30, 2026",
                      "October 2, 2024"):
            with self.subTest(wrong=wrong):
                with self.assertRaises(bis.BISHold):
                    bis.extract(html(CARD1.replace("October 2, 2026", wrong)),
                                as_of="2026-10-15")

    def test_card_structure_drift_holds(self):
        broken = html().replace(b'class="p-4"', b'class="p-5"')
        with self.assertRaisesRegex(bis.BISHold, "structure_missing"):
            bis.extract(broken, as_of="2026-10-15")

    def test_unrelated_footer_press_link_not_collected(self):
        other = '<footer><a href="/press-release/footer-case">Outside</a></footer>'
        rows = bis.extract(html(extra=other), as_of="2026-10-15")
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("footer-case" not in r["source_identity"] for r in rows))

    def test_empty_and_oversized_homepage_hold(self):
        with self.assertRaises(bis.BISHold):
            bis.extract(html("<li class='p-4'>Nothing published</li>"),
                        as_of="2026-10-15")
        with self.assertRaises(bis.BISHold):
            bis.extract(html() + b" " * bis.MAX_BYTES, as_of="2026-10-15")

    def test_bad_observation_date_holds_before_network(self):
        with self.assertRaises(bis.BISHold):
            bis.collect(opener=FakeOpener({}), as_of="tomorrow")

if __name__ == "__main__":
    unittest.main()
