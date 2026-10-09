#!/usr/bin/env python3
"""One local read-only snapshot: production, shadow bindings and Daily attempts.

Uses the existing authoritative production source-health report, checked static
shadow declarations and *optional* operator-supplied unauthenticated evidence.
By default no network is used. An explicit --fetch-daily-utc-day opts into
read-only GitHub Actions GET metadata only; no collectors, models or email.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.desk_registry import load_registry
from scripts import audit_daily_run_receipts as daily
from scripts import audit_analysis_queue_by_source as queue_audit
from scripts import audit_analysis_backlog_triage as triage_audit
from scripts import audit_shadow_workflow_bindings as bindings
from scripts import capture_daily_actions_receipts as capture
from scripts import operations_center as ops
from scripts import operations_center_shadow_overlay as shadow
from scripts.source_health_report import build_report

SCHEMA = "ipr-unified-daily-evidence/1"
QUEUE_SCHEMA = "ipr-operations-stored-queue-evidence/1"
NY = ZoneInfo("America/New_York")


def current_display_date(now=None):
    """Use the Daily scheduling guard's New York date, never runner UTC."""
    instant = datetime.now(timezone.utc) if now is None else now
    require(instant.tzinfo is not None,
            "explicit timezone required for Operations Center current date")
    return instant.astimezone(NY).date().isoformat()


class UnifiedError(ValueError):
    """Fail closed when evidence or a claimed authority does not fit."""


def require(condition, message):
    if not condition:
        raise UnifiedError(message)


def attach_daily(snapshot, receipt):
    """Revalidate raw canonical receipt; never trust an already-rendered verdict."""
    require(type(snapshot) is dict and snapshot.get("schema") == ops.SCHEMA
            and snapshot.get("publication_authorized") is False
            and snapshot.get("shadow_promotion_authorized") is False
            and snapshot.get("editor_delivery_authorized") is False,
            "base Operations Center snapshot cannot carry authorizations")
    require("daily_actions_evidence" not in snapshot,
            "duplicate Daily Actions evidence attachment")
    report = daily.interpret(receipt)
    require(report["publication_authorized"] is False
            and report["editor_delivery_authorized"] is False
            and report["archive_capture_verified"] is False
            and report["supplied_actions_export_authenticated"] is False
            and report["analysis_queue_current_state_verified"] is False
            and report["complete_actions_history_established"] is False
            and report["no_publications_inferred"] is False
            and report["source_rights_cleared"] is False
            and report["writes"] == 0,
            "Daily receipt report improperly claims editorial or production authority")
    require(all(row["created_new_york_date"] <= snapshot["as_of"]
                for row in report["attempts"]),
            "Daily receipt includes an attempt after the snapshot display date")
    require(all(row.get("collection_executed_authenticated") is False
                and row.get("deployment_authenticated") is False
                and row.get("log_metrics_authenticated") is False
                for row in report["attempts"]),
            "Daily attempt has unsupported authentication flags")
    combined = copy.deepcopy(snapshot)
    combined["daily_actions_evidence"] = {
        "schema": SCHEMA,
        "as_of_utc": report["as_of_utc"],
        "supplied_attempt_count": report["provided_attempts"],
        "attempts": report["attempts"],
        "created_new_york_day_counts": report["created_ny_day_counts"],
        "historical_backlog_snapshots": report["supplied_pipeline_backlog_snapshots"],
        "input_origin_authenticated": False,
        "complete_run_history_established": False,
        "collector_work_certified": False,
        "current_analysis_queue_verified": False,
        "publisher_silence_established": False,
        "publication_authorized": False,
        "source_promotion_authorized": False,
        "editor_delivery_authorized": False,
        "writes": 0,
    }
    return combined



