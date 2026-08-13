"""
Structured collection outcomes.

The rule this module exists to enforce (DECISION_LOG 2026-08-09 §6): *when a
stage can return empty for both a normal and a defective reason, it must record
which.* An empty list is not an answer. Every source, every run, produces one of
these values, and each value declares for itself whether it is a success.

Two distinctions carry the weight:

  * `OK_NO_PUBLICATIONS` vs everything below it. A source that published nothing
    today is healthy. A source that could not be reached returned the same empty
    list and is not.
  * `is_failure` vs `is_empty`. A failure degrades the aggregate run. Emptiness
    does not — but sustained emptiness past a source's expected cadence is what
    the health report escalates, separately.
"""

from __future__ import annotations

from typing import FrozenSet

# ── Success outcomes ──────────────────────────────────────────────────────────

OK = "ok"
"""Discovered, fetched and extracted at least one document."""

OK_NO_PUBLICATIONS = "ok_no_publications"
"""Listing reached successfully and it carried nothing new for the window.
This is a HEALTHY result. It is the value that must never again be confused
with a listing failure."""

OK_ALL_DUPLICATES = "ok_all_duplicates"
"""Everything discovered was already stored. Healthy: the source is reachable
and publishing, we simply have it all."""

OK_ALL_FILTERED = "ok_all_filtered"
"""Everything discovered was rejected by the keyword/relevance gate. Healthy
collection, zero editorial yield — a distinction that matters when judging
whether a source earns its place."""

# ── Non-failure, non-collecting ───────────────────────────────────────────────

SKIPPED_DISABLED = "skipped_disabled"
"""Source is configured but `enabled` is false. Not collected, not a failure."""

NOT_IMPLEMENTED = "not_implemented"
"""A documented stub with no working adapter (Xinhua Military today). Reported
explicitly so a configured-but-inert source is visible in every run instead of
silently contributing nothing while the run reports success."""

# ── Failure outcomes ──────────────────────────────────────────────────────────

LISTING_FAILURE = "listing_failure"
"""Could not retrieve or parse the listing page(s). The empty result is a
defect, not silence."""

AUTH_FAILURE = "auth_failure"
"""Authentication, authorization, or access refused (401/403, login wall)."""

TIMEOUT = "timeout"
"""Request exceeded the configured timeout."""

DISALLOWED_REDIRECT = "disallowed_redirect"
"""Redirected outside the source's allowed domains."""

UNEXPECTED_CONTENT_TYPE = "unexpected_content_type"
"""Response was not the declared/expected type (e.g. HTML expected, PDF served)."""

OVERSIZED_RESPONSE = "oversized_response"
"""Response exceeded the configured size ceiling and was refused unread."""

FETCH_FAILURE = "fetch_failure"
"""Listing succeeded but article fetches exhausted their retries."""

EXTRACTION_FAILURE = "extraction_failure"
"""Fetched successfully but the parser produced nothing usable — the signature
of source-side CSS/markup drift."""

ANALYSIS_FAILURE = "analysis_failure"
"""Collection succeeded; downstream analysis failed for this source's documents."""

ADAPTER_ERROR = "adapter_error"
"""The adapter raised an unexpected exception. Deliberately distinct from the
specific failures above so an unclassified crash is never silently absorbed."""

UNKNOWN_SOURCE = "unknown_source"
"""A slug was requested that no desk manifest declares."""


ALL_STATUSES: FrozenSet[str] = frozenset({
    OK, OK_NO_PUBLICATIONS, OK_ALL_DUPLICATES, OK_ALL_FILTERED,
    SKIPPED_DISABLED, NOT_IMPLEMENTED,
    LISTING_FAILURE, AUTH_FAILURE, TIMEOUT, DISALLOWED_REDIRECT,
    UNEXPECTED_CONTENT_TYPE, OVERSIZED_RESPONSE, FETCH_FAILURE,
    EXTRACTION_FAILURE, ANALYSIS_FAILURE, ADAPTER_ERROR, UNKNOWN_SOURCE,
})

SUCCESS_STATUSES: FrozenSet[str] = frozenset({
    OK, OK_NO_PUBLICATIONS, OK_ALL_DUPLICATES, OK_ALL_FILTERED,
})

#: Outcomes that degrade the aggregate run.
#: NOT_IMPLEMENTED and SKIPPED_DISABLED are excluded on purpose: both are
#: deliberate, acknowledged configuration states. Treating them as failures
#: would make every run degraded for as long as Xinhua stays a stub, and an
#: alarm that is always on is not an alarm.
FAILURE_STATUSES: FrozenSet[str] = frozenset({
    LISTING_FAILURE, AUTH_FAILURE, TIMEOUT, DISALLOWED_REDIRECT,
    UNEXPECTED_CONTENT_TYPE, OVERSIZED_RESPONSE, FETCH_FAILURE,
    EXTRACTION_FAILURE, ANALYSIS_FAILURE, ADAPTER_ERROR, UNKNOWN_SOURCE,
})

#: Outcomes where the source yielded no new stored document. Used by the health
#: report to reason about silence against expected cadence — never to decide
#: whether the run failed.
EMPTY_STATUSES: FrozenSet[str] = frozenset({
    OK_NO_PUBLICATIONS, OK_ALL_DUPLICATES, OK_ALL_FILTERED,
    SKIPPED_DISABLED, NOT_IMPLEMENTED,
}) | FAILURE_STATUSES


def is_failure(status: str) -> bool:
    """True when this outcome should degrade the aggregate run."""
    return status in FAILURE_STATUSES


def is_success(status: str) -> bool:
    """True when collection worked, regardless of whether it yielded anything."""
    return status in SUCCESS_STATUSES


def validate(status: str) -> str:
    """Reject an unknown status rather than storing it and hoping."""
    if status not in ALL_STATUSES:
        raise ValueError(
            "unknown collection status %r (permitted: %s)"
            % (status, ", ".join(sorted(ALL_STATUSES)))
        )
    return status
