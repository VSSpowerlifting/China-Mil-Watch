"""Owner-specific first-Sunday editorial delivery gate (not publication approval).

The first 2026-10-10 edition must be privately reviewed by the owner before
any direct-to-editor SMTP or scheduled Sunday send. This explicit GitHub Actions
variable is a human attestation, not cryptographic proof of preview or source
verification. It cannot substitute for the separate source/publication reviews.
"""
from __future__ import annotations

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
