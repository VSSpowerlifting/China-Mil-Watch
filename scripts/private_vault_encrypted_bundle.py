#!/usr/bin/env python3
"""Offline encrypted full-Git backup/restore gate (no remote or publishing calls).

Owner-controlled terminal only. Never use public CI to handle real publisher
originals. Requires a bare local Git mirror and owner-provided, locally trusted
GPG encryption key. Keeps plaintext bundle OFF disk on backup; restore uses
a mode-0700 temporary directory and deletes decrypted bundle on exit.
The encrypted artifact is NOT an independent backup until the owner copies
it to a separate encrypted medium and tests restore from that copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCHEMA = "ipr-private-vault-encrypted-git-backup/1"
OID = re.compile(r"[0-9a-f]{40}\Z")
FINGERPRINT = re.compile(r"[0-9A-Fa-f]{40}\Z")
MAX_META = 16 * 1024 * 1024


class BackupHold(ValueError):
    """Only controlled diagnostic categories, never paths/bytes/secrets."""


def _run(argv, *, cwd=None, max_output=MAX_META):
    try:
        proc = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise BackupHold("tool_unavailable_or_timeout") from None
    if proc.returncode:
        raise BackupHold("git_or_crypto_check_failed")
    if len(proc.stdout) > max_output:
        raise BackupHold("inventory_too_large")
    return proc.stdout


def _git(repo, *args, max_output=MAX_META):
    return _run(["git", "-C", str(repo), *args], max_output=max_output)


def _bare(repo):
    repo = Path(repo)
    if repo.is_symlink() or not repo.is_dir():
        raise BackupHold("bare_repository_required")
    if _git(repo, "rev-parse", "--is-bare-repository").strip() != b"true":
        raise BackupHold("bare_repository_required")
    return repo


def _inventory(repo):
    """Include heads, tags, notes and any other named refs, not just HEAD."""
    rows = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    try:
        decoded = rows.decode("ascii").splitlines()
    except UnicodeError:
        raise BackupHold("ref_inventory_invalid") from None
    refs = {}
    for line in decoded:
        parts = line.split(" ")
        if len(parts) != 2 or not parts[0].startswith("refs/") or not OID.fullmatch(parts[1]):
            raise BackupHold("ref_inventory_invalid")
        if parts[0] in refs or any(c in parts[0] for c in ("\n", "\r", "\t", " ")):
            raise BackupHold("ref_inventory_invalid")
        refs[parts[0]] = parts[1]
    if not refs:
        raise BackupHold("no_refs_to_preserve")
    return refs


def _expected(items):
    if not items:
        raise BackupHold("pinned_refs_required")
    results = {}
    for item in items:
        if type(item) is not str or "=" not in item:
            raise BackupHold("pinned_ref_invalid")
        ref, commit = item.split("=", 1)
        if not ref.startswith("refs/") or " " in ref or "\n" in ref or not OID.fullmatch(commit):
            raise BackupHold("pinned_ref_invalid")
        if ref in results:
            raise BackupHold("duplicate_pinned_ref")
        results[ref] = commit
    return results


def _object_count(repo):
    raw = _git(repo, "rev-list", "--objects", "--no-object-names", "--all")
    values = raw.decode("ascii").splitlines()
    if any(not OID.fullmatch(x) for x in values) or len(set(values)) != len(values):
        raise BackupHold("git_object_inventory_invalid")
    return len(values)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _gpg_home_args(home):
    if home is None:
        return []
    home = Path(home)
    if home.is_symlink() or not home.is_dir():
        raise BackupHold("gpg_home_invalid")
    return ["--homedir", str(home)]


def _gpg_identity(home, fingerprint):
    if not FINGERPRINT.fullmatch(fingerprint):
        raise BackupHold("recipient_fingerprint_invalid")
    rows = _run(["gpg", *_gpg_home_args(home), "--batch", "--no-tty",
                 "--with-colons", "--list-keys", fingerprint.upper()])
    matches = []
    for line in rows.decode("utf-8", errors="replace").splitlines():
        cols = line.split(":")
        if cols[0] == "fpr" and len(cols) > 9:
            matches.append(cols[9].upper())
    if fingerprint.upper() not in matches:
        raise BackupHold("recipient_key_not_verified")
    return fingerprint.upper()



def _inside_any_git_repository(path):
    """Do not stage encrypted custody backups within *any* Git repository."""
    resolved = Path(path).resolve()
    for directory in (resolved, *resolved.parents):
        marker = directory / ".git"
        if marker.exists() or marker.is_symlink():
            return True
        # Bare Git repositories have HEAD and objects at their root.
        if (directory / "HEAD").is_file() and (directory / "objects").is_dir():
            return True
    return False


def _target(path, repo):
    dest = Path(path)
    parent = dest.parent
    if (dest.is_symlink() or dest.exists() or not parent.is_dir()
            or parent.is_symlink() or dest.resolve().is_relative_to(repo.resolve())
            or _inside_any_git_repository(parent)):
        raise BackupHold("backup_target_unsafe_or_exists")
    return dest


def _verify_source(repo, expected):
    _bare(repo)
    actual = _inventory(repo)
    if actual != expected:
        raise BackupHold("unfrozen_source_refs")
    _git(repo, "fsck", "--full", "--no-reflogs", "--no-progress")
    return _object_count(repo)


def create_backup(repo, output, recipient, refs, *, gpg_home=None):
    """Stream a native full bundle directly to GPG; no plaintext bundle file."""
    repo = _bare(repo)
    expected = _expected(refs)
    objects = _verify_source(repo, expected)
    recipient = _gpg_identity(gpg_home, recipient)
    target = _target(output, repo)
    fd, partial = tempfile.mkstemp(prefix=".ipr-encrypted-", suffix=".part",
                                   dir=str(target.parent))
    os.close(fd)
    try:
        os.chmod(partial, 0o600)
        try:
            git = subprocess.Popen(
                ["git", "-C", str(repo), "bundle", "create", "-", "--all"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            gpg = None
            try:
                gpg = subprocess.Popen(
                    ["gpg", *_gpg_home_args(gpg_home), "--batch", "--no-tty",
                     "--yes", "--trust-model", "always", "--recipient", recipient,
                     "--output", partial, "--encrypt"],
                    stdin=git.stdout, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
                git.stdout.close()
                crypto_status = gpg.wait(timeout=120)
                source_status = git.wait(timeout=120)
            finally:
                # Always terminate/reap BOTH subprocesses on any failure.
                # In particular, a timed-out GPG writer must not survive.
                if git.stdout is not None and not git.stdout.closed:
                    git.stdout.close()
                try:
                    if gpg is not None:
                        if gpg.poll() is None:
                            gpg.kill()
                        gpg.wait(timeout=10)
                finally:
                    if git.poll() is None:
                        git.kill()
                    git.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            raise BackupHold("encrypted_export_unavailable") from None
        if source_status or crypto_status or not Path(partial).stat().st_size:
            raise BackupHold("encrypted_export_failed")
        # Reject changes while Git was serializing the source history. A
        # source mirror is frozen only if its refs and object census are still
        # the exact same ones after the encryption stream closes.
        if _inventory(repo) != expected or _object_count(repo) != objects:
            raise BackupHold("source_changed_during_backup")
        # Flush ciphertext bytes before publishing the final no-clobber name.
        with open(partial, "rb") as saved:
            os.fsync(saved.fileno())
        encrypted_sha = _sha256(partial)
        encrypted_bytes = Path(partial).stat().st_size
        # Atomic no-clobber; avoid os.replace, which could silently replace a
        # different backup written by another operator after our first check.
        try:
            os.link(partial, target)
            directory_fd = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            raise BackupHold("backup_target_race_or_unsafe") from None
        return {
            "schema": SCHEMA, "operation": "backup",
            "encrypted_sha256": encrypted_sha,
            "encrypted_bytes": encrypted_bytes,
            "source_ref_shas": expected,
            "reachable_git_objects": objects,
            "plaintext_bundle_written_to_disk": False,
            "independent_backup_medium_verified": False,
            "independent_restore_passed": False,
            "github_originals_transferred": False,
            "publisher_retention_rights_approved": False,
            "production_cutover_authorized": False,
        }
    finally:
        try:
            os.unlink(partial)
        except FileNotFoundError:
            pass


def verify_restore(encrypted, expected_cipher_sha, refs, object_count,
                   *, scratch_dir, gpg_home=None):
    """Decryption and restore in an owner-selected private scratch directory."""
    expected = _expected(refs)
    if type(expected_cipher_sha) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_cipher_sha):
        raise BackupHold("cipher_digest_invalid")
    if type(object_count) is not int or object_count < 1:
        raise BackupHold("expected_object_count_invalid")
    backup = Path(encrypted)
    scratch = Path(scratch_dir)
    if (backup.is_symlink() or not backup.is_file() or
            scratch.is_symlink() or not scratch.is_dir() or
            backup.resolve().is_relative_to(scratch.resolve())):
        raise BackupHold("restore_paths_unsafe")
    if _sha256(backup) != expected_cipher_sha:
        raise BackupHold("encrypted_bundle_sha_mismatch")
    with tempfile.TemporaryDirectory(prefix="ipr-recovery-", dir=str(scratch)) as temp:
        p = Path(temp)
        os.chmod(p, 0o700)
        plain = p / "decrypted.bundle"
        try:
            _run(["gpg", *_gpg_home_args(gpg_home), "--batch", "--no-tty",
                  "--decrypt", "--output", str(plain), str(backup)],
                 max_output=1024)
        except BackupHold:
            raise BackupHold("decrypt_failed_or_key_unavailable") from None
        os.chmod(plain, 0o600)
        restored = p / "restored.git"
        # 'git clone --bare' drops nonstandard refs (e.g., refs/notes/*
        # and refs/archives/*). Restore the full pinned namespace instead.
        _run(["git", "init", "--bare", "--quiet", str(restored)],
             max_output=1024)
        _run(["git", "-C", str(restored), "fetch", "--quiet", "--no-tags",
              str(plain), "+refs/*:refs/*"], max_output=1024)
        if _inventory(restored) != expected:
            raise BackupHold("restored_refs_mismatch")
        _git(restored, "fsck", "--full", "--no-reflogs", "--no-progress")
        actual_objects = _object_count(restored)
        if actual_objects != object_count:
            raise BackupHold("restored_git_objects_mismatch")
        return {
            "schema": SCHEMA, "operation": "restore",
            "encrypted_sha256": expected_cipher_sha,
            "verified_ref_count": len(expected),
            "reachable_git_objects": actual_objects,
            "encrypted_git_bundle_restored": True,
            "test_on_independent_backup_medium_authenticated": False,
            "lfs_binary_payloads_verified": False,
            "failed_attempt_zips_verified": False,
            "production_cutover_authorized": False,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--bare-repo", required=True)
    backup.add_argument("--encrypted-output", required=True)
    backup.add_argument("--recipient-fingerprint", required=True)
    backup.add_argument("--expect-ref", action="append", required=True)
    backup.add_argument("--gpg-home")
    restore = sub.add_parser("restore")
    restore.add_argument("--encrypted-input", required=True)
    restore.add_argument("--expected-sha256", required=True)
    restore.add_argument("--expected-object-count", type=int, required=True)
    restore.add_argument("--expect-ref", action="append", required=True)
    restore.add_argument("--scratch-dir", required=True)
    restore.add_argument("--gpg-home")
    args = parser.parse_args(argv)
    try:
        if args.operation == "backup":
            report = create_backup(args.bare_repo, args.encrypted_output,
                                   args.recipient_fingerprint, args.expect_ref,
                                   gpg_home=args.gpg_home)
        else:
            report = verify_restore(args.encrypted_input, args.expected_sha256,
                                    args.expect_ref, args.expected_object_count,
                                    scratch_dir=args.scratch_dir,
                                    gpg_home=args.gpg_home)
    except (BackupHold, OSError, UnicodeError) as exc:
        reason = str(exc) if isinstance(exc, BackupHold) else "operator_io_failure"
        print(json.dumps({"schema": SCHEMA, "result": "HOLD",
                          "reason": reason,
                          "production_cutover_authorized": False}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
