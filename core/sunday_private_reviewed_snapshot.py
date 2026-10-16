"""Disabled local-only freeze of the exact owner-reviewed first Sunday worksheet.

NO CLI, email, model, scheduler, GitHub Actions, publisher fetch or approval grant.
Copies the original attachment ONCE into an owner-only private directory. The
result is a no-overwrite snapshot, not a cryptographic owner authorization,
tamper-proof backup, license or safe-to-send decision.
"""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from scripts.sunday_first_pilot_reviewed_replay import (
    PILOT_SATURDAY, MAX_BYTES, ReplayRefused, inspect_file,
)


class SnapshotHold(ValueError):
    """The original reviewed bytes could not be privately frozen safely."""


def _private_directory(path):
    folder = Path(path)
    if (not folder.is_absolute() or folder.is_symlink() or
            not folder.is_dir() or folder.stat().st_uid != os.getuid() or
            stat.S_IMODE(folder.stat().st_mode) & 0o077):
        raise SnapshotHold("snapshot directory must be caller-owned, existing, and 0700")
    # Do not create private publisher/source text anywhere in the public repo,
    # even in a newly created owner-only directory. This is not a Git ignore
    # guarantee: avoid putting the files in the worktree in the first place.
    repo = Path(__file__).resolve().parents[1]
    resolved = folder.resolve(strict=True)
    # A lexical path inside Git may traverse a symlink to external storage.
    # Refuse that too; the operator must address private custody directly.
    # Otherwise a repository-controlled symlink can make a private artifact
    # reachable through the checkout even though resolve() points elsewhere.
    for candidate in (Path(os.path.abspath(str(folder))), resolved):
        try:
            candidate.relative_to(repo)
        except ValueError:
            continue
        raise SnapshotHold("private reviewed text cannot be stored inside the repository")
    return folder


def _read_once(source):
    """Reject link swaps; check file metadata before/after the bounded read."""
    path = Path(source)
    if not path.is_absolute() or path.is_symlink():
        raise SnapshotHold("reviewed input must be an absolute non-symlink path")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(path), flags)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or before.st_nlink != 1 or not 0 < before.st_size <= MAX_BYTES):
            raise SnapshotHold("owner-reviewed file is not a bounded caller-owned regular file")
        data = bytearray()
        while len(data) <= MAX_BYTES:
            chunk = os.read(fd, min(65536, MAX_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        after = os.fstat(fd)
        if (len(data) != before.st_size or
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise SnapshotHold("reviewed input changed during snapshot read")
        return bytes(data)
    finally:
        os.close(fd)


def freeze_exact_reviewed_attachment(source, private_dir, *,
                                     expected_sha256, week_ending=PILOT_SATURDAY):
    """Freeze exactly one private first-pilot TXT, never replacing an existing file.

    The caller must independently verify actual human approval, source accuracy,
    publisher reuse permissions and destination recipient. Only byte equality,
    format and private storage mechanics are checked here.
    """
    if week_ending != PILOT_SATURDAY:
        raise SnapshotHold("first Sunday pilot only; no silent future-week approval")
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or
            any(c not in "0123456789abcdef" for c in expected_sha256)):
        raise SnapshotHold("expected_sha256 must be exact lowercase SHA-256")
    root = _private_directory(private_dir)
    # A separate owner review process must attest this digest; an assertion by
    # the same code running the sender is NOT proof of a human review.
    original = _read_once(source)
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise SnapshotHold("input does not match the frozen owner-reviewed SHA-256")
    name = "IPR-" + week_ending + "-" + expected_sha256 + ".txt"
    target = root / name
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(target), flags, 0o600)
    except FileExistsError as exc:
        raise SnapshotHold("reviewed attachment already stored; no automatic overwrite") from exc
    try:
        try:
            with os.fdopen(fd, "wb") as output:
                fd = -1  # Ownership of descriptor moved to output.
                output.write(original)
                output.flush()
                os.fchmod(output.fileno(), 0o400)
                # Persist data AND protective file mode before publishing the
                # returned path. fsync after chmod covers file metadata too.
                os.fsync(output.fileno())
            # Check the actual frozen file with the existing editorial parser.
            # Never re-read the mutable incoming source after this point.
            actual, info = inspect_file(target, week_ending=week_ending)
            if actual != original or info["sha256"] != expected_sha256:
                raise SnapshotHold("stored reviewed bytes failed exact verification")
            dir_flags = os.O_RDONLY
            if hasattr(os, "O_DIRECTORY"):
                dir_flags |= os.O_DIRECTORY
            dirfd = os.open(str(root), dir_flags)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except BaseException:
            # Safe on validation/system errors; a hard process crash may leave
            # a partial file. O_EXCL intentionally refuses reuse in that case.
            target.unlink(missing_ok=True)
            raise
    finally:
        if fd >= 0:
            os.close(fd)
    return {"path": target, "sha256": expected_sha256,
            "week": week_ending, "bytes": len(original), "frozen": True}
