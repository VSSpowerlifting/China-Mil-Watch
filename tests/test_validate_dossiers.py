"""B1.3 CLI integration tests use imaginary JSON, SQLite and desk registry only."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from core.dossier_contract import dossier_content_digest
from scripts.validate_dossiers import (
    ROOT, PrivateReportPathError, _private_destination, main,
    review_directory, write_private_report,
)
from tests.test_dossier_sources import (
    BODIES, draft, fake_registry, synthetic_sqlite,
)


class PrivateDossierReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.source_dir = self.directory / "dossiers"
        self.source_dir.mkdir()
        self.db_path = self.directory / "synthetic.db"
        synthetic_sqlite(self.db_path)
        self.output = self.directory / "private_review.json"
        self.registry = fake_registry()

    def write(self, data=None, *, name="fictional-exercise-reporting.json"):
        target = self.source_dir / name
        target.write_text(json.dumps(draft() if data is None else data),
                          encoding="utf-8")
        return target

    def call(self, *, report=None, source_dir=None, db=None):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = main([
                "--source-dir", str(self.source_dir if source_dir is None else source_dir),
                "--db", str(self.db_path if db is None else db),
                "--report", str(self.output if report is None else report),
            ], registry=self.registry)
        return result, stdout.getvalue(), stderr.getvalue()

    def read(self, path=None):
        return json.loads((self.output if path is None else path).read_text())

    def test_fictional_review_reports_holds_not_permission(self):
        self.write()
        exit_code, output, errors = self.call()
        self.assertEqual(exit_code, 0)
        self.assertFalse(errors)
        self.assertIn("publication not authorized", output)
        report = self.read()
        self.assertEqual(report["dossier_count"], 1)
        self.assertEqual(report["mechanically_valid_count"], 1)
        self.assertEqual(report["status"], "review_hold")
        self.assertEqual(report["error_count"], 0)
        self.assertFalse(report["eligible_for_publication"])
        record = report["dossiers"][0]
        self.assertTrue(record["archive_reconciled"])
        self.assertFalse(record["eligible_for_publication"])
        self.assertGreater(report["hold_count"], 0)
        self.assertEqual(record["selected_record_ids"], [900001, 900002])

    def test_creates_owner_private_report_permissions(self):
        self.write()
        self.call()
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)

    def test_forged_rights_refs_cannot_clear_any_hold(self):
        data = draft()
        for source in data["sources"]:
            source["source_use_decision_ref"] = "invented-permission"
            source["editorial_admission_ref"] = "invented-editorial-approval"
        self.write(data)
        self.assertEqual(self.call()[0], 0)
        report = self.read()
        codes = [h["code"] for h in report["dossiers"][0]["holds"]]
        self.assertEqual(codes.count("independent-source-use-decision-required"), 2)
        self.assertEqual(codes.count("independent-source-admission-required"), 2)

    def test_claiming_approved_does_not_authorize_publication(self):
        data = draft()
        data["editorial_status"] = "approved"
        data["editor_name"] = "Synthetic Human Editor"
        data["revision"] = 1
        data["reviewed_on"] = data["updated_on"]
        data["changes"] = [{
            "revision": 1, "changed_on": data["updated_on"],
            "summary": "Entirely hypothetical first release.",
            "affected_claim_ids": ["alpha-training-claim"],
        }]
        data["approval"] = {
            "approved_by": data["editor_name"],
            "approved_on": data["updated_on"],
            "reference": "fake-owner-github-review",
            "content_sha256": dossier_content_digest(data),
        }
        self.write(data)
        self.assertEqual(self.call()[0], 0)
        result = self.read()["dossiers"][0]
        self.assertFalse(result["eligible_for_publication"])
        self.assertIn("independently-authenticated-editorial-approval-required",
                      [x["code"] for x in result["holds"]])

    def test_broken_archive_fails_and_does_not_expose_body(self):
        self.write()
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE articles SET text_original=? WHERE id=900001",
                       ("PRIVATE_FAKE_PUBLISHER_BODY " * 16,))
            db.commit()
        code, out, err = self.call()
        self.assertEqual(code, 1)
        result = self.read()
        self.assertIn("source-original-body-drift",
                      [e["code"] for e in result["dossiers"][0]["errors"]])
        matching = [e for e in result["dossiers"][0]["errors"]
                    if e["code"] == "source-original-body-drift"]
        self.assertEqual(matching, [{"code": "source-original-body-drift", "record_id": 900001}])
        self.assertNotIn("PRIVATE_FAKE_PUBLISHER_BODY", self.output.read_text())
        self.assertNotIn("PRIVATE_FAKE_PUBLISHER_BODY", out + err)

    def test_diagnostic_serializer_refuses_untrusted_numeric_ids(self):
        from scripts.validate_dossiers import _safe_error
        self.assertEqual(_safe_error("archive-unavailable"), {"code": "archive-unavailable"})
        for bad in (True, False, -1, 0, 2 ** 63, "900001", 900001.0):
            self.assertEqual(_safe_error("source-original-body-drift", bad),
                             {"code": "source-original-body-drift"})
        self.assertEqual(_safe_error("source-original-body-drift", 900001),
                         {"code": "source-original-body-drift", "record_id": 900001})

    def test_malformed_input_does_not_echo_secret_in_report(self):
        source = draft()
        source["PRIVATE_EMBARGOED_TEXT"] = "do-not-log-the-original"
        self.write(source)
        code, stdout, stderr = self.call()
        self.assertEqual(code, 1)
        self.assertEqual(self.read()["dossiers"][0]["errors"],
                         [{"code": "invalid-dossier-json-or-contract"}])
        self.assertNotIn("PRIVATE_EMBARGOED_TEXT", self.output.read_text() + stdout + stderr)
        self.assertNotIn("do-not-log-the-original", self.output.read_text() + stdout + stderr)

    def test_valid_and_invalid_inputs_report_independently(self):
        self.write()
        bad = draft()
        bad["slug"] = "second-case"
        bad["dossier_schema"] = "wrong"
        self.write(bad, name="second-case.json")
        exit_code, _, _ = self.call()
        report = self.read()
        self.assertEqual(exit_code, 1)
        self.assertEqual(report["dossier_count"], 2)
        self.assertEqual(report["mechanically_valid_count"], 1)
        self.assertEqual(report["status"], "error")

    def test_missing_db_reports_mechanical_failure(self):
        self.write()
        code, _, _ = self.call(db=self.directory / "missing.db")
        self.assertEqual(code, 1)
        report = self.read()
        self.assertEqual(report["dossiers"][0]["errors"], [{"code": "archive-unavailable"}])

    def test_model_screening_rejection_remains_human_hold(self):
        self.write()
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE articles SET passed_relevance=0 WHERE id=900001")
            db.commit()
        self.assertEqual(self.call()[0], 0)
        self.assertIn("screening-not-selected-human-review",
                      [h["code"] for h in self.read()["dossiers"][0]["holds"]])
        held = [h for h in self.read()["dossiers"][0]["holds"]
                if h["code"] == "screening-not-selected-human-review"]
        self.assertEqual(held, [{
            "code": "screening-not-selected-human-review", "record_id": 900001
        }])
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute(
                "SELECT passed_relevance FROM articles WHERE id=900001"
            ).fetchone()[0], 0)

    def test_empty_directory_is_no_publication_not_error(self):
        self.assertEqual(self.call()[0], 0)
        report = self.read()
        self.assertEqual(report["status"], "no_dossiers")
        self.assertEqual(report["dossier_count"], 0)
        self.assertFalse(report["eligible_for_publication"])

    def test_absent_directory_is_no_publication(self):
        missing_dir = self.directory / "absent"
        self.assertEqual(self.call(source_dir=missing_dir)[0], 0)
        self.assertEqual(self.read()["status"], "no_dossiers")

    def test_rejects_unexpected_source_dir_symlink(self):
        self.write()
        link = self.directory / "linked"
        try:
            link.symlink_to(self.source_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.call(source_dir=link)[0], 1)
        self.assertEqual(self.read()["errors"],
                         [{"code": "source-directory-not-canonical"}])

    def test_no_original_database_or_wal_files_written(self):
        self.write()
        before = self.db_path.read_bytes()
        self.call()
        self.assertEqual(self.db_path.read_bytes(), before)
        self.assertFalse(Path(str(self.db_path) + "-wal").exists())
        self.assertFalse(Path(str(self.db_path) + "-shm").exists())

    def test_refuses_overwrite_of_existing_private_report(self):
        self.write()
        self.output.write_text("PREVIOUS PRIVATE RECEIPT", encoding="utf-8")
        code, _, err = self.call()
        self.assertEqual(code, 2)
        self.assertEqual(self.output.read_text(), "PREVIOUS PRIVATE RECEIPT")
        self.assertIn("unsafe/unwritable", err)

    def test_rejects_relative_output_path(self):
        self.write()
        code, _, _ = self.call(report=Path("private.json"))
        self.assertEqual(code, 2)
        self.assertFalse(self.output.exists())

    def test_rejects_report_within_repository(self):
        inside = ROOT / "_ipr_b13_should_not_exist.json"
        self.assertFalse(inside.exists())
        with self.assertRaises(PrivateReportPathError):
            _private_destination(inside)
        self.assertFalse(inside.exists())

    def test_rejects_report_symlink(self):
        placeholder = self.directory / "other.json"
        placeholder.write_text("do not overwrite", encoding="utf-8")
        self.output.symlink_to(placeholder)
        self.assertEqual(self.call()[0], 2)
        self.assertEqual(placeholder.read_text(), "do not overwrite")

    def test_rejects_symlinked_report_parent(self):
        other = self.directory / "real"
        other.mkdir()
        linked = self.directory / "linked"
        linked.symlink_to(other, target_is_directory=True)
        with self.assertRaises(PrivateReportPathError):
            _private_destination(linked / "secret.json")

    def test_missing_report_parent_fails_before_source_read(self):
        self.write()
        self.assertEqual(self.call(report=self.directory / "missing" / "private.json")[0], 2)

    def test_file_writer_refuses_existing_without_creating_suffixes(self):
        self.output.write_text("keep", encoding="utf-8")
        with self.assertRaises(PrivateReportPathError):
            write_private_report({"secret": "not expected"}, self.output)
        self.assertEqual(self.output.read_text(), "keep")

    def test_report_contains_only_allowlisted_metadata_no_fake_source_text(self):
        self.write()
        self.call()
        report_text = self.output.read_text()
        for original in BODIES.values():
            self.assertNotIn(original, report_text)
        self.assertNotIn("model reasoning", report_text)
        self.assertNotIn("THIS IS A FABRICATED", report_text)
        self.assertNotIn("overview", report_text)


if __name__ == "__main__":
    unittest.main()
