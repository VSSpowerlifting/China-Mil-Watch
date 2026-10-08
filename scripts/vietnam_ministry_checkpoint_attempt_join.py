"""Join verified Vietnam ministry review packets with supplied Actions receipts.

This read-only offline adapter avoids copying publisher-state ledgers into a
separate hand-authored attempt-reconciliation input. It delegates packet-file
hash/manifest validation to merged #184 and date/Actions reconciliation to
the separate #188 candidate. It never establishes completeness of the
reviewer's GitHub Actions attempt inventory or completes human signoff.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import timedelta
from pathlib import Path

from scripts.vietnam_ministry_checkpoint_rollup import (
    read_packet, read_file, rollup, RollupRefused,
)
from scripts.vietnam_ministry_attempt_reconciliation import (
    SCHEMA, WORKFLOW, MINISTRY_SHADOW_START, strict_json, reconcile,
)

RECEIPT_SCHEMA = "ipr-vn-ministry-human-verified-actions-receipts/1"
REPORT_SCHEMA = "ipr-vn-ministry-packet-attempt-join/1"
LEDGER_FIELDS = (
    "run_id", "result", "health", "target_date",
    "target_date_source", "collector_commit", "finished_utc",
)
MAX_RECEIPTS_BYTES = 500_000
MAX_LEDGER_LINES = 500


class PacketJoinRefused(ValueError):
    """The local packet/receipt contract cannot be reconciled honestly."""


def require(condition, reason):
    if not condition:
        raise PacketJoinRefused(reason)


def extract_source_ledgers(packet_dir):
    """Select only seven run-metadata fields from a #184-verified packet."""
    packet_dir = Path(packet_dir)
    summary = read_packet(packet_dir)  # SHA256 + deterministic package check
    raw = read_file(packet_dir / "run_inventory.jsonl")
    # The producer always terminates JSONL records with LF; refuse truncation.
    require(raw and raw.endswith(b"\n"), "run inventory is missing or truncated")
    lines = raw.splitlines()
    require(0 < len(lines) <= MAX_LEDGER_LINES, "run inventory outside bounded historical size")
    records = []
    seen = set()
    for raw_line in lines:
        require(bool(raw_line), "empty run-inventory row")
        ledger = strict_json(raw_line.decode("utf-8"))
        require(isinstance(ledger, dict), "run inventory must contain JSON objects")
        require(ledger.get("source_slug") == summary["source_slug"]
                and ledger.get("desk_id") == "vietnam",
                "run inventory does not belong to its source packet")
        require(all(field in ledger for field in LEDGER_FIELDS),
                "run-inventory metadata missing essential reconciliation fields")
        item = {field: ledger[field] for field in LEDGER_FIELDS}
        identifier = item["run_id"]
        require(isinstance(identifier, str) and identifier not in seen,
                "duplicate or non-string run identity in committed packet")
        seen.add(identifier)
        records.append(item)
    require(records[-1]["run_id"] == summary["latest_run_id"],
            "packet manifest latest run differs from its source inventory")
    # Pin each input to the exact artifact digest which #184 already verified.
    return summary["source_slug"], {
        "state_branch": summary["state_branch"],
        "state_commit": summary["state_commit"],
        "runs": records,
    }, {
        "source_slug": summary["source_slug"],
        "state_commit": summary["state_commit"],
        "review_packet_sha256": summary["packet_sha256"],
        "review_manifest_sha256": summary["manifest_sha256"],
        "run_inventory_sha256": hashlib.sha256(raw).hexdigest(),
        "runs_extracted": len(records),
    }


def join(packets, receipt_document):
    """Return a human-held audit report, NEVER an authorization or signoff."""
    summary = rollup(packets)
    require(summary["all_three_machine_checkpoints_reached"],
            "cannot join prematurely generated machine checkpoint packets")
    require(isinstance(receipt_document, dict)
            and set(receipt_document) == {"schema", "github_attempts"}
            and receipt_document["schema"] == RECEIPT_SCHEMA,
            "Actions receipts need the explicitly verified input schema")
    attempts = receipt_document["github_attempts"]
    require(isinstance(attempts, list), "Actions receipts must be a list")
    from_day = MINISTRY_SHADOW_START
    try:
        from datetime import date
        end_day = date.fromisoformat(summary["as_of"])
    except (TypeError, ValueError) as exc:
        raise PacketJoinRefused("invalid source packet as-of date") from exc
    require(from_day <= end_day and (end_day - from_day).days <= 45,
            "source packet as-of lies outside the approved 45-day reliability review window")
    expected_days = [
        (from_day + timedelta(days=i)).isoformat()
        for i in range((end_day - from_day).days + 1)
    ]
    source_ledgers = {}
    anchors = {}
    for path in packets:
        slug, rows, anchor = extract_source_ledgers(path)
        require(slug not in source_ledgers, "duplicate source packet identity")
        source_ledgers[slug] = rows
        anchors[slug] = anchor
    reconciled_input = {
        "schema": SCHEMA,
        "workflow": WORKFLOW,
        "review_window": {"from": from_day.isoformat(), "through": end_day.isoformat()},
        "expected_target_dates": expected_days,
        "github_attempts": attempts,
        "source_ledgers": source_ledgers,
    }
    actions_report = reconcile(reconciled_input)
    return {
        "schema": REPORT_SCHEMA,
        "checkpoint": summary["checkpoint"],
        "as_of": summary["as_of"],
        "source_packet_anchors": {slug: anchors[slug] for slug in sorted(anchors)},
        "three_source_rollup": summary,
        "attempt_reconciliation": actions_report,
        "source_original_text_in_report": False,
        "actions_history_exhaustive": False,
        "failed_attempt_artifacts_verified": False,
        "human_checkpoint_signed": False,
        "source_rights_approved": False,
        "desk_qualified": False,
        "production_publication_authorized": False,
        "requires_human_verification": True,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--actions-receipts", required=True,
                    help="independently verified list of all Actions run attempts in JSON")
    ap.add_argument("packets", nargs=3,
                    help="three independently Git-authenticated formal review folders")
    args = ap.parse_args(argv)
    path = Path(args.actions_receipts)
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= MAX_RECEIPTS_BYTES,
            "receipt file missing, symlinked or oversized")
    receipts = strict_json(path.read_text(encoding="utf-8"))
    print(json.dumps(join(args.packets, receipts), sort_keys=True,
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