def attach_queue(snapshot, audit):
    """Attach an independently pinned local SQLite queue audit as stored evidence.

    Queue rows cannot alter production source health or authenticate live
    collection. Input comes from queue_audit.snapshot(), never external JSON.
    """
    require(type(snapshot) is dict and snapshot.get("schema") == ops.SCHEMA
            and snapshot.get("publication_authorized") is False
            and snapshot.get("shadow_promotion_authorized") is False
            and snapshot.get("editor_delivery_authorized") is False,
            "base Operations Center snapshot cannot carry authorizations")
    require("stored_analysis_queue_evidence" not in snapshot,
            "duplicate stored analysis queue evidence")
    require(type(audit) is dict and audit.get("schema") == queue_audit.SCHEMA,
            "expected canonical read-only analysis queue audit")
    for flag in ("model_spend_authorized", "publication_authorized",
                 "editor_delivery_authorized", "live_production_state_authenticated",
                 "collection_executed_authenticated"):
        require(audit.get(flag) is False,
                "analysis queue audit improperly claims authority: " + flag)
    require(audit.get("writes") == 0 and audit.get("model_calls") == 0,
            "analysis queue audit must perform no writes or model calls")
    totals = audit.get("totals")
    sources = audit.get("sources")
    require(type(totals) is dict and type(sources) is list,
            "analysis queue audit totals/sources missing")
    keys = queue_audit.BUCKETS
    require(set(totals) == set(keys) and
            all(type(totals[k]) is int and totals[k] >= 0 for k in keys),
            "analysis queue audit has malformed bucket totals")
    require(type(audit.get("article_rows")) is int and
            sum(totals.values()) == audit["article_rows"],
            "analysis queue total does not reconcile")
    daily = sum(totals[k] for k in keys if k.startswith("daily_unscored_"))
    held = totals["held_unscored"] + totals["held_pending_analysis"]
    require(audit.get("stored_daily_unscored") == daily
            and audit.get("stored_daily_pending_analysis") ==
                totals["daily_pending_analysis"]
            and audit.get("stored_daily_queue_eligible") ==
                daily + totals["daily_pending_analysis"]
            and audit.get("stored_held_out_of_daily") == held,
            "analysis queue eligibility totals do not reconcile")
    seen = set()
    rows = []
    for source in sources:
        require(type(source) is dict
                and type(source.get("desk_id")) is str
                and type(source.get("source_slug")) is str,
                "malformed source identity in analysis queue")
        key = (source["desk_id"], source["source_slug"])
        require(key not in seen and all(
            type(source.get(k)) is int and source[k] >= 0 for k in keys),
            "duplicate source or malformed queue bucket")
        seen.add(key)
        count = sum(source[k] for k in keys)
        require(source.get("rows_total") == count,
                "source analysis queue rows do not reconcile")
        rows.append({
            "desk_id": key[0], "source_slug": key[1],
            "daily_eligible_stored": sum(
                source[k] for k in keys if k.startswith("daily_unscored_")
            ) + source["daily_pending_analysis"],
            "held_out_stored": source["held_unscored"] +
                source["held_pending_analysis"],
            "paused_stored": source["paused"],
            "unknown_state_stored": source["unknown_state"],
            "rows_total": count,
        })
    require(sum(x["rows_total"] for x in rows) == audit["article_rows"]
            and sum(x["daily_eligible_stored"] for x in rows) ==
                audit["stored_daily_queue_eligible"]
            and sum(x["held_out_stored"] for x in rows) == held,
            "per-source queue audit does not reconcile")
    hashes = audit.get("input_file_sha256")
    require(type(hashes) is dict and type(hashes.get("db")) is str
            and len(hashes["db"]) == 64 and
            all(c in "0123456789abcdef" for c in hashes["db"]),
            "analysis queue missing pinned database digest")
    require(audit.get("input_file_identity_not_signed") is True,
            "analysis queue provenance is not externally attested")
    combined = copy.deepcopy(snapshot)
    combined["stored_analysis_queue_evidence"] = {
        "schema": QUEUE_SCHEMA,
        "audit_schema": queue_audit.SCHEMA,
        "audit_generated_utc": audit["snapshot_audit_generated_utc"],
        "live_unscored_cutoff_utc_day": audit["live_unscored_cutoff_utc_day"],
        "input_file_sha256": copy.deepcopy(hashes),
        "input_file_identity_not_signed": True,
        "article_rows": audit["article_rows"],
        "stored_daily_queue_eligible": audit["stored_daily_queue_eligible"],
        "stored_daily_unscored": audit["stored_daily_unscored"],
        "stored_daily_pending_analysis": audit["stored_daily_pending_analysis"],
        "stored_held_out_of_daily": held,
        "paused_stored": totals["paused"],
        "unknown_state_stored": totals["unknown_state"],
        "sources": rows,
        "live_production_state_authenticated": False,
        "next_run_queue_known": False,
        "model_spend_authorized": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "writes": 0,
        "model_calls": 0,
    }
    return combined




