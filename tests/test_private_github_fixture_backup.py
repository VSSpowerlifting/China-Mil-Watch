"""Real Git bundle/restore on a **fictional local repo**; no provider network."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import rehearse_private_github_fixture_backup as recovery


def git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True, timeout=15)
    return proc.stdout.decode("utf-8").strip()


def fake_case(name, path, status, body):
    return {"case_id": name, "source_path": path,
            "capture_status": status, "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body)}


class FictionalVaultRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ipr-fictional-source-")
        self.repo = Path(self.temp.name) / "test-source"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "fixture@example.invalid")
        git(self.repo, "config", "user.name", "Fixture verifier")
        files = self.repo / "pilot" / "source"
        files.mkdir(parents=True)
        self.success = (
            b"IPR SYNTHETIC ORIGINAL - NO GOVERNMENT DATA\n"
            b"source=fixture_testing_only\ncase=success\n")
        self.failed = (
            b"IPR SYNTHETIC FAILED-ATTEMPT CAPTURE - NO GOVERNMENT DATA\n"
            b"source=fixture_testing_only\ncase=failed\n")
        (files / "successful-original.txt").write_bytes(self.success)
        (files / "failed-attempt-original.txt").write_bytes(self.failed)
        (self.repo / "README.md").write_text("Synthetic private vault test\n")
        self.manifest = {
            "schema": recovery.PILOT_SCHEMA,
            "status": "FICTIONAL_TEST_ONLY_NO_PUBLISHER_DATA",
            "cases": [
                fake_case("success", "pilot/source/successful-original.txt",
                          "success", self.success),
                fake_case("failed_uncommitted_capture",
                          "pilot/source/failed-attempt-original.txt",
                          "attempt_failed_before_source_branch_push", self.failed),
            ],
            "governance": {"government_originals_transferred": False,
                           "independent_backup_restored": False,
                           "source_rights_review_complete": False},
        }
        self._write_manifest()
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "Fictional vault fixture")
        git(self.repo, "branch", "-M", "pilot/fictional-custody-20261015")
        self.head = git(self.repo, "rev-parse", "HEAD")

    def _write_manifest(self):
        (self.repo / "pilot" / "manifest.json").write_text(
            json.dumps(self.manifest, sort_keys=True) + "\n")

    def commit_changes(self):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "Synthetic fixture revision")

    def tearDown(self):
        self.temp.cleanup()

    def test_bundle_restores_exact_original_and_failed_only_capture(self):
        receipt = recovery.rehearse(self.repo)
        self.assertEqual(receipt["source_commit"], self.head)
        self.assertEqual(receipt["restored_commit"], self.head)
        self.assertGreater(receipt["reachable_git_objects"], 0)
        self.assertEqual(len(receipt["bundle_sha256"]), 64)
        self.assertTrue(receipt["fixture_success_capture_verified"])
        self.assertTrue(receipt["fixture_failed_only_capture_verified"])
        self.assertTrue(receipt["temporary_git_recovery_passed"])
        self.assertFalse(receipt["independent_durable_encrypted_backup_proven"])
        self.assertFalse(receipt["real_publisher_originals_migrated"])
        self.assertFalse(receipt["production_cutover_authorized"])
        self.assertEqual(self.head, git(self.repo, "rev-parse", "HEAD"))

    def test_tampered_sha_digest_is_not_recovered_as_success(self):
        self.manifest["cases"][1]["sha256"] = "0" * 64
        self._write_manifest()
        self.commit_changes()
        with self.assertRaisesRegex(recovery.FictionalRecoveryError,
                                    "fixture_capture_sha_mismatch"):
            recovery.rehearse(self.repo)

    def test_missing_failed_run_capture_fails(self):
        (self.repo / "pilot" / "source" / "failed-attempt-original.txt").unlink()
        self.commit_changes()
        with self.assertRaisesRegex(recovery.FictionalRecoveryError,
                                    "nonfictional_or_extra_file"):
            recovery.rehearse(self.repo)

    def test_extra_original_or_hidden_payload_is_rejected(self):
        (self.repo / "pilot" / "secret.bin").write_bytes(b"NO SOURCE DATA HERE")
        self.commit_changes()
        with self.assertRaisesRegex(recovery.FictionalRecoveryError,
                                    "nonfictional_or_extra_file"):
            recovery.rehearse(self.repo)

    def test_governance_claim_and_nonfictional_marker_fail_closed(self):
        self.manifest["governance"]["source_rights_review_complete"] = True
        self._write_manifest()
        self.commit_changes()
        with self.assertRaisesRegex(recovery.FictionalRecoveryError,
                                    "fixture_governance_not_closed"):
            recovery.rehearse(self.repo)

    def test_modified_body_is_not_a_recovery(self):
        (self.repo / "pilot" / "source" / "successful-original.txt").write_bytes(
            b"IPR SYNTHETIC ORIGINAL - NO GOVERNMENT DATA\n"
            b"source=fixture_testing_only\nchanged=unexpected\n")
        self.commit_changes()
        with self.assertRaisesRegex(recovery.FictionalRecoveryError,
                                    "fixture_capture_sha_mismatch"):
            recovery.rehearse(self.repo)

    def test_source_repo_must_be_restricted_to_a_real_directory_not_symlink(self):
        link = Path(self.temp.name) / "source-symlink"
        link.symlink_to(self.repo, target_is_directory=True)
        with self.assertRaisesRegex(recovery.FictionalRecoveryError,
                                    "fictional_temp_source_required"):
            recovery.rehearse(link)
        with self.assertRaisesRegex(recovery.FictionalRecoveryError,
                                    "fictional_temp_source_required"):
            recovery.rehearse(Path("/definitely-not-an-ipr-repository"))


if __name__ == "__main__":
    unittest.main()
