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
from scripts import audit_shadow_workflow_bindings as bindings
from scripts import capture_daily_actions_receipts as capture
from scripts import operations_center as ops
from scripts import operations_center_shadow_overlay as shadow
from scripts.source_health_report import build_report

SCHEMA = "ipr-unified-daily-evidence/1"
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


def build_unified(registry, production_report, shadow_root, marker_path,
                  as_of, binding_report, slot_reports=(), receipt=None, *, root=ROOT):
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
    return base


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--as-of", default=current_display_date(),
                   help="New York display date by default; not a historical DB time machine")
    p.add_argument("--db", type=Path, default=Path(ops.DB_PATH))
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
        report = build_unified(
            load_registry(), build_report(args.db),
            ops.SHADOW_ROOT, ops.DAILY_MARKER, as_of,
            binding_report,
            [shadow.read_json(path) for path in args.slot_report],
            receipt,
            root=ROOT,
        )
        json_text = json.dumps(report, ensure_ascii=False,
                               indent=2, sort_keys=True) + "\n"
        html_text = ops.render_html(report)
        # Both destinations already passed ops.safe_destination and are new.
        # No file in the repository or any source state is ever written.
        with output.open("x", encoding="utf-8") as file:
            file.write(json_text)
        with html.open("x", encoding="utf-8") as file:
            file.write(html_text)
        print("Read-only unified Operations Center: %s" % html)
    except (UnifiedError, daily.ReceiptError, bindings.BindingError,
            capture.CaptureError, shadow.OverlayError, ops.SnapshotError,
            OSError, KeyError,
            ValueError, TypeError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
