"""Owner-specific first-Sunday editorial delivery gate (not publication approval).

The first 2026-10-10 edition must be privately reviewed by the owner before
any direct-to-editor SMTP or scheduled Sunday send. This explicit GitHub Actions
variable is a human attestation, not cryptographic proof of preview or source
verification. It cannot substitute for the separate source/publication reviews.
"""
from __future__ import annotations

import hashlib
import re

PILOT_SATURDAY = "2026-10-10"
OWNER_WEEK_VARIABLE = "IPR_SUNDAY_OWNER_REVIEWED_WEEK"


class OwnerReviewRequired(ValueError):
    """Owner has not affirmatively cleared this pilot for editor delivery."""


def require_owner_review(*, week_ending, sending, approved_week):
    """Reject October 10 editor send without exact-week manual acknowledgement.

    Owner-only previews and no-send rehearsals are always unaffected.
    Later weeks retain the existing schedule and editorial protections.
    Do not use a general truthy boolean: authorization is edition-specific.
    """
    if type(sending) is not bool:
        raise OwnerReviewRequired("editor send state must be an explicit boolean")
    if not sending or week_ending != PILOT_SATURDAY:
        return False
    if approved_week != PILOT_SATURDAY:
        raise OwnerReviewRequired(
            "Refused: first Sunday draft to Dylan requires the explicit "
            + OWNER_WEEK_VARIABLE + "=" + PILOT_SATURDAY
            + " after private owner preview and source review; "
            "no model or editor email is authorized"
        )
    return True

SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def require_exact_reviewed_manuscript(*, week_ending, sending, manuscript_bytes,
                                      approved_sha256):
    """Make pilot editor release specific to the ACTUAL reviewed attachment.

    A calendar-week GitHub variable cannot approve a freshly regenerated
    manuscript from a separate model call. Exact bytes (including all cited
    source receipts) must match the owner's manually confirmed SHA-256.
    """
    if type(sending) is not bool:
        raise OwnerReviewRequired("editor send state must be an explicit boolean")
    if not sending or week_ending != PILOT_SATURDAY:
        return False
    if not isinstance(manuscript_bytes, bytes):
        raise OwnerReviewRequired("original reviewed manuscript bytes required")
    if not isinstance(approved_sha256, str) or not SHA256.fullmatch(approved_sha256):
        raise OwnerReviewRequired(
            "Oct10 Dylan delivery requires exact reviewed manuscript "
            "SHA-256 in IPR_SUNDAY_OWNER_REVIEWED_SHA256"
        )
    actual = hashlib.sha256(manuscript_bytes).hexdigest()
    if actual != approved_sha256:
        raise OwnerReviewRequired(
            "Oct10 generated manuscript differs from owner's reviewed "
            "attachment; no delivery. Re-review the precise file bytes."
        )
    return True
