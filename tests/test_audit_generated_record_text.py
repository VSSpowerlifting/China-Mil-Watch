"""Read-only public-build body inventory tests with fake source text only."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from html import escape
from pathlib import Path

from scripts.audit_generated_record_text import (
    CapturedTextParser, _expected_body, audit_generated_record_text, main,
)


class GeneratedTextExposureAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "fictional.db"
        self.output = self.root / "site"
        (self.output / "record").mkdir(parents=True)
        with sqlite3.connect(self.db) as con:
            con.executescript("""
                CREATE TABLE sources (id INTEGER PRIMARY KEY, slug TEXT UNIQUE);
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY,
                    source_id INTEGER REFERENCES sources(id),
                    text_original TEXT, url TEXT
                );
                INSERT INTO sources VALUES(1,'fictional_ministry');
                INSERT INTO sources VALUES(2,'unrelated_publisher');
            """)
            con.executemany("INSERT INTO articles VALUES(?,?,?,?)", [
                (101, 1, "FICTIONAL ALPHA & BETA\n\nAnother paragraph <not markup>",
                 "https://example.org/alpha"),
                (102, 1, "FAKE EXERCISE BODY " * 5, "https://example.org/beta"),
                (103, 1, "", "https://example.org/gamma"),
                (104, 2, "UNRELATED DUMMY", "https://example.org/unrelated"),
            ])
            con.commit()
        self.body1 = "FICTIONAL ALPHA & BETA\n\nAnother paragraph <not markup>"
        self.write_record(101, self.body1, "https://example.org/alpha")
        self.write_record(102, "WRONG CAPTURE", "https://example.org/beta")
        self.write_record(103, "", "https://example.org/gamma")

    def write_record(self, rid, original, url, *, include_body=True,
                     include_link=True):
        if include_body and original:
            body = '<div class="original-text" lang="en">' + "".join(
                "<p>" + escape(p.strip()) + "</p>"
                for p in original.split("\n") if p.strip()
            ) + "</div>"
        else:
            body = '<p>Original text is unavailable in this stored record.</p>'
        link = '<a href="' + escape(url, quote=True) + '">Open original</a>' if include_link else ""
        (self.output / "record" / (str(rid) + ".html")).write_text(
            "<!doctype html><html><body>" + link + body +
            "</body></html>", encoding="utf-8"
        )

    def audit(self):
        return audit_generated_record_text(self.db, self.output,
                                           "fictional_ministry")

    def test_exact_source_body_recognized_without_leaking_prose(self):
        result = self.audit()
        self.assertEqual(result["record_ids"]["exact_full_body_rendered"], [101])
        self.assertEqual(result["counts"]["captured_body_rendered_exact"], 1)
        dumped = json.dumps(result)
        self.assertNotIn("FICTIONAL ALPHA", dumped)
        self.assertNotIn("FAKE EXERCISE", dumped)
        self.assertEqual(result["legal_conclusion"], None)
        self.assertFalse(result["source_use_permission_checked"])

    def test_source_filter_does_not_count_unrelated_publisher(self):
        result = self.audit()
        self.assertEqual(result["counts"]["archived_records"], 3)
        self.assertNotIn(104, sum(result["record_ids"].values(), []))

    def test_mismatch_and_blank_source_are_distinct(self):
        r = self.audit()
        self.assertEqual(r["counts"]["captured_body_rendered_different"], 1)
        self.assertEqual(r["record_ids"]["body_mismatch"], [102])
        self.assertEqual(r["record_ids"]["body_not_rendered"], [103])
        self.assertEqual(r["counts"]["archived_body_nonempty"], 2)

    def test_missing_generated_page_is_measured(self):
        (self.output / "record" / "102.html").unlink()
        r = self.audit()
        self.assertEqual(r["record_ids"]["missing_pages"], [102])
        self.assertEqual(r["counts"]["generated_page_present"], 2)
        self.assertEqual(r["counts"]["generated_page_missing"], 1)

    def test_source_url_hyperlinks_counted_separately(self):
        self.write_record(101, self.body1, "https://example.org/alpha",
                          include_link=False)
        r = self.audit()
        self.assertEqual(r["record_ids"]["missing_official_link"], [101])
        self.assertEqual(r["counts"]["original_url_link_present"], 2)

    def test_original_block_missing_even_when_disclaimer_present(self):
        self.write_record(101, "", "https://example.org/alpha")
        r = self.audit()
        self.assertEqual(r["counts"]["original_text_container_present"], 1)
        self.assertIn(101, r["record_ids"]["body_not_rendered"])

    def test_encoded_ampersands_and_html_escape_compare_exactly(self):
        p = CapturedTextParser()
        p.feed('<div class="original-text"><p>FICTIONAL ALPHA &amp; BETA</p>'
               '<p>Another paragraph &lt;not markup&gt;</p></div>')
        self.assertEqual(" ".join(" ".join(p.fragments).split()),
                         _expected_body(self.body1))

    def test_generated_html_and_sqlite_file_never_mutated(self):
        original_db = hashlib.sha256(self.db.read_bytes()).hexdigest()
        html = self.output / "record" / "101.html"
        original_html = hashlib.sha256(html.read_bytes()).hexdigest()
        self.audit()
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(),
                         original_db)
        self.assertEqual(hashlib.sha256(html.read_bytes()).hexdigest(),
                         original_html)
        self.assertFalse(Path(str(self.db) + "-wal").exists())
        self.assertFalse(Path(str(self.db) + "-shm").exists())

    def test_source_missing_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "no archive records"):
            audit_generated_record_text(self.db, self.output, "absent_source")

    def test_output_missing_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "generated site directory"):
            audit_generated_record_text(self.db, self.root / "not-output",
                                        "fictional_ministry")

    def test_no_original_text_in_cli_stdout(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--db", str(self.db), "--output", str(self.output),
                         "--source", "fictional_ministry"])
        self.assertEqual(code, 0)
        self.assertNotIn("FICTIONAL ALPHA", output.getvalue())
        self.assertNotIn("WRONG CAPTURE", output.getvalue())
        self.assertEqual(json.loads(output.getvalue())["counts"]["archived_records"], 3)

    def test_parser_does_not_include_text_outside_div(self):
        p = CapturedTextParser()
        p.feed("<h1>do not copy</h1><div class='original-text'><p>inside</p></div>"
               "<aside>not part of capture</aside>")
        self.assertEqual(" ".join(p.fragments).strip(), "inside")

    def test_parser_nested_tags(self):
        p = CapturedTextParser()
        p.feed("<div class='original-text'><p>Alpha <em>Beta</em> Gamma</p>"
               "<p>Delta</p></div>")
        self.assertEqual(" ".join(p.fragments).split(), ["Alpha", "Beta", "Gamma", "Delta"])

    def test_parser_br_void_tag_does_not_absorb_footer(self):
        p = CapturedTextParser()
        p.feed('<div class="original-text"><p>Alpha<br>Beta &amp; Gamma</p>'
               '</div><p>UNRELATED FOOTER</p>')
        self.assertEqual(" ".join(p.fragments).split(),
                         ["Alpha", "Beta", "&", "Gamma"])
        self.assertEqual(p.depth, 0)

    def test_parser_img_void_tag_does_not_absorb_footer(self):
        p = CapturedTextParser()
        p.feed('<div class="original-text"><p>Alpha<img src="fake.png">'
               '<em>Beta</em></p></div><aside>UNRELATED FOOTER</aside>')
        self.assertEqual(" ".join(p.fragments).split(), ["Alpha", "Beta"])
        self.assertEqual(p.depth, 0)


if __name__ == "__main__":
    unittest.main()
