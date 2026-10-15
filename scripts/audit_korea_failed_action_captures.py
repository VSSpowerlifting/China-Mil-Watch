"""Read-only Korea failed-Action capture inventory against a pinned shadow Git tree.

This tool NEVER extracts source bodies, moves originals, uploads artifacts,
authenticates GitHub run provenance, or authorizes copying/publishing.
Use only on a trusted offline operator machine with an already downloaded ZIP.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import zipfile
from pathlib import Path

SHA = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_MEMBERS = 1000
MAX_MEMBER_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 250 * 1024 * 1024
MAX_ZIP_BYTES = 100 * 1024 * 1024
SCHEMA = "ipr-korea-failed-actions-capture-census/1"


class ArtifactHold(ValueError):
    """Fixed diagnostic codes: do not expose source data or local paths."""


def require(ok, reason):
    if not ok:
        raise ArtifactHold(reason)


def _hash_stream(stream):
    digest, length = hashlib.sha256(), 0
    while True:
        piece = stream.read(1024 * 1024)
        if not piece:
            break
        length += len(piece)
        require(length <= MAX_MEMBER_BYTES, "oversize_payload")
        digest.update(piece)
    return digest.hexdigest(), length


def _pinned_state(root, expected_sha):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(),
            "invalid_shadow_checkout")
    require(type(expected_sha) is str and GIT_SHA.fullmatch(expected_sha),
            "invalid_requested_git_sha")
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ArtifactHold("git_identity_unavailable") from None
    require(proc.returncode == 0 and
            proc.stdout.decode("ascii", "strict").strip() == expected_sha,
            "unmatched_shadow_git_commit")
    try:
        clean = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise ArtifactHold("git_worktree_status_unavailable") from None
    require(clean.returncode == 0 and not clean.stdout.strip(),
            "shadow_checkout_has_uncommitted_or_untracked_files")
    captures = root / "state" / "captures"
    require(captures.is_dir() and not captures.is_symlink(),
            "shadow_capture_directory_missing")
    observed = {}
    for path in captures.iterdir():
        require(path.is_file() and not path.is_symlink()
                and path.name.endswith(".bin")
                and SHA.fullmatch(path.stem) is not None,
                "invalid_shadow_capture_file")
        require(len(observed) < MAX_MEMBERS
                and 0 < path.stat().st_size <= MAX_MEMBER_BYTES,
                "shadow_capture_budget_exceeded")
        with path.open("rb") as stream:
            digest, count = _hash_stream(stream)
        require(digest == path.stem, "shadow_capture_digest_mismatch")
        observed[path.stem] = count
    require(observed, "empty_shadow_capture_set")
    return observed


def _safe_member(info):
    name = info.filename
    require(type(name) is str and name and len(name) <= 400
            and not name.startswith("/") and "\\" not in name
            and "\x00" not in name
            and not any(part in ("", ".", "..") for part in name.rstrip("/").split("/"))
            and not any(ord(c) < 32 or ord(c) == 127 for c in name),
            "unsafe_zip_member_name")
    # Unix external_attr mode only indicates a symlink for Unix-created ZIPs.
    if info.create_system == 3:
        mode = (info.external_attr >> 16) & 0xFFFF
        require(not stat.S_ISLNK(mode), "zip_symlink_refused")
    require(not (info.flag_bits & 1), "encrypted_zip_entry_refused")
    require(info.file_size <= MAX_MEMBER_BYTES,
            "zip_member_uncompressed_budget_exceeded")
    return name


def _capture_id(filename):
    # GitHub Actions artifact archives commonly flatten the uploaded state/
    # directory to archive root. Accept either layout, never both.
    for prefix in ("captures/", "state/captures/",
                   "candidate-state/state/captures/"):
        if filename.startswith(prefix):
            suffix = filename[len(prefix):]
            require(suffix.endswith(".bin")
                    and SHA.fullmatch(suffix[:-4]) is not None,
                    "unrecognized_capture_path")
            return prefix, suffix[:-4]
    return None


def inspect(zip_path, shadow_checkout, expected_commit, *, run_id, attempt=1):
    """Calculate digest and unique-only counts; NEVER export original source."""
    require(type(run_id) is int and run_id > 0
            and type(attempt) is int and attempt >= 1,
            "invalid_action_attempt_identity")
    shadow = _pinned_state(shadow_checkout, expected_commit)
    archive = Path(zip_path)
    require(archive.is_file() and not archive.is_symlink()
            and 0 < archive.stat().st_size <= MAX_ZIP_BYTES,
            "missing_or_oversize_actions_zip")
    seen, member_count, total, prefix_used = set(), 0, 0, None
    archived = {}
    try:
        with zipfile.ZipFile(archive, "r") as z:
            members = z.infolist()
            require(0 < len(members) <= MAX_MEMBERS,
                    "zip_entry_count_out_of_bounds")
            for info in members:
                name = _safe_member(info)
                require(name not in seen, "duplicate_zip_entry")
                seen.add(name)
                member_count += 1
                total += info.file_size
                require(total <= MAX_TOTAL_BYTES,
                        "zip_total_uncompressed_budget_exceeded")
                kind = _capture_id(name.rstrip("/"))
                if not kind:
                    # Other state files may include logs/ledgers/SQLite.
                    # None are extracted or used to infer successful collection.
                    continue
                require(not info.is_dir(), "capture_cannot_be_directory")
                prefix, digest_id = kind
                if prefix_used is None:
                    prefix_used = prefix
                require(prefix_used == prefix, "mixed_capture_roots")
                require(digest_id not in archived, "duplicate_capture_identity")
                with z.open(info, "r") as stream:
                    calculated, size = _hash_stream(stream)
                require(calculated == digest_id and size == info.file_size
                        and size > 0, "artifact_capture_digest_mismatch")
                archived[digest_id] = size
    except (OSError, zipfile.BadZipFile, RuntimeError, EOFError):
        raise ArtifactHold("unreadable_actions_zip") from None
    require(archived, "zip_has_no_verifiable_captures")
    shared = set(archived) & set(shadow)
    require(all(archived[k] == shadow[k] for k in shared),
            "archive_vs_shadow_byte_length_mismatch")
    new = sorted(set(archived) - set(shadow))
    receipt = {
        "schema": SCHEMA,
        "shadow_commit": expected_commit,
        "claimed_action_run_id": run_id,
        "claimed_action_attempt": attempt,
        "run_identity_authenticated_by_tool": False,
        "archive_member_count": member_count,
        "verified_capture_count": len(archived),
        "captures_already_in_shadow": len(shared),
        "captures_absent_from_shadow": len(new),
        "unique_capture_bytes": sum(archived[k] for k in new),
        "sha256_bytes_checked": True,
        "capture_bodies_exported": False,
        "raw_originals_transferred": False,
        "government_source_retrieval_performed": False,
        "independent_backup_restored": False,
        "legal_source_retention_approved": False,
        "scheduled_october_12_gap_repaired": False,
        "source_rights_or_publication_approved": False,
        "korea_production_admission_authorized": False,
    }
    # Return the sensitive unique SHA list to caller, but NEVER stdout.
    return receipt, new


def write_private_manifest(destination, receipt, unique_sha):
    """Optional private metadata receipt; strict new 0600 path outside cwd/repo."""
    target = Path(destination).expanduser()
    require(target.is_absolute() and target.parent.is_dir() and
            not target.parent.is_symlink() and not target.exists()
            and not target.is_symlink(), "private_output_not_new_absolute_file")
    try:
        cwd = Path.cwd().resolve()
        resolved = target.resolve(strict=False)
        require(resolved != cwd and cwd not in resolved.parents,
                "private_output_inside_repository_checkout")
    except OSError:
        raise ArtifactHold("private_output_unverifiable") from None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(target, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump({"receipt": receipt, "unique_capture_sha256": unique_sha},
                      out, indent=2, sort_keys=True)
            out.write("\n")
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--actions-zip", required=True)
    parser.add_argument("--shadow-checkout", required=True)
    parser.add_argument("--expected-shadow-commit", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--private-manifest-out",
                        help="optional absolute new restricted file outside repository")
    parser.add_argument("--acknowledge-offline-only", action="store_true", required=True)
    args = parser.parse_args(argv)
    if not args.acknowledge_offline_only:
        parser.error("--acknowledge-offline-only required")
    try:
        receipt, unique = inspect(
            args.actions_zip, args.shadow_checkout, args.expected_shadow_commit,
            run_id=args.run_id, attempt=args.attempt)
        if args.private_manifest_out:
            write_private_manifest(args.private_manifest_out, receipt, unique)
        print(json.dumps(receipt, sort_keys=True))
        return 0
    except ArtifactHold as exc:
        print(json.dumps({"schema": SCHEMA, "result": "HOLD",
                          "reason": str(exc),
                          "korea_production_admission_authorized": False},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
