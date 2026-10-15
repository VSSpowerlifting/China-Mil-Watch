"""Synthetic original evidence only: GPG encrypted Git bundle and restore test."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import backup_korea_encrypted_custody as backup
from tests.test_korea_private_custody_equivalence import fixture


@unittest.skipUnless(shutil.which("gpg") and shutil.which("git"),
                     "GPG and Git required for encrypted offline proof")
class KoreaEncryptedLocalBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gpg_tmp = tempfile.TemporaryDirectory()
        cls.gpg = Path(cls.gpg_tmp.name)
        cls.gpg.chmod(0o700)
        run = subprocess.run(
            ["gpg", "--homedir", str(cls.gpg), "--batch", "--pinentry-mode",
             "loopback", "--passphrase", "", "--quick-generate-key",
             "IPR Synthetic Fixture <ipr-synthetic@example.invalid>",
             "rsa2048", "encr", "0"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=35)
        if run.returncode:
            cls.gpg_tmp.cleanup()
            raise RuntimeError("test-only GPG key generation unavailable")
        response = subprocess.run(
            ["gpg", "--homedir", str(cls.gpg), "--batch", "--with-colons",
             "--list-keys"],
            check=True, capture_output=True, timeout=10)
        rows = [x for x in response.stdout.decode().splitlines()
                if x.startswith("fpr:")]
        cls.fingerprint = rows[0].split(":")[9]
        if len(cls.fingerprint) != 40:
            raise RuntimeError("synthetic fixture fingerprint invalid")

    @classmethod
    def tearDownClass(cls):
        cls.gpg_tmp.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.cloned, self.pin, _, _ = fixture(self.root)
        self.encrypted = self.root / "korea-state.bundle.gpg"
        self.scratch = self.root / "encrypted-scratch"
        self.scratch.mkdir(mode=0o700)

    def run_backup(self, **changes):
        kw = dict(
            source_checkout=str(self.source),
            encrypted_output=str(self.encrypted),
            recipient_fingerprint=self.fingerprint,
            gpg_home=str(self.gpg),
            scratch_parent=str(self.scratch),
            frozen_commit=self.pin,
            explicit_owner_restricted_retention=True,
        )
        return backup.backup_restore(**dict(kw, **changes))

    def test_real_gpg_encrypted_bundle_restores_exact_fake_capture_bytes(self):
        report = self.run_backup()
        self.assertTrue(report["local_decrypt_and_git_restore_equivalent"])
        self.assertEqual(report["source_commit"], self.pin)
        self.assertEqual(report["captured_objects"], 2)
        self.assertEqual(report["source_originals"], 5)
        self.assertEqual(self.encrypted.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b"synthetic-hwpx", self.encrypted.read_bytes())
        self.assertNotIn(b"Synthetic original", self.encrypted.read_bytes())
        for hold in ("durable_off_provider_backup_verified",
                     "independent_recovery_operator_verified",
                     "source_retention_rights_judged_by_tool",
                     "private_github_archive_writer_activated",
                     "korea_sunday_or_publication_authorized",
                     "production_promotion_authorized"):
            self.assertIs(report[hold], False)
        text = json.dumps(report)
        self.assertNotIn(str(self.source), text)
        self.assertNotIn(self.fingerprint, text)

    def test_owner_retention_approval_required_even_on_synthetic_input(self):
        with self.assertRaises(backup.BackupHold):
            self.run_backup(explicit_owner_restricted_retention=False)
        self.assertFalse(self.encrypted.exists())

    def test_existing_destination_never_overwritten(self):
        self.encrypted.write_text("KEEP ME")
        with self.assertRaises(backup.BackupHold):
            self.run_backup()
        self.assertEqual(self.encrypted.read_text(), "KEEP ME")

    def test_unpinned_git_history_or_corrupt_source_never_encrypted(self):
        with self.assertRaises(backup.BackupHold):
            self.run_backup(frozen_commit="f" * 40)
        self.assertFalse(self.encrypted.exists())
        capture = next((self.source / "state" / "captures").glob("*.bin"))
        capture.write_bytes(b"corruption")
        with self.assertRaises(backup.BackupHold):
            self.run_backup()
        self.assertFalse(self.encrypted.exists())

    def test_wrong_gpg_key_or_unsafe_directory_fails_closed(self):
        with self.assertRaises(backup.BackupHold):
            self.run_backup(recipient_fingerprint="f" * 40)
        self.assertFalse(self.encrypted.exists())
        self.root.chmod(0o755)
        with self.assertRaises(backup.BackupHold):
            self.run_backup()
        self.assertFalse(self.encrypted.exists())

    def test_no_unsafe_archive_path_or_output_in_public_checkout(self):
        with self.assertRaises(backup.BackupHold):
            self.run_backup(encrypted_output=str(self.source / "bad.gpg"))
        with self.assertRaises(backup.BackupHold):
            self.run_backup(encrypted_output="relative.gpg")
        self.assertFalse(self.encrypted.exists())

    def test_unsafe_or_missing_scratch_directory_is_refused(self):
        self.scratch.chmod(0o755)
        with self.assertRaises(backup.BackupHold):
            self.run_backup()
        self.assertFalse(self.encrypted.exists())
        self.scratch.chmod(0o700)
        with self.assertRaises(backup.BackupHold):
            self.run_backup(scratch_parent=str(self.source))
        self.assertFalse(self.encrypted.exists())
        with self.assertRaises(backup.BackupHold):
            self.run_backup(scratch_parent=str(self.root / "nonexistent"))
        self.assertFalse(self.encrypted.exists())

    def test_invalid_cli_receipt_cannot_claim_release_authority(self):
        status = backup.main([
            "--source-checkout", str(self.source),
            "--encrypted-out", str(self.encrypted),
            "--recipient-fingerprint", self.fingerprint,
            "--gpg-home", str(self.gpg),
        ])
        self.assertEqual(status, 2)
        self.assertFalse(self.encrypted.exists())


if __name__ == "__main__":
    unittest.main()
