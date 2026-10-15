#!/usr/bin/env python3
"""No-network, temporary-only Git bundle/restore proof for FICTIONAL vault pilot.

For real originals an owner must separately approve a durable encrypted
off-provider backup and its *independent* restore. This demo proves only
lossless temporary native Git object recovery, never actual archive readiness.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

SCHEMA = "ipr-private-github-fictional-bundle-recovery/1"
PILOT_SCHEMA = "ipr-private-github-fictional-vault-pilot/1"
BRANCH = "refs/heads/pilot/fictional-custody-20261015"
ALLOWED = frozenset({
    "README.md",
    "pilot/manifest.json",
    "pilot/source/successful-original.txt",
    "pilot/source/failed-attempt-original.txt",
})
MAX_CAPTURE = 16 * 1024


class FictionalRecoveryError(ValueError):
    """Fixed codes only; never relay Git stderr or source content."""


def _git(repo, *args, max_bytes=2 * 1024 * 1024):
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise FictionalRecoveryError("git_unavailable") from None
    if done.returncode:
        raise FictionalRecoveryError("git_ref_or_integrity_invalid") from None
    if len(done.stdout) > max_bytes:
        raise FictionalRecoveryError("git_output_oversize")
    return done.stdout


def _head(repo):
    head = _git(repo, "rev-parse", "--verify", BRANCH + "^{commit}").decode("ascii").strip()
    if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
        raise FictionalRecoveryError("head_invalid")
    return head


def _objects(repo):
    data = _git(repo, "rev-list", "--objects", "--no-object-names", BRANCH,
                max_bytes=4 * 1024 * 1024).decode("ascii").splitlines()
    if len(set(data)) != len(data) or any(len(h) != 40 or
          any(c not in "0123456789abcdef" for c in h) for h in data):
        raise FictionalRecoveryError("git_object_inventory_invalid")
    return set(data)


def _check_fixture(repo):
    raw = _git(repo, "ls-tree", "-r", "--name-only", BRANCH).decode("utf-8").splitlines()
    if set(raw) != ALLOWED or len(raw) != len(ALLOWED):
        raise FictionalRecoveryError("nonfictional_or_extra_file")
    m_bytes = _git(repo, "show", BRANCH + ":pilot/manifest.json", max_bytes=MAX_CAPTURE)
    try:
        manifest = json.loads(m_bytes)
    except (UnicodeError, ValueError):
        raise FictionalRecoveryError("fixture_manifest_invalid") from None
    if (type(manifest) is not dict or manifest.get("schema") != PILOT_SCHEMA or
            manifest.get("status") != "FICTIONAL_TEST_ONLY_NO_PUBLISHER_DATA"):
        raise FictionalRecoveryError("fixture_manifest_invalid")
    cases = manifest.get("cases")
    if type(cases) is not list or len(cases) != 2:
        raise FictionalRecoveryError("fixture_case_count")
    expected = {
        "success": ("pilot/source/successful-original.txt", "success"),
        "failed_uncommitted_capture": (
            "pilot/source/failed-attempt-original.txt",
            "attempt_failed_before_source_branch_push"),
    }
    if {c.get("case_id") for c in cases if type(c) is dict} != set(expected):
        raise FictionalRecoveryError("fixture_case_identity")
    governance = manifest.get("governance")
    if type(governance) is not dict or not governance or any(
            value is not False for value in governance.values()):
        raise FictionalRecoveryError("fixture_governance_not_closed")
    for case in cases:
        if type(case) is not dict:
            raise FictionalRecoveryError("fixture_case_invalid")
        filename, status = expected[case["case_id"]]
        if case.get("source_path") != filename or case.get("capture_status") != status:
            raise FictionalRecoveryError("fixture_case_invalid")
        body = _git(repo, "show", BRANCH + ":" + filename, max_bytes=MAX_CAPTURE)
        if (not body.startswith(b"IPR SYNTHETIC ") or
                b"source=fixture_testing_only\n" not in body or len(body) > MAX_CAPTURE):
            raise FictionalRecoveryError("nonfictional_capture_forbidden")
        if hashlib.sha256(body).hexdigest() != case.get("sha256") or len(body) != case.get("bytes"):
            raise FictionalRecoveryError("fixture_capture_sha_mismatch")
    return manifest


def rehearse(repo):
    """No network, no source mutation, no destination archive writes."""
    root = Path(repo)
    temp = Path(tempfile.gettempdir()).resolve()
    if root.is_symlink() or not root.is_dir() or temp not in root.resolve().parents:
        raise FictionalRecoveryError("fictional_temp_source_required")
    _check_fixture(root)
    original_head, original_objects = _head(root), _objects(root)
    with tempfile.TemporaryDirectory(prefix="ipr-fictional-vault-recovery-") as tmp:
        base = Path(tmp)
        bundle = base / "fixture.bundle"
        _git(root, "bundle", "create", str(bundle), BRANCH)
        _git(root, "bundle", "verify", str(bundle))
        if not bundle.is_file() or not bundle.stat().st_size:
            raise FictionalRecoveryError("fixture_bundle_empty")
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        restored = base / "restored.git"
        try:
            command = subprocess.run(
                ["git", "clone", "--quiet", "--bare", str(bundle), str(restored)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=False, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise FictionalRecoveryError("fixture_restore_unavailable") from None
        if command.returncode:
            raise FictionalRecoveryError("fixture_restore_failed")
        if _head(restored) != original_head or _objects(restored) != original_objects:
            raise FictionalRecoveryError("fixture_restore_objects_mismatch")
        _git(restored, "fsck", "--connectivity-only", "--no-progress")
        _check_fixture(restored)
        return {
            "schema": SCHEMA,
            "fictional_pilot_only": True,
            "source_commit": original_head,
            "restored_commit": _head(restored),
            "reachable_git_objects": len(original_objects),
            "bundle_sha256": digest,
            "fixture_success_capture_verified": True,
            "fixture_failed_only_capture_verified": True,
            "temporary_git_recovery_passed": True,
            "independent_durable_encrypted_backup_proven": False,
            "real_publisher_originals_migrated": False,
            "production_cutover_authorized": False,
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fictional-local-repo", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(rehearse(args.fictional_local_repo), sort_keys=True))
    except FictionalRecoveryError as error:
        print(json.dumps({"schema": SCHEMA, "result": "HOLD",
                          "reason": str(error), "production_cutover_authorized": False},
                         sort_keys=True))
        raise SystemExit(2) from None
