"""Synthetic offline checks for the pinned Japan October 5 archive source.

The authentic 2026-10-05 PDF bytes are NOT bundled in these tests. Patches
below permit purely synthetic strings to exercise integrity gates; they are
not substitute source evidence or a human original-PDF review.
"""
from __future__ import annotations

import copy
import hashlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import audit_japan_oct05_brief_source as audit  # noqa: E402

SYNTHETIC_PREFIX = "SYNTHETIC OCTOBER 2026 SOURCE TEXT ONLY "
SYNTHETIC_BODY = SYNTHETIC_PREFIX + ("X" * (580 - len(SYNTHETIC_PREFIX)))
SYNTHETIC_SHA = hashlib.sha256(SYNTHETIC_BODY.encode("utf-8")).hexdigest()


def fake_row():
    return {
        "url": audit.PDF_URL, "source_slug": audit.SOURCE,
        "title_original": audit.TITLE,
        "published_date": "2026-10-05",
        "language_tag": "ja",
        "publication_kind": "press release",
        "text_original": SYNTHETIC_BODY,
        "content_sha256": SYNTHETIC_SHA,
        "capture_sha256": audit.CAPTURE_SHA256,
        "first_seen_run": audit.EXPECTED_RUN,
    }


def fake_sqlite(*, extra_current=False):
    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp) / "shadow.db"
        with sqlite3.connect(file) as cx:
            cx.execute("""
                CREATE TABLE shadow_records (
                    url TEXT, source_slug TEXT, title_original TEXT,
                    published_date TEXT, language_tag TEXT,
                    publication_kind TEXT, text_original TEXT,
                    content_sha256 TEXT, capture_sha256 TEXT,
                    first_seen_run TEXT)
            """)
            row = fake_row()
            keys = list(row)
            sql = ("INSERT INTO shadow_records (" + ",".join(keys) +
                   ") VALUES (" + ",".join("?" for _ in keys) + ")")
            cx.execute(sql, list(row.values()))
            for i in range(4):
                old = dict(row, url="https://www.mod.go.jp/synthetic/%d.pdf" % i,
                           published_date="2026-08-28")
                cx.execute(sql, [old[k] for k in keys])
            if extra_current:
                other = dict(row, url="https://www.mod.go.jp/synthetic/fake-new.pdf",
                             published_date="2026-10-06")
                cx.execute(sql, [other[k] for k in keys])
        return file.read_bytes()


