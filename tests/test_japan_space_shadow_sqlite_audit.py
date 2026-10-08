"""Contracts for the Japan shadow URL audit, using SYNTHETIC Git and SQLite.

Fixtures are not a real IPR snapshot, real archival evidence, or human labels.
"""
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

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import audit_japan_space_shadow as audit  # noqa: E402


def synthetic_packet():
    return {
        "packet_id": audit.PACKET_ID,
        "archive_status": "not_pinned_not_verified_against_full_japan_shadow",
        "collection_authorized": False,
        "topic_assignments_authorized": False,
        "human_review_complete": False,
        "candidates": [{
            "id": "JSP%02d" % i,
            "url": "https://www.mod.go.jp/test/path/%d.html" % i,
            "archive_identity": None,
            "body_sha256": None,
            "owner_approval": None,
            "review_state": "awaiting_source_admission",
        } for i in range(1, 7)],
    }


def synthetic_db(db_path: Path):
    with sqlite3.connect(str(db_path)) as db:
        db.executescript("""
            CREATE TABLE shadow_records (
                url TEXT PRIMARY KEY, source_slug TEXT,
                published_date TEXT, text_original TEXT);
            CREATE TABLE shadow_unretrieved (
                url TEXT PRIMARY KEY, source_slug TEXT,
                published_date TEXT, reason TEXT);
            CREATE TABLE shadow_pre_bootstrap (
                url TEXT PRIMARY KEY, source_slug TEXT, published_date TEXT);
            CREATE TABLE shadow_validators (
                url TEXT PRIMARY KEY, etag TEXT);
        """)
        db.executemany(
            "INSERT INTO shadow_records VALUES (?,?,?,?)", [
                ("https://www.mod.go.jp/test/path/1.html",
                 "jp_mod_news_ja", "2026-09-01", "SYNTHETIC ONLY"),
                ("https://www.mod.go.jp/other.pdf",
                 "jp_mod_news_ja", "2026-09-02", "SYNTHETIC ONLY"),
            ]
        )
        db.executemany(
            "INSERT INTO shadow_unretrieved VALUES (?,?,?,?)", [
                ("https://www.mod.go.jp/test/path/2.html",
                 "jp_mod_siteupdate_ja", "2026-09-03", "access_challenged"),
                ("https://www.mod.go.jp/another.html",
                 None, "2026-09-04", "pdf: no_text_layer"),
            ]
        )
        db.execute("INSERT INTO shadow_pre_bootstrap VALUES (?,?,?)",
                   ("https://www.mod.go.jp/test/path/3.html",
                    "jp_mod_news_ja", "2026-08-20"))
        db.execute("INSERT INTO shadow_validators VALUES (?,?)",
                   ("https://www.mod.go.jp/test/path/1.html", '"SYNTHETIC"'))


def git_cmd(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True,
    ).stdout


class SnapshotAuditContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-test-japan-audit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "fixture.sqlite"
        self.packet = self.root / "synthetic-candidates.json"
        synthetic_db(self.db)
        self.packet.write_text(
            json.dumps(synthetic_packet()), encoding="utf-8",
        )

    def test_exact_url_matches_all_four_sqlite_tables(self):
        result = audit.audit_database(self.db, synthetic_packet()["candidates"])
        self.assertEqual(result["candidate_count"], 6)
        self.assertEqual(result["exact_url_matches"], 3)
        match = {row["id"]: row["matched_tables"] for row in result["candidates"]}
        self.assertEqual(match["JSP01"], {
            "shadow_records": 1, "shadow_validators": 1
        })
        self.assertEqual(match["JSP02"], {"shadow_unretrieved": 1})
        self.assertEqual(match["JSP03"], {"shadow_pre_bootstrap": 1})
        for ident in ("JSP04", "JSP05", "JSP06"):
            self.assertEqual(match[ident], {})

    def test_different_canonical_url_is_not_silently_equated(self):
        packet = synthetic_packet()
        packet["candidates"][0]["url"] += "?new=1"
        data = audit.audit_database(self.db, packet["candidates"])
        self.assertFalse(data["candidates"][0]["exact_url_present"])
        self.assertFalse(data["archive_snapshot_is_complete_history"])
        self.assertIn("alternate", data["interpretation"])

    def test_reasons_and_pre_bootstrap_are_separated(self):
        data = audit.audit_database(self.db, synthetic_packet()["candidates"])
        self.assertEqual(data["tables"]["shadow_unretrieved"]["by_reason"], {
            "access_challenged": 1, "pdf: no_text_layer": 1
        })
        self.assertEqual(data["tables"]["shadow_pre_bootstrap"]["rows"], 1)
        self.assertEqual(
            data["tables"]["shadow_unretrieved"]["by_source"]["unassigned"], 1
        )
        self.assertEqual(
            data["tables"]["shadow_records"]["stored_date_range"],
            ["2026-09-01", "2026-09-02"]
        )

    def test_database_access_is_immutable_and_does_not_write_to_input(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        data = audit.audit_database(self.db, synthetic_packet()["candidates"])
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)
        self.assertFalse(data["source_issuer_webpage_fetched"])
        self.assertFalse(data["human_classification_approved"])
        self.assertEqual(data["production_writes"], 0)
        self.assertFalse((self.root / "fixture.sqlite-wal").exists())
        self.assertFalse((self.root / "fixture.sqlite-shm").exists())

    def test_unknown_tables_fail_closed(self):
        with sqlite3.connect(str(self.db)) as db:
            db.execute("CREATE TABLE surprise (url TEXT)")
        with self.assertRaisesRegex(audit.SnapshotAuditError, "unknown or missing"):
            audit.audit_database(self.db, synthetic_packet()["candidates"])

    def test_missing_url_column_fails_closed(self):
        with sqlite3.connect(str(self.db)) as db:
            db.execute("ALTER TABLE shadow_validators RENAME TO old")
            db.execute("CREATE TABLE shadow_validators (etag TEXT)")
            db.execute("DROP TABLE old")
        with self.assertRaisesRegex(audit.SnapshotAuditError, "missing URL"):
            audit.audit_database(self.db, synthetic_packet()["candidates"])

    def test_corrupted_db_fails_closed(self):
        self.db.write_bytes(b"not sqlite3")
        with self.assertRaises(audit.SnapshotAuditError):
            audit.audit_database(self.db, synthetic_packet()["candidates"])

    def test_valid_packet_loads_six_unsigned_candidates(self):
        self.assertEqual(len(audit.load_candidates(self.packet)), 6)
        p = synthetic_packet()
        p["candidates"][0]["archive_identity"] = "made-up-git-record"
        self.packet.write_text(json.dumps(p), encoding="utf-8")
        with self.assertRaisesRegex(audit.SnapshotAuditError, "archived or approved"):
            audit.load_candidates(self.packet)

    def test_duplicate_candidate_and_owner_approval_are_rejected(self):
        packet = synthetic_packet()
        packet["candidates"][1]["url"] = packet["candidates"][0]["url"]
        self.packet.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaisesRegex(audit.SnapshotAuditError, "duplicate"):
            audit.load_candidates(self.packet)
        packet = synthetic_packet()
        packet["human_review_complete"] = True
        self.packet.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaisesRegex(audit.SnapshotAuditError, "approvals"):
            audit.load_candidates(self.packet)

    def test_pinned_git_commit_blob_and_direct_cli(self):
        repo = self.root / "synthetic_repo"
        repo.mkdir()
        git_cmd(repo, "init", "-q")
        source = repo / "state"
        source.mkdir()
        (source / "shadow.db").write_bytes(self.db.read_bytes())
        git_cmd(repo, "add", "state/shadow.db")
        git_cmd(repo, "-c", "user.name=SYNTHETIC TEST",
                "-c", "user.email=test@example.invalid",
                "commit", "-qm", "synthetic historical snapshot")
        commit = git_cmd(repo, "rev-parse", "HEAD").decode().strip()
        blob = git_cmd(repo, "rev-parse", "HEAD:state/shadow.db").decode().strip()
        self.assertEqual(
            audit.read_pinned_git_blob(repo, commit, blob), self.db.read_bytes()
        )
        report = audit.audit_git_snapshot(repo, commit, blob, self.packet)
        self.assertEqual(report["provenance"]["git_commit"], commit)
        self.assertEqual(report["exact_url_matches"], 3)

        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts/audit_japan_space_shadow.py"),
             "--repo", str(repo), "--commit", commit, "--blob", blob,
             "--candidates", str(self.packet)],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["exact_url_matches"], 3)

    def test_wrong_historical_git_blob_is_rejected(self):
        repo = self.root / "synthetic_repo"
        repo.mkdir()
        git_cmd(repo, "init", "-q")
        (repo / "state").mkdir()
        (repo / "state/shadow.db").write_bytes(self.db.read_bytes())
        git_cmd(repo, "add", "state/shadow.db")
        git_cmd(repo, "-c", "user.name=SYNTHETIC TEST",
                "-c", "user.email=test@example.invalid", "commit", "-qm", "snapshot")
        commit = git_cmd(repo, "rev-parse", "HEAD").decode().strip()
        with self.assertRaisesRegex(audit.SnapshotAuditError, "identity changed"):
            audit.read_pinned_git_blob(repo, commit, "0" * 40)

    def test_absent_historical_commit_never_substitutes_current_branch(self):
        repo = self.root / "synthetic_repo"
        repo.mkdir()
        git_cmd(repo, "init", "-q")
        with self.assertRaisesRegex(audit.SnapshotAuditError, "no fallback"):
            audit.read_pinned_git_blob(repo, "0" * 40, "0" * 40)

    def test_sha_literals_must_be_exact(self):
        with self.assertRaisesRegex(audit.SnapshotAuditError, "literal"):
            audit.read_pinned_git_blob(self.root, "main", "0" * 40)


if __name__ == "__main__":
    unittest.main()
