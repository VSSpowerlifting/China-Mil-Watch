"""Network-free, fail-closed checks for the first-party Joint Staff index."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.review_japan_joint_staff_index import (
    JointStaffIndexError, inspect_index_html, main,
)

BASE = "https://www.mod.go.jp/js/pdf/2026/"


def index(*items):
    """Pairs are publisher list-row date labels and official PDF filenames."""
    return ("<html><body><h2>2026年:報道発表</h2><ul>" +
            "".join('<li><a href="/js/pdf/2026/' + name + '">' + label +
                    "</a></li>" for label, name in items) +
            "</ul></body></html>")


Y9 = ("2026年10月13日 公表 中国軍機の動向について（Y-9）",
      "p20261013_01.pdf")
IL20 = ("2026年10月09日 公表 ロシア軍機の動向について（IL-20）",
        "p20261009_03.pdf")
TB001 = ("2026年10月09日 公表 中国軍機の動向について（TB-001）",
         "p20261009_02.pdf")


class JapanJointStaffIndexTests(unittest.TestCase):
    def report(self, content=None, cutoff="2026-10-13"):
        return inspect_index_html(
            content if content is not None else index(Y9, IL20, TB001),
            week_ending="2026-10-17", cutoff=cutoff)

    def test_actual_three_official_link_identities_keep_oct9_outside_week(self):
        item = self.report()
        self.assertEqual(item["saw_current_year_pdf_links"], 3)
        self.assertEqual(len(item["in_window_official_links"]), 1)
        row = item["in_window_official_links"][0]
        self.assertEqual(row["official_url"], BASE + "p20261013_01.pdf")
        self.assertEqual(row["published_date"], "2026-10-13")
        self.assertEqual(row["publisher"], "Japan Joint Staff")
        self.assertFalse(row["archived_source_body"])
        self.assertFalse(row["eligible_for_automatic_model_drafting"])
        self.assertFalse(row["editorial_approved"])
        self.assertFalse(row["production_record"])
        self.assertFalse(item["complete_japan_defense_coverage"])
        self.assertFalse(item["model_called"])
        self.assertFalse(item["email_sent"])

    def test_same_day_distinct_docs_are_not_merged_by_date_or_generic_title(self):
        second = ("2026年10月13日 公表 ロシア軍機の動向について",
                  "p20261013_02.pdf")
        rows = self.report(index(Y9, second))["in_window_official_links"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r["official_url"] for r in rows}), 2)

    def test_bad_source_row_date_fails_closed(self):
        mismatched = ("2026年10月12日 公表 中国軍機の動向について",
                      "p20261013_01.pdf")
        for entry in (mismatched,
                      ("中国軍機の動向について（Y-9）", "p20261013_01.pdf"),
                      ("2026年10月13日 2026年10月12日 公表", "p20261013_01.pdf")):
            with self.subTest(entry=entry), self.assertRaises(JointStaffIndexError):
                self.report(index(entry))

    def test_invalid_current_year_original_identity_is_refused(self):
        bad = ("2026年10月13日 公表 変形PDF", "p20261013_1.pdf")
        invalid_calendar = ("2026年10月13日 公表 不正日付", "p20261313_01.pdf")
        for row in (bad, invalid_calendar):
            with self.subTest(row=row), self.assertRaises(JointStaffIndexError):
                self.report(index(row))

    def test_duplicate_entry_and_query_parameter_blocked(self):
        with self.assertRaises(JointStaffIndexError):
            self.report(index(Y9, Y9))
        query = ("2026年10月13日 公表 元の文書", "p20261013_01.pdf?download=1")
        with self.assertRaises(JointStaffIndexError):
            self.report(index(query))

    def test_dates_and_cutoff_refuse_false_publication_future(self):
        self.assertEqual(len(self.report(cutoff="2026-10-12")["in_window_official_links"]), 0)
        for ending, cutoff in (
            ("2026-10-16", "2026-10-13"),
            ("2026-10-17", "2026-10-18"),
            ("2026-10-17", "2026-10-10"),
            ("2026-10-17", "foo"),
        ):
            with self.subTest(ending=ending, cutoff=cutoff):
                with self.assertRaises(JointStaffIndexError):
                    inspect_index_html(index(Y9), week_ending=ending, cutoff=cutoff)

    def test_missing_index_source_evidence_does_not_claim_silence(self):
        for html in ("<html><body>Navigation only</body></html>",
                     "<html><body><a href='/js/pdf/2025/p20250101_01.pdf'>"
                     "2025年1月1日</a></body></html>"):
            with self.subTest(html=html):
                with self.assertRaises(JointStaffIndexError):
                    self.report(html)

    def test_operator_rehearsal_writes_metadata_only_and_does_not_network(self):
        with tempfile.TemporaryDirectory() as t:
            directory = Path(t)
            source = directory / "index.html"
            target = directory / "review.json"
            source.write_text(index(Y9, IL20), encoding="utf-8")
            self.assertEqual(main([
                "--index-html", str(source),
                "--week-ending", "2026-10-17",
                "--cutoff", "2026-10-13",
                "--output", str(target),
            ]), 0)
            report = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(len(report["in_window_official_links"]), 1)
            self.assertNotIn("text_original", target.read_text(encoding="utf-8"))
            self.assertNotIn("pdf_bytes", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
