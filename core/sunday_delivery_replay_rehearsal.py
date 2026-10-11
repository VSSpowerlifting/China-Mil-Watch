"""Offline contract rehearsal: exact reviewed Sunday TXT -> fictional send journal.

NO network or SMTP imports, no model, no CLI, no workflow wiring. This module
must not be used as live approval, source-rights clearance, or email delivery.
It consumes the existing October 10 pilot's exact-byte checks and a private
*fictional* DeliveryJournal from the parent PR #377.

Unlike an SMTP adapter, the scenario is selected from fixed internal outcomes.
No transport callback or arbitrary executable code can be supplied.
"""
from __future__ import annotations

import hashlib

from core.sunday_delivery_journal import DeliveryHold, DeliveryJournal
from scripts.sunday_first_pilot_reviewed_replay import inspect_file
from scripts.sunday_pilot_owner_review import (
    require_owner_review, require_exact_reviewed_manuscript,
)

BEGIN = b"=== MANUSCRIPT SOURCE USE \xe2\x80\x94 EDITORIAL TRIAGE ONLY ==="
END = b"END OF MANUSCRIPT SOURCE USE"
APPENDIX = b"=== SOURCE APPENDIX \xe2\x80\x94 DO NOT EDIT ==="
SOURCE_END = b"END OF SOURCE APPENDIX"
SCENARIOS = frozenset((
    "preflight_only", "hold_before_contact", "crash_after_reservation",
    "mock_timeout", "mock_acceptance", "mock_acceptance_lost_ack",
))


class FictionalReplayRefused(ValueError):
    """Offline rehearsal cannot establish exact identity or safe state."""


class FictionalCrash(RuntimeError):
    """Simulates loss of process after durable reservation; never retry."""


def source_use_fingerprint(original):
    """Fingerprint only the exact contiguous private source-use receipt bytes.

    The manuscript's own receipt remains an unverified model attribution, NOT
    proof of factual support, rights, independent source reading, or consent.
    """
    if not isinstance(original, bytes):
        raise FictionalReplayRefused("immutable UTF-8 attachment bytes required")
    if any(original.count(x) != 1 for x in (BEGIN, END, APPENDIX, SOURCE_END)):
        raise FictionalReplayRefused("source-use markers missing or duplicated")
    a, b = original.index(APPENDIX), original.index(BEGIN)
    c, d = original.index(END), original.index(SOURCE_END)
    if not (a < b < c < d):
        raise FictionalReplayRefused("source-use receipt outside the original appendix")
    return hashlib.sha256(original[b:c + len(END)]).hexdigest()


def rehearse_reviewed_delivery(
        file_path, journal, *, week, approved_week, reviewed_sha256,
        source_use_sha256, recipient, owner_approval_sha256,
        scenario="preflight_only"):
    """Dry-run-only: validate exact file, journal synthetic intent, inject fault.

    The caller-supplied approval digest is ONLY an input identity claim:
    authentication of the owner and genuine source permissions are out of scope.
    Even a mock "accepted" result is fictional and can never prove a real SMTP
    acceptance. There is deliberately no send method or callback.
    """
    if scenario not in SCENARIOS:
        raise FictionalReplayRefused("unsupported fictional delivery scenario")
    if not isinstance(journal, DeliveryJournal):
        raise FictionalReplayRefused("explicit fictional DeliveryJournal required")
    original, info = inspect_file(file_path, week_ending=week)
    require_owner_review(
        week_ending=week, sending=True, approved_week=approved_week,
    )
    require_exact_reviewed_manuscript(
        week_ending=week, sending=True, manuscript_bytes=original,
        approved_sha256=reviewed_sha256,
    )
    fingerprint = source_use_fingerprint(original)
    if not isinstance(source_use_sha256, str) or fingerprint != source_use_sha256:
        raise FictionalReplayRefused("exact source-use receipt digest mismatch")
    # No cached bytes or second LLM draft: re-read original path only through
    # the existing private pilot inspector; never write to manuscript.
    report = {
        "scenario": scenario, "week": week, "manuscript_sha256": info["sha256"],
        "source_use_sha256": fingerprint, "bytes": info["bytes"],
    }
    if scenario == "preflight_only":
        return dict(report, state="preflight_only", reserved=False)

    # This registers a fictional, externally asserted approval identity. It
    # cannot fabricate a genuine editor decision or source permission.
    identity = journal.register(
        week=week, manuscript_sha256=info["sha256"],
        source_receipt_sha256=fingerprint, recipient=recipient,
        owner_approval_sha256=owner_approval_sha256,
    )
    if scenario == "hold_before_contact":
        journal.hold_before_send(identity)
        return dict(report, state="held", reserved=False)

    journal.reserve_attempt(identity)  # Committed before any fake transport.
    if scenario == "crash_after_reservation":
        raise FictionalCrash("fictional process died after reservation; manual hold")
    if scenario in ("mock_timeout", "mock_acceptance_lost_ack"):
        journal.mark_unknown(identity)
        return dict(report, state="outcome_unknown", reserved=True)
    if scenario == "mock_acceptance":
        # This fake digest represents NO actual external server acknowledgment.
        fake = hashlib.sha256(
            b"FICTIONAL-NOT-SMTP\x00" + identity.encode("ascii")
        ).hexdigest()
        journal.record_smtp_acceptance(identity, fake)
        return dict(report, state="smtp_accepted_mock_only", reserved=True)
    raise AssertionError("unreachable fictional scenario")
