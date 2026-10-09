"""No-text source receipts: identity is available without text leakage or fetch."""
from __future__ import annotations

import hashlib
import logging
import re
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.collection.contract import ExtractedDocument
from core.collection.text_gap_receipts import (
    _url_receipt,
    log_unreadable_source_receipts,
)


def document(body="", url="https://www.81.cn/yw_208727/1234.html",
             published="2026-10-09"):
    return ExtractedDocument(
        url=url, source_slug="pla_daily", title_original="PRIVATE HEADLINE",
        text_original=body, published_date=published,
    )


class TextGapReceiptContracts(unittest.TestCase):
    def setUp(self):
        self.log = Mock(spec=logging.Logger)

    def messages(self):
        # Emulate logging formatting, including %r escaping.
        return [c.args[0] % c.args[1:] for c in self.log.warning.call_args_list]

    def test_empty_whitespace_and_usable_are_distinguished(self):
        docs = [document(""), document(" \n\t", "https://www.81.cn/a/2.html"),
                document("real prose", "https://www.81.cn/a/3.html"),
                document("字", "https://www.81.cn/a/4.html")]
        self.assertEqual(log_unreadable_source_receipts("pla_daily", docs,
                                                         self.log), 2)
        self.assertEqual(self.log.warning.call_count, 2)
        self.assertIn("https://www.81.cn/a/2.html", self.messages()[1])
        self.assertTrue(all("PRIVATE HEADLINE" not in m for m in self.messages()))
        self.assertTrue(all("real prose" not in m for m in self.messages()))

    def test_no_gaps_means_no_new_logs(self):
        self.assertEqual(log_unreadable_source_receipts(
            "pla_daily", [document("one"), document("two")], self.log), 0)
        self.log.warning.assert_not_called()

    def test_full_count_even_when_detail_is_capped(self):
        docs = [document("", "https://www.81.cn/a/%d.html" % i)
                for i in range(25)]
        self.assertEqual(log_unreadable_source_receipts(
            "pla_daily", docs, self.log), 25)
        msgs = self.messages()
        self.assertEqual(len(msgs), 11)
        self.assertIn("shown=10 total=25", msgs[-1])
        self.assertNotIn("/24.html", "\n".join(msgs))
        self.assertIn("/0.html", msgs[0])

    def test_scrub_credentials_query_and_fragment_keep_stable_digest(self):
        source_url = "https://user:PRIVATE_PASS@www.81.cn/yw/77.html?token=PRIVATE_KEY#SECRET"
        self.assertEqual(log_unreadable_source_receipts(
            "pla_daily", [document("", source_url)], self.log), 1)
        msg = self.messages()[0]
        self.assertIn("https://www.81.cn/yw/77.html", msg)
        self.assertIn(hashlib.sha256(source_url.encode()).hexdigest()[:16], msg)
        for secret in ("PRIVATE_PASS", "PRIVATE_KEY", "SECRET", "PRIVATE HEADLINE"):
            self.assertNotIn(secret, msg)
        self.assertNotIn("content=", msg)

    def test_control_characters_cannot_inject_log_lines(self):
        url = "https://www.81.cn/a/77%0a.html"
        self.assertEqual(log_unreadable_source_receipts(
            "pla_daily", [document("", url)], self.log), 1)
        self.assertEqual(len(self.messages()[0].splitlines()), 1)

    def test_bad_url_source_and_date_are_fail_closed(self):
        bad = document("", "file:///tmp/PRIVATE_FILE", "2026-10-09\nPRIVATE")
        log_unreadable_source_receipts("pla_daily\nPRIVATE", [bad], self.log)
        msg = self.messages()[0]
        self.assertIn("source=unknown", msg)
        self.assertIn("<invalid-url>", msg)
        self.assertIn("published_date=unknown", msg)
        self.assertNotIn("PRIVATE_FILE", msg)
        self.assertNotIn("\n", msg)

    def test_zero_cap_keeps_count_without_individual_identities(self):
        docs = [document(), document("", "https://www.81.cn/yw/2.html")]
        self.assertEqual(log_unreadable_source_receipts(
            "pla_daily", docs, self.log, limit=0), 2)
        self.assertEqual(len(self.messages()), 1)
        self.assertIn("shown=0 total=2", self.messages()[0])

    def test_metadata_receipts_are_upstream_of_dedup_and_storage(self):
        source = (Path(__file__).resolve().parents[1] / "pipeline.py").read_text()
        start = source.index("result, documents = adapter.collect(")
        receipt = source.index("log_unreadable_source_receipts(slug, documents, logger)")
        storage = source.index("all_scraped.extend(doc.as_article_dict() for doc in documents)")
        dedup = source.index("title_deduped = dedup_articles(normalized)")
        self.assertLess(start, receipt)
        self.assertLess(receipt, storage)
        self.assertLess(storage, dedup)
        self.assertIn("no_text_count != result.text_unavailable", source)


if __name__ == "__main__":
    unittest.main()
