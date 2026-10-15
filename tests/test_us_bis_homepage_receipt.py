"""Source-free BIS packet integrity, issuer/date and tamper adversarial tests."""
import copy
import unittest
from scripts import collect_us_bis_homepage_metadata as bis
from scripts import verify_us_bis_homepage_receipt as proof
from tests.test_us_bis_homepage_metadata import html

def packet():
    rows = bis.extract(html(), as_of="2026-10-15")
    return {
        "schema": bis.SCHEMA,
        "source_host": bis.HOST,
        "source_family": bis.FAMILY,
        "publisher": proof.PUBLISHER,
        "issuer": bis.ISSUER,
        "collection_mode": "bounded_exact_homepage_metadata_only",
        "observed_on_utc": "2026-10-15",
        "official_listing_url": bis.INDEX,
        "official_listing_sha256": "a" * 64,
        "rows": rows,
        "visible_dated_rows": len(rows),
        "original_titles_copied": False,
        "bodies_copied": False,
        "document_media_copied": False,
        "analysis_performed": False,
        "publication_authorized_by_collector": False,
        "production_records_written": 0,
        "complete_publisher_history_claimed": False,
    }

class BISReceiptContracts(unittest.TestCase):
    def test_verified_packet_from_exact_source_rows(self):
        self.assertEqual(proof.verify(packet(), expected_day="2026-10-15"), 2)

    def test_wrong_observed_day_and_invalid_day_hold(self):
        for day in ("2026-10-14", "2026-02-30", "20261015"):
            with self.subTest(day=day):
                test = packet()
                test["observed_on_utc"] = day
                with self.assertRaises(bis.BISHold):
                    proof.verify(test, expected_day="2026-10-15")

    def test_bad_or_mismatched_listing_sha_holds(self):
        for digest in ("", "g" * 64, "a" * 63, "A" * 64, 27):
            with self.subTest(digest=digest):
                test = packet()
                test["official_listing_sha256"] = digest
                with self.assertRaises(bis.BISHold):
                    proof.verify(test, expected_day="2026-10-15")

    def test_original_or_publication_flags_never_allowed(self):
        for field in proof.FALSE_FLAGS:
            with self.subTest(field=field):
                test = packet()
                test[field] = True
                with self.assertRaises(bis.BISHold):
                    proof.verify(test, expected_day="2026-10-15")

    def test_reject_untrusted_packet_field_and_issuer(self):
        for field, value in (
            ("issuer", "us_department_treasury"),
            ("source_host", "evil.invalid"),
            ("source_family", "uscc_press_releases"),
            ("official_listing_url", "https://www.bis.gov/news-updates"),
            ("visible_dated_rows", 99),
            ("production_records_written", 1),
        ):
            with self.subTest(field=field):
                test = packet()
                test[field] = value
                with self.assertRaises(bis.BISHold):
                    proof.verify(test, expected_day="2026-10-15")
        test = packet()
        test["article_body"] = "Publisher text"
        with self.assertRaises(bis.BISHold):
            proof.verify(test, expected_day="2026-10-15")

    def test_bad_canonical_url_wrong_identity_or_wrong_issuer(self):
        changes = (
            ("canonical_official_url",
             "https://evil.invalid/press-release/official-first-case"),
            ("canonical_official_url",
             "https://www.bis.gov/press-release/official-first-case?x=1"),
            ("source_identity", "us-treasury-press:official-first-case"),
            ("official_issuer", "us_department_treasury"),
            ("official_publisher", "www.uscc.gov"),
            ("publisher_listing_url", "https://www.bis.gov/enforcement"),
            ("publisher_posted_date", "2026-10-16"),
        )
        for key, val in changes:
            with self.subTest(key=key, val=val):
                test = packet()
                test["rows"][0][key] = val
                with self.assertRaises(bis.BISHold):
                    proof.verify(test, expected_day="2026-10-15")

    def test_duplicate_identity_extra_fields_and_order_change_hold(self):
        cases = []
        other = packet()
        other["rows"].append(copy.deepcopy(other["rows"][0]))
        other["visible_dated_rows"] += 1
        cases.append(other)
        other = packet()
        other["rows"][0]["headline"] = "Unapproved"
        cases.append(other)
        other = packet()
        other["rows"].reverse()
        cases.append(other)
        for candidate in cases:
            with self.subTest(candidate=candidate["rows"]):
                with self.assertRaises(bis.BISHold):
                    proof.verify(candidate, expected_day="2026-10-15")

    def test_bool_is_not_acceptable_as_count(self):
        test = packet()
        test["visible_dated_rows"] = True
        with self.assertRaises(bis.BISHold):
            proof.verify(test, expected_day="2026-10-15")

if __name__ == "__main__":
    unittest.main()
