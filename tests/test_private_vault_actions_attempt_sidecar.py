"""Offline fictional Actions ZIP evidence + ephemeral GPG key; no publisher API."""
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import private_vault_encrypt_actions_attempts as box

RUN = 37656171920
ONE = 11498114543
TWO = 11499686512
FAKE_JOB_ONE = 112911609417
FAKE_JOB_TWO = 112916943525


def run(*args):
    result = subprocess.run(args, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=25)
    return result.stdout.decode("utf-8")


class EncryptedAttemptSidecarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory(prefix="ipr-fixture-keys-")
        cls.home = Path(cls.keys.name) / "gpg"
        cls.home.mkdir(mode=0o700)
        run("gpg", "--homedir", str(cls.home), "--batch",
            "--pinentry-mode", "loopback", "--passphrase", "",
            "--quick-generate-key",
            "Fixture archive only <no-reply@example.invalid>", "rsa2048",
            "encrypt", "0")
        keys = run("gpg", "--homedir", str(cls.home), "--batch",
                   "--with-colons", "--list-keys")
        cls.fpr = next(x.split(":")[9] for x in keys.splitlines()
                       if x.startswith("fpr:"))

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-attempt-fiction-")
        self.root = Path(self.temp.name)
        self.zips = self.root / "zips"
        self.zips.mkdir()
        self.encrypted = self.root / "sidecar.tar.gpg"
        self.scratch = self.root / "scratch"
        self.scratch.mkdir(mode=0o700)
        self.manifest = self.root / "inventory.json"
        self.record = {
            "schema": box.SOURCE_SCHEMA,
            "repo": box.REPO,
            "production_cutover_authorized": False,
            "actual_artifact_bytes_downloaded_or_hashed": False,
            "runs": [{
                "run_id": RUN,
                "workflow": ".github/workflows/vietnam_ministry_shadow.yml",
                "event": "workflow_dispatch",
                "latest_run_attempt": 2,
                "conclusion": "success",
                "historical_attempt_jobs": [
                    {"attempt": 1, "has_unsuccessful_job": True, "jobs": [{
                        "job_id": FAKE_JOB_ONE, "name": "fictional failed collection",
                         "status": "completed",
                        "conclusion": "failure"}]},
                    {"attempt": 2, "has_unsuccessful_job": False, "jobs": [{
                        "job_id": FAKE_JOB_TWO, "name": "fictional successful rerun",
                         "status": "completed",
                        "conclusion": "success"}]},
                ],
                "artifacts": [
                    {"id": ONE, "name": "vietnam-ministry-shadow-%d-1" % RUN,
                     "name_attempt": 1, "expired": False},
                    {"id": TWO, "name": "vietnam-ministry-shadow-%d-2" % RUN,
                     "name_attempt": 2, "expired": False},
                ],
            }]
        }
        for ident, text in (
            (ONE, "Fictional failed attempt: imaginary weather station"),
            (TWO, "Fictional successful rerun: imaginary survey boat"),
        ):
            with zipfile.ZipFile(self.zips / ("artifact-%d.zip" % ident), "w") as zipf:
                zipf.writestr("ONLY-FICTIONAL-BODY.txt", text)
        for item in self.record["runs"][0]["artifacts"]:
            archive = self.zips / ("artifact-%d.zip" % item["id"])
            item["provider_sha256"] = box.digest(archive)
            item["bytes"] = archive.stat().st_size
        self.write_inventory()

    def tearDown(self):
        self.temp.cleanup()

    def write_inventory(self):
        self.manifest.write_text(json.dumps(self.record, indent=2) + "\n")

    def create(self):
        return box.create(self.manifest, RUN, self.zips, self.encrypted,
                          self.fpr, gpg_home=self.home)

    def verify(self, record):
        return box.restore(self.encrypted, record["ciphertext_sha256"],
                           record["source_inventory_sha256"], RUN,
                           inventory=self.manifest, scratch_dir=self.scratch, gpg_home=self.home)

    def test_real_encrypted_roundtrip_with_failed_and_successful_opaque_zips(self):
        receipt = self.create()
        self.assertEqual(receipt["attempt_artifact_count"], 2)
        self.assertFalse(receipt["plaintext_tar_written_to_disk"])
        self.assertEqual(self.encrypted.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(b"Fictional failed attempt", self.encrypted.read_bytes())
        verified = self.verify(receipt)
        self.assertTrue(verified["all_opaque_zip_sha256_verified"])
        self.assertTrue(receipt["provider_digest_parity_verified_against_input_census"])
        self.assertTrue(verified["provider_sha256_parity_preserved_in_manifest"])
        self.assertTrue(verified["original_inventory_receipt_and_artifact_ids_verified"])
        self.assertFalse(verified["source_rights_approved"])
        self.assertFalse(verified["individual_zip_contents_verified"])
        self.assertFalse(verified["downloaded_zip_origin_authenticated"])
        self.assertFalse(verified["independent_backup_medium_verified"])
        self.assertFalse(verified["production_cutover_authorized"])
        self.assertFalse(verified["plaintext_tar_written_to_disk"])
        self.assertEqual(list(self.scratch.iterdir()), [])
        self.assertFalse(any(".part" in p.name for p in self.root.iterdir()))

    def test_single_failed_attempt_can_be_backed_up_without_rerun_jobs(self):
        # An original failed run may never have been re-run; its retained ZIP
        # must still remain eligible for integrity-only encrypted custody.
        run_row = self.record["runs"][0]
        run_row["latest_run_attempt"] = 1
        run_row["conclusion"] = "failure"
        run_row["historical_attempt_jobs"] = []
        run_row["artifacts"] = [run_row["artifacts"][0]]
        (self.zips / ("artifact-%d.zip" % TWO)).unlink()
        self.write_inventory()
        receipt = self.create()
        self.assertEqual(receipt["attempt_artifact_count"], 1)
        verified = self.verify(receipt)
        self.assertEqual(verified["artifact_count_verified"], 1)
        self.assertFalse(verified["downloaded_zip_origin_authenticated"])
        self.assertFalse(verified["production_cutover_authorized"])

    def test_encrypt_rejects_streamed_bytes_that_differ_from_provider_receipt(self):
        # The staging ZIP stays untouched; interception of the TAR input must
        # still cause HOLD, not a superficially successful encrypted backup.
        addfile = tarfile.TarFile.addfile

        def tamper_stream(bundle, member, fileobj=None):
            if member.name == "artifacts/artifact-%d.zip" % ONE:
                return addfile(bundle, member, io.BytesIO(b"X" * member.size))
            return addfile(bundle, member, fileobj)

        with patch.object(tarfile.TarFile, "addfile", tamper_stream):
            with self.assertRaisesRegex(
                    box.Hold, "staged_artifact_stream_digest_mismatch"):
                self.create()
        self.assertFalse(self.encrypted.exists())
        self.assertFalse(any(".part" in path.name for path in self.root.iterdir()))

    def test_wrong_private_key_cannot_certify_recovery(self):
        receipt = self.create()
        wrong_home = self.root / "not-our-private-key"
        wrong_home.mkdir(mode=0o700)
        with self.assertRaises(box.Hold):
            box.restore(self.encrypted, receipt["ciphertext_sha256"],
                        receipt["source_inventory_sha256"], RUN,
                        inventory=self.manifest, scratch_dir=self.scratch,
                        gpg_home=wrong_home)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_moving_or_modified_original_receipt_fails_closed(self):
        self.record["runs"][0]["artifacts"][0]["id"] = 98765432101
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold,
                                    "unexpected_or_missing_staged_artifact"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_missing_first_failed_attempt_even_after_green_rerun_is_rejected(self):
        self.record["runs"][0]["artifacts"] = [self.record["runs"][0]["artifacts"][1]]
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold,
                                    "one_or_more_attempt_artifacts_missing"):
            self.create()

    def test_absent_failed_attempt_job_proof_is_rejected(self):
        self.record["runs"][0]["historical_attempt_jobs"][0]["jobs"] = []
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "rerun_job_rows_missing"):
            self.create()

    def test_repeated_historical_job_id_is_rejected(self):
        attempts = self.record["runs"][0]["historical_attempt_jobs"]
        attempts[1]["jobs"][0]["job_id"] = attempts[0]["jobs"][0]["job_id"]
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "rerun_job_identity_or_status_invalid"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_inconsistent_historical_failure_flag_is_rejected(self):
        attempts = self.record["runs"][0]["historical_attempt_jobs"]
        attempts[0]["has_unsuccessful_job"] = False
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "rerun_job_outcome_flag_inconsistent"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_extra_unrecognized_rerun_attempt_receipt_is_rejected(self):
        self.record["runs"][0]["historical_attempt_jobs"].append("not a job receipt")
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "rerun_job_attempt_inventory_missing"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_malformed_attempt_number_is_a_clean_hold(self):
        attempts = self.record["runs"][0]["historical_attempt_jobs"]
        attempts[0]["attempt"] = "not-an-integer"
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "rerun_job_attempt_inventory_missing"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_missing_zip_and_unexpected_files_are_refused(self):
        (self.zips / ("artifact-%d.zip" % ONE)).unlink()
        with self.assertRaisesRegex(box.Hold, "unexpected_or_missing_staged_artifact"):
            self.create()

    def test_wrong_provider_digest_rejects_relabelled_zip(self):
        self.record["runs"][0]["artifacts"][0]["provider_sha256"] = "f" * 64
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "staged_zip_provider_digest_mismatch"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_missing_provider_digest_prevents_backup(self):
        del self.record["runs"][0]["artifacts"][0]["provider_sha256"]
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "artifact_provider_digest_or_size_missing"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_staged_zip_provider_byte_count_mismatch(self):
        self.record["runs"][0]["artifacts"][0]["bytes"] += 1
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "staged_zip_provider_size_mismatch"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_changed_inventory_digest_is_rejected_on_restore(self):
        receipt = self.create()
        with self.assertRaisesRegex(box.Hold, "restore_inventory_checksum_mismatch"):
            box.restore(self.encrypted, receipt["ciphertext_sha256"],
                        "0"*64, RUN, inventory=self.manifest, scratch_dir=self.scratch, gpg_home=self.home)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_restore_rejects_changed_retained_census_even_if_zip_is_intact(self):
        receipt = self.create()
        self.record["local_test_only_untrusted_extra"] = "different receipt bytes"
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "restore_inventory_checksum_mismatch"):
            self.verify(receipt)

    def test_create_refuses_out_of_scope_event_before_encryption(self):
        self.record["runs"][0]["event"] = "pull_request"
        self.write_inventory()
        with self.assertRaisesRegex(box.Hold, "inventory_run_scope_invalid"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_corrupted_ciphertext_and_wrong_key_are_refused(self):
        receipt = self.create()
        with self.encrypted.open("ab") as stream:
            stream.write(b"FICTITIOUS-TAMPER")
        with self.assertRaisesRegex(box.Hold, "encrypted_sidecar_checksum_mismatch"):
            self.verify(receipt)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_restore_refuses_world_readable_scratch_and_leaves_no_plaintext(self):
        receipt = self.create()
        self.scratch.chmod(0o755)
        try:
            with self.assertRaisesRegex(box.Hold, "restore_paths_unsafe"):
                self.verify(receipt)
        finally:
            self.scratch.chmod(0o700)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def forge_encrypted_fixture(self, *, corrupt_id=None, drop_id=None,
                                forget_manifest_id=None, corrupt_count=False,
                                rewrite_single_attempt=False):
        """Test-only re-encryption of fictional payloads; never run on originals."""
        receipt = self.create()
        test_plain = self.root / "fictional-only-plaintext-test.tar"
        run("gpg", "--homedir", str(self.home), "--batch", "--yes",
            "--output", str(test_plain), "--decrypt", str(self.encrypted))
        manifest = None
        files = {}
        with tarfile.open(test_plain, "r:") as existing:
            for item in existing:
                payload = existing.extractfile(item).read()
                if item.name == "manifest.json":
                    manifest = payload
                else:
                    files[item.name] = payload
        self.assertIsNotNone(manifest)
        if forget_manifest_id is not None or corrupt_count or rewrite_single_attempt:
            changed = json.loads(manifest)
            if forget_manifest_id is not None:
                changed["captured_artifacts"] = [
                    item for item in changed["captured_artifacts"]
                    if item["id"] != forget_manifest_id]
                changed["case_count"] = len(changed["captured_artifacts"])
            if corrupt_count:
                changed["case_count"] += 1
            if rewrite_single_attempt:
                changed["captured_artifacts"] = [
                    x for x in changed["captured_artifacts"] if x["id"] != ONE]
                changed["captured_artifacts"][0]["attempt"] = 1
                changed["latest_run_attempt"] = 1
                changed["case_count"] = 1
            manifest = (json.dumps(changed, sort_keys=True) + "\n").encode()
        forged_plain = self.root / "fictional-forged-test.tar"
        with tarfile.open(forged_plain, "w:") as archive:
            meta = tarfile.TarInfo("manifest.json")
            meta.size = len(manifest)
            archive.addfile(meta, io.BytesIO(manifest))
            for name, value in files.items():
                if drop_id is not None and name.endswith("/artifact-%d.zip" % drop_id):
                    continue
                if corrupt_id is not None and name.endswith("/artifact-%d.zip" % corrupt_id):
                    value = value + b"FICTIONAL MALICIOUS TAMPER"
                info = tarfile.TarInfo(name)
                info.size = len(value)
                archive.addfile(info, io.BytesIO(value))
        encrypted = self.root / "forged-sidecar.tar.gpg"
        run("gpg", "--homedir", str(self.home), "--batch", "--yes",
            "--trust-model", "always", "--recipient", self.fpr,
            "--output", str(encrypted), "--encrypt", str(forged_plain))
        return encrypted, hashlib.sha256(encrypted.read_bytes()).hexdigest(), receipt

    def test_restore_rejects_reencrypted_modified_attempt_zip(self):
        encrypted, digest, receipt = self.forge_encrypted_fixture(corrupt_id=ONE)
        with self.assertRaisesRegex(box.Hold, "sidecar_item_length_mismatch"):
            box.restore(encrypted, digest, receipt["source_inventory_sha256"],
                        RUN, inventory=self.manifest, scratch_dir=self.scratch, gpg_home=self.home)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_restore_rejects_valid_ciphertext_missing_failed_attempt(self):
        encrypted, digest, receipt = self.forge_encrypted_fixture(drop_id=ONE)
        with self.assertRaisesRegex(box.Hold, "sidecar_members_missing"):
            box.restore(encrypted, digest, receipt["source_inventory_sha256"],
                        RUN, inventory=self.manifest, scratch_dir=self.scratch, gpg_home=self.home)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_restore_rejects_self_consistent_attempt_count_rewrite(self):
        encrypted, sha, receipt = self.forge_encrypted_fixture(
            drop_id=ONE, rewrite_single_attempt=True)
        with self.assertRaisesRegex(box.Hold, "sidecar_inventory_scope_mismatch"):
            box.restore(encrypted, sha, receipt["source_inventory_sha256"],
                        RUN, inventory=self.manifest, scratch_dir=self.scratch,
                        gpg_home=self.home)

    def test_restore_rejects_coherent_manifest_that_erases_failed_attempt(self):
        # The original census parity check now catches the missing artifact
        # before the secondary within-manifest attempt-coverage guard.
        encrypted, sha, receipt = self.forge_encrypted_fixture(
            drop_id=ONE, forget_manifest_id=ONE)
        with self.assertRaisesRegex(box.Hold, "sidecar_inventory_scope_mismatch"):
            box.restore(encrypted, sha, receipt["source_inventory_sha256"],
                        RUN, inventory=self.manifest, scratch_dir=self.scratch, gpg_home=self.home)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_restore_rejects_manifest_count_inconsistency(self):
        encrypted, sha, receipt = self.forge_encrypted_fixture(corrupt_count=True)
        with self.assertRaisesRegex(box.Hold, "sidecar_manifest_scope_invalid"):
            box.restore(encrypted, sha, receipt["source_inventory_sha256"],
                        RUN, inventory=self.manifest, scratch_dir=self.scratch, gpg_home=self.home)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_filename_that_claims_zip_but_is_plaintext_is_refused(self):
        target = self.zips / ("artifact-%d.zip" % ONE)
        # Preserve the declared provider byte length so this isolates the
        # invalid-ZIP guard rather than failing at the earlier size check.
        length = target.stat().st_size
        target.write_bytes((b"NOT-A-ZIP-" * (length // 10 + 1))[:length])
        with self.assertRaisesRegex(box.Hold, "staged_file_not_zip"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_no_overwrite_existing_encrypted_backup(self):
        self.create()
        with self.assertRaisesRegex(box.Hold, "encrypted_target_unsafe_or_exists"):
            self.create()

    def test_untrusted_zip_directory_symlink_refused(self):
        symlink = self.root / "linked"
        symlink.symlink_to(self.zips, target_is_directory=True)
        with self.assertRaisesRegex(box.Hold, "artifact_staging_directory_invalid"):
            box.create(self.manifest, RUN, symlink, self.encrypted, self.fpr,
                       gpg_home=self.home)

    def test_refuse_original_zip_staging_inside_git_checkout(self):
        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(box.Hold, "artifact_staging_inside_git_checkout"):
            self.create()
        self.assertFalse(self.encrypted.exists())

    def test_refuse_ciphertext_target_inside_git_checkout(self):
        tracked = self.root / "fake-repo"
        tracked.mkdir()
        (tracked / ".git").mkdir()
        destination = tracked / "encrypted-unsafe.tar.gpg"
        with self.assertRaisesRegex(box.Hold, "encrypted_target_inside_git_checkout"):
            box.create(self.manifest, RUN, self.zips, destination,
                       self.fpr, gpg_home=self.home)
        self.assertFalse(destination.exists())

    def test_no_fake_permission_or_private_archive_claim(self):
        receipt = self.create()
        self.assertFalse(receipt["source_rights_approved"])
        self.assertFalse(receipt["downloaded_zip_origin_authenticated"])
        self.assertFalse(receipt["independent_backup_medium_verified"])
        self.assertFalse(receipt["production_cutover_authorized"])
        self.assertEqual(box.SCHEMA, "ipr-actions-attempt-encrypted-sidecar/1")

    def test_no_real_source_access_or_public_network_tool_in_code(self):
        code = Path(box.__file__).read_text(encoding="utf-8")
        self.assertNotIn('gh", "api"', code)
        self.assertNotIn("requests.get(", code)
        self.assertNotIn("https://api.github", code)
        self.assertNotIn("github_token", code.lower())


if __name__ == "__main__":
    unittest.main()
