"""Guard Sunday's IPR Briefs editorial handoff and late-week source freshness.

Independent of SMTP/model/source access. The tracked daily-success marker is
required for same-Sunday generation to avoid drafting from yesterday's corpus.
Manual historical replays require a separate affirmative send override.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from scripts.sunday_pilot_owner_review import (
    OwnerReviewRequired, require_approved_digest_format, require_owner_review,
)

NY = ZoneInfo("America/New_York")


class SundayHandoffRefused(ValueError):
    """Unsafe edition, conflicting Friday service, or stale daily source data."""


def _date(value: str) -> date:
    try:
        result = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise SundayHandoffRefused(
            "reporting_saturday must be a valid YYYY-MM-DD date"
        ) from exc
    if result.isoformat() != value or result.weekday() != 5:
        raise SundayHandoffRefused(
            "reporting_saturday must be a Saturday in YYYY-MM-DD format"
        )
    return result


def resolve_sunday_handoff(*, event: str, now: datetime = None,
                           reporting_saturday: str = "",
                           send_email: bool = False,
                           allow_historical_send: bool = False,
                           sunday_daily_marker: str = "",
                           friday_delivery_enabled: bool = False,
                           pilot_owner_reviewed_week: str = "",
                           pilot_owner_reviewed_sha256: str = "") -> dict:
    """Resolve Saturday reporting dates, and refuse stale Sunday generation.

    A current Sunday requires the daily pipeline's *success marker* for that
    same Sunday even for a no-send rehearsal. A previous Saturday may be
    previewed later without it, but sending an older issue requires explicit
    override and preserves an unapproved-status packet.

    The Friday service must be OFF for *any* Sunday email. Mere dry-runs do
    not require turning off the proven Friday workflow.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise SundayHandoffRefused("runner clock must have a timezone")
    today = now.astimezone(NY).date()

    if event == "schedule":
        if today.weekday() != 6:
            raise SundayHandoffRefused(
                "scheduled Sunday run started outside New York-local Sunday"
            )
        if reporting_saturday or allow_historical_send:
            raise SundayHandoffRefused("scheduled runs cannot select historical weeks")
        target = today - timedelta(days=1)
        sending = True
        if not send_email:
            raise SundayHandoffRefused("scheduled Sunday delivery flag is not enabled")
    elif event == "workflow_dispatch":
        latest_saturday = today - timedelta(days=(today.weekday() - 5) % 7)
        target = _date(reporting_saturday) if reporting_saturday else latest_saturday
        if target > today:
            raise SundayHandoffRefused("future Saturday evidence is unavailable")
        if target == today:
            raise SundayHandoffRefused(
                "reporting Saturday has not ended in New York; wait until Sunday"
            )
        if target < latest_saturday - timedelta(days=91):
            raise SundayHandoffRefused("historical editions older than 91 days require separate review")
        sending = send_email
        if sending and target != today - timedelta(days=1) and not allow_historical_send:
            raise SundayHandoffRefused(
                "manual email for an earlier reporting Saturday requires "
                "allow_historical_send=true"
            )
        if sending and today.weekday() != 6 and not allow_historical_send:
            raise SundayHandoffRefused(
                "manual Sunday editorial email outside Sunday requires "
                "allow_historical_send=true"
            )
    else:
        raise SundayHandoffRefused("unsupported GitHub Actions event")

    if sending and friday_delivery_enabled:
        raise SundayHandoffRefused(
            "refused parallel services: disable IPR_EDITOR_DELIVERY_ENABLED "
            "before emailing from the Sunday workflow"
        )
    # Pilot-only, edition-specific owner's consent before generating a
    # scheduled or manually requested draft intended for Dylan. The private
    # no-send preview is always exempt, and later weeks are unchanged.
    try:
        require_owner_review(
            week_ending=target.isoformat(), sending=sending,
            approved_week=pilot_owner_reviewed_week,
        )
        require_approved_digest_format(
            week_ending=target.isoformat(), sending=sending,
            approved_sha256=pilot_owner_reviewed_sha256,
        )
    except OwnerReviewRequired as exc:
        raise SundayHandoffRefused(str(exc)) from exc
    if today.weekday() == 6 and target == today - timedelta(days=1):
        if sunday_daily_marker.strip() != today.isoformat():
            raise SundayHandoffRefused(
                "Sunday production update has not recorded a success marker "
                "for New York-local " + today.isoformat() +
                "; no draft or email attempted"
            )

    start = target - timedelta(days=6)
    return {
        "IPR_SUNDAY_WEEK_START": start.isoformat(),
        "IPR_SUNDAY_AS_OF": target.isoformat(),
        "IPR_SUNDAY_WEEK_END": target.isoformat(),
        "IPR_SUNDAY_SHOULD_SEND": "true" if sending else "false",
    }
