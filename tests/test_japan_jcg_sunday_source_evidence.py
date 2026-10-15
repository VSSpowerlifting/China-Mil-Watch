"""Japan Coast Guard source-note identity tests, no publisher requests or email."""
from __future__ import annotations

import unittest

from core.brief_editorial_evidence import EditorialEvidenceError, evidence_prompt
from tests.test_japan_joint_staff_editorial_evidence import source, load


class JapanCoastGuardSundayTests(unittest.TestCase):
    def candidate(self):
        item = source()
        item.update({
            "id": "JP-W42-08",
            "source_name": "Japan Coast Guard",
            "source_url": "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html",
            "published_date": "2026-10-13",
            "language": "en",
            "title_original": "Capacity Building Support for the Philippine Coast Guard",
            "summary": (
                "Japan Coast Guard described instructor training and support "
                "for Philippine authorities in an official English release. "
                "This fictional date is an offline parser fixture, not a claimed publication."
            ),
        })
        return item

    def test_english_jcg_original_is_a_link_first_research_family(self):
        item = self.candidate()
        verified = load(item)
        self.assertEqual(len(verified), 1)
        self.assertEqual(verified[0]["desk"], "japan")
        self.assertEqual(verified[0]["source_name"], "Japan Coast Guard")
        self.assertEqual(verified[0]["source_kind"],
                         "official-publisher-page-reviewed-for-research")
        self.assertIn("Japan Coast Guard", evidence_prompt(verified))

    def test_jcg_host_issuer_language_and_source_body_fail_closed(self):
        invalid = (
            ("source_name", "Japan Joint Staff"),
            ("source_name", "Japan Ministry of Defense"),
            ("language", "ja"),
            ("source_url", "https://www.kaiho.mlit.go.jp.evil.test/e/topics_archive/article9455.html"),
            ("source_url", "https://www.kaiho.mlit.go.jp/e/topics_archive/index.html"),
            ("source_url", "https://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html?x=1"),
            ("source_url", "http://www.kaiho.mlit.go.jp/e/topics_archive/article9455.html"),
            ("source_kind", "shadow-extracted-original"),
            ("state_commit", "b" * 40),
            ("status", "approved"),
            ("copy_scope", "approved-for-release"),
            ("body_original", "Copied government release not allowed"),
        )
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                item = self.candidate()
                item[key] = value
                with self.assertRaises(EditorialEvidenceError):
                    load(item)

    def test_distinct_jcg_urls_with_same_headline_stay_distinct(self):
        a = self.candidate()
        b = self.candidate()
        b["id"] = "JP-W42-09"
        b["source_url"] = "https://www.kaiho.mlit.go.jp/e/topics_archive/article9453.html"
        rows = load(a, b)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({x["source_url"] for x in rows}), 2)
        self.assertEqual(len({x["title_original"] for x in rows}), 1)


if __name__ == "__main__":
    unittest.main()
