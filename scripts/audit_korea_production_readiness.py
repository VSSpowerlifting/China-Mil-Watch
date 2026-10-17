"""Read-only, offline Korea Desk source-to-editorial-production reconciliation.

No model access, outbound requests, private draft text, or publication writes.
This audit does NOT establish that scheduled collectors or public HTTPS are live.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

from core.korea_english_publication import public_registry
from core.korea_published_originals import read_release_index
from scripts.send_korea_english_owner_drafts import read_receipts

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ipr-korea-production-readiness-audit/1"
IDENTITY = re.compile(r"korea-policy:[0-9]{9}\Z")


class AuditHold(ValueError):
    """Safe, non-content error code."""


def require(condition, code):
    if not condition:
        raise AuditHold(code)


def assess(root=ROOT, *, as_of=None):
    """Reconcile three independently validated registries; never change state."""
    root = Path(root)
    as_of = as_of or datetime.now(timezone.utc).date()
    require(type(as_of) is date, "korea_readiness_date_invalid")
    research = root / "research"
    source_index = research / "korea_published_original_texts.json"
    source_dir = research / "korea_published_original_texts"
    sources = read_release_index(index=source_index, original_dir=source_dir)
    reviews = public_registry(
        index=research / "korea_english_publications.json",
        directory=research / "korea_english_reviewed",
        source_index=source_index,
        source_dir=source_dir,
    )
    receipts, _ = read_receipts(
        research / "korea_english_draft_handoff_receipts.json"
    )
    by_id = {r["source_identity"]: r for r in sources}
    require(len(by_id) == len(sources), "korea_readiness_source_duplicate")
    released = {record["source_identity"] for record, _, _ in reviews}
    delivered = {}
    for entry in receipts["delivered"]:
        ident = entry["source_identity"]
        require(type(ident) is str and IDENTITY.fullmatch(ident) is not None
                and ident in by_id,
                "korea_readiness_orphan_delivery")
        require(entry["source_sha256"] == by_id[ident]["original_text_sha256"],
                "korea_readiness_receipt_source_version_mismatch")
        require(ident not in delivered, "korea_readiness_duplicate_delivery")
        delivered[ident] = entry

    records = []
    counts = {
        "awaiting_private_draft": 0,
        "awaiting_owner_review": 0,
        "reviewed_english_published": 0,
    }
    for record in sorted(sources, key=lambda r: r["source_identity"]):
        ident = record["source_identity"]
        if ident in released:
            state = "reviewed_english_published"
        elif ident in delivered:
            state = "awaiting_owner_review"
        else:
            state = "awaiting_private_draft"
        counts[state] += 1
        # Only public identities, dates, and SHA digests; never source/draft prose.
        records.append({
            "source_identity": ident,
            "original_sha256": record["original_text_sha256"],
            "publisher_posted_date": record["publisher_posted_date"],
            "editorial_stage": state,
        })
    total = len(records)
    return {
        "schema": SCHEMA,
        "as_of_date": as_of.isoformat(),
        "status": ("NO_PUBLISHED_ORIGINALS" if not total else
                   "EDITORIAL_BACKLOG" if
                   counts["awaiting_private_draft"] or counts["awaiting_owner_review"]
                   else "EDITORIAL_QUEUE_CLEARED"),
        "source_originals_verified_offline": total,
        "reviewed_english_published": counts["reviewed_english_published"],
        "private_drafts_delivered_pending_review": counts["awaiting_owner_review"],
        "private_drafts_not_delivered": counts["awaiting_private_draft"],
        "reviewed_coverage_pct": (
            round(100 * counts["reviewed_english_published"] / total, 1)
            if total else 0.0
        ),
        "online_https_readback": "NOT_CHECKED",
        "scheduled_ingestion_reliability": "NOT_CHECKED",
        "dapa_source_qualification": "NOT_CHECKED",
        "full_desk_production_ready": False,
        "records": records,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--as-of", help="UTC audit date (YYYY-MM-DD)")
    parser.add_argument("--output", type=Path, help="write sanitized JSON artifact")
    args = parser.parse_args(argv)
    try:
        day = (date.fromisoformat(args.as_of) if args.as_of else
               datetime.now(timezone.utc).date())
        report = assess(args.root, as_of=day)
    except Exception:
        # Data/source parsing exceptions may carry private review text.
        # Never echo them, paths, or tracebacks in public Actions logs.
        print(json.dumps({"schema": SCHEMA, "status": "HOLD",
                          "reason_code": "korea_readiness_registry_hold"},
                         sort_keys=True))
        return 2
    rendered = json.dumps(report, sort_keys=True, separators=(",", ":"))
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
