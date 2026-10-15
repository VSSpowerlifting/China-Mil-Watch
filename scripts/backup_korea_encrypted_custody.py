"""Operator-only encrypted Korea Git-state backup and real restore verification.

NEVER runs in scheduled CI on actual sources. Requires the owner's separately
approved retention/backup decision. Encryption uses an already-authorized GPG
public-key fingerprint and a local private key for decryption. It performs
NO GitHub network calls, source collection, scheduler switch, AI, SMTP or site
publication. Its own positive receipt does NOT certify durable off-provider
storage, a key-recovery plan, source rights or release authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from scripts.verify_korea_private_custody_equivalence import (
    FROZEN_14, CustodyHold, compare, inventory,
)

SCHEMA = "ipr-korea-encrypted-local-git-backup-restore/1"
KEY_ID = re.compile(r"[0-9A-Fa-f]{40}\Z")
MAX_BACKUP_BYTES = 300 * 1024 * 1024


class BackupHold(ValueError):
    """Only fixed status codes, never command stderr or source contents."""


def require(condition, reason):
    if not condition:
        raise BackupHold(reason)


def _safe_directory(path, *, label):
    original = Path(path).expanduser()
    require(original.is_absolute() and original.is_dir()
            and not original.is_symlink(), label + "_directory_unsafe")
    resolved = original.resolve()
    require(resolved.is_dir(), label + "_directory_unavailable")
    require(stat.S_IMODE(resolved.stat().st_mode) & 0o077 == 0,
            label + "_directory_not_owner_only")
    return resolved


def _destination(path, source, *, home):
    output = Path(path).expanduser()
    require(output.is_absolute() and output.parent.is_dir()
            and not output.parent.is_symlink() and not output.exists()
            and not output.is_symlink(), "encrypted_destination_not_new")
    dest = output.resolve(strict=False)
    src = Path(source).resolve()
    from_repo = Path(__file__).resolve().parents[1]
    require(src != dest and src not in dest.parents
            and from_repo != dest and from_repo not in dest.parents
            and home != dest and home not in dest.parents,
            "encrypted_destination_inside_source_or_code")
    parent = _safe_directory(output.parent, label="backup")
    require(parent != src and src not in parent.parents,
            "encrypted_destination_inside_source")
    return output


def _hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(args, *, stdout=None, timeout=180):
    try:
        result = subprocess.run(args, stdout=stdout or subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=timeout,
                                check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise BackupHold("local_crypto_or_git_unavailable") from None
    require(result.returncode == 0, "local_crypto_or_git_failed")


def backup_restore(source_checkout, encrypted_output, recipient_fingerprint,
                   gpg_home, scratch_parent, *, frozen_commit=FROZEN_14,
                   explicit_owner_restricted_retention=False):
    """Generate *encrypted-only* durable output, restore in owner-only scratch.

    No persistently written plaintext backup at encryption time (pipe Git
    bundle directly to GPG). Decryption uses a temporary 0600 plaintext bundle
    inside an explicitly chosen 0700 local scratch directory; the OS may retain deleted blocks.
    Run only on an owner-approved encrypted trusted host.
    """
    require(explicit_owner_restricted_retention is True,
            "owner_restricted_retention_approval_required")
    require(type(recipient_fingerprint) is str
            and KEY_ID.fullmatch(recipient_fingerprint) is not None,
            "exact_gpg_recipient_fingerprint_required")
    require(shutil.which("gpg") is not None
            and shutil.which("git") is not None,
            "git_and_gpg_required")
    gpg = _safe_directory(gpg_home, label="gpg_home")
    scratch = _safe_directory(scratch_parent, label="scratch")
    source = Path(source_checkout).expanduser()
    require(source.is_absolute() and source.is_dir()
            and not source.is_symlink(), "source_checkout_invalid")
    source = source.resolve()
    code_root = Path(__file__).resolve().parents[1]
    require(scratch != source and source not in scratch.parents
            and scratch != code_root and code_root not in scratch.parents,
            "scratch_inside_source_or_public_repository")
    try:
        before = inventory(source, frozen_commit=frozen_commit)
    except (CustodyHold, OSError, ValueError) as exc:
        raise BackupHold("source_archive_integrity_hold") from exc
    target = _destination(encrypted_output, source, home=gpg)
    # Require local GPG key availability *before* creating any output.
    _run(["gpg", "--homedir", str(gpg), "--batch", "--list-keys",
          recipient_fingerprint])
    fd = -1
    created = False
    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o600)
        created = True
        with os.fdopen(fd, "wb") as encrypted_stream:
            fd = -1
            try:
                git_proc = subprocess.Popen(
                    ["git", "-C", str(source), "bundle", "create", "-", "HEAD"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                enc_proc = subprocess.Popen(
                    ["gpg", "--homedir", str(gpg), "--batch", "--quiet",
                     "--trust-model", "always", "--recipient",
                     recipient_fingerprint, "--encrypt"],
                    stdin=git_proc.stdout, stdout=encrypted_stream,
                    stderr=subprocess.DEVNULL)
                git_proc.stdout.close()
                enc_proc.wait(timeout=180)
                git_proc.wait(timeout=180)
            except (OSError, subprocess.TimeoutExpired):
                for proc in (locals().get("enc_proc"), locals().get("git_proc")):
                    if proc is not None and proc.poll() is None:
                        proc.kill()
                        proc.wait()
                raise BackupHold("stream_encryption_failed") from None
            require(enc_proc.returncode == 0 and git_proc.returncode == 0,
                    "stream_encryption_failed")
        require(0 < target.stat().st_size <= MAX_BACKUP_BYTES
                and stat.S_IMODE(target.stat().st_mode) == 0o600,
                "encrypted_backup_size_or_mode_invalid")
        with tempfile.TemporaryDirectory(prefix="ipr-korea-private-restore-",
                                         dir=scratch) as tmp:
            folder = Path(tmp)
            os.chmod(folder, 0o700)
            plain = folder / "restorable.bundle"
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            with os.fdopen(os.open(plain, flags, 0o600), "wb") as output:
                _run(["gpg", "--homedir", str(gpg), "--batch", "--quiet",
                      "--decrypt", str(target)], stdout=output)
            restored = folder / "restored"
            _run(["git", "clone", "--quiet", "--no-local", str(plain),
                  str(restored)])
            try:
                proof = compare(source, restored, frozen_commit=frozen_commit)
            except (CustodyHold, OSError, ValueError) as exc:
                raise BackupHold("decrypted_git_restore_not_equivalent") from exc
            require(proof["source_and_candidate_bytes_identical"] is True
                    and proof["preserved_git_commit"] == before["head"],
                    "decrypted_git_restore_not_equivalent")
        after = inventory(source, frozen_commit=frozen_commit)
        require(before == after, "source_changed_during_backup")
        return {
            "schema": SCHEMA,
            "source_commit": before["head"],
            "frozen_ancestor": frozen_commit,
            "encrypted_backup_sha256": _hash_file(target),
            "encrypted_backup_bytes": target.stat().st_size,
            "captured_objects": before["capture_count"],
            "source_originals": before["original_count"],
            "state_file_count": len(before["files"]),
            "local_decrypt_and_git_restore_equivalent": True,
            "recipient_fingerprint_format_verified": True,
            "gpg_private_key_was_usable_locally": True,
            "durable_off_provider_backup_verified": False,
            "independent_recovery_operator_verified": False,
            "source_retention_rights_judged_by_tool": False,
            "private_github_archive_writer_activated": False,
            "korea_sunday_or_publication_authorized": False,
            "production_promotion_authorized": False,
        }
    except BaseException:
        if fd != -1:
            os.close(fd)
        if created:
            target.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-checkout", required=True)
    parser.add_argument("--encrypted-out", required=True)
    parser.add_argument("--recipient-fingerprint", required=True)
    parser.add_argument("--gpg-home", required=True)
    parser.add_argument("--scratch-parent", required=True,
                        help="existing 0700 trusted encrypted scratch directory")
    parser.add_argument("--owner-approved-restricted-retention", action="store_true")
    args = parser.parse_args(argv)
    try:
        receipt = backup_restore(
            args.source_checkout, args.encrypted_out,
            args.recipient_fingerprint, args.gpg_home, args.scratch_parent,
            explicit_owner_restricted_retention=args.owner_approved_restricted_retention)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except (BackupHold, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, BackupHold) else "backup_failed_closed"
        print(json.dumps({"schema": SCHEMA, "result": "HOLD",
                          "reason": reason,
                          "korea_sunday_or_publication_authorized": False,
                          "production_promotion_authorized": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
