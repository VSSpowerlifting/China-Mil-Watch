"""Build a bounded metadata-only journal observation from source page bytes.

The caller supplies four already-acquired, separately authorized English
category response bodies and each body's measured UTC capture time. No HTTP,
file writes, publisher text retention, or source activation happens here.
Digesting each body alongside parsing prevents accidental hash/page mismatch.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta

from scraper.sources.vn_journal_listing import (
    CATEGORY_URLS, MAX_BYTES, parse_category_html,
)
from scripts.vn_journal_observation import make_observation
from scripts.vn_journal_window_drift import (
    CATEGORIES, ObservationRefused, _stamp,
)

MAX_SNAPSHOT_SPAN_SECONDS = 30 * 60


def make_observation_from_bytes(
    body_by_category,
    *,
    captured_at_by_category,
    observation_id,
):
    """Return an ordinary v1 observation containing metadata, never HTML.

    Caller independently determines lawful access and bibliographic-use
    scope. Values are immutable bytes of the exact *supplied HTTP entity
    bodies*, not proof of unaltered network wire bytes. The snapshot's single
    observed_at is the LAST category capture time; it does not claim all
    pages were observed simultaneously.
    """
    if set(CATEGORIES) != set(CATEGORY_URLS):
        raise ObservationRefused("listing and snapshot category registries differ")
    if any(CATEGORIES[key] != CATEGORY_URLS[key] for key in CATEGORIES):
        raise ObservationRefused("listing URLs and snapshot contract have drifted")
    if not isinstance(body_by_category, dict) or set(body_by_category) != set(CATEGORIES):
        raise ObservationRefused("exactly four category page bodies required")
    if (not isinstance(captured_at_by_category, dict)
            or set(captured_at_by_category) != set(CATEGORIES)):
        raise ObservationRefused("one measured UTC capture time per category required")

    instants = []
    for category in CATEGORIES:
        instant = _stamp(captured_at_by_category[category])
        instants.append(instant)
    earliest, latest = min(instants), max(instants)
    if latest - earliest > timedelta(seconds=MAX_SNAPSHOT_SPAN_SECONDS):
        raise ObservationRefused("category captures are not one bounded observation window")

    parsed = []
    response_digests = {}
    for category in CATEGORIES:
        raw = body_by_category[category]
        if not isinstance(raw, bytes):
            raise ObservationRefused("page content must be immutable raw bytes")
        if not 0 < len(raw) <= MAX_BYTES:
            raise ObservationRefused("page content outside byte budget")
        if b"\x00" in raw:
            raise ObservationRefused("page content contains NUL bytes")
        try:
            html = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ObservationRefused("page content is not strict UTF-8") from exc
        response_digests[category] = hashlib.sha256(raw).hexdigest()
        # Exact declared category URL and merged offline parser.
        parsed.append(parse_category_html(html, CATEGORY_URLS[category]))
        del html
    if len(set(response_digests.values())) != len(CATEGORIES):
        raise ObservationRefused("identical responses from different category URLs")

    return make_observation(
        parsed,
        response_sha256_by_category=response_digests,
        observed_at=latest.strftime("%Y-%m-%dT%H:%M:%SZ"),
        observation_id=observation_id,
    )
