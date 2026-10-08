"""Emit provenance-only receipt for a JCG pinned shadow review.

Consumes the independent verifier's report; cannot attest human approval.
Never reads, logs, or copies original archived article bodies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

SHA40 = re.compile(r"[0-9a-f]{40}")


def make_receipt(report, expected_sha, as_of, run_id):
    if not SHA40.fullmatch(expected_sha):
        raise ValueError("exact lower-case 40-character commit required")
    if date.fromisoformat(as_of).isoformat() != as_of:
        raise ValueError("invalid ISO as-of date")
    if not str(run_id).isdigit():
        raise ValueError("numeric Actions run identifier required")
    if (report.get("mode") != "formal_commit_snapshot" or
            report.get("state_ref") != "shadow/japan-jcg" or
            report.get("desk") != "japan_jcg" or
            report.get("state_commit") != expected_sha or
            report.get("as_of") != as_of or
            not isinstance(report.get("state_tree"), str) or
            not SHA40.fullmatch(report["state_tree"])):
        raise ValueError("review is not pinned to exact Japan JCG state")
    if report.get("human_review_completed") is not False or report.get("promotion_authorized") is not False:
        raise ValueError("a machine report may not assert human approval/promotion")
    for key in ("records", "ledgers"):
        if not isinstance(report.get(key), int) or report[key] < 0:
            raise ValueError("invalid record or ledger count")
    if report["ledgers"] < 1:
        raise ValueError("a formal review requires a recorded shadow attempt")
    # A legitimate official-source day may have no publications. Preserve
    # that zero explicitly; do not treat it as failed collection or coverage.
    for key in ("findings", "review_holds", "missing_successful_days"):
        if not isinstance(report.get(key), list) or any(
                not isinstance(item, str) for item in report[key]):
            raise ValueError("missing/invalid review observation list")
    return {
        "schema": "japan-jcg-pinned-shadow-review-receipt/1",
        "desk": "japan_jcg",
        "source_scope": "japan_coast_guard_english_html_only",
        "state_ref": "shadow/japan-jcg",
        "state_commit": expected_sha,
        "state_tree": report["state_tree"],
        "as_of": as_of,
        "actions_run_id": str(run_id),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "reviewed_record_count": report["records"],
        "reviewed_ledger_count": report["ledgers"],
        "machine_findings_count": len(report["findings"]),
        "human_review_holds_count": len(report["review_holds"]),
        "missing_successful_days_count": len(report["missing_successful_days"]),
        "machine_integrity_verdict": (
            "integrity_findings_require_disposition" if report["findings"] else
            "no_records_not_a_coverage_attestation" if not report["records"] else
            "checks_clear_not_human_approved"),
        "human_review_completed": False,
        "promotion_authorized": False,
        "production_database_changed": False,
        "editorial_release_authorized": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--actions-run-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    if a.output.exists():
        p.error("receipt already exists; overwrite refused")
    try:
        content = a.report.read_bytes()
        report = json.loads(content.decode("utf-8"))
        receipt = make_receipt(report, a.state_commit, a.as_of, a.actions_run_id)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        p.error(str(exc))
    receipt["report_sha256"] = hashlib.sha256(content).hexdigest()
    a.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "state_commit": receipt["state_commit"],
        "machine_integrity_verdict": receipt["machine_integrity_verdict"],
        "human_review_completed": False, "promotion_authorized": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
