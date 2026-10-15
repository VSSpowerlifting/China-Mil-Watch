"""No-network encrypted backup/restore tests with deliberately fictional Git bytes.

Temporary GPG key exists only for this process's test. There are no
publisher originals, live vault clones, credentials or account operations.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import private_vault_encrypted_bundle as backup


def run(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True, timeout=25).stdout.decode().strip()


class EncryptedVaultBackupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.secure = tempfile.TemporaryDirectory(prefix="ipr-fictional-gpg-")
        cls.gpg_home = Path(cls.secure.name) / "keyring"
        cls.gpg_home.mkdir(mode=0o700)
        run("gpg", "--homedir", str(cls.gpg_home), "--batch", "--pinentry-mode",
            "loopback", "--passphrase", "", "--quick-generate-key",
            "IPR Fictional Restore <fixture@example.invalid>", "rsa2048",
            "encrypt", "0")
        keys = run("gpg", "--homedir", str(cls.gpg_home), "--batch",
                   "--with-colons", "--list-keys")
        cls.fpr = [row.split(":")[9] for row in keys.splitlines()
                   if row.startswith("fpr:")][0]
        assert len(cls.fpr) == 40

    @classmethod
    def tearDownClass(cls):
        cls.secure.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-test-backup-")
        root = Path(self.temp.name)
        self.root = root
        self.work = root / "fictional-worktree"
        self.work.mkdir()
        run("git", "-C", str(self.work), "init", "-q")
        run("git", "-C", str(self.work), "config", "user.name", "Fictional Runner")
        run("git", "-C", str(self.work), "config", "user.email", "fixture@example.invalid")
        (self.work / "state").mkdir()
        (self.work / "state" / "successful.txt").write_bytes(
            b"IPR FICTIONAL SUCCESS ORIGINAL. No publisher data.\n")
        run("git", "-C", str(self.work), "add", ".")
        run("git", "-C", str(self.work), "commit", "-qm", "fictional success")
        run("git", "-C", str(self.work), "branch", "-M", "main")
        run("git", "-C", str(self.work), "checkout", "-qb",
            "archive/fictional-failed-attempt")
        (self.work / "state" / "failed-attempt-capture.bin").write_bytes(
            b"IPR FICTIONAL FAILED RUN CAPTURE. Not pushed in real collectors.\n")
        run("git", "-C", str(self.work), "add", ".")
        run("git", "-C", str(self.work), "commit", "-qm", "fictional failure receipt")
        self.bare = root / "source.git"
        run("git", "clone", "-q", "--bare", str(self.work), str(self.bare))
        self.refs = backup._inventory(self.bare)
        self.assertEqual(set(self.refs), {
            "refs/heads/main", "refs/heads/archive/fictional-failed-attempt",
        })
        self.pins = [key + "=" + sha for key, sha in sorted(self.refs.items())]
        self.output = root / "vault-20261015.bundle.gpg"
        self.scratch = root / "restore-scratch"
        self.scratch.mkdir(mode=0o700)

    def tearDown(self):
        self.temp.cleanup()

    def create(self):
        return backup.create_backup(self.bare, self.output, self.fpr,
                                    self.pins, gpg_home=self.gpg_home)

    def test_real_gpg_encryption_and_full_history_restore_of_fictional_captures(self):
        receipt = self.create()
        self.assertEqual(receipt["source_ref_shas"], self.refs)
        self.assertFalse(receipt["plaintext_bundle_written_to_disk"])
        self.assertGreater(receipt["reachable_git_objects"], 0)
        self.assertEqual(len(receipt["encrypted_sha256"]), 64)
        self.assertTrue(self.output.is_file())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b"IPR FICTIONAL", self.output.read_bytes())
        self.assertFalse(any(x.name.endswith(".part") for x in self.root.iterdir()))
        self.assertFalse(any(x.name.endswith(".bundle") for x in self.root.iterdir()))
        result = backup.verify_restore(
            self.output, receipt["encrypted_sha256"], self.pins,
            receipt["reachable_git_objects"], scratch_dir=self.scratch,
            gpg_home=self.gpg_home,
        )
        self.assertTrue(result["encrypted_git_bundle_restored"])
        self.assertEqual(result["verified_ref_count"], 2)
        self.assertFalse(result["test_on_independent_backup_medium_authenticated"])
        self.assertFalse(result["lfs_binary_payloads_verified"])
        self.assertFalse(result["failed_attempt_zips_verified"])
        self.assertFalse(result["production_cutover_authorized"])
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_recovery_preserves_notes_and_custom_archive_refs(self):
        # A bare clone of a bundle silently discards custom namespaces.
        # This fixture proves their preservation rather than a false HOLD.
        run("git", "-C", str(self.work), "notes", "add", "-m",
            "Fictional provenance note")
        run("git", "-C", str(self.bare), "fetch", str(self.work),
            "+refs/notes/*:refs/notes/*")
        run("git", "-C", str(self.bare), "update-ref",
            "refs/archives/fictional-custody", self.refs["refs/heads/main"])
        refs = backup._inventory(self.bare)
        pins = [name + "=" + oid for name, oid in sorted(refs.items())]
        self.assertIn("refs/notes/commits", refs)
        self.assertIn("refs/archives/fictional-custody", refs)
        receipt = backup.create_backup(self.bare, self.output, self.fpr,
                                       pins, gpg_home=self.gpg_home)
        result = backup.verify_restore(
            self.output, receipt["encrypted_sha256"], pins,
            receipt["reachable_git_objects"], scratch_dir=self.scratch,
            gpg_home=self.gpg_home,
        )
        self.assertEqual(result["verified_ref_count"], 4)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_copied_ciphertext_restores_without_original_repository(self):
        info = self.create()
        duplicate = self.root / "separate-cipher-copy.gpg"
        shutil.copy2(self.output, duplicate)
        self.assertTrue(backup.verify_restore(
            duplicate, info["encrypted_sha256"], self.pins,
            info["reachable_git_objects"], scratch_dir=self.scratch,
            gpg_home=self.gpg_home)["encrypted_git_bundle_restored"])

    def test_source_ref_changes_during_encryption_are_not_published(self):
        prior = backup._inventory
        call = [0]
        def drift(repo):
            call[0] += 1
            original = prior(repo)
            if call[0] == 2:
                return dict(original, **{"refs/heads/new-unaudited-branch": "0" * 40})
            return original
        with mock.patch.object(backup, "_inventory", side_effect=drift):
            with self.assertRaisesRegex(backup.BackupHold, "source_changed_during_backup"):
                self.create()
        self.assertEqual(call[0], 2)
        self.assertFalse(self.output.exists())
        self.assertFalse(any(p.name.endswith(".part") for p in self.root.iterdir()))

    def test_timeout_reaps_both_children_without_publishing_ciphertext(self):
        # Genuine fictional Git producer, synthetic stalled GPG child.
        real_popen = subprocess.Popen
        created = []
        git_children = []

        class TimedOutGPG:
            def __init__(self):
                self.killed = False

            def wait(self, timeout=None):
                if not self.killed:
                    raise subprocess.TimeoutExpired("fictional-gpg", timeout)
                return -9

            def poll(self):
                return -9 if self.killed else None

            def kill(self):
                self.killed = True

        def launch(argv, *args, **kwargs):
            if argv[0] == "gpg" and "--encrypt" in argv:
                child = TimedOutGPG()
                created.append(child)
                return child
            child = real_popen(argv, *args, **kwargs)
            if argv[0] == "git" and "bundle" in argv and "create" in argv:
                git_children.append(child)
            return child

        with mock.patch.object(backup.subprocess, "Popen", side_effect=launch):
            with self.assertRaisesRegex(
                    backup.BackupHold, "encrypted_export_unavailable"):
                self.create()
        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].killed)
        self.assertEqual(len(git_children), 1)
        self.assertIsNotNone(git_children[0].poll())
        self.assertFalse(self.output.exists())
        self.assertFalse(any(p.name.endswith(".part") for p in self.root.iterdir()))

    def test_gpg_launch_failure_reaps_git_producer_and_leaves_no_backup(self):
        # The git producer can start successfully before GPG refuses to
        # launch. The exceptional path must still close and reap Git.
        real_popen = subprocess.Popen
        git_children = []

        def launch(argv, *args, **kwargs):
            if argv[0] == "gpg" and "--encrypt" in argv:
                raise OSError("fictional GPG launch failure")
            child = real_popen(argv, *args, **kwargs)
            if argv[0] == "git" and "bundle" in argv and "create" in argv:
                git_children.append(child)
            return child

        with mock.patch.object(backup.subprocess, "Popen", side_effect=launch):
            with self.assertRaisesRegex(
                    backup.BackupHold, "encrypted_export_unavailable"):
                self.create()
        self.assertEqual(len(git_children), 1)
        self.assertIsNotNone(git_children[0].poll())
        self.assertTrue(git_children[0].stdout.closed)
        self.assertFalse(self.output.exists())
        self.assertFalse(any(p.name.endswith(".part") for p in self.root.iterdir()))

    def test_encrypted_file_tamper_is_rejected_before_decryption(self):
        info = self.create()
        with self.output.open("ab") as handle:
            handle.write(b"tampered ciphertext")
        with self.assertRaisesRegex(backup.BackupHold, "encrypted_bundle_sha_mismatch"):
            backup.verify_restore(
                self.output, info["encrypted_sha256"], self.pins,
                info["reachable_git_objects"], scratch_dir=self.scratch,
                gpg_home=self.gpg_home)

    def test_no_overwriting_existing_backup_or_symlink(self):
        self.create()
        with self.assertRaisesRegex(backup.BackupHold, "backup_target_unsafe_or_exists"):
            self.create()
        other = self.root / "backup-link.bundle.gpg"
        other.symlink_to(self.output)
        with self.assertRaisesRegex(backup.BackupHold, "backup_target_unsafe_or_exists"):
            backup.create_backup(self.bare, other, self.fpr,
                                 self.pins, gpg_home=self.gpg_home)

    def test_bad_ref_and_source_drift_fail_before_encryption(self):
        with self.assertRaisesRegex(backup.BackupHold, "unfrozen_source_refs"):
            backup.create_backup(self.bare, self.output, self.fpr,
                                 ["refs/heads/main=" + "0" * 40],
                                 gpg_home=self.gpg_home)
        self.assertFalse(self.output.exists())
        run("git", "-C", str(self.work), "checkout", "-q", "main")
        (self.work / "state" / "changed.txt").write_text("fixture revision")
        run("git", "-C", str(self.work), "add", ".")
        run("git", "-C", str(self.work), "commit", "-qm", "changed source")
        run("git", "-C", str(self.bare), "fetch", str(self.work),
            "refs/heads/main:refs/heads/main")
        with self.assertRaisesRegex(backup.BackupHold, "unfrozen_source_refs"):
            self.create()

    def test_wrong_private_key_does_not_leave_plaintext(self):
        data = self.create()
        empty = self.root / "no-key"
        empty.mkdir(mode=0o700)
        with self.assertRaisesRegex(
                backup.BackupHold, "decrypt_failed_or_key_unavailable"):
            backup.verify_restore(self.output, data["encrypted_sha256"],
                                  self.pins, data["reachable_git_objects"],
                                  scratch_dir=self.scratch, gpg_home=empty)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_wrong_object_count_is_not_restore_success(self):
        data = self.create()
        with self.assertRaisesRegex(backup.BackupHold, "restored_git_objects_mismatch"):
            backup.verify_restore(self.output, data["encrypted_sha256"],
                                  self.pins, data["reachable_git_objects"] + 1,
                                  scratch_dir=self.scratch, gpg_home=self.gpg_home)

    def test_refusal_does_not_echo_secret_or_original_contents(self):
        secret = "FICTIONAL_CAPTURE_SECRET_NOT_FOR_STDOUT"
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = backup.main([
                "backup", "--bare-repo", str(self.bare),
                "--encrypted-output", str(self.output),
                "--recipient-fingerprint", secret, "--gpg-home",
                str(self.gpg_home), "--expect-ref", self.pins[0],
            ])
        self.assertEqual(code, 2)
        self.assertIn('"result": "HOLD"', out.getvalue())
        self.assertNotIn(secret, out.getvalue())
        self.assertNotIn("IPR FICTIONAL", out.getvalue())

    def test_plaintext_bundle_cannot_write_inside_bare_repo(self):
        unsafe = self.bare / "unsafe.bundle.gpg"
        with self.assertRaisesRegex(backup.BackupHold, "backup_target_unsafe_or_exists"):
            backup.create_backup(self.bare, unsafe, self.fpr, self.pins,
                                 gpg_home=self.gpg_home)

    def test_backup_target_inside_a_different_git_checkout_is_rejected(self):
        # Unlike the bare source mirror, this is a separate Git worktree.
        # Never let encrypted custody backups become accidentally committable.
        unsafe = self.work / "accidental-public-git-backup.bundle.gpg"
        with self.assertRaisesRegex(
                backup.BackupHold, "backup_target_unsafe_or_exists"):
            backup.create_backup(self.bare, unsafe, self.fpr, self.pins,
                                 gpg_home=self.gpg_home)
        self.assertFalse(unsafe.exists())

    def test_invalid_crypto_fingerprint_and_duplicate_ref_fail(self):
        with self.assertRaisesRegex(backup.BackupHold, "recipient_fingerprint_invalid"):
            backup.create_backup(self.bare, self.output, "not-a-key",
                                 self.pins, gpg_home=self.gpg_home)
        with self.assertRaisesRegex(backup.BackupHold, "duplicate_pinned_ref"):
            backup.create_backup(self.bare, self.output, self.fpr,
                                 self.pins + [self.pins[0]], gpg_home=self.gpg_home)


if __name__ == "__main__":
    unittest.main()