def attach_dispatch_readiness(snapshot, triage):
    """Attach only body-level, locally pinned model-input readiness counts.

    The operator must already have requested a canonical stored-queue view.
    This is a snapshot of source text availability, never future Daily workload,
    source authorization or an instruction to spend.
    """
    require(type(snapshot) is dict and
            type(snapshot.get("stored_analysis_queue_evidence")) is dict,
            "dispatch readiness requires the canonical stored queue overlay")
    queue = snapshot["stored_analysis_queue_evidence"]
    require("model_dispatch_body_readiness" not in queue,
            "duplicate model dispatch body readiness")
    require(type(triage) is dict and triage.get("schema") == triage_audit.SCHEMA,
            "dispatch readiness requires canonical read-only backlog triage")
    for key in ("model_spend_authorized", "publication_authorized",
                "editor_delivery_authorized", "text_extraction_verified",
                "live_production_state_authenticated", "next_run_workload_known"):
        require(triage.get(key) is False, "triage may not authorize: " + key)
    require(triage.get("model_dispatch_preview_not_future_run_workload") is True
            and triage.get("model_dispatch_preview_not_spending_approval") is True
            and triage.get("model_dispatch_body_test_matches_python_strip") is True,
            "unverified body readiness contract")
    require(triage.get("writes") == 0 and triage.get("model_calls") == 0,
            "dispatch triage must be model-free and read-only")
    require(triage.get("input_file_sha256") ==
            queue["input_file_sha256"],
            "readiness and queue audit use different database bytes")
    eligible = queue["stored_daily_queue_eligible"]
    require(triage.get("stored_daily_queue_eligible") == eligible,
            "dispatch and stored queue eligibility disagree")
    ready = triage.get("stored_daily_model_dispatch_body_ready")
    withheld = triage.get("stored_daily_model_dispatch_body_withheld")
    require(type(ready) is int and type(withheld) is int and
            ready >= 0 and withheld >= 0 and ready + withheld == eligible,
            "body-ready and withheld counts do not reconcile")
    src = triage.get("sources")
    require(type(src) is list and type(queue.get("sources")) is list,
            "source-level dispatch readiness absent")
    index = {}
    for r in queue["sources"]:
        key = (r["desk_id"], r["source_slug"])
        require(key not in index, "duplicate stored queue source identity")
        index[key] = r
    seen = set()
    rows = []
    for r in src:
        require(type(r) is dict and
                type(r.get("desk_id")) is str and
                type(r.get("source_slug")) is str,
                "malformed source identity in dispatch triage")
        key = (r["desk_id"], r["source_slug"])
        require(key in index and key not in seen,
                "unmatched or duplicate dispatch triage source")
        seen.add(key)
        n, w = r.get("daily_model_dispatch_body_ready"), r.get(
            "daily_model_dispatch_body_withheld")
        require(type(n) is int and type(w) is int and n >= 0 and w >= 0
                and n + w == index[key]["daily_eligible_stored"],
                "per-source dispatch counts do not reconcile")
        rows.append({"desk_id": key[0], "source_slug": key[1],
                     "body_ready": n, "body_withheld": w,
                     "stored_daily_eligible": n + w})
    # The canonical archive includes sources whose only rows were fully
    # analyzed or relevance-rejected. Those sources legitimately have no
    # review/dispatch triage row and must carry zero Daily eligibility.
    require(all(index[key]["daily_eligible_stored"] == 0
                for key in set(index) - seen) and
            sum(r["body_ready"] for r in rows) == ready and
            sum(r["body_withheld"] for r in rows) == withheld,
            "dispatch sources do not reconcile with stored queue")
    result = copy.deepcopy(snapshot)
    result["stored_analysis_queue_evidence"]["model_dispatch_body_readiness"] = {
        "schema": "ipr-ops-dispatch-body-readiness/1",
        "body_ready": ready,
        "body_withheld_for_source_review": withheld,
        "stored_daily_queue_eligible": eligible,
        "sources": rows,
        "input_file_sha256": copy.deepcopy(triage["input_file_sha256"]),
        "future_workload_authenticated": False,
        "source_extraction_verified": False,
        "model_spend_authorized": False,
        "publication_authorized": False,
        "writes": 0,
        "model_calls": 0,
    }
    return result


