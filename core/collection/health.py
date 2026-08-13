"""
Collection health: aggregate run status and source-health reporting.

Answers, per run and per source: was zero a silence or a failure, is the silence
within this source's own expected cadence, and does any of it degrade the run.

Two report shapes, on purpose:

  * `machine_report()` — JSON for tooling and future coverage metrics.
  * `human_report()`   — a short fixed-width block for logs and PR bodies.

Neither ever emits secrets, credentials or raw stack traces. Adapter errors are
already length-capped single lines by the time they arrive here, and nothing in
this module is intended for a public page — the public surface gets a coverage
statement written by a human, not this.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Sequence

from core.collection import status as st
from core.collection.contract import SourceRunResult

#: Fallback when a source declares no silence threshold in its manifest.
DEFAULT_SILENCE_THRESHOLD_DAYS = 7


def aggregate_status(results: Sequence[SourceRunResult]) -> str:
    """
    The run's overall status, from its per-source results.

    The rule that matters: **one required source failing degrades the run even
    when every other source succeeded.** Before per-source results existed, PLA
    Daily's ~87% share meant the totals never moved when MOD China died, and
    four weeks of silence produced no failed run at all.

    'failed' is reserved for a run where nothing at all was collected — a
    partial collection that published real work is 'degraded', not 'failed',
    consistent with how pipeline.py already treats analysis.
    """
    if not results:
        return "failed"

    collectible = [
        r for r in results
        if r.status not in (st.SKIPPED_DISABLED, st.NOT_IMPLEMENTED)
    ]
    if not collectible:
        # Everything configured is disabled or a stub. Not a failure of this
        # run, but not a healthy state either.
        return "degraded"

    if all(r.is_failure for r in collectible):
        return "failed"
    if any(r.is_failure for r in collectible):
        return "degraded"
    return "completed"


def silence_verdict(
    days_silent: Optional[int], source=None
) -> str:
    """
    Judge silence against the source's own expected cadence.

    A source that genuinely publishes twice a month is not sick after seven quiet
    days, and an alarm that cries wolf is worse than no alarm
    (DECISION_LOG 2026-08-09 §8). The threshold comes from the manifest, which
    records it as measured from the SOURCE's own listings — never from our
    collection, which is the thing being tested.
    """
    if days_silent is None:
        return "unknown"
    threshold = DEFAULT_SILENCE_THRESHOLD_DAYS
    if source is not None and getattr(source, "silence_threshold_days", None):
        threshold = source.silence_threshold_days
    return "within_cadence" if days_silent <= threshold else "overdue"


def machine_report(
    results: Sequence[SourceRunResult],
    run_id: Optional[int] = None,
    extra: Optional[Dict] = None,
) -> Dict:
    """Structured report. Stable keys — tooling may depend on these."""
    report = {
        "run_id": run_id,
        "aggregate_status": aggregate_status(results),
        "source_count": len(results),
        "failed_sources": sorted(r.source_slug for r in results if r.is_failure),
        "empty_sources": sorted(
            r.source_slug for r in results
            if r.status in st.EMPTY_STATUSES and not r.is_failure
        ),
        "sources": [
            {
                "source_slug": r.source_slug,
                "desk_id": r.desk_id,
                "status": r.status,
                "is_failure": r.is_failure,
                "references_discovered": r.references_discovered,
                "fetched": r.fetched,
                "extracted": r.extracted,
                "duplicates": r.duplicates,
                "new_documents": r.new_documents,
                "relevance_rejected": r.relevance_rejected,
                "failed_fetches": r.failed_fetches,
                "error_detail": r.error_detail,
            }
            for r in sorted(results, key=lambda x: x.source_slug)
        ],
    }
    if extra:
        report.update(extra)
    return report


def human_report(
    results: Sequence[SourceRunResult], run_id: Optional[int] = None
) -> str:
    """Short fixed-width block for logs. No secrets, no stack traces."""
    agg = aggregate_status(results)
    lines = [
        "Collection health — run %s — aggregate: %s"
        % (run_id if run_id is not None else "?", agg.upper()),
        "-" * 78,
    ]
    for r in sorted(results, key=lambda x: x.source_slug):
        marker = "FAIL" if r.is_failure else ("ok  " if r.is_success else "note")
        lines.append("%s  %s" % (marker, r.summary_line()))
    lines.append("-" * 78)

    failed = [r.source_slug for r in results if r.is_failure]
    if failed:
        lines.append(
            "%d source(s) failed: %s — run is %s"
            % (len(failed), ", ".join(sorted(failed)), agg)
        )
    else:
        quiet = [
            r.source_slug for r in results
            if r.status in (st.OK_NO_PUBLICATIONS, st.OK_ALL_DUPLICATES)
        ]
        lines.append(
            "no source failures"
            + ("; published nothing new: %s" % ", ".join(sorted(quiet)) if quiet else "")
        )
    return "\n".join(lines)


def write_machine_report(path, report: Dict) -> None:
    with open(str(path), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
