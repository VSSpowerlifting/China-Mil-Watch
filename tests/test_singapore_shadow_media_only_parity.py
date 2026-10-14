"""Offline Singapore shadow parity for publisher-authenticated text-unavailable pages.

The September 29 captured MINDEF release fixture is a trimmed portion of a
real response, not a fabricated transcription. Other filler pages are marked
synthetic in tests.test_singapore_image_only_release. No publisher network,
OCR, model, main database, email or release operation occurs here.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from core.collection import status as st
from scraper.sources import sg_mindef as sg
from scripts import shadow_collect as shadow
from tests.test_singapore_image_only_release import (
    INFOGRAPHIC, FakeSession, adapter as recovery_adapter, captured,
    release_page, para, url,
)

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class TestSingaporeRealCapturedMediaOnlyShadow(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ipr-sg-shadow-media-")
        self.addCleanup(self.temporary.cleanup)
        self.state = Path(self.temporary.name) / "sg-shadow"

    def run_shadow(self, session=None, run_id="first"):
        return shadow.run(
            self.state, date(2026, 9, 28), 6, 40,
            run_id, "offline-test-sha",
            adapter=recovery_adapter(session or FakeSession()))

    def read_info(self):
        with sqlite3.connect(str(self.state / "shadow.db")) as conn:
            return conn.execute(
                "SELECT title_original,text_original,published_date,"
                "content_sha256,capture_sha256 FROM shadow_records WHERE url=?",
                (url(INFOGRAPHIC),),
            ).fetchone()

    def test_captured_image_only_record_has_identity_but_never_image_text(self):
        self.assertEqual(len(sg.document_body(captured(INFOGRAPHIC))), 178)
        evidence = sg.article_evidence(captured(INFOGRAPHIC))
        self.assertIsNotNone(evidence)
        self.assertTrue(evidence.is_image_only)
        self.assertEqual(evidence.prose_chars, 0)
        self.assertEqual(evidence.images, 1)

        receipt = self.run_shadow()
        self.assertEqual(receipt["health"], "ok")
        self.assertEqual(receipt["result"], st.OK)
        self.assertEqual(receipt["selected"], 11)
        self.assertEqual(receipt["retrieved"], 11)
        self.assertEqual(receipt["inserted"], 11)
        self.assertEqual(receipt["extraction_failures"], 0)
        self.assertEqual(receipt["fetch_failures"], 0)
        self.assertEqual(receipt["failure_log"], [])
        self.assertEqual(receipt["text_unavailable"], 1)
        self.assertEqual(receipt["media_only_urls"], [url(INFOGRAPHIC)])

        record = self.read_info()
        self.assertIsNotNone(record)
        self.assertEqual(record[0], "Infographic: Ex Trident Resolve 2026")
        self.assertEqual(record[1], "")
        self.assertEqual(record[2], "2026-09-22")
        self.assertEqual(record[3], EMPTY_SHA256)
        self.assertEqual(len(record[4]), 64)
        self.assertTrue((self.state / "clock.json").is_file())
        receipts = list((self.state / "ledger").glob("*.json"))
        self.assertEqual(len(receipts), 1)
        stored = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual(stored["media_only_urls"], [url(INFOGRAPHIC)])
        self.assertNotIn("Infographic: Ex Trident 2026" + " IMAGE", json.dumps(stored))
        self.assertNotIn("image_alt_text", stored)
        self.assertNotIn("image_bytes", stored)

    def test_image_only_record_is_idempotent_and_no_new_body_is_invented(self):
        first = self.run_shadow(run_id="one")
        original = self.read_info()
        second = self.run_shadow(run_id="two")
        self.assertEqual(first["inserted"], 11)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["duplicates"], 11)
        self.assertEqual(second["result"], st.OK_ALL_DUPLICATES)
        self.assertEqual(second["health"], "ok")
        self.assertEqual(second["text_unavailable"], 1)
        self.assertEqual(second["media_only_urls"], [url(INFOGRAPHIC)])
        self.assertEqual(self.read_info(), original)

    def test_unknown_short_template_still_fails_and_never_starts_clock(self):
        corrupted = release_page("A malformed release", container="")
        receipt = self.run_shadow(
            session=FakeSession(overrides={INFOGRAPHIC: corrupted}))
        self.assertEqual(receipt["extraction_failures"], 1)
        self.assertEqual(receipt["text_unavailable"], 0)
        self.assertEqual(receipt["media_only_urls"], [])
        self.assertEqual(receipt["health"], "fail")
        self.assertEqual(receipt["result"], st.EXTRACTION_FAILURE)
        self.assertEqual(receipt["failure_log"], [{
            "url": url(INFOGRAPHIC),
            "stage": "extract",
            "status": st.EXTRACTION_FAILURE,
        }])
        self.assertIsNone(receipt["shadow_day"])
        self.assertFalse((self.state / "clock.json").exists())

    def test_short_genuine_prose_is_not_mistaken_for_image_only(self):
        snippet = "The Singapore Armed Forces conducted a short readiness exercise."
        page = release_page("A short official release", container=para(snippet))
        self.assertLess(len(sg.document_body(page)), sg.MIN_BODY_CHARS)
        receipt = self.run_shadow(
            session=FakeSession(overrides={INFOGRAPHIC: page}))
        self.assertEqual(receipt["health"], "ok")
        self.assertEqual(receipt["text_unavailable"], 0)
        self.assertEqual(receipt["media_only_urls"], [])
        self.assertIn(snippet, self.read_info()[1])

    def test_unmodified_strict_extract_still_refuses_the_old_short_body(self):
        # Only the explicitly selected shadow structural method changes.
        # Other generic users of .extract() retain the strict old behavior.
        from tests.test_singapore_image_only_release import capture
        strict = recovery_adapter().extract(capture(INFOGRAPHIC))
        permitted = recovery_adapter().extract_shadow_structural(
            capture(INFOGRAPHIC))
        self.assertEqual(strict.status, st.EXTRACTION_FAILURE)
        self.assertEqual(permitted.status, st.OK)
        self.assertEqual(permitted.documents[0].text_original, "")
        self.assertEqual(
            permitted.documents[0].extra["content_verdict"], "media_only")
        self.assertEqual(
            permitted.documents[0].extra["content_sha256"], EMPTY_SHA256)


if __name__ == "__main__":
    unittest.main()
