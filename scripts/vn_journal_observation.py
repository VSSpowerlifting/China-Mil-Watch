"""Build a metadata-only journal listing snapshot from *supplied* parser results.

This module performs no HTTP or file I/O and does not authorize retrieval,
retention, publication, or a future automatic collection schedule. Caller must
supply genuine independently authorized listing results and measured metadata.
"""
from __future__ import annotations

from scripts.vn_journal_window_drift import (
    CATEGORIES,
    SCHEMA,
    SOURCE,
    ObservationRefused,
    validate_observation,
)


def make_observation(observations, *, response_sha256_by_category, observed_at, observation_id):
    """Construct a validated evidence packet without source bodies or titles.

    Input observations must be the four `ListingObservation` values returned by
    `vn_journal_listing.parse_category_html`. Only canonical URL, ID, and
    provisional date hint are transferred. Response hashes are supplied by the
    caller, not synthesized. The timestamp is a caller-provided UTC instant;
    this module never reads the wall clock.
    """
    if not isinstance(observations, (tuple, list)) or len(observations) != len(CATEGORIES):
        raise ObservationRefused("exactly four listing observations required")
    if not isinstance(response_sha256_by_category, dict) or set(response_sha256_by_category) != set(CATEGORIES):
        raise ObservationRefused("exactly four response digests required")

    sections = []
    seen = set()
    for observation in observations:
        category = getattr(observation, "category_page", None)
        if category not in CATEGORIES or category in seen:
            raise ObservationRefused("unexpected or duplicate listing category")
        seen.add(category)
        candidates = getattr(observation, "candidates", None)
        if not isinstance(candidates, (list, tuple)):
            raise ObservationRefused("invalid parser observation candidates")
        if (getattr(observation, "completeness_proven", None) is not False
                or getattr(observation, "pagination_verified", None) is not False):
            raise ObservationRefused("parser may not assert pagination or completeness")
        entries = []
        for candidate in candidates:
            if getattr(candidate, "category_page", None) != category:
                raise ObservationRefused("parser candidate provenance category disagrees")
            if getattr(candidate, "article_date_verified", None) is not False:
                raise ObservationRefused("a listing hint cannot be article-verified")
            entries.append({
                "source_identity": getattr(candidate, "source_identity", None),
                "canonical_url": getattr(candidate, "canonical_url", None),
                "date_hint": getattr(candidate, "date_hint", None),
            })
        sections.append({
            "category": category,
            "listing_url": CATEGORIES[category],
            "response_sha256": response_sha256_by_category[category],
            "candidates": entries,
        })

    payload = {
        "schema": SCHEMA,
        "source_slug": SOURCE,
        "observed_at": observed_at,
        "observation_id": observation_id,
        "sections": sorted(sections, key=lambda v: list(CATEGORIES).index(v["category"])),
        "source_html_retained": False,
        "article_text_retained": False,
        "pagination_proven": False,
        "historical_completeness_proven": False,
    }
    validate_observation(payload)
    return payload
