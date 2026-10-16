"""DVIDS official USINDOPACOM news API source-free contracts."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import date

from scripts import collect_us_dvids_official_metadata as d

DAY="2026-10-15"

def record(i, day=DAY):
    return {
        "id": "news:"+str(i),
        "type": "news",
        "date_published": day+"T17:42:19Z",
        "url": "https://www.dvidshub.net/news/"+str(i)+"/example-event",
        "title": "Publisher title NOT stored",
        "short_description": "Sensitive publisher description NOT stored",
        "thumbnail": "https://example.invalid/no-media-copy.jpg",
        "unit_name": "A US military service",
    }

def response():
    return {"page_info":{"total_results":77,"results_per_page":2},
            "results":[record(123456),record(123457,"2026-10-14")]}

class DVIDSNeutralMetadata(unittest.TestCase):
    def test_only_official_identity_date_url_and_issuer_retained(self):
        packet=d.build_packet(response(),observed_on_utc=DAY)
        self.assertEqual(len(packet["rows"]),2)
        self.assertEqual(packet["query_filters"]["cocom"],"USINDOPACOM")
        self.assertEqual(packet["query_filters"]["type"],"news")
        self.assertTrue(packet["first_page_only"])
        self.assertFalse(packet["complete_cocom_history_claimed"])
        self.assertFalse(packet["source_remove_and_update_sync_verified"])
        self.assertFalse(packet["public_release_authorized"])
        self.assertFalse(packet["credentials_verified_for_publisher_use"])
        dumped=json.dumps(packet)
        for content in ("Publisher title", "Sensitive publisher", "thumbnail", "unit_name"):
            self.assertNotIn(content,dumped)
        self.assertTrue(all(set(row)=={
            "source_identity","canonical_official_url","publisher_posted_date",
            "official_issuer","official_publisher","api_source_family",
        } for row in packet["rows"]))

    def test_reject_mismatched_identity_or_external_host(self):
        for field,val in (
            ("url","https://malicious.invalid/news/123456"),
            ("url","http://www.dvidshub.net/news/123456/example-event"),
            ("url","https://www.dvidshub.net/news/999999/wrong"),
            ("id","news:999999"),
            ("id","image:123456"),
            ("type","image"),
        ):
            with self.subTest(field=field,val=val):
                p=response()
                p["results"][0][field]=val
                with self.assertRaises(d.DVIDSHold):
                    d.sanitize(p,observed_on_utc=DAY)

    def test_reject_future_undated_non_utc_or_duplicate(self):
        for day in ("2026-10-16","2026-10-15T10:00:00+02:00",None):
            with self.subTest(day=day):
                p=response()
                p["results"][0]["date_published"]=(day+"T01:00:00Z" if day and len(day)==10 else day)
                with self.assertRaises(d.DVIDSHold):
                    d.sanitize(p,observed_on_utc=DAY)
        p=response();p["results"][1]=p["results"][0].copy()
        with self.assertRaisesRegex(d.DVIDSHold,"duplicate"):
            d.sanitize(p,observed_on_utc=DAY)

    def test_reject_unbounded_empty_or_malformed_response(self):
        for invalid in (
            {"results":[],"page_info":{"total_results":0,"results_per_page":20}},
            {"results":[record(i) for i in range(21)],
             "page_info":{"total_results":21,"results_per_page":21}},
            {"results":[record(11)],
             "page_info":{"total_results":0,"results_per_page":1}},
            {"results":[record(11)],
             "page_info":{"total_results":1,"results_per_page":"one"}},
            {"error":"api credential denied"},
        ):
            with self.subTest(payload=str(invalid)[:50]):
                with self.assertRaises(d.DVIDSHold):
                    d.sanitize(invalid,observed_on_utc=DAY)

    def test_credentials_are_mandatory_without_network_fallback(self):
        with patch.object(d.urllib.request, "build_opener") as remote:
            for key in (None, "", "  ", "public-demo"):
                with self.subTest(key_description="empty or nonpublic key"):
                    with self.assertRaises(d.DVIDSHold):
                        d.fetch_with_issued_key(key)
            remote.assert_not_called()

    def test_dvids_search_public_key_requires_documented_prefix(self):
        # DVIDS specifies public Search keys begin with 'key-'.
        # Do not transform a private key or account secret into Search access.
        with self.assertRaisesRegex(d.DVIDSHold,"public_search_key_prefix_missing"):
            d.normalize_issued_key("ABC123-private-or-wrong-key")
        with self.assertRaisesRegex(d.DVIDSHold,"issued_api_key_missing"):
            d.normalize_issued_key(" \n  ")

    def test_key_copy_whitespace_is_safe_to_trim_without_changing_key(self):
        key = "key-" + "A1b2C3d4E5f6"
        self.assertEqual(d.normalize_issued_key(key), key)
        self.assertEqual(d.normalize_issued_key(" \n" + key + "\r\t"), key)
        with self.assertRaisesRegex(d.DVIDSHold,"public_search_key_suffix_invalid"):
            d.normalize_issued_key(key[:6] + " " + key[6:])

    def test_do_not_invent_an_undocumented_key_suffix_alphabet_or_length(self):
        # Public Search documentation specifies prefix, not suffix encoding.
        # All printable ASCII is safe when urllib.parse.urlencode encodes it.
        for key in ("key-x", "key-case.with+encoded%chars=ok",
                    "key-" + "a" * 508):
            with self.subTest(suffix_category="printable"):
                self.assertEqual(d.normalize_issued_key(key), key)
        for bad in ("key-", "key-\x00abc", "key-new\nline",
                    "key-α", "key-" + "a" * 509):
            with self.subTest(suffix_category="invalid"):
                with self.assertRaisesRegex(d.DVIDSHold,
                                            "public_search_key_suffix_invalid"):
                    d.normalize_issued_key(bad)


    def test_private_scratch_only_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"private.json"
            result=d.stage_private(d.build_packet(response(),observed_on_utc=DAY),path)
            self.assertEqual(result,path)
            self.assertEqual(json.loads(path.read_text())["production_records_written"],0)
            with self.assertRaises(d.DVIDSHold):
                d.stage_private({},path)
            with self.assertRaises(d.DVIDSHold):
                d.stage_private({},Path("relative.json"))

    def test_a_manual_rehearsal_does_not_authorize_live_collection(self):
        with self.assertRaises(SystemExit) as caught:
            d.main(["--scratch-json","/tmp/temporary.json"])
        self.assertIn("explicit owner-approved",str(caught.exception))


if __name__=="__main__":
    unittest.main()
