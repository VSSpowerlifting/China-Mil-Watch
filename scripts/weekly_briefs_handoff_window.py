"""Choose a bounded Friday source window for IPR Briefs editorial handoffs.

Pure, stdlib-only resolver: no database access, API requests, SMTP, file writes,
approval, or publishing. Dates always follow America/New_York rather than UTC.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


class ReportingWindowRefused(ValueError):
    """The intended handoff week or dispatch permission is unsafe."""


LOCAL_TZ = ZoneInfo("America/New_York")


def _parse_friday(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ReportingWindowRefused(
            "reporting_friday must be a valid YYYY-MM-DD date"
        ) from exc
    if parsed.isoformat() != value or parsed.weekday() != 4:
        raise ReportingWindowRefused(
            "reporting_friday must identify a Friday in YYYY-MM-DD format"
        )
    return parsed


def resolve_handoff_window(*, event: str, now: datetime = None,
                           reporting_friday: str = "",
                           sending_email: bool = False,
                           allow_historical_send: bool = False) -> dict:
    """Return Sunday-Friday evidence boundaries and Saturday edition identity.

    Scheduled event: only the CURRENT New York-local Friday is safe; delayed
    execution on Saturday/Monday must NOT silently fall back a full week.

    Manual event: preview defaults to the most recently reached Friday,
    with optional explicitly named Friday. A manual SEND for a prior Friday
    requires an additional affirmative historical replay switch. This guards
    against accidentally emailing last week's packet as though current.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ReportingWindowRefused("current time must include a timezone")
    local = now.astimezone(LOCAL_TZ)
    today = local.date()

    if event == "schedule":
        if reporting_friday or allow_historical_send:
            raise ReportingWindowRefused(
                "scheduled dispatch cannot override its reporting date"
            )
        if today.weekday() != 4:
            raise ReportingWindowRefused(
                "scheduled Friday editorial dispatch began outside local Friday; "
                "refusing to silently send an older packet"
            )
        friday = today
    elif event == "workflow_dispatch":
        latest_friday = today - timedelta(days=(today.weekday() - 4) % 7)
        friday = (_parse_friday(reporting_friday)
                  if reporting_friday else latest_friday)
        if friday > today:
            raise ReportingWindowRefused("future Friday evidence is unavailable")
        if friday < latest_friday - timedelta(days=91):
            raise ReportingWindowRefused(
                "historical Friday beyond 91 days requires separate editorial review"
            )
        if sending_email and friday != today and not allow_historical_send:
            raise ReportingWindowRefused(
                "manual email would deliver an earlier Friday's packet; "
                "check allow_historical_send to authorize this historical replay"
            )
    else:
        raise ReportingWindowRefused("unsupported GitHub Actions event")

    return {
        "IPR_EDITOR_WEEK_START": (friday - timedelta(days=5)).isoformat(),
        "IPR_EDITOR_AS_OF": friday.isoformat(),
        "IPR_EDITOR_WEEK_END": (friday + timedelta(days=1)).isoformat(),
    }
