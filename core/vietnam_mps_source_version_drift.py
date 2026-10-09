"""Compare MPS historical and latest shadow SOURCE VERSIONS, not publisher pages.

All queues MUST be independently produced from the exact local Git shadow
commits with prepare_vietnam_mps_review_queue.prepare(). A self-hashed queue
alone does not prove Git authenticity; CI and operators enforce that boundary.
Only existing Oct10 private research candidates are compared. No source bodies.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter

from scripts.prepare_vietnam_briefs_evidence import verified_queue

SCHEMA = "ipr-vietnam-mps-historical-current-shadow-version-drift/1"
WEEK = "2026-10-10"
OCT5 = "46f6a0e59e25b03868bf7ad600963d6921ee5124"
OCT7 = "c7c13dc7c15d855412afff99db23695dd50e51a5"
EXPECTED = {
    "VN-MPS-1791199100": OCT5,
    "VN-MPS-1791199677": OCT5,
    "VN-MPS-1791366010": OCT7,
}
REVIEW_SCOPE = "private-model-drafting-only-no-source-body"
HELD_STATUS = "unapproved-source-linked-editorial-candidate"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class VietnamRowDriftError(ValueError):
    """Missing, manipulated or falsely authorized MPS source versions."""


def need(cond, reason):
    if not cond:
        raise VietnamRowDriftError(reason)


def _records(queue):
    try:
        rows = verified_queue(queue)
    except (ValueError, KeyError, TypeError) as exc:
        raise VietnamRowDriftError("MPS machine queue self-check failed") from exc
    need(len(rows) <= 10000, "MPS historical queue is unbounded")
    result = {}
    for row in rows:
        need(isinstance(row, dict), "invalid MPS queue source row")
        ident = row.get("source_identity")
        need(isinstance(ident, str) and ident not in result,
             "duplicate or missing MPS source identity")
        result[ident] = row
    return result


def _row_checks(row):
    need(isinstance(row, dict),
         "pinned historical MPS queue source row missing or malformed")
    need(row.get("human_source_reviewed") is False
         and row.get("reuse_rights_reviewed") is False
         and row.get("production_publication_authorized") is False,
         "MPS queue cannot inherit human reuse or publishing approval")
    need(row.get("source_slug") == "vn_mps_foreign_affairs_vi",
         "foreign Vietnamese ministry source")
    for k in ("canonical_url", "published_date", "content_sha256"):
        need(isinstance(row.get(k), str), "MPS source field missing: " + k)
    need(HEX64.fullmatch(row["content_sha256"]),
         "MPS source digest is malformed")
    need(isinstance(row.get("machine_blockers"), list)
         and all(isinstance(x, str) for x in row["machine_blockers"])
         and type(row.get("machine_review_candidate")) is bool,
         "MPS machine eligibility malformed")
    return row


def compare_mps_versions(research_rows, historical_queues, current_queue):
    """Strict Oct10 three-source pinned ledger-vs-current metadata comparison.

    Never fetches official pages, treats source absence as publisher silence,
    exports body text, or upgrades research to eligible model/publication use.
    """
    need(isinstance(research_rows, list), "expected validated typed research")
    mps = [x for x in research_rows if isinstance(x, dict)
           and x.get("desk") == "vietnam"]
    need(len(mps) == len(EXPECTED) and
         {x.get("id") for x in mps} == set(EXPECTED),
         "Oct10 research packet is not the exact three MPS source IDs")
    need(isinstance(historical_queues, list) and len(historical_queues) == 2
         and all(isinstance(q, dict) for q in historical_queues)
         and isinstance(current_queue, dict),
         "two exact historical MPS queues and one current queue required")
    snapshots = {}
    for queue in historical_queues:
        commit = queue.get("state_commit")
        need(commit in (OCT5, OCT7) and commit not in snapshots,
             "historical commit missing or duplicated")
        snapshots[commit] = _records(queue)
    need(set(snapshots) == {OCT5, OCT7},
         "MPS historical state commit roster incomplete")
    current = _records(current_queue)
    current_commit = current_queue["state_commit"]
    need(re.fullmatch(r"[0-9a-f]{40}", current_commit) is not None,
         "newer state commit malformed")
    out = []
    for item in sorted(mps, key=lambda x: x["id"]):
        ident, commit = item["id"], item["state_commit"]
        need(commit == EXPECTED[ident]
             and item.get("status") == HELD_STATUS
             and item.get("copy_scope") == REVIEW_SCOPE
             and item.get("source_kind") == "shadow-extracted-original"
             and item.get("source_name") == "Vietnam Ministry of Public Security"
             and item.get("language") == "vi"
             and item.get("hash_rule") == "mps-vi-content-v1",
             "typed MPS evidence provenance or scope drifted")
        content_sha = item.get("source_content_sha256")
        need(isinstance(content_sha, str) and HEX64.fullmatch(content_sha),
             "typed MPS historical content digest missing")
        article = ident.removeprefix("VN-MPS-")
        need(re.fullmatch(r"[1-9][0-9]{9}", article) is not None,
             "MPS article identity malformed")
        identity = "mps-vi:" + article
        old = _row_checks(snapshots[commit].get(identity))
        publisher = item.get("source_url")
        need(isinstance(publisher, str)
             and old["canonical_url"] == publisher
             and old["published_date"] == item.get("published_date")
             and old["content_sha256"] == content_sha
             and old.get("body_status") == "text"
             and old.get("machine_review_candidate") is True
             and old["machine_blockers"] == [],
             "pinned historical MPS source body/identity not independently recoverable")
        latest = current.get(identity)
        fields = []
        new_digest = None
        if latest is None:
            verdict = "source_missing_from_newer_shadow_not_publisher_silence"
            fields = ["source_identity_missing"]
        else:
            _row_checks(latest)
            new_digest = latest["content_sha256"]
            for field in ("canonical_url", "published_date", "content_sha256",
                          "first_capture_sha256", "body_status", "title_original"):
                if latest.get(field) != old.get(field):
                    fields.append(field)
            if latest["canonical_url"] != publisher:
                fields.append("held_publisher_url_mismatch")
            if (latest.get("machine_blockers")
                or latest.get("machine_review_candidate") is not True):
                fields.append("newer_source_machine_hold")
            verdict = ("same_shadow_source_version_and_metadata"
                       if not fields else "newer_shadow_source_changed_or_held")
        out.append({
            "typed_id": ident,
            "historical_state_commit": commit,
            "historical_content_sha256": content_sha,
            "newer_content_sha256": new_digest,
            "version_comparison": verdict,
            "changed_fields": sorted(set(fields)),
            "current_publisher_body_independently_checked": False,
            "human_vietnamese_original_compared": False,
            "reuse_rights_reviewed": False,
            "eligible_for_regional_model": False,
            "editor_email_authorized": False,
            "publication_authorized": False,
        })
    counts = dict(sorted(Counter(x["version_comparison"] for x in out).items()))
    return {
        "schema": SCHEMA,
        "week_ending": WEEK,
        "historical_state_commits": sorted(snapshots),
        "newer_state_commit": current_commit,
        "compared_sources": len(out),
        "comparison_counts": counts,
        "items": out,
        "model_called": False,
        "source_body_or_publisher_url_in_report": False,
        "current_publisher_body_independently_checked": False,
        "live_official_publisher_silence_inferred": False,
        "human_source_review_completed": False,
        "source_reuse_rights_reviewed": False,
        "model_input_authorized": False,
        "dylan_editor_email_authorized": False,
        "publication_authorized": False,
        "vietnam_production_desk_activated": False,
    }
