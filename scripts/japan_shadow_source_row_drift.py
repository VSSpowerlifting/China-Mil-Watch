#!/usr/bin/env python3
"""Compare archived Oct 5 Japan MOD shadow *row* with current shadow state.

Requires a previously fetched local state repo containing the exact orphan
historical commit and shadow branch. Never fetches publisher PDFs, writes
shadow/production state, sends an editor email or authorizes model reuse.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.japan_shadow_source_row_drift import (  # noqa: E402
    JapanRowDriftError, compare_pinned_row, inspect_current_snapshot, need,
)
from scripts import audit_japan_oct05_brief_source as pinned  # noqa: E402

CURRENT_REFS = (
    "refs/heads/shadow/jp-mod",
    "refs/remotes/origin/shadow/jp-mod",
)


def git(repo, *args):
    try:
        return subprocess.run(
            ["git", *args], cwd=repo, check=True, capture_output=True,
            timeout=30,
        ).stdout.decode("ascii").strip()
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise JapanRowDriftError(
            "required exact local shadow Git history unavailable; no web fallback"
        ) from exc


def audit(repo, *, current_ref):
    """Verify commit ancestry, Git blob bytes and Japanese source identity."""
    need(current_ref in CURRENT_REFS,
         "only fetched official Japan MOD shadow refs are allowed")
    repo = Path(repo)
    need(repo.is_dir(), "local state repository must already exist")
    commit = git(repo, "rev-parse", "--verify", current_ref + "^{commit}")
    need(re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
         "current ref did not resolve to an exact commit")
    # If the historical state is not in this current branch's ancestry, a
    # matching row alone must not be mistaken for continuity of archiving.
    git(repo, "merge-base", "--is-ancestor", pinned.STATE_COMMIT, commit)
    blob = git(repo, "rev-parse", "--verify",
               commit + ":" + pinned.STATE_PATH)
    need(re.fullmatch(r"[0-9a-f]{40}", blob) is not None,
         "current shadow blob hash missing")
    older = pinned.read_git_blob(repo)
    historical = pinned.inspect_snapshot(older)
    need(historical["archived_text_sha256_verified"] is True
         and historical["archived_original_pdf_bytes_verified"] is False,
         "historical extracted text not independently verified")
    current = pinned.read_git_blob(repo, commit=commit, expected_blob=blob)
    row = inspect_current_snapshot(current)
    return compare_pinned_row(row, current_commit=commit, current_blob=blob)


def exclusive_private(path, result):
    # Resolve for repository containment, but open the original leaf path:
    # resolving the destination itself could follow a swapped symlink.
    target = Path(path).expanduser().absolute()
    resolved = target.resolve()
    root = ROOT.resolve()
    need(not target.exists() and not target.is_symlink()
         and resolved != root and root not in resolved.parents
         and target.parent.is_dir() and not target.parent.is_symlink(),
         "private audit must be a new output outside repo, never overwritten")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(target), flags, 0o600)
    owned = None
    try:
        owned = os.fstat(fd)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = None  # fdopen's text stream now owns the descriptor.
            json.dump(result, stream, indent=2, ensure_ascii=False,
                      sort_keys=True, allow_nan=False)
            stream.write("\n")
    except BaseException:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        # Never unlink a file replacing our originally created inode.
        if owned is not None:
            try:
                current = target.lstat()
                if (not target.is_symlink() and
                        (current.st_dev, current.st_ino) ==
                        (owned.st_dev, owned.st_ino)):
                    target.unlink()
            except OSError:
                pass
        raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state-repo", required=True, type=Path)
    p.add_argument("--current-ref", required=True, choices=CURRENT_REFS)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        result = audit(args.state_repo, current_ref=args.current_ref)
        exclusive_private(args.out, result)
    except (ValueError, OSError) as exc:
        p.error(str(exc))
    print("Japan Oct 5 shadow source: " + result["row_comparison"])
    print("Current official PDF/reuse rights NOT checked; model/email/publication FALSE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
