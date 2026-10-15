#!/usr/bin/env python3
"""Read-only Git-object parity proof between original and isolated vault refs.

An owner runs this on TWO already-authorized local Git clones. There is NO
fetch/push, source-body print, GitHub API, LFS download, provider configuration,
collector, SMTP, model or public release. Matching commits and reachable Git
objects alone never prove private visibility, independent backup or rights.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "ipr-private-github-ref-parity/1"
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
BRANCH = re.compile(r"(?:shadow|archive)/[a-z][a-z0-9._/-]{1,110}\Z")
MAX_OBJECT_IDS_BYTES = 12 * 1024 * 1024


class ParityError(ValueError):
    """Fixed safe codes; never expose original filenames or file contents."""


def _ref(kind, name):
    if type(name) is not str or not BRANCH.fullmatch(name):
        raise ParityError("ref_name_invalid")
    if not name.startswith(kind + "/") or any(x in name for x in ("..", "//", "@{")) or name.endswith((".", "/")):
        raise ParityError("ref_name_invalid")
    return "refs/heads/" + name


def _git(repo: Path, *args):
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=90, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise ParityError("git_inspection_unavailable") from None
    if out.returncode:
        raise ParityError("git_integrity_or_ref_error") from None
    if len(out.stdout) > MAX_OBJECT_IDS_BYTES:
        raise ParityError("git_inventory_exceeds_bound")
    return out.stdout


def _objects(repo: Path, ref: str):
    raw = _git(repo, "rev-list", "--objects", "--no-object-names", ref)
    try:
        rows = raw.decode("ascii").splitlines()
    except UnicodeError:
        raise ParityError("git_inventory_invalid") from None
    if any(not COMMIT.fullmatch(item) for item in rows):
        raise ParityError("git_inventory_invalid")
    if len(set(rows)) != len(rows):
        raise ParityError("git_inventory_duplicate")
    return set(rows)


def compare(source_repo, vault_repo, source_ref, vault_ref, expected_source_commit):
    if type(expected_source_commit) is not str or not COMMIT.fullmatch(expected_source_commit):
        raise ParityError("expected_commit_invalid")
    sr, vr = Path(source_repo), Path(vault_repo)
    if sr.is_symlink() or vr.is_symlink() or not sr.is_dir() or not vr.is_dir():
        raise ParityError("git_repository_path_invalid")
    if sr.resolve() == vr.resolve():
        raise ParityError("source_is_destination")
    origin = _ref("shadow", source_ref)
    archive = _ref("archive", vault_ref)
    _git(sr, "rev-parse", "--git-dir")
    _git(vr, "rev-parse", "--git-dir")
    src_head = _git(sr, "rev-parse", "--verify", origin + "^{commit}").decode("ascii").strip()
    vault_head = _git(vr, "rev-parse", "--verify", archive + "^{commit}").decode("ascii").strip()
    if not COMMIT.fullmatch(src_head) or not COMMIT.fullmatch(vault_head):
        raise ParityError("commit_identity_invalid")
    if src_head != expected_source_commit:
        raise ParityError("source_head_changed_since_freeze")
    if vault_head != expected_source_commit:
        raise ParityError("archive_head_does_not_match_source")
    _git(sr, "fsck", "--full", "--no-reflogs", "--no-progress", "--connectivity-only", src_head)
    _git(vr, "fsck", "--full", "--no-reflogs", "--no-progress", "--connectivity-only", vault_head)
    expected = _objects(sr, origin)
    observed = _objects(vr, archive)
    if expected != observed:
        raise ParityError("source_archive_object_inventory_mismatch")
    return {
        "schema": SCHEMA,
        "source_head": src_head,
        "vault_head": vault_head,
        "reachable_git_objects_verified": len(expected),
        "source_archive_git_object_sets_match": True,
        "private_destination_visibility_authenticated": False,
        "git_lfs_binary_objects_independently_verified": False,
        "failed_uncommitted_attempts_verified": False,
        "independent_backup_restored": False,
        "publisher_source_retention_rights_approved": False,
        "production_cutover_authorized": False,
        "ready_for_live_migration": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--vault-repo", required=True, type=Path)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--vault-ref", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args(argv)
    try:
        report = compare(args.source_repo, args.vault_repo, args.source_ref,
                         args.vault_ref, args.source_commit)
    except ParityError as exc:
        print(json.dumps({"schema": SCHEMA, "result": "HOLD", "reason": str(exc),
                          "ready_for_live_migration": False}, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