def build_unified(registry, production_report, shadow_root, marker_path,
                  as_of, binding_report, slot_reports=(), receipt=None, queue_report=None,
                  dispatch_report=None, *, root=ROOT):
    """Join independently validated source declarations and optional evidence.

    The source health report remains solely based on the production DB;
    no supplied GitHub receipt can change existing production/desk health.
    """
    base = ops.assemble(registry, production_report, shadow_root,
                        marker_path, as_of)
    if binding_report is not None:
        base = shadow.attach(base, binding_report, list(slot_reports), root=root)
    else:
        require(not slot_reports, "slot candidates require source bindings")
    if receipt is not None:
        base = attach_daily(base, receipt)
    if queue_report is not None:
        base = attach_queue(base, queue_report)
    if dispatch_report is not None:
        base = attach_dispatch_readiness(base, dispatch_report)
    return base



def write_report_pair(json_path, json_text, html_path, html_text):
    """Retain the unified API, sharing the guarded private-report writer."""
    ops.write_private_reports(((json_path, json_text),
                               (html_path, html_text)))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", default=current_display_date(),
                   help="New York display date by default; not a historical DB time machine")
    p.add_argument("--db", type=Path, default=Path(ops.DB_PATH))
    p.add_argument("--include-analysis-queue", action="store_true",
                   help="opt-in source-attributed read-only stored SQLite queue; not a live monitor")
    p.add_argument("--include-dispatch-readiness", action="store_true",
                   help="opt-in extra body-ready/withheld SQLite scan; requires --include-analysis-queue")
    evidence = p.add_mutually_exclusive_group()
    evidence.add_argument("--daily-receipts", type=Path,
                          help="operator-supplied raw Actions receipt JSON, no network")
    evidence.add_argument("--fetch-daily-utc-day",
                          help="explicit opt-in: GET Actions metadata for UTC YYYY-MM-DD; "
                               "does not retrieve job logs, make collection claims or dispatch jobs")
    p.add_argument("--slot-report", type=Path, action="append", default=[],
                   help="optional unauthenticated source-scoped slot candidate report")
    p.add_argument("--html", required=True, type=Path,
                   help="new HTML report outside the repository")
    p.add_argument("--json", required=True, type=Path,
                   help="new JSON report outside the repository")
    args = p.parse_args(argv)
    try:
        as_of = ops.exact_date(args.as_of)
        require(not args.include_dispatch_readiness or args.include_analysis_queue,
                "--include-dispatch-readiness requires --include-analysis-queue")
        html = ops.safe_destination(args.html)
        output = ops.safe_destination(args.json)
        require(html.resolve() != output.resolve(),
                "JSON and HTML output paths must be different")
        # Network is strictly opt-in. No workflow is ever dispatched and the
        # GitHub API metadata never fabricates missing guard/log evidence.
        receipt = (shadow.read_json(args.daily_receipts)
                   if args.daily_receipts else
                   capture.capture(args.fetch_daily_utc_day)
                   if args.fetch_daily_utc_day else None)
        # Validate declarations in the working checkout, not a guessed
        # authenticated source execution. No workflow is dispatched.
        binding_report = bindings.validate(ROOT)
        # Both locally derived SQLite observations must describe the same
        # pinned input bytes. Refuse a concurrent change rather than blend them.
        hashes_before = (queue_audit._snapshot_file_hashes(args.db)
                         if args.include_analysis_queue else None)
        production_report = build_report(args.db)
        queue_report = (queue_audit.snapshot(args.db)
                        if args.include_analysis_queue else None)
        if queue_report is not None:
            require(hashes_before == queue_report["input_file_sha256"],
                    "database changed between source-health and queue audits")
        dispatch_report = (triage_audit.snapshot(args.db)
                           if args.include_dispatch_readiness else None)
        if dispatch_report is not None:
            require(dispatch_report["input_file_sha256"] == hashes_before,
                    "database changed during dispatch readiness audit")
        report = build_unified(
            load_registry(), production_report,
            ops.SHADOW_ROOT, ops.DAILY_MARKER, as_of,
            binding_report,
            [shadow.read_json(path) for path in args.slot_report],
            receipt,
            queue_report,
            dispatch_report,
            root=ROOT,
        )
        json_text = json.dumps(report, ensure_ascii=False,
                               indent=2, sort_keys=True) + "\n"
        html_text = ops.render_html(report)
        # Both destinations passed ops.safe_destination and are new.
        # An I/O error must not strand a partial unmatched local report.
        write_report_pair(output, json_text, html, html_text)
        print("Read-only unified Operations Center: %s" % html)
    except (UnifiedError, queue_audit.QueueAuditError, daily.ReceiptError, bindings.BindingError,
            capture.CaptureError, shadow.OverlayError, ops.SnapshotError,
            OSError, KeyError,
            ValueError, TypeError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
