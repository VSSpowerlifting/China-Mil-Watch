"""Synthetic-only regression contracts for Issue #168 Singapore historical replay."""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import audit_issue168_singapore_production as audit  # noqa: E402


def git(repo, *args, input_data=None):
    return subprocess.check_output(["git", "-C", str(repo), *args],
                                   input=input_data).decode().strip()


class SingaporeProductionReplaySynthetic(unittest.TestCase):
    def setUp(self):
        self.context = tempfile.TemporaryDirectory(prefix="ipr-sg-168-synthetic-")
        self.addCleanup(self.context.cleanup)
        self.repo = Path(self.context.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "fixture@example.org")
        git(self.repo, "config", "user.name", "Fixture")
        self.db = self.repo / audit.DB_PATH
        with sqlite3.connect(self.db) as con:
            con.execute("""CREATE TABLE articles (
                url TEXT PRIMARY KEY, text_original TEXT, title_original TEXT,
                published_date TEXT, source_slug TEXT, content_hash TEXT
            )""")
            self.pilot = []
            for i in range(25, 37):
                pid = f"P{i}"
                url = f"https://www.mindef.gov.sg/synthetic/{pid}/"
                body = "" if i == 36 else f"Synthetic source body {pid} for checksum checking."
                title = f"Synthetic original {pid}"
                content_hash = f"stored-hash-{pid}"
                con.execute("INSERT INTO articles VALUES (?, ?, ?, ?, ?, ?)",
                            (url, body, title, "2026-09-28",
                             "sg_mindef_releases", content_hash))
                excerpts = [] if i == 36 else [{
                    "id": "E1", "field": "text_original", "start": 8, "end": 20,
                    "quote": body[8:20],
                }]
                self.pilot.append({
                    "pilot_id": pid, "record_id": f"synthetic-{pid}",
                    "canonical_url": url, "origin": "production",
                    "storage_layer": "production", "desk_id": "singapore",
                    "source_slug": "sg_mindef_releases",
                    "row_locator": {"table": "articles", "url": url},
                    "review_state": "pending",
                    "title_original": title, "published_date": "2026-09-28",
                    "stored_content_hash": content_hash,
                    "body_chars": len(body), "body_sha256":
                    hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "evidence": excerpts,
                })
        git(self.repo, "add", audit.DB_PATH)
        git(self.repo, "commit", "-q", "-m", "frozen synthetic db")
        self.commit = git(self.repo, "rev-parse", "HEAD")
        self.db_oid = git(self.repo, "rev-parse", f"HEAD:{audit.DB_PATH}")
        self.ledger = {"origins": {"production": {
            "commit": self.commit, "path": audit.DB_PATH,
            "blob": self.db_oid,
        }}, "records": self.pilot}
        self.ledger_oid = self.new_ledger(self.ledger)
        for key, val in (("COMMIT", self.commit), ("DB_BLOB", self.db_oid),
                         ("LEDGER_BLOB", self.ledger_oid)):
            patched = patch.object(audit, key, val)
            patched.start()
            self.addCleanup(patched.stop)

    def new_ledger(self, content):
        raw = json.dumps(content, sort_keys=True, ensure_ascii=False).encode()
        return git(self.repo, "hash-object", "-w", "--stdin", input_data=raw)

    def test_full_12_row_replay_and_unmodified_worktree(self):
        baseline = git(self.repo, "status", "--porcelain")
        out = audit.replay(self.repo)
        self.assertEqual(out["sqlite_integrity_check"], "ok")
        self.assertEqual(out["rows_verified"], 12)
        self.assertEqual(out["body_records_verified"], 11)
        self.assertEqual(out["bodyless_rows_confirmed"], 1)
        self.assertEqual(out["excerpts_verified"], 11)
        self.assertFalse(out["human_review_complete"])
        self.assertEqual(out["records"][-1]["status"], "bodyless_not_body_verified")
        self.assertEqual(git(self.repo, "status", "--porcelain"), baseline)

    def test_null_bodyless_p36_is_not_claimed_as_text(self):
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE articles SET text_original=NULL WHERE url=?",
                        (self.pilot[-1]["canonical_url"],))
        report = audit.check_db(self.db, self.pilot)
        self.assertEqual(report["body_records_verified"], 11)
        self.assertEqual(report["bodyless_rows_confirmed"], 1)

    def test_nonempty_p36_body_fails(self):
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE articles SET text_original='invented' WHERE url=?",
                        (self.pilot[-1]["canonical_url"],))
        with self.assertRaisesRegex(audit.VerificationError, "P36 unexpectedly"):
            audit.check_db(self.db, self.pilot)

    def test_missing_row_fails(self):
        with sqlite3.connect(self.db) as con:
            con.execute("DELETE FROM articles WHERE url=?", (self.pilot[0]["canonical_url"],))
        with self.assertRaisesRegex(audit.VerificationError, "P25: exact historical URL"):
            audit.check_db(self.db, self.pilot)

    def test_wrong_frozen_hash_or_quote_fails(self):
        altered = copy.deepcopy(self.ledger)
        altered["records"][0]["body_sha256"] = "a" * 64
        oid = self.new_ledger(altered)
        with patch.object(audit, "LEDGER_BLOB", oid):
            with self.assertRaisesRegex(audit.VerificationError, "SHA-256 mismatch"):
                audit.replay(self.repo)
        altered = copy.deepcopy(self.ledger)
        altered["records"][0]["evidence"][0]["quote"] = "not the original"
        oid = self.new_ledger(altered)
        with patch.object(audit, "LEDGER_BLOB", oid):
            with self.assertRaisesRegex(audit.VerificationError, "offset/quote mismatch"):
                audit.replay(self.repo)

    def test_wrong_pinned_commit_blob_fails(self):
        with patch.object(audit, "DB_BLOB", "0" * 40):
            with self.assertRaisesRegex(audit.VerificationError, "pinned commit"):
                audit.replay(self.repo)

    def test_corrupt_db_fails_integrity(self):
        with tempfile.TemporaryDirectory() as folder:
            corrupt = Path(folder) / "corrupt.sqlite"
            corrupt.write_bytes(b"SQLite format 3\x00" + bytes(500))
            with self.assertRaises(sqlite3.DatabaseError):
                audit.check_db(corrupt, self.pilot)

    def test_false_approval_or_fabricated_p36_excerpts_fails(self):
        changed = copy.deepcopy(self.ledger)
        changed["records"][-1]["evidence"] = [{"id": "E1", "quote": "invented"}]
        with self.assertRaisesRegex(audit.VerificationError, "P36: bodyless"):
            audit.load_pilot(json.dumps(changed).encode())
        changed = copy.deepcopy(self.ledger)
        changed["records"][0]["review_state"] = "approved"
        with self.assertRaisesRegex(audit.VerificationError, "source identity drift"):
            audit.load_pilot(json.dumps(changed).encode())


if __name__ == "__main__":
    unittest.main()
