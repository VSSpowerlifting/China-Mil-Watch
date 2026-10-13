"""Offline negative tests for PCG MEPCOM's *unapproved* source lead.

These tests are fully synthetic. No HTTP, full publisher text, production DB,
source admission, or output regeneration.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import validate_ph_mepcom_candidate as v  # noqa: E402


class MepcomBoundary(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(v.PACKET.read_text(encoding="utf-8"))

    def test_two_actual_links_remain_discovery_only(self):
        result = v.validate(self.packet)
        self.assertEqual(result["first_party_page_links"], 2)
        self.assertEqual(result["verified_enumerators"], 0)
        self.assertEqual(result["archived_records"], 0)
        self.assertFalse(result["collection_enabled"])
        self.assertFalse(result["source_reuse_cleared"])

    def test_reject_any_invented_permission_or_enabled_collecting(self):
        for key in v.HOLD_KEYS:
            altered = copy.deepcopy(self.packet)
            altered["holds"][key] = (
                True if isinstance(altered["holds"][key], bool) else "allowed")
            with self.subTest(key=key), self.assertRaises(v.BoundaryError):
                v.validate(altered)

    def test_news_page_is_not_automatically_a_complete_enumerator(self):
        for key in ("complete_enumerator_verified",
                    "archive_completeness_verified"):
            altered = copy.deepcopy(self.packet)
            altered["index_observation"][key] = True
            with self.subTest(key=key), self.assertRaises(v.BoundaryError):
                v.validate(altered)

    def test_article_permalink_is_exact_unicode_slug_byte_identity(self):
        a = self.packet["candidates"][0]["url"]
        self.assertIn("%F0%9D", a)
        for bad in (
            a.lower(),
            a.replace("%F0%9D", "%f0%9d"),
            a.replace("%F0%9D", "MARINE"),
            a.replace("https://", "http://"),
            a.replace("coastguard.gov.ph", "coastguard.gov.ph.evil.test"),
            a + "?x=1",
            a + "#fragment",
        ):
            altered = copy.deepcopy(self.packet)
            altered["candidates"][0]["url"] = bad
            with self.subTest(url=bad[:75]), self.assertRaises(v.BoundaryError):
                v.validate(altered)

    def test_no_unverified_raw_bytes_corpus_id_or_rights_attestation(self):
        for key, value in (
            ("raw_response_sha256", "0" * 64),
            ("archive_record_id", 12345),
            ("rights_approval", {"approved_by": "fictional"}),
        ):
            altered = copy.deepcopy(self.packet)
            altered["candidates"][1][key] = value
            with self.subTest(field=key), self.assertRaises(v.BoundaryError):
                v.validate(altered)

    def test_posted_on_sep10_remains_distinct_from_july21_22_events(self):
        a, b = self.packet["candidates"]
        self.assertEqual(a["visible_post_date"], b["visible_post_date"])
        self.assertNotEqual(a["visible_post_date"], a["reported_event_start"])
        self.assertNotEqual(b["visible_post_date"], b["reported_event_end"])
        for key, false_date in (
            ("visible_post_date", "2026-07-21"),
            ("reported_event_start", "2026-09-10"),
            ("reported_event_end", "2026-09-10"),
        ):
            altered = copy.deepcopy(self.packet)
            altered["candidates"][0][key] = false_date
            with self.subTest(field=key), self.assertRaises(v.BoundaryError):
                v.validate(altered)

    def test_subcommand_is_not_replaced_by_generic_coast_guard_issuer(self):
        altered = copy.deepcopy(self.packet)
        altered["candidates"][1]["issuing_unit"] = "Philippine Coast Guard"
        with self.assertRaises(v.BoundaryError):
            v.validate(altered)

    def test_duplicate_or_unreviewed_url_is_refused(self):
        for variation in ("duplicate", "extra", "deleted"):
            altered = copy.deepcopy(self.packet)
            if variation == "duplicate":
                altered["candidates"][1]["url"] = altered["candidates"][0]["url"]
            elif variation == "extra":
                altered["candidates"].append(copy.deepcopy(altered["candidates"][0]))
            else:
                altered["candidates"].pop()
            with self.subTest(variation=variation), self.assertRaises(v.BoundaryError):
                v.validate(altered)

    def test_disallows_body_publication_claims_and_issuer_mislabeling(self):
        for changed_key, value in (
            ("publisher_institution", "Philippine Information Agency"),
            ("mode", "production"),
        ):
            altered = copy.deepcopy(self.packet)
            altered[changed_key] = value
            with self.subTest(changed_key=changed_key), self.assertRaises(v.BoundaryError):
                v.validate(altered)
        altered = copy.deepcopy(self.packet)
        altered["candidates"][0]["publisher_full_text"] = "do not copy originals"
        with self.assertRaises(v.BoundaryError):
            v.validate(altered)

    def test_cli_succeeds_without_any_network_or_repository_writes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fixture.json"
            p.write_text(json.dumps(self.packet), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(v.ROOT / "scripts/validate_ph_mepcom_candidate.py"),
                 "--packet", str(p)],
                capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)["archived_records"], 0)
            self.assertEqual(sorted(p.name for p in Path(d).iterdir()), ["fixture.json"])


if __name__ == "__main__":
    unittest.main()