class SourceMetadataContracts(unittest.TestCase):
    def validate(self, row=None):
        with mock.patch.object(audit, "TEXT_SHA256", SYNTHETIC_SHA), \
                mock.patch.object(audit, "EXPECTED_PHRASES",
                                  ("SYNTHETIC", "OCTOBER")):
            return audit.validate_row(fake_row() if row is None else row)

    def test_synthetic_fidelity_contract_is_not_editorial_authority(self):
        result = self.validate()
        self.assertTrue(result["archived_text_sha256_verified"])
        self.assertFalse(result["archived_original_pdf_bytes_verified"])
        self.assertFalse(result["full_pdf_human_fidelity_review_complete"])
        self.assertIsNone(result["production_backed_citation_id"])
        self.assertFalse(result["eligible_for_automatic_friday_writer"])
        self.assertFalse(result["exercise_performed_verified"])
        self.assertFalse(result["editorial_inclusion_approved"])
        self.assertEqual(result["production_writes"], 0)

    def test_change_original_source_url_rejected(self):
        row = fake_row()
        row["url"] = "https://example.com/fake.pdf"
        with self.assertRaisesRegex(audit.JapanShadowAuditError, "identity"):
            self.validate(row)

    def test_japan_notice_cannot_be_backdated_to_agreement(self):
        row = fake_row()
        row["published_date"] = "2026-09-17"
        with self.assertRaisesRegex(audit.JapanShadowAuditError, "date drifted"):
            self.validate(row)

    def test_source_title_and_first_seen_run_are_bound(self):
        for field, changed in (
            ("title_original", "SYNTHETIC TITLE"),
            ("first_seen_run", "another-run"),
            ("source_slug", "jp_joint_staff_ja"),
            ("language_tag", "en"),
        ):
            row = fake_row()
            row[field] = changed
            with self.subTest(field=field):
                with self.assertRaisesRegex(audit.JapanShadowAuditError, "identity"):
                    self.validate(row)

    def test_extracted_body_alteration_refused(self):
        row = fake_row()
        row["text_original"] = "SYNTHETIC ALTERED"
        with self.assertRaisesRegex(audit.JapanShadowAuditError, "text"):
            self.validate(row)

    def test_wrong_body_digest_refused_even_if_text_unchanged(self):
        row = fake_row()
        row["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(audit.JapanShadowAuditError, "hash"):
            self.validate(row)

    def test_source_capture_hash_is_attested_but_not_regenerated(self):
        row = fake_row()
        row["capture_sha256"] = "0" * 64
        with self.assertRaisesRegex(audit.JapanShadowAuditError, "capture digest"):
            self.validate(row)

    def test_missing_expected_original_japanese_wording_refused(self):
        with mock.patch.object(audit, "TEXT_SHA256", SYNTHETIC_SHA):
            with self.assertRaisesRegex(audit.JapanShadowAuditError, "missing exact"):
                audit.validate_row(fake_row())

    def test_exactly_one_current_week_record_gate(self):
        with mock.patch.object(audit, "TEXT_SHA256", SYNTHETIC_SHA), \
                mock.patch.object(audit, "EXPECTED_PHRASES", ("SYNTHETIC",)):
            report = audit.inspect_snapshot(fake_sqlite())
        self.assertEqual(report["archive_total_full_text_records"], 5)
        self.assertEqual(report["archive_current_week_records_through_oct08"], 1)
        self.assertEqual(report["source_published_date"], "2026-10-05")

    def test_two_current_week_records_block_fixed_snapshot_claim(self):
        with self.assertRaisesRegex(audit.JapanShadowAuditError,
                                    "exactly one full-text"):
            audit.inspect_snapshot(fake_sqlite(extra_current=True))

    def test_snapshot_rejected_if_not_sqlite(self):
        with self.assertRaisesRegex(audit.JapanShadowAuditError, "SQLite"):
            audit.inspect_snapshot(b"not a source db")

    def test_readonly_sqlite_snapshot_bytes_remain_identical(self):
        b = fake_sqlite()
        before = hashlib.sha256(b).hexdigest()
        with mock.patch.object(audit, "TEXT_SHA256", SYNTHETIC_SHA), \
                mock.patch.object(audit, "EXPECTED_PHRASES", ("SYNTHETIC",)):
            audit.inspect_snapshot(b)
        self.assertEqual(hashlib.sha256(b).hexdigest(), before)

    def test_git_snapshot_cannot_follow_branch_ref(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(audit.JapanShadowAuditError, "exact"):
                audit.read_git_blob(temp, commit="shadow/jp-mod")

    def test_missing_historical_state_git_object_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            subprocess.run(["git", "init", "-q"], cwd=temp, check=True)
            with self.assertRaisesRegex(audit.JapanShadowAuditError,
                                        "no branch or HTTP fallback"):
                audit.read_git_blob(temp)

    def test_pin_to_exact_git_blob_and_ignore_mutated_worktree(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            db = repo / audit.STATE_PATH
            db.parent.mkdir(parents=True)
            original = fake_sqlite()
            db.write_bytes(original)
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "-c", "user.name=SYNTHETIC",
                            "-c", "user.email=test@example.invalid",
                            "commit", "-qm", "SYNTHETIC SNAPSHOT"],
                           cwd=repo, check=True)
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                             cwd=repo).decode().strip()
            blob = subprocess.check_output([
                "git", "rev-parse", "HEAD:" + audit.STATE_PATH
            ], cwd=repo).decode().strip()
            db.write_bytes(b"TAMPERED WORKTREE")
            fetched = audit.read_git_blob(repo, commit=commit,
                                          expected_blob=blob)
            self.assertEqual(fetched, original)
            with self.assertRaisesRegex(audit.JapanShadowAuditError,
                                        "fixed pin"):
                audit.read_git_blob(repo, commit=commit,
                                    expected_blob="0"*40)


if __name__ == "__main__":
    unittest.main()
