"""Fail-closed snapshot lineage proof for the protected China production cutover."""
from hashlib import sha256
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.verify_china_retirement_backup_lineage import verify


class ChinaRetirementBackupLineageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "China Cutover Test")
        self.git("config", "user.email", "china-test@example.invalid")
        self.db = self.repo / "pla_watch.db"
        self.db.write_bytes(b"original verified private SQLite bytes")
        (self.repo / "note.txt").write_text("initial", encoding="utf-8")
        self.commit("original backup source")
        self.backup = self.git("rev-parse", "HEAD").strip()
        self.digest = sha256(self.db.read_bytes()).hexdigest()
        (self.repo / "note.txt").write_text("Korea code-only change", encoding="utf-8")
        self.commit("new Korea verification, original database untouched")
        self.current = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repo), *args],
            text=True, stderr=subprocess.STDOUT,
        )

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def test_backup_ancestor_with_identical_db_survives_code_only_merge(self):
        receipt = verify(self.repo, self.backup, self.digest)
        self.assertEqual(receipt["release_main_sha"], self.current)
        self.assertEqual(receipt["backup_source_sha"], self.backup)
        self.assertTrue(receipt["live_db_exactly_backed_up"])

    def test_exact_same_current_backup_source_is_valid(self):
        receipt = verify(self.repo, self.current, self.digest)
        self.assertEqual(receipt["release_main_sha"], self.current)

    def test_modified_tracked_database_always_rejected(self):
        self.db.write_bytes(b"new unbacked China record")
        self.commit("unbacked corpus change")
        with self.assertRaisesRegex(ValueError, "SQLite Git blob changed"):
            verify(self.repo, self.backup, self.digest)

    def test_different_worktree_bytes_rejected_even_without_git_commit(self):
        self.db.write_bytes(b"uncommitted unverified corpus")
        with self.assertRaisesRegex(ValueError, "live SQLite bytes differ"):
            verify(self.repo, self.backup, self.digest)

    def test_unrelated_newer_backup_sha_not_ancestor_is_rejected(self):
        self.git("checkout", "-qb", "alternate", self.backup)
        (self.repo / "alternate.txt").write_text("diverged")
        self.commit("different history")
        alternate = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-q", self.current)
        with self.assertRaisesRegex(ValueError, "not an ancestor"):
            verify(self.repo, alternate, self.digest)

    def test_malformed_backup_id_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact 40-character"):
            verify(self.repo, "not-a-sha", self.digest)

    def test_wrong_backup_digest_rejected(self):
        with self.assertRaisesRegex(ValueError, "live SQLite bytes differ"):
            verify(self.repo, self.backup, "0" * 64)


if __name__ == "__main__":
    unittest.main()
