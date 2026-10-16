"""Offline fictional Sunday release-receipt verifier. No genuine authority.

This module deliberately accepts *only* reserved test identities and a single
historic pilot date. It neither grants real owner permission nor sends email,
requests models, touches files, or fetches rights records. Verification keys are
injected by tests; never embed or load a real signing key into this module.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

SCHEMA = "ipr-sunday-fictional-editor-release/1"
PILOT_WEEK = "2026-10-10"
PURPOSE = "language_review_only"
DOMAIN = b"IPR-SUNDAY-FICTIONAL-RELEASE-v1\x00"
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
ID = re.compile(r"fictional-[a-z][a-z0-9-]{3,60}\Z")
ADDRESS = re.compile(r"[a-z][a-z0-9._+-]{0,60}@example[.]invalid\Z")
CLAIM_FIELDS = frozenset({
    "schema", "decision_id", "signer_id", "reporting_week",
    "manuscript_sha256", "source_use_sha256", "byte_length", "recipient",
    "purpose", "source_review_id", "rights_decision_id", "approved_at",
    "expires_at",
})


class FictionalApprovalHold(ValueError):
    """A claim failed: hold without release or retry."""


@dataclass(frozen=True)
class FictionalRelease:
    """Metadata only. No owner identity, publication rights or send authority."""
    week: str
    manuscript_sha256: str
    source_use_sha256: str
    recipient: str
    decision_id: str
    purpose: str = PURPOSE
    authenticated_owner: bool = False
    rights_verified: bool = False
    mail_authorized: bool = False


def _digest(value):
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


def _timestamp(value):
    """Only canonical whole-second UTC timestamps, preventing clock ambiguity."""
    if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise FictionalApprovalHold("noncanonical UTC receipt timestamp")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError as exc:
        raise FictionalApprovalHold("invalid UTC receipt timestamp") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise FictionalApprovalHold("noncanonical UTC receipt timestamp")
    return parsed


def canonical_fixture_claims(claims):
    """Return deterministic bytes; only restricted synthetic claims accepted."""
    if not isinstance(claims, dict) or frozenset(claims) != CLAIM_FIELDS:
        raise FictionalApprovalHold("exact fictional receipt claim keys required")
    if (claims["schema"] != SCHEMA or claims["reporting_week"] != PILOT_WEEK
            or claims["purpose"] != PURPOSE):
        raise FictionalApprovalHold("unknown schema, week or release purpose")
    if (claims["signer_id"] != "fictional-owner@example.invalid" or
            not isinstance(claims["recipient"], str) or
            not ADDRESS.fullmatch(claims["recipient"]) or
            ".." in claims["recipient"] or ".@" in claims["recipient"] or
            claims["recipient"] == claims["signer_id"]):
        raise FictionalApprovalHold("only distinct synthetic fixture identities")
    for key in ("decision_id", "source_review_id", "rights_decision_id"):
        if not isinstance(claims[key], str) or not ID.fullmatch(claims[key]):
            raise FictionalApprovalHold("independently labeled fictional decision missing")
    if (not _digest(claims["manuscript_sha256"]) or
            not _digest(claims["source_use_sha256"])):
        raise FictionalApprovalHold("exact manuscript and source-use hashes required")
    if type(claims["byte_length"]) is not int or not 0 < claims["byte_length"] <= 2_000_000:
        raise FictionalApprovalHold("bounded exact byte length required")
    approved = _timestamp(claims["approved_at"])
    expiry = _timestamp(claims["expires_at"])
    if expiry <= approved or expiry - approved > timedelta(hours=72):
        raise FictionalApprovalHold("nonpositive or excessive approval lifetime")
    return json.dumps(claims, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def verify_fictional_editor_release(
        manuscript_bytes, source_use_sha256, signed_receipt, *,
        verifier_key, now_utc, revoked_decision_ids):
    """Verify synthetic HMAC binding. This intentionally CANNOT grant real mail.

    The supplied source-use hash and revocation set must be pinned by an
    independent reviewing authority in real implementations. This test helper
    cannot attest sources, signer custody, or revocation completeness.
    """
    if (not isinstance(manuscript_bytes, bytes) or
            not 0 < len(manuscript_bytes) <= 2_000_000 or
            not _digest(source_use_sha256)):
        raise FictionalApprovalHold("bounded byte-exact artifact inputs required")
    if (not isinstance(verifier_key, bytes) or len(verifier_key) < 32 or
            not isinstance(now_utc, datetime) or now_utc.tzinfo is None or
            not isinstance(revoked_decision_ids, frozenset)):
        raise FictionalApprovalHold("explicit private verifier, UTC time and revocation fixture required")
    if (not isinstance(signed_receipt, dict) or
            frozenset(signed_receipt) != frozenset(("claims", "mac_sha256")) or
            not _digest(signed_receipt["mac_sha256"])):
        raise FictionalApprovalHold("canonical fictional signed receipt required")
    claims = signed_receipt["claims"]
    canonical = canonical_fixture_claims(claims)
    signature = hmac.new(verifier_key, DOMAIN + canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, signed_receipt["mac_sha256"]):
        raise FictionalApprovalHold("fictional verifier authentication failed")
    if (claims["manuscript_sha256"] != hashlib.sha256(manuscript_bytes).hexdigest()
            or claims["source_use_sha256"] != source_use_sha256
            or claims["byte_length"] != len(manuscript_bytes)):
        raise FictionalApprovalHold("reviewed bytes/source receipt differ from release")
    checked_at = now_utc.astimezone(timezone.utc)
    if not _timestamp(claims["approved_at"]) <= checked_at < _timestamp(claims["expires_at"]):
        raise FictionalApprovalHold("fictional receipt premature or expired")
    if claims["decision_id"] in revoked_decision_ids:
        raise FictionalApprovalHold("fictional approval revoked")
    return FictionalRelease(
        week=claims["reporting_week"],
        manuscript_sha256=claims["manuscript_sha256"],
        source_use_sha256=claims["source_use_sha256"],
        recipient=claims["recipient"],
        decision_id=claims["decision_id"],
    )
