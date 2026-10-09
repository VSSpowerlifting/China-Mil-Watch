"""No-network exact-row historical/current Japan source comparison tests."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.japan_shadow_source_row_drift import (
    JapanRowDriftError, FIELDS, compare_pinned_row,
    inspect_current_snapshot,
)
from scripts import audit_japan_oct05_brief_source as pinned
from scripts.japan_shadow_source_row_drift import (
    audit, exclusive_private, CURRENT_REFS,
)

CURRENT_COMMIT = "f" * 40
CURRENT_BLOB = "e" * 40
SAMPLE_TEXT = "Synthetic original-language source for test " * 14


def record(body=SAMPLE_TEXT, **changes):
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    data = {
        "url": pinned.PDF_URL, "source_slug": pinned.SOURCE,
        "title_original": pinned.TITLE, "text_original": body,
        "published_date": "2026-10-05", "language_tag": "ja",
        "publication_kind": "press release",
        "content_sha256": digest, "capture_sha256": pinned.CAPTURE_SHA256,
        "first_seen_run": pinned.EXPECTED_RUN,
    }
    data.update(changes)
    return data


def db_bytes(*rows):
    with tempfile.TemporaryDirectory() as folder:
        dest = Path(folder) / "shadow.db"
        con = sqlite3.connect(str(dest))
        try:
            con.execute("CREATE TABLE shadow_records (" +
                        ",".join(f"{f} TEXT" for f in FIELDS) + ")")
            for row in rows:
                con.execute(
                    "INSERT INTO shadow_records (" + ",".join(FIELDS) + ") VALUES (" +
                    ",".join("?" for _ in FIELDS) + ")",
                    [row[f] for f in FIELDS],
                )
            con.commit()
        finally:
            con.close()
        return dest.read_bytes()


class JapanShadowRowDriftTests(unittest.TestCase):
    def test_unchanged_extracted_text_is_only_historical_archive_continuity(self):
        body = SAMPLE_TEXT
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        with patch.object(pinned, "TEXT_SHA256", digest):
            result = compare_pinned_row(
                record(), current_commit=CURRENT_COMMIT, current_blob=CURRENT_BLOB)
        self.assertEqual(result["row_comparison"],
                         "same_archived_extracted_text_and_row_identity")
        self.assertTrue(result["historical_and_current_text_equal"])
        self.assertEqual(result["changed_fields"], [])
        for k in (
            "archived_original_pdf_bytes_verified",
            "live_official_publisher_version_verified",
            "complete_original_pdf_human_checked",
            "source_reuse_rights_reviewed",
            "private_regional_model_input_authorized",
            "dylan_editor_email_authorized",
            "publication_authorized",
            "shadow_desk_promoted_to_production",
        ):
            self.assertFalse(result[k])
        self.assertNotIn(pinned.PDF_URL, json.dumps(result))
        self.assertNotIn(body, json.dumps(result))

    def test_changed_body_or_source_metadata_does_not_pass(self):
        historical = hashlib.sha256(SAMPLE_TEXT.encode("utf-8")).hexdigest()
        altered = [
            record(body=SAMPLE_TEXT + " changed"),
            record(published_date="2026-10-06"),
            record(title_original="A forged statement"),
            record(language_tag="en"),
            record(capture_sha256="0" * 64),
            record(content_sha256="0" * 64),
        ]
        with patch.object(pinned, "TEXT_SHA256", historical):
            for row in altered:
                with self.subTest(row=row):
                    out = compare_pinned_row(
                        row, current_commit=CURRENT_COMMIT, current_blob=CURRENT_BLOB)
                    self.assertEqual(out["row_comparison"],
                                     "changed_or_inconsistent_current_shadow_source")
                    self.assertTrue(out["changed_fields"])
                    self.assertFalse(out["publication_authorized"])

    def test_disappeared_original_is_explicit_hold_not_publisher_silence(self):
        report = compare_pinned_row(None, current_commit=CURRENT_COMMIT,
                                    current_blob=CURRENT_BLOB)
        self.assertEqual(report["row_comparison"],
                         "held_original_row_missing_in_new_shadow_archive")
        self.assertEqual(report["changed_fields"],
                         ["canonical_publisher_record_missing"])
        self.assertFalse(report["historical_and_current_text_equal"])
        self.assertFalse(report["live_official_publisher_version_verified"])

    def test_unbounded_or_malformed_current_row_refused(self):
        for data in ({"url": pinned.PDF_URL},
                     record(text_original=None),
                     record(text_original="x" * 100001)):
            with self.assertRaises(JapanRowDriftError):
                compare_pinned_row(data, current_commit=CURRENT_COMMIT,
                                   current_blob=CURRENT_BLOB)
        for commit, blob in (("not-a-commit", CURRENT_BLOB),
                             (CURRENT_COMMIT, "short")):
            with self.assertRaises(JapanRowDriftError):
                compare_pinned_row(record(), current_commit=commit,
                                   current_blob=blob)

    def test_read_only_snapshot_selects_exact_row_not_latest_unrelated(self):
        chosen = record()
        other = record(url="https://official.example/other",
                       published_date="2026-10-09")
        read = inspect_current_snapshot(db_bytes(chosen, other))
        self.assertEqual(read, chosen)
        self.assertIsNone(inspect_current_snapshot(db_bytes(other)))

    def test_duplicate_publisher_url_and_malformed_sqlite_rejected(self):
        with self.assertRaisesRegex(JapanRowDriftError, "duplicate"):
            inspect_current_snapshot(db_bytes(record(), copy.deepcopy(record())))
        with self.assertRaisesRegex(JapanRowDriftError, "SQLite"):
            inspect_current_snapshot(b"garbage")
        with self.assertRaises(JapanRowDriftError):
            inspect_current_snapshot(b"SQLite format 3\x00" + b"x" * 50)

    def test_git_ancestry_exact_pins_and_no_publisher_network(self):
        sha = hashlib.sha256(SAMPLE_TEXT.encode("utf-8")).hexdigest()
        historical = {
            "archived_text_sha256_verified": True,
            "archived_original_pdf_bytes_verified": False,
        }
        with tempfile.TemporaryDirectory() as folder, patch(
                "scripts.japan_shadow_source_row_drift.git",
                side_effect=[CURRENT_COMMIT, "", CURRENT_BLOB]) as g, patch(
                "scripts.japan_shadow_source_row_drift.pinned.read_git_blob",
                side_effect=[b"old-db", b"new-db"]) as read_blob, patch(
                "scripts.japan_shadow_source_row_drift.pinned.inspect_snapshot",
                return_value=historical), patch(
                "scripts.japan_shadow_source_row_drift.inspect_current_snapshot",
                return_value=record()), patch.object(pinned, "TEXT_SHA256", sha):
            output = audit(folder, current_ref=CURRENT_REFS[0])
        self.assertTrue(output["historical_and_current_text_equal"])
        self.assertEqual(g.call_count, 3)
        self.assertIn("merge-base", g.call_args_list[1].args)
        self.assertEqual(read_blob.call_count, 2)
        self.assertEqual(read_blob.call_args_list[1].kwargs["expected_blob"],
                         CURRENT_BLOB)
        self.assertFalse(output["publication_authorized"])

    def test_refuses_untrusted_git_ref_without_invoking_git(self):
        with tempfile.TemporaryDirectory() as folder, patch(
                "scripts.japan_shadow_source_row_drift.git") as g:
            with self.assertRaisesRegex(JapanRowDriftError, "official"):
                audit(folder, current_ref="refs/heads/main")
            g.assert_not_called()

    def test_private_report_exclusive_mode_and_does_not_write_repo(self):
        report = compare_pinned_row(None, current_commit=CURRENT_COMMIT,
                                    current_blob=CURRENT_BLOB)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.json"
            exclusive_private(path, report)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())["schema"],
                             "ipr-japan-oct05-shadow-row-version-comparison/1")
            with self.assertRaises(JapanRowDriftError):
                exclusive_private(path, report)
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(JapanRowDriftError):
            exclusive_private(root / "DO_NOT_CREATE_JAPAN_DRIFT.json", report)


    def test_failed_json_serialization_cleans_only_new_private_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "private.json"
            with self.assertRaises(TypeError):
                exclusive_private(output, {"cannot_encode": object()})
            self.assertFalse(output.exists())

    def test_fdopen_failure_closes_still_owned_raw_descriptor(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "private.json"
            raw_open, raw_close = os.open, os.close
            opened = []

            def tracking_open(*args, **kwargs):
                fd = raw_open(*args, **kwargs)
                opened.append(fd)
                return fd

            with patch("scripts.japan_shadow_source_row_drift.os.open",
                       side_effect=tracking_open), patch(
                    "scripts.japan_shadow_source_row_drift.os.fdopen",
                    side_effect=OSError("simulated fdopen failure")), patch(
                    "scripts.japan_shadow_source_row_drift.os.close",
                    wraps=raw_close) as close:
                with self.assertRaisesRegex(OSError, "simulated fdopen failure"):
                    exclusive_private(output, {"private": True})
            self.assertEqual(len(opened), 1)
            close.assert_called_once_with(opened[0])
            self.assertFalse(output.exists())

    def test_failed_write_preserves_unrelated_replacement_inode(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "private.json"
            independent = Path(folder) / "unrelated.txt"
            independent.write_text("KEEP", encoding="utf-8")
            raw_close = os.close

            def replace_then_fail(fd, *args, **kwargs):
                output.unlink()
                os.link(independent, output)
                raise OSError("simulated replacement")

            with patch("scripts.japan_shadow_source_row_drift.os.fdopen",
                       side_effect=replace_then_fail), patch(
                    "scripts.japan_shadow_source_row_drift.os.close",
                    wraps=raw_close):
                with self.assertRaisesRegex(OSError, "simulated replacement"):
                    exclusive_private(output, {"private": True})
            self.assertEqual(output.read_text(encoding="utf-8"), "KEEP")
            self.assertEqual(independent.read_text(encoding="utf-8"), "KEEP")

    def test_dangling_symlink_refused_without_creating_target(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "private.json"
            victim = Path(folder) / "never-create.json"
            output.symlink_to(victim)
            with self.assertRaises(JapanRowDriftError):
                exclusive_private(output, {"private": True})
            self.assertTrue(output.is_symlink())
            self.assertFalse(victim.exists())

    def test_symlink_swap_during_resolve_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "private.json"
            victim = Path(folder) / "never-create.json"
            original_resolve = Path.resolve

            def replace_during_resolve(path_obj, *args, **kwargs):
                if path_obj == output:
                    output.symlink_to(victim)
                return original_resolve(path_obj, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True,
                              side_effect=replace_during_resolve):
                with self.assertRaises(JapanRowDriftError):
                    exclusive_private(output, {"private": True})
            self.assertTrue(output.is_symlink())
            self.assertFalse(victim.exists())


if __name__ == "__main__":
    unittest.main()
