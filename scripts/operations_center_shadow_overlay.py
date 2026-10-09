#!/usr/bin/env python3
"""Optional read-only, UNAUTHENTICATED shadow-candidate overlay for IPR Ops.

Consumes separately produced static binding-audit JSON and optional offline
slot-candidate reports. Does not trust their origins, inspect Actions APIs,
read a state branch, collect, send, publish, or qualify a desk.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.desk_registry import load_registry
from scripts import operations_center as ops
from scripts.source_health_report import build_report

BINDING_SCHEMA = "ipr-shadow-source-workflow-bindings/1"
SLOT_SCHEMA = "ipr-shadow-slot-candidates/1"
EVIDENCE_SCHEMA = "ipr-operations-shadow-candidates/1"
TRIGGERS = frozenset(("scheduled", "manual_only", "research_only"))
SLOT_STATUSES = frozenset((
    "pending_grace", "scheduled_success_new_records_candidate",
    "scheduled_success_no_new_records_candidate",
    "explicit_manual_recovery_candidate",
    "mature_slot_missing_from_supplied_evidence",
    "attempt_present_but_not_attested_success",
    "only_nonqualifying_attempts_observed",
    "conflicting_multiple_success_candidates",
    "success_with_other_unresolved_attempt",
))
COUNTS = {
    "pending": frozenset(("pending_grace",)),
    "candidate_supported": frozenset((
        "scheduled_success_new_records_candidate",
        "scheduled_success_no_new_records_candidate",
        "explicit_manual_recovery_candidate",
    )),
    "missing_from_supplied_evidence": frozenset((
        "mature_slot_missing_from_supplied_evidence",
    )),
    "review_required": SLOT_STATUSES - frozenset((
        "pending_grace", "scheduled_success_new_records_candidate",
        "scheduled_success_no_new_records_candidate",
        "explicit_manual_recovery_candidate",
        "mature_slot_missing_from_supplied_evidence",
    )),
}
SOURCE_SLUG = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


class OverlayError(ValueError):
    """Untrusted, mismatched or overclaiming operator-supplied evidence."""


def require(ok, reason):
    if not ok:
        raise OverlayError(reason)


def read_json(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OverlayError("missing/malformed supplied evidence JSON") from exc
    require(type(data) is dict, "supplied report must be a JSON object")
    return data


def _manifest_sources(snapshot, root):
    """Cross-check declarations against the exact manifest inventory shown."""
    source_pairs = set()
    manifests = snapshot.get("shadow_source_manifests")
    require(type(manifests) is list and bool(manifests),
            "snapshot lacks shadow source manifest inventory")
    paths = set()
    for manifest in manifests:
        require(type(manifest) is dict, "malformed snapshot shadow family")
        relative = manifest.get("manifest")
        require(type(relative) is str and
                bool(re.fullmatch(r"shadow/[a-z0-9_-]+/manifest.json", relative)) and
                relative not in paths, "invalid or duplicate shadow manifest path")
        paths.add(relative)
        target = root / relative
        require(not target.is_symlink() and target.is_file() and
                target.resolve().is_relative_to(root.resolve()),
                "unsafe or missing snapshot shadow manifest")
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise OverlayError("malformed local shadow manifest") from exc
        rows = data.get("sources")
        require(type(rows) is list and
                len(rows) == manifest.get("declared_source_count"),
                "snapshot/manifests disagree about source count")
        for source in rows:
            require(type(source) is dict and
                    type(source.get("slug")) is str and
                    bool(SOURCE_SLUG.fullmatch(source["slug"])),
                    "malformed local shadow source identity")
            identity = (relative, source["slug"])
            require(identity not in source_pairs, "duplicate shadow source identity")
            source_pairs.add(identity)
    return source_pairs


def _check_bindings(report, expected):
    require(type(report) is dict and
            report.get("schema") == BINDING_SCHEMA and
            report.get("declaration_only") is True and
            report.get("all_runs_attested") is False and
            report.get("production_eligible") is False and
            report.get("shadow_promotion_authorized") is False and
            report.get("editorial_publication_authorized") is False and
            report.get("writes") == 0,
            "binding audit must be explicitly declaration-only/nonauthorizing")
    rows = report.get("sources")
    require(type(rows) is list and len(rows) == len(expected) and
            report.get("source_families_checked") == len(expected),
            "binding report omits or adds source families")
    indexed = {}
    families = set()
    for row in rows:
        require(type(row) is dict, "malformed source-family binding")
        manifest, source = row.get("manifest"), row.get("source_slug")
        identity = (manifest, source)
        require(identity in expected and identity not in indexed,
                "unknown or duplicated source binding")
        trigger = row.get("trigger")
        require(trigger in TRIGGERS and
                row.get("run_attested") is False and
                row.get("production_eligible") is False and
                row.get("editorial_authorized") is False,
                "binding claims source readiness or invalid trigger")
        branch = row.get("state_branch")
        if trigger == "research_only":
            require(branch is None and row.get("workflow") is None and
                    row.get("cron") is None, "research-only source has collector binding")
        else:
            require(type(branch) is str and
                    bool(re.fullmatch(r"shadow/[a-z0-9_/-]+", branch)) and
                    type(row.get("workflow")) is str,
                    "collector source missing isolated state/workflow")
            if trigger == "scheduled":
                require(type(row.get("cron")) is str,
                        "scheduled source has no declared cron")
            else:
                require(row.get("cron") is None,
                        "manual-only source unexpectedly has a cron")
        indexed[identity] = row
        families.add(manifest)
    require(set(indexed) == expected and
            report.get("manifests_checked") == len(families),
            "binding source/manifest coverage drift")
    return indexed


def _slot_report(report, binding, snapshot_as_of):
    require(type(report) is dict and report.get("schema") == SLOT_SCHEMA and
            report.get("source_slug") == binding["source_slug"] and
            report.get("state_branch") == binding["state_branch"],
            "slot report has wrong version or source/state identity")
    require(binding["trigger"] == "scheduled",
            "slot report attached to non-scheduled family")
    parts = binding["cron"].split(" ")
    require(len(parts) == 5 and all(part.isdigit() for part in parts[:2]),
            "binding has no fixed UTC daily hour/minute")
    minute, hour = int(parts[0]), int(parts[1])
    require(0 <= minute < 60 and 0 <= hour < 24 and
            report.get("cron_utc") == ("%02d:%02d" % (hour, minute)),
            "slot report cron differs from source binding")
    require(report.get("supplied_actions_export_authenticated") is False and
            report.get("source_capture_chain_verified_by_this_audit") is False and
            report.get("all_historical_scheduled_attempts_exhaustively_observed") is False and
            report.get("government_silence_established") is False and
            report.get("desk_production_eligible") is False and
            report.get("weekly_ai_writer_eligible") is False and
            report.get("editor_delivery_authorized") is False and
            report.get("automatic_recovery_dispatched") is False and
            report.get("writes") == 0, "slot report improperly claims authority")
    instant = report.get("as_of_utc")
    require(type(instant) is str and
            bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z", instant)) and
            instant[:10] <= snapshot_as_of,
            "future or malformed supplied slot observation")
    slots = report.get("slots")
    counts = report.get("counts")
    require(type(slots) is list and 0 < len(slots) <= 31 and type(counts) is dict
            and set(counts) == set(COUNTS), "malformed slot candidates/counts")
    seen_dates = set()
    statuses = []
    for row in slots:
        require(type(row) is dict and type(row.get("logical_date")) is str and
                bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", row["logical_date"])) and
                row["logical_date"] not in seen_dates and
                row.get("status") in SLOT_STATUSES and
                row.get("new_record_count_is_not_publication_completeness") is True,
                "malformed/duplicate logical slot or readiness claim")
        seen_dates.add(row["logical_date"])
        statuses.append(row["status"])
    for name, accepted in COUNTS.items():
        require(type(counts[name]) is int and
                counts[name] == sum(status in accepted for status in statuses),
                "slot count/status mismatch")
    return {
        "checked_at_utc": instant, "slots_observed": len(slots),
        "pending_slots": counts["pending"],
        "candidate_supported_slots": counts["candidate_supported"],
        "review_required_slots": counts["review_required"],
        "missing_from_supplied_evidence": counts["missing_from_supplied_evidence"],
        "latest_candidate_date": max(seen_dates),
        "collection_verified": False,
        "input_origin_authenticated": False,
    }


def attach(snapshot, binding_report, slot_reports, *, root=ROOT):
    """Join read-only declarations and candidate reports; never grant health."""
    require(type(snapshot) is dict and snapshot.get("schema") == ops.SCHEMA and
            snapshot.get("publication_authorized") is False and
            snapshot.get("shadow_promotion_authorized") is False and
            snapshot.get("editor_delivery_authorized") is False,
            "base snapshot has unexpected schema or editorial authorization")
    root = Path(root).resolve()
    expected = _manifest_sources(snapshot, root)
    indexed = _check_bindings(binding_report, expected)
    by_slug = {}
    for (manifest, slug), row in indexed.items():
        require(slug not in by_slug,
                "ambiguous cross-manifest source slug cannot be joined safely")
        by_slug[slug] = row
    slot_index = {}
    require(type(slot_reports) is list and len(slot_reports) <= len(indexed),
            "unbounded or malformed slot report list")
    for report in slot_reports:
        require(type(report) is dict and type(report.get("source_slug")) is str,
                "malformed supplied slot source")
        slug = report["source_slug"]
        require(slug in by_slug and slug not in slot_index,
                "unknown/duplicate supplied slot source")
        slot_index[slug] = _slot_report(report, by_slug[slug], snapshot["as_of"])
    combined = []
    for identity, row in sorted(indexed.items()):
        slot = slot_index.get(row["source_slug"])
        combined.append({
            "manifest": identity[0],
            "source_slug": identity[1],
            "state_branch": row["state_branch"],
            "workflow": row.get("workflow"),
            "trigger": row["trigger"],
            "schedule_cron_utc": row.get("cron"),
            "binding_status": "static_declared_not_execution_proof",
            "slot_evidence_status": ("operator_supplied_candidates_not_authenticated"
                                     if slot else "not_supplied"),
            "slot_candidate_summary": slot,
            "collection_verified": False,
            "production_eligible": False,
            "rights_approved": False,
            "editorial_publication_authorized": False,
        })
    new = copy.deepcopy(snapshot)
    new["shadow_evidence_overlay"] = {
        "schema": EVIDENCE_SCHEMA,
        "source_families": combined,
        "families_with_slot_candidates": len(slot_index),
        "input_origin_authenticated": False,
        "collection_verified": False,
        "publisher_silence_established": False,
        "publication_authorized": False,
        "editor_delivery_authorized": False,
        "state_branch_changes": 0,
    }
    return new


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bindings", type=Path, required=True,
                   help="JSON stdout of the offline binding audit")
    p.add_argument("--slot-report", action="append", type=Path, default=[],
                   help="optional JSON stdout of one offline slot-candidate audit")
    p.add_argument("--as-of", default=None,
                   help="display date; does not time-travel the database")
    p.add_argument("--db", type=Path)
    p.add_argument("--html", required=True, type=Path)
    p.add_argument("--json", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        import datetime
        as_of = ops.exact_date(args.as_of or datetime.date.today().isoformat())
        html_path = ops.safe_destination(args.html)
        json_path = ops.safe_destination(args.json)
        require(html_path.resolve() != json_path.resolve(),
                "JSON and HTML destinations must be distinct")
        original = ops.assemble(load_registry(),
                                build_report(args.db or Path(ops.DB_PATH)),
                                ops.SHADOW_ROOT, ops.DAILY_MARKER, as_of)
        report = attach(original, read_json(args.bindings),
                        [read_json(path) for path in args.slot_report])
        html = ops.render_html(report)
        # Both outputs are outside the repository; new private files only.
        ops.write_private_reports((
            (json_path, json.dumps(report, indent=2, ensure_ascii=False,
                                   sort_keys=True) + "\n"),
            (html_path, html),
        ))
        print("Offline shadow-candidate overlay (unauthenticated): " +
              str(html_path))
    except (OverlayError, ops.SnapshotError, OSError, ValueError,
            TypeError, KeyError) as exc:
        p.error(str(exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
