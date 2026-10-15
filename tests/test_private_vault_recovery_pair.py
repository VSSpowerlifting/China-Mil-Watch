"""Fictional-only actual GPG joint recovery; neither publisher nor GitHub IO."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import private_vault_encrypted_bundle as gitbox
from scripts import private_vault_recovery_pair as gate


class JointRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_private_vault_actions_attempt_sidecar import (
            EncryptedAttemptSidecarTests)
        EncryptedAttemptSidecarTests.setUpClass()
        cls.side_type = EncryptedAttemptSidecarTests

    @classmethod
    def tearDownClass(cls):
        cls.side_type.tearDownClass()

    def setUp(self):
        from tests.test_private_vault_encrypted_bundle import (
            EncryptedVaultBackupTests)
        self.gitcase = EncryptedVaultBackupTests(
            "test_real_gpg_encryption_and_full_history_restore_of_fictional_captures")
        self.gitcase.setUp()
        self.zipcase = self.side_type(
            "test_real_encrypted_roundtrip_with_failed_and_successful_opaque_zips")
        self.zipcase.setUp()
        self.git_backup = gitbox.create_backup(
            self.gitcase.bare, self.gitcase.output, self.side_type.fpr,
            self.gitcase.pins, gpg_home=self.side_type.home)
        self.zip_backup = self.zipcase.create()
        self.git_receipt = self.gitcase.root / "git-receipt.json"
        self.zip_receipt = self.zipcase.root / "zip-receipt.json"
        self.write_receipts()
        self.scratch = self.gitcase.scratch

    def tearDown(self):
        self.zipcase.tearDown()
        self.gitcase.tearDown()

    def write_receipts(self):
        for path, obj in ((self.git_receipt, self.git_backup),
                          (self.zip_receipt, self.zip_backup)):
            path.write_text(json.dumps(obj, sort_keys=True) + "\n")

    def args(self):
        return {
            "git_encrypted": self.gitcase.output,
            "git_receipt": self.git_receipt,
            "git_receipt_sha": hashlib.sha256(self.git_receipt.read_bytes()).hexdigest(),
            "zip_encrypted": self.zipcase.encrypted,
            "zip_receipt": self.zip_receipt,
            "zip_receipt_sha": hashlib.sha256(self.zip_receipt.read_bytes()).hexdigest(),
            "inventory": self.zipcase.manifest,
            "run_id": self.zipcase.record["runs"][0]["run_id"],
            "scratch_dir": self.scratch,
            "gpg_home": self.side_type.home,
        }

    def test_real_double_decrypt_restores_git_and_failed_attempt_zip(self):
        result = gate.verify_pair(**self.args())
        self.assertEqual(result["status"], "OFFLINE_BYTE_PARITY_PASS")
        self.assertEqual(result["git_ref_count"], 2)
        self.assertEqual(result["attempt_artifact_count"], 2)
        self.assertTrue(result["native_git_bundle_restored"])
        self.assertTrue(result["all_opaque_artifact_zip_digests_restored"])
        self.assertFalse(result["separate_off_github_backup_location_verified"])
        self.assertFalse(result["github_artifact_http_origin_authenticated"])
        self.assertFalse(result["production_cutover_authorized"])
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_changed_receipt_is_refused_before_any_decrypt(self):
        args = self.args()
        self.git_receipt.write_text(self.git_receipt.read_text() + " ")
        with mock.patch.object(gitbox, "verify_restore") as decrypt:
            with self.assertRaisesRegex(
                    gate.RecoveryHold, "receipt_out_of_band_digest_mismatch"):
                gate.verify_pair(**args)
            decrypt.assert_not_called()

    def test_same_ciphertext_cannot_be_both_parts_of_pair(self):
        args = self.args()
        args["zip_encrypted"] = args["git_encrypted"]
        with self.assertRaisesRegex(gate.RecoveryHold,
                                   "recovery_artifact_paths_unsafe"):
            gate.verify_pair(**args)

    def test_wrong_inventory_refused_before_any_decrypt(self):
        args = self.args()
        self.zipcase.manifest.write_text(self.zipcase.manifest.read_text() + " ")
        with mock.patch.object(gitbox, "verify_restore") as git_decrypt:
            with mock.patch.object(gate.zipbox, "restore") as zip_decrypt:
                with self.assertRaisesRegex(
                        gate.RecoveryHold, "restore_inventory_checksum_mismatch"):
                    gate.verify_pair(**args)
                git_decrypt.assert_not_called()
                zip_decrypt.assert_not_called()
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_tampered_second_ciphertext_refused_before_git_decrypt(self):
        args = self.args()
        with self.zipcase.encrypted.open("ab") as handle:
            handle.write(b"fictional appended damage")
        with mock.patch.object(gitbox, "verify_restore") as git_decrypt:
            with self.assertRaisesRegex(
                    gate.RecoveryHold, "encrypted_sidecar_checksum_mismatch"):
                gate.verify_pair(**args)
            git_decrypt.assert_not_called()
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_wrong_cipher_receipt_digest_refused_before_decrypt(self):
        args = self.args()
        self.git_backup["encrypted_sha256"] = "invalid"
        self.write_receipts()
        args = self.args()
        with mock.patch.object(gitbox, "verify_restore") as git_decrypt:
            with self.assertRaisesRegex(
                    gate.RecoveryHold, "git_backup_receipt_invalid"):
                gate.verify_pair(**args)
            git_decrypt.assert_not_called()

    def test_sidecar_inventory_count_mismatch_refused_before_decrypt(self):
        args = self.args()
        self.zip_backup["attempt_artifact_count"] += 1
        self.write_receipts()
        args = self.args()
        with mock.patch.object(gitbox, "verify_restore") as git_decrypt:
            with self.assertRaisesRegex(
                    gate.RecoveryHold, "sidecar_receipt_coverage_mismatch"):
                gate.verify_pair(**args)
            git_decrypt.assert_not_called()

    def test_wrong_private_key_returns_hold_without_plaintext(self):
        args = self.args()
        wrong = self.gitcase.root / "empty-gpg-home"
        wrong.mkdir(mode=0o700)
        args["gpg_home"] = wrong
        with self.assertRaises(gate.RecoveryHold):
            gate.verify_pair(**args)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_writable_scratch_directory_is_rejected(self):
        args = self.args()
        self.scratch.chmod(0o755)
        with mock.patch.object(gitbox, "verify_restore") as decrypt:
            with self.assertRaisesRegex(gate.RecoveryHold,
                                        "scratch_directory_not_private"):
                gate.verify_pair(**args)
            decrypt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
