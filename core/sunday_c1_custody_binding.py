"""C1: disabled, fictional-only exact Sunday TXT -> private snapshot -> journal binding.

This is an INERT offline rehearsal. It cannot email, call a model, reserve a
send, sign a human approval, validate publisher rights, or modify workflows.
PR dependencies: #377 (journal), #382 (source-use receipt), #385 (snapshot).

A digest given by the caller is not authenticated human owner authorization.
All recipient identities in this rehearsal must use the reserved *.invalid
fixture domain, never a real recipient or a private production mailing list.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path

from core.sunday_delivery_journal import DeliveryHold, DeliveryJournal, intent_id
from core.sunday_delivery_replay_rehearsal import source_use_fingerprint
from core.sunday_private_reviewed_snapshot import freeze_exact_reviewed_attachment
from scripts.sunday_first_pilot_reviewed_replay import inspect_file
from scripts.sunday_pilot_owner_review import (
    PILOT_SATURDAY, require_exact_reviewed_manuscript, require_owner_review,
)


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class FictionalCustodyHold(ValueError):
    """Preflight failed; no sender or automatic retry exists."""


def _pinned_digest(value, label):
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise FictionalCustodyHold(label + " requires lowercase SHA-256")
    return value


def _require_outside_repository(value, kind):
    """Refuse an original or journal path under public Git, before any read."""
    path = Path(value)
    if not path.is_absolute():
        raise FictionalCustodyHold(kind + " requires an absolute private path")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise FictionalCustodyHold(kind + " private path missing or invalid") from exc
    repository = Path(__file__).resolve().parents[1]
    # Reject paths *located* inside Git and destinations reached through
    # symlinked parents into Git. Resolving only the final target would accept
    # a link created inside the public checkout that points outward.
    for candidate in (Path(os.path.abspath(str(path))), resolved):
        try:
            candidate.relative_to(repository)
        except ValueError:
            continue
        raise FictionalCustodyHold(kind + " must remain outside the public repository")


def bind_fictional_reviewed_snapshot(
        source, private_dir, journal, *, week, approved_week,
        reviewed_sha256, source_use_sha256, recipient,
        fictional_owner_approval_sha256):
    """Register a fictional reviewed file after durable private byte capture.

    A completed return is *not* SMTP or editorial approval: this only registers
    an offline journal identity, never a reserved send attempt. The caller must
    not print or publish the returned private path. This is scoped to one pilot.
    """
    if week != PILOT_SATURDAY:
        raise FictionalCustodyHold("C1 rehearsal is limited to first pilot Saturday")
    if not isinstance(journal, DeliveryJournal):
        raise FictionalCustodyHold("explicit already-initialized private journal required")
    # This code cannot undo public exposure from an already staged source.
    # Refuse both sensitive input and journal state inside the Git worktree
    # even if the eventual frozen destination lies elsewhere.
    _require_outside_repository(source, "reviewed source")
    # The reviewed original may contain private source text and unpublished
    # analysis. It must not be accessible to other local users before the
    # first manuscript read. Snapshot's descriptor read separately checks
    # owner, link count and in-flight changes.
    source_metadata = Path(source).lstat()
    if (not stat.S_ISREG(source_metadata.st_mode) or
            source_metadata.st_uid != os.getuid() or
            source_metadata.st_nlink != 1 or
            stat.S_IMODE(source_metadata.st_mode) & 0o077):
        raise FictionalCustodyHold(
            "reviewed original must be caller-owned and privately readable"
        )
    _require_outside_repository(journal.path, "journal")
    # Validate all three custody locations BEFORE the preliminary source
    # inspector. A checkout-local path through a symlinked ancestor must not
    # become an implicit exception to the private-storage policy.
    _require_outside_repository(private_dir, "snapshot destination")
    reviewed_sha256 = _pinned_digest(reviewed_sha256, "reviewed attachment")
    source_use_sha256 = _pinned_digest(source_use_sha256, "source-use receipt")
    fictional_owner_approval_sha256 = _pinned_digest(
        fictional_owner_approval_sha256, "fictional owner approval reference"
    )
    # Hard isolation: no real destination identity, even as a guessable hash.
    if (not isinstance(recipient, str) or not recipient.endswith("@example.invalid")
            or recipient != recipient.strip().lower()):
        raise FictionalCustodyHold("rehearsal recipient must be a fixture @example.invalid")
    key = intent_id(week, reviewed_sha256, recipient)

    # Fail-early syntactic checks only. This preliminary mutable-file read is
    # NOT the reviewed artifact; freeze/independent verification follow below.
    require_owner_review(
        week_ending=week, sending=True, approved_week=approved_week,
    )
    first, _ = inspect_file(Path(source), week_ending=week)
    require_exact_reviewed_manuscript(
        week_ending=week, sending=True, manuscript_bytes=first,
        approved_sha256=reviewed_sha256,
    )
    if source_use_fingerprint(first) != source_use_sha256:
        raise FictionalCustodyHold("original source-use receipt digest mismatches review")
    # Even a matching SHA already in a journal cannot be re-authorized merely
    # by using a new snapshot filename. Unknown is the only pre-admission case.
    try:
        current = journal.state(key)
    except DeliveryHold as exc:
        if str(exc) != "unknown intent":
            raise
    else:
        raise FictionalCustodyHold(
            "journal already holds an intent in state {}; no automatic reuse".format(current)
        )

    frozen = freeze_exact_reviewed_attachment(
        Path(source), Path(private_dir),
        expected_sha256=reviewed_sha256, week_ending=week,
    )
    # Independently reopen the frozen immutable-by-policy snapshot and verify
    # what C1 will later bind, not the mutable downloaded source file.
    raw, info = inspect_file(frozen["path"], week_ending=week)
    if (info["sha256"] != reviewed_sha256 or len(raw) != frozen["bytes"] or
            source_use_fingerprint(raw) != source_use_sha256):
        raise FictionalCustodyHold("frozen packet changed before journal binding")
    path = frozen["path"]
    metadata = path.stat()
    if (not stat.S_ISREG(metadata.st_mode) or
            stat.S_IMODE(metadata.st_mode) != 0o400 or
            metadata.st_nlink != 1):
        raise FictionalCustodyHold("snapshot no longer a private read-only single-link file")
    identity = journal.register(
        week=week, manuscript_sha256=reviewed_sha256,
        source_receipt_sha256=source_use_sha256, recipient=recipient,
        owner_approval_sha256=fictional_owner_approval_sha256,
    )
    if identity != key or journal.state(identity) != "registered":
        raise FictionalCustodyHold("journal registration did not stay pre-send")
    return {
        "status": "FICTIONAL_REGISTERED_NO_SEND",
        "week": week,
        "sha256": reviewed_sha256,
        "source_use_sha256": source_use_sha256,
        "journal_identity": identity,
        "bytes": len(raw),
        "frozen_private_path": path,  # Private: caller must never log this value.
        "owner_authenticated": False,
        "source_rights_verified": False,
        "smtp_attempted": False,
        "sender_enabled": False,
    }
