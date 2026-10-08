"""Fail-closed tests for Vietnam's separately reviewed source-link surface."""
import json
import tempfile
import unittest
from pathlib import Path

from core.reviewed_source_links import ReviewedLinkError, load_reviewed_links


def example():
    return {
        "id": "mps-vi-1791199100",
        "source_slug": "vn_mps_foreign_affairs_vi",
        "source_url": "https://bocongan.gov.vn/bai-viet/official-example?id=1791199100",
        "title_original": "Thông tin đối ngoại chính thức",
        "language": "vi",
        "published_date": "2026-10-05",
        "reviewed_by": "Named human reviewer",
        "reviewed_on": "2026-10-08",
        "state_commit": "a" * 40,
        "checks": {
            "source_page_opened": True,
            "title_checked": True,
            "publication_date_checked": True,
            "issuing_institution_checked": True,
            "link_publication_approved": True,
        },
    }


class VietnamReviewedLinksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "links.json"

    def load(self, rows):
        self.path.write_text(json.dumps({
            "schema": "vietnam-reviewed-source-links/1", "entries": rows,
        }, ensure_ascii=False), encoding="utf-8")
        return load_reviewed_links(self.path, today=__import__("datetime").date(2026, 10, 8))

    def test_missing_optional_file_and_empty_register(self):
        self.assertEqual(load_reviewed_links(self.path), [])
        self.assertEqual(self.load([]), [])

    def test_approved_metadata_only_and_deterministic_order(self):
        first = example()
        second = example()
        second.update(id="moit-vi-abc", source_slug="vn_moit_energy_vi",
                      source_url="https://moit.gov.vn/tin-tuc/energy",
                      published_date="2026-10-06")
        result = self.load([first, second])
        self.assertEqual([r["id"] for r in result],
                         ["moit-vi-abc", "mps-vi-1791199100"])
        self.assertNotIn("checks", result[0])
        self.assertNotIn("text_original", result[0])

    def test_refuses_missing_or_false_manual_check(self):
        for value in [False, None]:
            row = example()
            row["checks"]["link_publication_approved"] = value
            with self.subTest(value=value), self.assertRaises(ReviewedLinkError):
                self.load([row])

    def test_refuses_missing_reviewer_and_unpinned_version(self):
        for field, value in [("reviewed_by", ""), ("state_commit", "a" * 39)]:
            row = example()
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ReviewedLinkError):
                self.load([row])

    def test_refuses_unsafe_source_domains_and_unapproved_family(self):
        cases = [
            ("https://evil.example/article", "vn_mps_foreign_affairs_vi"),
            ("http://bocongan.gov.vn/article", "vn_mps_foreign_affairs_vi"),
            ("https://bocongan.gov.vn.evil.example/article", "vn_mps_foreign_affairs_vi"),
            ("https://moit.gov.vn/article", "vn_mps_foreign_affairs_vi"),
            ("https://tapchiqptd.vn/en/article", "vn_journal_en"),
            ("https://bocongan.gov.vn:bad/article", "vn_mps_foreign_affairs_vi"),
            ("https://bocongan.gov.vn/article#fragment", "vn_mps_foreign_affairs_vi"),
            ("https://bocongan.gov.vn/article\\nmalicious", "vn_mps_foreign_affairs_vi"),
        ]
        for url, slug in cases:
            row = example()
            row.update(source_url=url, source_slug=slug)
            with self.subTest(url=url), self.assertRaises(ReviewedLinkError):
                self.load([row])

    def test_refuses_unreviewed_translation_and_unexpected_body(self):
        for unexpected in ("english_title", "text_original", "body"):
            row = example()
            row[unexpected] = "Do not publish this"
            with self.subTest(key=unexpected), self.assertRaises(ReviewedLinkError):
                self.load([row])

    def test_refuses_future_review_and_duplicate_urls(self):
        row = example()
        row["reviewed_on"] = "2026-10-09"
        with self.assertRaises(ReviewedLinkError):
            self.load([row])
        row = example()
        dup = example()
        dup["id"] = "another-id"
        with self.assertRaises(ReviewedLinkError):
            self.load([row, dup])

    def test_duplicate_json_keys_are_refused(self):
        self.path.write_text('{"schema":"vietnam-reviewed-source-links/1","schema":"other","entries":[]}')
        with self.assertRaises(ReviewedLinkError):
            load_reviewed_links(self.path)

    def test_is_not_a_production_desk_or_brief_source(self):
        from core.brief_contract import eligible_desks
        from core.desk_registry import load_registry
        desks = eligible_desks(load_registry())
        self.assertNotIn("vietnam", desks)


if __name__ == "__main__":
    unittest.main()
