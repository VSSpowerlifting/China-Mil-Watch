"""No-network adversarial contracts for the frozen U.S. PACOM research docket."""
import contextlib
import copy
import io
import json
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import review_us_pacom_official_link_docket as us

class OfficialPACOMDocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = us.DOCKET.read_bytes()
        cls.data = json.loads(cls.original.decode("utf-8"))

    def test_exact_nine_official_host_links_are_unpublished(self):
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("network prohibited")):
            report = us.validate(copy.deepcopy(self.data))
        self.assertEqual(report["result"], "PASS_INDEX_ONLY")
        self.assertEqual(report["frozen_first_party_url_leads"], 9)
        for field in ("source_originals_downloaded", "automated_requests_made",
                      "production_records_written", "site_references_published"):
            self.assertEqual(report[field], 0)
        self.assertFalse(report["full_page_or_robots_retrieval_verified"])

    def test_not_a_publication_or_an_authorization_to_crawl(self):
        for key in ("published_to_ipr", "source_original_downloaded_for_this_snapshot",
                    "original_body_or_media_stored",
                    "automatic_discovery_or_publication_approved"):
            altered = copy.deepcopy(self.data)
            altered[key] = True
            with self.subTest(key=key), self.assertRaises(us.DocketHold):
                us.validate(altered)
        altered = copy.deepcopy(self.data)
        altered["collector_state"] = "collecting"
        with self.assertRaises(us.DocketHold):
            us.validate(altered)

    def test_unapproved_title_body_photo_or_claims_are_rejected(self):
        for field in ("title_original", "text_original", "photograph",
                      "summary", "analysis", "rights_granted"):
            altered = copy.deepcopy(self.data)
            altered["records"][0][field] = "unexpected"
            with self.subTest(field=field), self.assertRaises(us.DocketHold):
                us.validate(altered)

    def test_false_domain_path_query_and_source_id_fail(self):
        target = "official_url"
        cases = (
            "https://pacom.mil/Media/News/News-Articles/Article/4519249/test/",
            "https://www.pacom.mil.evil.invalid/Media/News/News-Articles/Article/4519249/test/",
            "http://www.pacom.mil/Media/News/News-Articles/Article/4519249/test/",
            self.data["records"][0][target] + "?file=1",
            self.data["records"][0][target].replace("4519249", "4519250"),
        )
        for value in cases:
            changed = copy.deepcopy(self.data)
            changed["records"][0][target] = value
            with self.subTest(value=value), self.assertRaises(us.DocketHold):
                us.validate(changed)

    def test_duplicate_and_fabricated_record_cannot_extend_snapshot(self):
        changed = copy.deepcopy(self.data)
        changed["records"][1] = changed["records"][0]
        with self.assertRaises(us.DocketHold):
            us.validate(changed)
        changed = copy.deepcopy(self.data)
        changed["records"].append(changed["records"][-1])
        changed["count"] += 1
        with self.assertRaises(us.DocketHold):
            us.validate(changed)

    def test_wrong_date_section_and_unreviewed_publisher_hold(self):
        for key, value in (("publisher_posted_date", "2026-10-16"),
                           ("publisher_posted_date", "2026-09-31"),
                           ("hosted_section", "command_statement"),
                           ("verification_basis", "live_robots_permission")):
            altered = copy.deepcopy(self.data)
            altered["records"][1][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(us.DocketHold):
                us.validate(altered)

    def test_historical_dvids_day_zero_is_not_silently_erased(self):
        historical = (us.ROOT / "shadow/us_indopacom/README.md").read_text(
            encoding="utf-8")
        self.assertIn("September 19, 2026", historical)
        self.assertIn("40 eligible records", historical)
        self.assertIn("manual-only", historical)
        self.assertIn("18 consecutive", historical)
        self.assertNotIn("no state branch exists", historical)
        self.assertNotIn("Day zero has not been reached", historical)

    def test_index_fixture_unchanged_and_cli_read_only(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            rc = us.main()
        self.assertEqual(rc, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["result"], "PASS_INDEX_ONLY")
        self.assertEqual(us.DOCKET.read_bytes(), self.original)
        self.assertNotIn("title", json.dumps(self.data))
        self.assertNotIn("document_text", json.dumps(self.data))

if __name__ == "__main__":
    unittest.main()
