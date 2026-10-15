"""Fictional Git repos only; no publisher originals or remote credentials."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import verify_private_github_ref_parity as proof

SOURCE_REF = "shadow/korea-policy-briefing"
VAULT_REF = "archive/korea-policy-briefing"


def git(repo, *args):
    out = subprocess.run(["git", "-C", str(repo), *args], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return out.stdout.decode("ascii").strip()


class GitRefParityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name)
        self.src = home / "source"
        self.vault = home / "vault"
        subprocess.run(["git", "init", "-q", str(self.src)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git(self.src, "config", "user.name", "Synthetic-only reviewer")
        git(self.src, "config", "user.email", "fixture@example.invalid")
        (self.src / "state").mkdir()
        (self.src / "state" / "fictional-capture.bin").write_bytes(
            b"SYNTHETIC ORIGINAL CAPTURE NOT FROM A PUBLISHER\x00\x01")
        git(self.src, "add", "state")
        git(self.src, "commit", "-qm", "Fictional immutable source")
        git(self.src, "branch", "-M", SOURCE_REF)
        self.sha = git(self.src, "rev-parse", "HEAD")
        subprocess.run(["git", "clone", "--quiet", "--bare", str(self.src),
                        str(self.vault)], check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        git(self.vault, "branch", VAULT_REF, SOURCE_REF)

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_original_commit_and_reachable_git_objects(self):
        report = proof.compare(self.src, self.vault, SOURCE_REF, VAULT_REF, self.sha)
        self.assertEqual(report["source_head"], self.sha)
        self.assertEqual(report["vault_head"], self.sha)
        self.assertGreater(report["reachable_git_objects_verified"], 0)
        self.assertTrue(report["source_archive_git_object_sets_match"])
        for field in ("private_destination_visibility_authenticated",
                      "git_lfs_binary_objects_independently_verified",
                      "failed_uncommitted_attempts_verified",
                      "independent_backup_restored",
                      "publisher_source_retention_rights_approved",
                      "production_cutover_authorized", "ready_for_live_migration"):
            self.assertFalse(report[field])

    def test_moving_source_branch_without_repinning_stops(self):
        (self.src / "state" / "new-capture.bin").write_bytes(b"SYNTHETIC NEXT ORIGINAL")
        git(self.src, "add", "state")
        git(self.src, "commit", "-qm", "Fictional newer source capture")
        with self.assertRaisesRegex(proof.ParityError, "source_head_changed_since_freeze"):
            proof.compare(self.src, self.vault, SOURCE_REF, VAULT_REF, self.sha)

    def test_wrong_or_missing_vault_ref_is_not_a_successful_copy(self):
        with self.assertRaisesRegex(proof.ParityError, "git_integrity_or_ref_error"):
            proof.compare(self.src, self.vault, SOURCE_REF, "archive/other", self.sha)
        git(self.vault, "update-ref", "refs/heads/" + VAULT_REF,
            self.sha)  # idempotent, never repairs a failing copy
        self.assertTrue(proof.compare(self.src, self.vault, SOURCE_REF, VAULT_REF,
                                      self.sha)["source_archive_git_object_sets_match"])

    def test_changed_vault_commit_does_not_pass_object_copy(self):
        with self.assertRaisesRegex(proof.ParityError, "source_head_changed_since_freeze"):
            proof.compare(self.src, self.vault, SOURCE_REF, VAULT_REF, "0" * 40)
        git(self.src, "checkout", "-q", "-b", "fictional-unrelated")
        (self.src / "state" / "different.bin").write_bytes(b"FICTIONAL-DIFFERENT-BRANCH")
        git(self.src, "add", "state")
        git(self.src, "commit", "-qm", "Fixture unrelated new capture")
        subprocess.run(["git", "-C", str(self.vault), "fetch", "--quiet",
                        str(self.src), "refs/heads/fictional-unrelated:refs/heads/"
                        + VAULT_REF], check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        with self.assertRaisesRegex(proof.ParityError, "archive_head_does_not_match_source"):
            proof.compare(self.src, self.vault, SOURCE_REF, VAULT_REF, self.sha)

    def test_no_symlinks_or_same_repo_or_unsafe_refs(self):
        with self.assertRaisesRegex(proof.ParityError, "source_is_destination"):
            proof.compare(self.src, self.src, SOURCE_REF, VAULT_REF, self.sha)
        symlink = self.src.parent / "symlink-to-public-source"
        symlink.symlink_to(self.src)
        with self.assertRaisesRegex(proof.ParityError, "git_repository_path_invalid"):
            proof.compare(symlink, self.vault, SOURCE_REF, VAULT_REF, self.sha)
        for ref in ("shadow/../a", "shadow//bad", "archive/foo",
                    "shadow/name;echo", "shadow/name\n", "shadow/name@{1}"):
            with self.subTest(ref=ref), self.assertRaisesRegex(
                    proof.ParityError, "ref_name_invalid"):
                proof.compare(self.src, self.vault, ref, VAULT_REF, self.sha)

    def test_nonexistent_git_directory_and_bad_pin_fail_closed(self):
        with self.assertRaisesRegex(proof.ParityError, "git_repository_path_invalid"):
            proof.compare(self.src.parent / "missing", self.vault,
                          SOURCE_REF, VAULT_REF, self.sha)
        with self.assertRaisesRegex(proof.ParityError, "expected_commit_invalid"):
            proof.compare(self.src, self.vault, SOURCE_REF, VAULT_REF, "nope")

    def test_error_cli_does_not_echo_original_bytes_or_sensitive_path(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            result = proof.main([
                "--source-repo", str(self.src),
                "--vault-repo", str(self.vault),
                "--source-ref", SOURCE_REF, "--vault-ref", "archive/wrong",
                "--source-commit", self.sha,
            ])
        report = json.loads(stream.getvalue())
        self.assertEqual(result, 2)
        self.assertFalse(report["ready_for_live_migration"])
        self.assertNotIn(str(self.src), stream.getvalue())
        self.assertNotIn("SYNTHETIC ORIGINAL", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
