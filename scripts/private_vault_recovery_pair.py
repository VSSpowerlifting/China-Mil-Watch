#!/usr/bin/env python3
"""Offline joint restore of pinned encrypted Git and opaque Actions ZIP backups.

The operator must supply receipt SHA-256 values recorded outside the backup
medium. This verifies bytes and completeness, not independent-medium custody,
authenticated GitHub download provenance, publisher rights or production cutover.
No network or original-source content is printed or written to public Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from scripts import private_vault_encrypted_bundle as gitbox
from scripts import private_vault_encrypt_actions_attempts as zipbox

SCHEMA = "ipr-private-vault-joint-recovery/1"
SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_RECEIPT = 1024 * 1024


class RecoveryHold(ValueError):
    """Stable, non-disclosing failure codes."""


def require(value, reason):
    if not value:
        raise RecoveryHold(reason)


def read_receipt(path, expected_sha, schema, operation):
    require(type(expected_sha) is str and SHA.fullmatch(expected_sha),
            "receipt_pinned_digest_invalid")
    source = Path(path)
    require(source.is_file() and not source.is_symlink(),
            "receipt_file_invalid")
    with source.open("rb") as handle:
        raw = handle.read(MAX_RECEIPT + 1)
    require(0 < len(raw) <= MAX_RECEIPT, "receipt_size_invalid")
    require(hashlib.sha256(raw).hexdigest() == expected_sha,
            "receipt_out_of_band_digest_mismatch")
    try:
        report = json.loads(raw)
    except (ValueError, UnicodeError):
        raise RecoveryHold("receipt_not_json") from None
    require(type(report) is dict and report.get("schema") == schema and
            report.get(operation[0]) == operation[1],
            "receipt_schema_or_operation_invalid")
    require(report.get("production_cutover_authorized") is False,
            "receipt_policy_flags_invalid")
    return report


def verify_pair(*, git_encrypted, git_receipt, git_receipt_sha,
                zip_encrypted, zip_receipt, zip_receipt_sha, inventory,
                run_id, scratch_dir, gpg_home=None):
    require(type(run_id) is int and run_id > 0, "run_id_invalid")
    scratch = Path(scratch_dir)
    require(scratch.is_dir() and not scratch.is_symlink() and
            (scratch.stat().st_mode & 0o077) == 0 and
            not zipbox._under_git_checkout(scratch),
            "scratch_directory_not_private")
    git_path, zip_path = Path(git_encrypted), Path(zip_encrypted)
    require(git_path.resolve() != zip_path.resolve() and
            not git_path.resolve().is_relative_to(scratch.resolve()) and
            not zip_path.resolve().is_relative_to(scratch.resolve()),
            "recovery_artifact_paths_unsafe")

    git = read_receipt(git_receipt, git_receipt_sha, gitbox.SCHEMA,
                       ("operation", "backup"))
    zipr = read_receipt(zip_receipt, zip_receipt_sha, zipbox.SCHEMA,
                        ("status", "encrypted_backup_created"))
    refs = git.get("source_ref_shas")
    require(type(refs) is dict and refs and
            all(type(key) is str and type(value) is str
                for key, value in refs.items()),
            "git_pinned_refs_invalid")
    git_pins = [key + "=" + value for key, value in sorted(refs.items())]
    require(git.get("plaintext_bundle_written_to_disk") is False and
            git.get("independent_backup_medium_verified") is False and
            git.get("independent_restore_passed") is False and
            git.get("publisher_retention_rights_approved") is False and
            zipr.get("plaintext_tar_written_to_disk") is False and
            zipr.get("downloaded_zip_origin_authenticated") is False and
            zipr.get("independent_backup_medium_verified") is False and
            zipr.get("source_rights_approved") is False and
            zipr.get("provider_digest_parity_verified_against_input_census") is True,
            "receipt_policy_flags_invalid")
    require(type(zipr.get("run_id")) is int and zipr["run_id"] == run_id and
            type(zipr.get("attempt_artifact_count")) is int and
            zipr["attempt_artifact_count"] > 0, "sidecar_receipt_run_invalid")

    try:
        restored_git = gitbox.verify_restore(
            git_path, git["encrypted_sha256"], git_pins,
            git["reachable_git_objects"], scratch_dir=scratch,
            gpg_home=gpg_home)
        restored_zips = zipbox.restore(
            zip_path, zipr["ciphertext_sha256"],
            zipr["source_inventory_sha256"], run_id, inventory=inventory,
            scratch_dir=scratch, gpg_home=gpg_home)
    except (gitbox.BackupHold, zipbox.Hold) as exc:
        # Upstream codes are controlled diagnostic categories, not file data.
        raise RecoveryHold(str(exc)) from None
    require(restored_git.get("encrypted_git_bundle_restored") is True and
            restored_git.get("verified_ref_count") == len(refs) and
            restored_zips.get("all_opaque_zip_sha256_verified") is True and
            restored_zips.get("original_inventory_receipt_and_artifact_ids_verified")
                is True and
            restored_zips.get("artifact_count_verified") ==
                zipr["attempt_artifact_count"], "joint_recovery_report_inconsistent")
    return {
        "schema": SCHEMA, "status": "OFFLINE_BYTE_PARITY_PASS",
        "git_ref_count": len(refs),
        "reachable_git_objects": restored_git["reachable_git_objects"],
        "run_id": run_id,
        "attempt_artifact_count": restored_zips["artifact_count_verified"],
        "out_of_band_receipt_digest_parity_checked": True,
        "native_git_bundle_restored": True,
        "all_opaque_artifact_zip_digests_restored": True,
        "separate_off_github_backup_location_verified": False,
        "github_artifact_http_origin_authenticated": False,
        "publisher_retention_rights_approved": False,
        "production_cutover_authorized": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("git-encrypted", "git-receipt", "git-receipt-sha256",
                 "zip-encrypted", "zip-receipt", "zip-receipt-sha256",
                 "inventory", "run-id", "scratch-dir"):
        parser.add_argument("--" + name, required=True,
                            type=int if name == "run-id" else str)
    parser.add_argument("--gpg-home")
    args = parser.parse_args(argv)
    try:
        report = verify_pair(
            git_encrypted=args.git_encrypted,
            git_receipt=args.git_receipt,
            git_receipt_sha=args.git_receipt_sha256,
            zip_encrypted=args.zip_encrypted,
            zip_receipt=args.zip_receipt,
            zip_receipt_sha=args.zip_receipt_sha256,
            inventory=args.inventory, run_id=args.run_id,
            scratch_dir=args.scratch_dir, gpg_home=args.gpg_home)
    except (RecoveryHold, OSError, UnicodeError, TypeError, KeyError) as exc:
        print(json.dumps({
            "schema": SCHEMA, "status": "HOLD",
            "reason": str(exc) if isinstance(exc, RecoveryHold)
                      else "operator_receipt_or_io_invalid",
            "production_cutover_authorized": False}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
