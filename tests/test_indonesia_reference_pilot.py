"""Offline safety contracts: Indonesia public-reference candidate is PRIVATE and held."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.preview_indonesia_reference_pilot import (
    DEFAULT, PilotHold, load, main, private_preview, validate,
)


class IndonesiaPilotTests(unittest.TestCase):
    def setUp(self):
        self.obj = load(DEFAULT)

    def test_actual_four_held_references_and_safe_html(self):
        rows = validate(self.obj)
        self.assertEqual([x["reference_id"] for x in rows],
                         ["ID-01", "ID-02", "ID-03", "ID-04"])
        self.assertTrue(all(r["source_url"].startswith(
            "https://www.kemhan.go.id/") for r in rows))
        self.assertTrue(all(r["published_date"] in r["source_url"]
                            .replace("/", "-") for r in rows))
        self.assertFalse(self.obj["owner_release_approved"])
        self.assertFalse(self.obj["day7_review_completed"])
        self.assertFalse(self.obj["independent_human_source_review_completed"])
        self.assertFalse(self.obj["public_renderer_consumes_this_file"])
        body = private_preview(self.obj)
        self.assertEqual(body.count('<li>'), 4)
        self.assertIn("NOT APPROVED FOR PUBLICATION", body)
        self.assertIn("noindex,nofollow,noarchive", body)
        self.assertIn("The Sudirman Dialogue 2027", body)
        self.assertNotIn("text_original", body)
        self.assertNotIn("publisher_response", body)
        self.assertNotIn("site/preview", body)

    def test_approval_and_scope_mutations_fail_closed(self):
        for key in ("owner_release_approved", "day7_review_completed",
                    "independent_human_source_review_completed",
                    "public_renderer_consumes_this_file", "production_admitted"):
            with self.subTest(top=key):
                bad = copy.deepcopy(self.obj)
                bad[key] = True
                with self.assertRaises(PilotHold):
                    validate(bad)
        for key in ("public_reference_approved", "source_specific_rights_approved",
                    "independent_human_original_review",
                    "publisher_body_republication_approved"):
            with self.subTest(row=key):
                bad = copy.deepcopy(self.obj)
                bad["candidates"][0][key] = True
                with self.assertRaises(PilotHold):
                    validate(bad)

    def test_spoofed_official_sources_and_publication_time_fail_closed(self):
        cases = [
            ("source_url", "http://www.kemhan.go.id/2026/10/10/fake.html"),
            ("source_url", "https://bad.example/2026/10/10/fake.html"),
            ("source_url", "https://www.kemhan.go.id/2026/10/10/fake.html"),
            ("source_url", self.obj["candidates"][0]["source_url"] + "?share=1"),
            ("source_identity", "kemhan:/2026/10/10/other.html"),
            ("published_date", "2026-10-09"),
            ("language", "en"),
            ("archived_at_commit", "f" * 40),
            ("source_family", "id_kemhan_siaran_pers"),
            ("title_original", "<script>alert(1)</script>"),
            ("editorial_caveat_tag", "verified_defense_treaty"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                bad = copy.deepcopy(self.obj)
                bad["candidates"][0][key] = value
                with self.assertRaises(PilotHold):
                    validate(bad)

    def test_extra_body_fields_and_duplicate_links_rejected(self):
        bad = copy.deepcopy(self.obj)
        bad["candidates"][0]["body"] = "UNLICENSED ARTICLE"
        with self.assertRaises(PilotHold):
            validate(bad)
        bad = copy.deepcopy(self.obj)
        bad["candidates"][1]["source_url"] = bad["candidates"][0]["source_url"]
        with self.assertRaises(PilotHold):
            validate(bad)
        bad = copy.deepcopy(self.obj)
        bad["candidates"][0]["reference_id"] = "ID-05"
        with self.assertRaises(PilotHold):
            validate(bad)

    def test_double_json_key_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text('{"schema":"a","schema":"b"}')
            with self.assertRaises(PilotHold):
                load(p)

    def test_file_preview_only_to_new_private_external_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "id-preview.html"
            self.assertEqual(main(["--preview", str(p)]), 0)
            self.assertTrue(p.is_file())
            self.assertIn("PRIVATE RESEARCH ONLY", p.read_text(encoding="utf-8"))
            with self.assertRaises(SystemExit):
                main(["--preview", str(p)])
            self.assertIn("NOT APPROVED", p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
