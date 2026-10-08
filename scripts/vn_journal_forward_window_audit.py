"""Audit metadata-only Vietnam journal listing windows without qualifying collection.

Built on the governed ipr-vndj-listing-observation/1 contract (#161).
This tool uses only user-supplied, already-authorized observation JSON. It
never fetches the publisher, stores article prose, reads state, or establishes
completeness, publication dates, permission, or a collection reliability clock.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import timedelta, date
from pathlib import Path

from scripts.vn_journal_window_drift import (
    CATEGORIES, ObservationRefused, compare_observations, validate_observation,
)

MAX_SNAPSHOTS = 90
SUSPECT_SAME_DAY_COUNT = 3


def _candidate_hints(observation):
    """Union date hints; recommendation/sidebar links may recur across pages."""
    hints = {}
    for section in observation["sections"]:
        for candidate in section["candidates"]:
            ident = candidate["source_identity"]
            hint = candidate["date_hint"]
            if ident not in hints or (hints[ident] is None and hint is not None):
                hints[ident] = hint
            elif hint is not None and hints[ident] != hint:
                # validate_observation already guards this; defend locally too.
                raise ObservationRefused("one observation has inconsistent date hints")
    return hints


def _observation_audit(observation, instant, indexed):
    local_day = (instant + timedelta(hours=7)).date().isoformat()
    merged_hints = _candidate_hints(observation)
    future = sorted(
        ident for ident, hint in merged_hints.items()
        if hint is not None and hint > local_day
    )
    categories = {}
    clock_clusters = []
    for section in observation["sections"]:
        ids = indexed[section["category"]]
        hint_groups = {}
        for candidate in section["candidates"]:
            hint = candidate["date_hint"]
            if hint is not None:
                hint_groups.setdefault(hint, []).append(candidate["source_identity"])
        suspicious_ids = sorted(hint_groups.get(local_day, []))
        if len(suspicious_ids) >= SUSPECT_SAME_DAY_COUNT:
            # A cluster is a manual-review cue, not proof of clock leakage:
            # legitimate same-day publication can create the same pattern.
            clock_clusters.append({
                "listing_page": section["category"],
                "hint_day": local_day,
                "ids_to_review": suspicious_ids,
                "suspected_clock_contamination_proven": False,
            })
        categories[section["category"]] = {
            "visible_ids": len(ids),
            "dated_hint_links": sum(len(values) for values in hint_groups.values()),
            "null_date_hint_links": len(ids) - sum(len(values) for values in hint_groups.values()),
            "observation_day_hint_links": len(suspicious_ids),
        }
    return {
        "observation_id": observation["observation_id"],
        "observed_at": observation["observed_at"],
        "observation_local_day_vietnam": local_day,
        "visible_unique_ids": len(merged_hints),
        "dated_unique_ids": sum(v is not None for v in merged_hints.values()),
        "null_date_hint_unique_ids": sum(v is None for v in merged_hints.values()),
        "future_hint_ids_to_review": future,
        "possible_site_clock_clusters": clock_clusters,
        "listing_pages": categories,
    }


def audit_forward_windows(observations, *, reference_gap_hours=None):
    """Describe *observed* coverage risk without declaring forward reliability.

    reference_gap_hours is an optional analyst-supplied comparison threshold,
    not an authorized collection schedule or an assumed publisher cadence.
    """
    if (not isinstance(observations, list)
            or not 2 <= len(observations) <= MAX_SNAPSHOTS):
        raise ObservationRefused("need 2 to 90 authentic metadata snapshots")
    if reference_gap_hours is not None:
        if (isinstance(reference_gap_hours, bool)
                or not isinstance(reference_gap_hours, (int, float))
                or not math.isfinite(reference_gap_hours)
                or not 0 < reference_gap_hours <= 720):
            raise ObservationRefused("reference gap must be finite and in (0, 720] hours")

    # Both mandatory validator and comparator refuse drift in ID/URL identity,
    # duplicate sample IDs, out-of-order times, invalid dates and prose keys.
    drift = compare_observations(observations)
    parsed = [validate_observation(obs) for obs in observations]
    reports = [
        _observation_audit(obs, validated[0], validated[1])
        for obs, validated in zip(observations, parsed)
    ]
    changes = []
    warning_counts = Counter()
    for report in reports:
        warning_counts["future_date_hint_ids"] += len(report["future_hint_ids_to_review"])
        warning_counts["possible_site_clock_clusters"] += len(report["possible_site_clock_clusters"])
    for index in range(1, len(observations)):
        old, new = parsed[index-1][1], parsed[index][1]
        old_hints = _candidate_hints(observations[index-1])
        new_hints = _candidate_hints(observations[index])
        seconds = (parsed[index][0] - parsed[index-1][0]).total_seconds()
        gap_hours = round(seconds / 3600.0, 3)
        over_ref = (None if reference_gap_hours is None
                    else (seconds / 3600.0 > reference_gap_hours))
        if over_ref:
            warning_counts["gaps_over_reference"] += 1

        windows = {}
        zero_overlap = []
        drift_info = drift["transitions"][index-1]["sections"]
        for category in list(CATEGORIES) + ["union"]:
            previous = old[category] if category != "union" else set().union(*old.values())
            current = new[category] if category != "union" else set().union(*new.values())
            retained = previous & current
            if not retained:
                zero_overlap.append(category)
                warning_counts["zero_overlap_windows"] += 1
            drift_section = drift_info[category]
            windows[category] = {
                "previous_visible": len(previous),
                "current_visible": len(current),
                "overlap_count": len(retained),
                "previous_id_retention_fraction": round(len(retained)/len(previous), 4),
                "first_observed_count": len(drift_section["first_observed_ids"]),
                "reappeared_count": len(drift_section["reappeared_ids"]),
                "no_longer_visible_count": len(drift_section["no_longer_visible_ids"]),
                "publisher_deletion_inferred": False,
                "new_publications_inferred": False,
            }

        changed_hints = [
            ident for ident in sorted(old_hints.keys() & new_hints.keys())
            if old_hints[ident] is not None and new_hints[ident] is not None
            and old_hints[ident] != new_hints[ident]
        ]
        warning_counts["date_hint_changed_ids"] += len(changed_hints)
        changes.append({
            "from": observations[index-1]["observation_id"],
            "to": observations[index]["observation_id"],
            "elapsed_hours": gap_hours,
            "reference_gap_hours": reference_gap_hours,
            "above_reference_gap": over_ref,
            "zero_overlap_listing_pages": zero_overlap,
            "date_hint_changed_ids_to_review": changed_hints,
            "windows": windows,
        })

    return {
        "schema": "ipr-vndj-forward-window-audit/1",
        "source_slug": "vn_national_defence_journal_en",
        "snapshot_count": len(observations),
        "first_observed_at": observations[0]["observed_at"],
        "last_observed_at": observations[-1]["observed_at"],
        "reference_gap_hours": reference_gap_hours,
        "observations": reports,
        "transitions": changes,
        "warning_counts": dict(sorted(warning_counts.items())),
        "diagnostic_only": True,
        "candidate_dates_verified": False,
        "new_publisher_articles_inferred": False,
        "publisher_deletions_inferred": False,
        "historical_completeness_proven": False,
        "forward_capture_completeness_proven": False,
        "publisher_access_and_rights_validated_by_this_report": False,
        "journal_day_zero_started": False,
        "eligible_for_shadow_activation": False,
        "needs_independent_rights_review": True,
        "meaning": (
            "Only visible first-page memberships and unverified listing date hints. "
            "Zero warnings cannot prove missed-item absence, full feed coverage, "
            "article publication dates, access permission, or readiness. "
            "Review publisher support, source-use rights and independent "
            "human reliability evidence before any authorized collection."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots", nargs="+", help="2-90 authorized metadata JSON snapshots, in UTC order")
    parser.add_argument("--reference-gap-hours", type=float, default=None,
                        help="Optional diagnostic threshold, NOT a collector schedule")
    args = parser.parse_args(argv)
    if not 2 <= len(args.snapshots) <= MAX_SNAPSHOTS:
        parser.error("2-90 snapshots required")
    observations = []
    for name in args.snapshots:
        file_path = Path(name)
        if file_path.stat().st_size > 200_000:
            raise ObservationRefused("observation metadata exceeds 200KB")
        observations.append(json.loads(file_path.read_text(encoding="utf-8")))
    report = audit_forward_windows(observations, reference_gap_hours=args.reference_gap_hours)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
