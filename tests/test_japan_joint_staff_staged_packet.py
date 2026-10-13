"""Validate a real first-party Japan editorial source packet without network/model/mail.

This file is a separately reviewable research candidate. It is not the
scheduled Sunday input, an approved Brief or an archived source body.
"""
from pathlib import Path
import unittest

from core.brief_editorial_evidence import load_editorial_evidence, evidence_prompt


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "japan" / "week_2026-10-11" / "source_packets"
URL = "https://www.mod.go.jp/js/pdf/2026/p20261013_01.pdf"


class JapanJointStaffStagedPacketTest(unittest.TestCase):
    def test_real_oct13_source_is_typed_and_no_original_body_is_retained(self):
        rows = load_editorial_evidence("2026-10-17", "2026-10-17", directory=DIR)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["source_url"], URL)
        self.assertEqual(row["id"], "JP-W42-07")
        self.assertEqual(row["source_name"], "Japan Joint Staff")
        self.assertEqual(row["status"], "unapproved-source-linked-editorial-candidate")
        self.assertEqual(row["source_kind"], "official-publisher-page-reviewed-for-research")
        self.assertIsNone(row["state_commit"])
        self.assertIsNone(row["source_content_sha256"])
        self.assertIsNone(row["hash_rule"])
        prompt = evidence_prompt(rows)
        self.assertIn(URL, prompt)
        self.assertIn("one institutional account", prompt)
        self.assertNotIn("text_original", prompt)
        self.assertNotIn("body_original", prompt)


if __name__ == "__main__":
    unittest.main()
