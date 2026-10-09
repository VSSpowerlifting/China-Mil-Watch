"""Offline private UNSIGNED human source-review worksheet tests."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.regional_typed_human_review_prep import (
    HumanReviewWorksheetError, REVIEW_FIELDS, create_unsigned_worksheet,
)
from core.regional_typed_research_holds import canonical
from scripts.regional_typed_human_review_prep import main, save_private
from tests.test_regional_typed_research_holds import fixture


class TypedHumanReviewPreparationTests(unittest.TestCase):
    def test_real_six_research_sources_all_unsigned_and_held(self):
        inventory, rows = fixture()
        worksheet = create_unsigned_worksheet(inventory, rows)
        self.assertEqual(worksheet["schema"],
                         "ipr-regional-typed-source-human-review-worksheet/1")
        self.assertEqual(worksheet["source_count"], 6)
        self.assertEqual(len(worksheet["records"]), 6)
        self.assertEqual({r["desk"] for r in worksheet["records"]},
                         {"japan", "vietnam"})
        self.assertTrue(worksheet["all_records_remain_held"])
        for key in ("model_input_authorized", "editor_email_authorized",
                    "publication_authorized", "japan_vietnam_production_activated",
                    "is_signed_or_reusable_authorization"):
            self.assertFalse(worksheet[key])
        self.assertIsNone(worksheet["owner_release_signature"])
        for item in worksheet["records"]:
            self.assertEqual(set(item["review_checks"]), set(REVIEW_FIELDS))
            self.assertTrue(all(value is None for value in
                                item["review_checks"].values()))
            self.assertEqual(item["status"], "UNREVIEWED_UNSIGNED_TEMPLATE_ONLY")
            for key in ("model_input_authorized", "publisher_body_copy_authorized",
                        "editor_email_authorized", "publication_authorized"):
                self.assertFalse(item[key])
            self.assertIsNone(item["rights_basis_url_or_document"])
            self.assertIsNone(item["reuse_permission_scope"])
            self.assertIsNone(item["reviewer_identity"])
        without = {k: v for k, v in worksheet.items()
                   if k != "unsigned_template_sha256"}
        self.assertEqual(worksheet["unsigned_template_sha256"],
                         hashlib.sha256(canonical(without)).hexdigest())

    def test_captured_source_body_and_analyst_synopses_never_copied(self):
        inventory, rows = fixture()
        out = json.dumps(create_unsigned_worksheet(inventory, rows),
                         ensure_ascii=False)
        for row in rows:
            self.assertIn(row["source_url"], out)
            self.assertIn(row["title_original"], out)
            self.assertNotIn(row["summary"], out)
            for caveat in row["caveats"]:
                self.assertNotIn(caveat, out)
        self.assertNotIn("text_original", out)
        self.assertNotIn("article_body", out)

    def test_source_specific_missing_original_explained(self):
        inventory, rows = fixture()
        out = create_unsigned_worksheet(inventory, rows)
        by_id = {r["id"]: r for r in out["records"]}
        self.assertIn("HTML_original_not_preserved",
                      by_id["JP-W41-01"]["machine_source_gap"])
        self.assertIn("PDF_bytes", by_id["JP-W41-06"]["machine_source_gap"])
        self.assertIn("current_Vietnamese_original",
                      by_id["VN-MPS-1791199100"]["machine_source_gap"])

    def test_changed_original_url_or_date_and_untrusted_desk_refused(self):
        inv, rows = fixture()
        edits = [
            lambda rr: rr[0].update(source_url="https://www.mod.go.jp/forged"),
            lambda rr: rr[0].update(published_date="2026-10-01"),
            lambda rr: rr[0].update(desk="china"),
            lambda rr: rr[0].update(copy_scope="public"),
        ]
        for change in edits:
            altered = copy.deepcopy(rows)
            change(altered)
            with self.subTest(change=change), self.assertRaises(
                    HumanReviewWorksheetError):
                create_unsigned_worksheet(inv, altered)

    def test_original_language_metadata_must_be_printable_and_bounded(self):
        inv, rows = fixture()
        for key, replacement in (
            ("title_original", "False\nforged review approval"),
            ("title_original", "x" * 600),
            ("language", "owner-reviewed"),
            ("language", "EN"),
        ):
            changed = copy.deepcopy(rows)
            changed[0][key] = replacement
            with self.subTest(key=key), self.assertRaises(
                    HumanReviewWorksheetError):
                create_unsigned_worksheet(inv, changed)

    def test_cli_writes_exclusive_private_worksheet_no_send(self):
        inv, rows = fixture()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "review-only.json"
            args = ["--week-ending", "2026-10-10", "--as-of", "2026-10-10",
                    "--review-local-day", "2026-10-11",
                    "--research-directory", folder, "--out", str(target)]
            with patch("scripts.regional_typed_human_review_prep.inspect",
                       return_value=inv), patch(
                       "scripts.regional_typed_human_review_prep.load_editorial_evidence",
                       return_value=rows), patch(
                       "scripts.sunday_editorial_handoff.send_packet") as send:
                self.assertEqual(main(args), 0)
                send.assert_not_called()
            out = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(out["source_count"], 6)
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertFalse(out["publication_authorized"])
            with self.assertRaises(ValueError):
                save_private(target, out)

    def test_failed_serialization_removes_only_our_incomplete_worksheet(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            with self.assertRaises(TypeError):
                save_private(path, {"not_json": object()})
            self.assertFalse(path.exists())

    def test_fdopen_failure_closes_descriptor_and_cleans_worksheet(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            raw_open, raw_close = os.open, os.close
            opened = []

            def record_open(*args, **kwargs):
                fd = raw_open(*args, **kwargs)
                opened.append(fd)
                return fd

            with patch("scripts.regional_typed_human_review_prep.os.open",
                       side_effect=record_open), patch(
                    "scripts.regional_typed_human_review_prep.os.fdopen",
                    side_effect=OSError("synthetic fdopen failure")), patch(
                    "scripts.regional_typed_human_review_prep.os.close",
                    wraps=raw_close) as close:
                with self.assertRaisesRegex(OSError, "synthetic fdopen failure"):
                    save_private(path, {"private": True})
            self.assertFalse(path.exists())
            self.assertEqual(len(opened), 1)
            close.assert_called_once_with(opened[0])

    def test_replaced_worksheet_survives_failed_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            independent = Path(folder) / "someone-elses-file.json"
            independent.write_text("OTHER", encoding="utf-8")
            raw_close = os.close

            def replace_then_fail(fd, *args, **kwargs):
                path.unlink()
                os.link(independent, path)
                raise OSError("synthetic replaced worksheet")

            with patch("scripts.regional_typed_human_review_prep.os.fdopen",
                       side_effect=replace_then_fail), patch(
                    "scripts.regional_typed_human_review_prep.os.close",
                    wraps=raw_close):
                with self.assertRaisesRegex(OSError, "synthetic replaced worksheet"):
                    save_private(path, {"private": True})
            self.assertEqual(path.read_text(encoding="utf-8"), "OTHER")
            self.assertEqual(independent.read_text(encoding="utf-8"), "OTHER")

    def test_dangling_symlink_is_never_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            victim = Path(folder) / "must-not-be-created.json"
            path.symlink_to(victim)
            with self.assertRaises(ValueError):
                save_private(path, {"private": True})
            self.assertTrue(path.is_symlink())
            self.assertFalse(victim.exists())

    def test_symlink_swap_during_resolve_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private.json"
            victim = Path(folder) / "must-not-be-created.json"
            original_resolve = Path.resolve

            def swap(path_obj, *args, **kwargs):
                if path_obj == path:
                    path.symlink_to(victim)
                return original_resolve(path_obj, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True, side_effect=swap):
                with self.assertRaises(ValueError):
                    save_private(path, {"private": True})
            self.assertTrue(path.is_symlink())
            self.assertFalse(victim.exists())

    def test_worksheet_cannot_write_into_repository(self):
        inv, rows = fixture()
        report = create_unsigned_worksheet(inv, rows)
        repo = Path(__file__).resolve().parents[1]
        with self.assertRaises(ValueError):
            save_private(repo / "NEVER_WRITE_THIS.json", report)


if __name__ == "__main__":
    unittest.main()
