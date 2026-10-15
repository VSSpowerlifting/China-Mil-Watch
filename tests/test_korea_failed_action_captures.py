"""Only synthetic ZIP/shadow content; no real Korean records or network."""
import copy
import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import audit_korea_failed_action_captures as audit


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(folder, *args):
    return subprocess.run(
        ["git", "-C", str(folder), *args],
        capture_output=True, text=True, check=True, timeout=15,
    ).stdout.strip()


class KoreaFailedCaptureAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "public-shadow"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        git(self.repo, "config", "user.name", "Synthetic Archive Fixture")
        captures = self.repo / "state" / "captures"
        captures.mkdir(parents=True)
        self.original = b"IPR FICTIONAL original already committed"
        self.failed_only = b"IPR FICTIONAL capture from failed Action only"
        self.original_sha = sha(self.original)
        self.failed_sha = sha(self.failed_only)
        (captures / (self.original_sha + ".bin")).write_bytes(self.original)
        git(self.repo, "add", "state")
        git(self.repo, "commit", "-q", "-m", "fictional source")
        self.tip = git(self.repo, "rev-parse", "HEAD")
        self.archive = self.root / "historical-artifact.zip"
        self._archive([
            ("captures/" + self.original_sha + ".bin", self.original),
            ("captures/" + self.failed_sha + ".bin", self.failed_only),
            ("state/clock.json", b'{"desk":"korea"}'),
        ])

    def _archive(self, members):
        with zipfile.ZipFile(self.archive, "w", zipfile.ZIP_DEFLATED) as z:
            for name, raw in members:
                z.writestr(name, raw)

    def inspect(self):
        return audit.inspect(self.archive, self.repo, self.tip,
                             run_id=38323793488, attempt=1)

    def test_verified_failed_only_capture_is_never_exported_in_stdout(self):
        receipt, unique = self.inspect()
        self.assertEqual(receipt["captures_absent_from_shadow"], 1)
        self.assertEqual(receipt["captures_already_in_shadow"], 1)
        self.assertEqual(receipt["unique_capture_bytes"], len(self.failed_only))
        self.assertEqual(receipt["verified_capture_count"], 2)
        self.assertEqual(unique, [self.failed_sha])
        encoded = json.dumps(receipt)
        for forbidden in (self.original_sha, self.failed_sha, "FICTIONAL",
                          "state/clock.json", str(self.repo)):
            self.assertNotIn(forbidden, encoded)
        for name in ("run_identity_authenticated_by_tool",
                     "capture_bodies_exported", "raw_originals_transferred",
                     "independent_backup_restored", "legal_source_retention_approved",
                     "korea_production_admission_authorized",
                     "scheduled_october_12_gap_repaired"):
            self.assertIs(receipt[name], False)

    def test_flattened_or_state_prefix_valid_but_mixed_prefix_held(self):
        self._archive([
            ("state/captures/" + self.original_sha + ".bin", self.original),
            ("state/captures/" + self.failed_sha + ".bin", self.failed_only),
        ])
        self.assertEqual(self.inspect()[0]["captures_absent_from_shadow"], 1)
        self._archive([
            ("captures/" + self.original_sha + ".bin", self.original),
            ("state/captures/" + self.failed_sha + ".bin", self.failed_only),
        ])
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()

    def test_corrupt_digest_duplicate_capture_and_zip_entry_fail(self):
        self._archive([("captures/" + self.failed_sha + ".bin", b"wrong")])
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()
        self._archive([
            ("captures/" + self.failed_sha + ".bin", self.failed_only),
            ("captures/" + self.failed_sha + ".bin", self.failed_only),
        ])
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()

    def test_zip_slip_and_other_unsafe_member_rejected(self):
        for malicious in ("../sensitive.bin", "/root/secret.bin",
                          "captures/../sensitive.bin", "captures//bad.bin",
                          "captures/other.bin", "captures\\bad.bin"):
            self._archive([
                ("captures/" + self.original_sha + ".bin", self.original),
                (malicious, b"payload"),
            ])
            with self.subTest(name=malicious), self.assertRaises(audit.ArtifactHold):
                self.inspect()

    def test_wrong_or_changed_git_head_rejected(self):
        with self.assertRaises(audit.ArtifactHold):
            audit.inspect(self.archive, self.repo, "f" * 40, run_id=38323793488)
        new = self.repo / "state" / "captures" / (self.original_sha + ".bin")
        new.write_bytes(b"modified")
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()

    def test_untracked_capture_or_other_source_data_refused(self):
        extra = self.repo / "state" / "captures" / (self.failed_sha + ".bin")
        extra.write_bytes(self.failed_only)
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()
        extra.unlink()
        (self.repo / "state" / "untracked-secret.txt").write_text("fictional")
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()

    def test_missing_archive_capture_cannot_pass(self):
        self._archive([("state/clock.json", b'{"desk":"korea"}')])
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()

    def test_private_manifest_requires_new_abs_path_and_does_not_copy_bytes(self):
        receipt, unique = self.inspect()
        path = self.root / "private-record.json"
        audit.write_private_manifest(path, receipt, unique)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        result = json.loads(path.read_text())
        self.assertEqual(result["unique_capture_sha256"], [self.failed_sha])
        self.assertNotIn(self.failed_only.decode("ascii"), path.read_text())
        with self.assertRaises(audit.ArtifactHold):
            audit.write_private_manifest(path, receipt, unique)
        with self.assertRaises(audit.ArtifactHold):
            audit.write_private_manifest("relative.json", receipt, unique)
        link = self.root / "linked.json"
        link.symlink_to(path)
        with self.assertRaises(audit.ArtifactHold):
            audit.write_private_manifest(link, receipt, unique)

    def test_empty_zip_or_invalid_action_identity_refused(self):
        self._archive([])
        with self.assertRaises(audit.ArtifactHold):
            self.inspect()
        self._archive([("captures/" + self.original_sha + ".bin", self.original)])
        with self.assertRaises(audit.ArtifactHold):
            audit.inspect(self.archive, self.repo, self.tip, run_id=0)


if __name__ == "__main__":
    unittest.main()
