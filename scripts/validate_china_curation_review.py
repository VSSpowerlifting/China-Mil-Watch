#!/usr/bin/env python3
"""Validate the China editorial review ledger; never select or publish records.

This checks identity, structure and workflow completeness. It CANNOT establish
the accuracy of a reviewed claim, authenticate a reviewer, or authorize release.
No DB, site output, source file or Brief is written.
"""
import argparse
from collections import Counter
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "output" / "corpus-index.json"
REQUIRED_FIELDS = ["id", "date", "source", "state", "title_en", "title_orig"]
DISPOSITIONS = frozenset({
    "retain_primary", "retain_context", "group_secondary",
    "exclude_discovery", "hold_quality",
})
REVIEW_STAGES = ("triage", "source_checked", "owner_approved")
EVIDENCE_KINDS = frozenset({
    "stored_record", "publisher_original", "independent_republication",
    "historical_capture", "editorial_brief",
})
QUALITY_STATES = frozenset({"complete", "partial", "contaminated", "unknown"})


def _date(value, label):
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError:
        raise ValueError("%s is not an ISO publication/review date" % label) from None


def _nonblank(text, field, min_chars=1):
    if not isinstance(text, str) or len(text.strip()) < min_chars:
        raise ValueError("%s must be nonblank (%s chars)" % (field, min_chars))


def _index_records(index):
    if index.get("fields") != REQUIRED_FIELDS:
        raise ValueError("unexpected corpus-index field schema")
    sources, states = index["sources"], index["states"]
    protected = index.get("trail_ids")
    if not isinstance(protected, list) or len(set(protected)) != len(protected):
        raise ValueError("missing or duplicate published trail IDs")
    rows = {}
    for row in index["records"]:
        if not isinstance(row, list) or len(row) != len(REQUIRED_FIELDS):
            raise ValueError("unexpected corpus-index record shape")
        ident, day, source, state, title_en, title_orig = row
        if (type(ident) is not int or ident <= 0 or ident in rows
                or type(source) is not int or type(state) is not int
                or not 0 <= source < len(sources) or not 0 <= state < len(states)):
            raise ValueError("invalid/duplicate corpus-index record")
        _date(day, "record date")
        if not isinstance(title_en, str) or not isinstance(title_orig, str):
            raise ValueError("missing source title")
        src = sources[source]
        rows[ident] = {
            "source": src["code"],
            "desk": (src.get("desk") or {}).get("code"),
            "date": day,
            "title": title_orig or title_en,
            "state": states[state]["code"],
            "trail": ident in protected,
        }
    if not set(protected).issubset(rows):
        raise ValueError("unknown published Brief trail ID")
    return rows


def _validate_evidence(items, ident):
    if not isinstance(items, list):
        raise ValueError("record %d evidence must be an array" % ident)
    for entry in items:
        if not isinstance(entry, dict) or set(entry) != {"kind", "url"}:
            raise ValueError("record %d evidence requires kind and URL" % ident)
        if entry["kind"] not in EVIDENCE_KINDS:
            raise ValueError("unknown evidence kind for record %d" % ident)
        url = entry["url"]
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("evidence URL must use HTTPS")
        parsed = urlparse(url)
        if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("invalid or fragment-only evidence URL")


def _validate_check(entry, ident, stage):
    check = entry.get("source_check")
    if stage == "triage":
        if check is not None:
            raise ValueError("triage record %d cannot imply checked source" % ident)
        if entry.get("owner_approval") is not None:
            raise ValueError("triage cannot claim owner approval")
        return
    if not isinstance(check, dict) or set(check) != {
        "checked_by", "checked_on", "capture_quality", "issuer", "verification_note"
    }:
        raise ValueError("source-checked record %d needs complete review receipt" % ident)
    _nonblank(check["checked_by"], "checked_by", 2)
    _date(check["checked_on"], "checked_on")
    if check["capture_quality"] not in QUALITY_STATES:
        raise ValueError("unsupported capture quality")
    _nonblank(check["issuer"], "issuer (use unknown if uncertain)", 2)
    _nonblank(check["verification_note"], "verification_note", 25)
    if not entry["evidence"] or not any(x["kind"] != "stored_record" for x in entry["evidence"]):
        raise ValueError("source check cannot rely only on an IPR stored record")
    if stage == "owner_approved":
        approval = entry.get("owner_approval")
        if not isinstance(approval, dict) or set(approval) != {"approved_by", "approved_on"}:
            raise ValueError("owner approval must have separate explicit receipt")
        _nonblank(approval["approved_by"], "approved_by", 2)
        _date(approval["approved_on"], "approved_on")
        if entry["disposition"] == "hold_quality":
            raise ValueError("quality holds cannot receive editorial approval")
        if check["capture_quality"] in ("contaminated", "unknown"):
            raise ValueError("uncertain/contaminated text cannot be approved")
    elif entry.get("owner_approval") is not None:
        raise ValueError("only owner_approved stage can carry approval receipt")


def validate_ledger(index, ledger):
    """Check ID continuity, explicit review states and duplicate relations.

    Returns aggregate review status only; not a publication manifest/allowlist.
    """
    if not isinstance(ledger, dict) or ledger.get("version") != 1:
        raise ValueError("ledger version must be 1")
    if ledger.get("scope") != "china" or ledger.get("publication_enabled") is not False:
        raise ValueError("ledger must be China-only and publication-disabled")
    if ledger.get("purpose") != "internal_editorial_review":
        raise ValueError("review ledger cannot be reused as a publication manifest")
    snapshot = index.get("snapshot")
    if not isinstance(snapshot, dict) or type(snapshot.get("records")) is not int:
        raise ValueError("invalid index snapshot")
    baseline = ledger.get("baseline_snapshot")
    if not isinstance(baseline, dict) or type(baseline.get("records")) is not int:
        raise ValueError("invalid baseline snapshot")
    _date(baseline.get("date"), "baseline date")
    _date(snapshot.get("date"), "corpus date")
    if snapshot["date"] < baseline["date"] or snapshot["records"] < baseline["records"]:
        raise ValueError("index older/smaller than the ledger baseline; inspect custody")
    records = _index_records(index)
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("decisions must be an array")
    by_id = {}
    for entry in decisions:
        if not isinstance(entry, dict):
            raise ValueError("each decision must be an object")
        required = {
            "id", "source", "published_date", "source_title", "review_stage",
            "disposition", "rationale", "evidence", "source_check",
            "owner_approval", "representative_id",
        }
        if set(entry) != required:
            raise ValueError("decision fields missing or unrecognized")
        ident = entry["id"]
        if type(ident) is not int or ident in by_id:
            raise ValueError("duplicate/invalid review record ID")
        record = records.get(ident)
        if record is None or record["desk"] != "china":
            raise ValueError("review record %d missing/non-China" % ident)
        if (entry["source"] != record["source"]
                or entry["published_date"] != record["date"]
                or entry["source_title"] != record["title"]):
            raise ValueError("record %d source identity/date/title drift" % ident)
        if entry["review_stage"] not in REVIEW_STAGES:
            raise ValueError("unsupported review stage")
        if entry["disposition"] not in DISPOSITIONS:
            raise ValueError("unsupported editorial disposition")
        _nonblank(entry["rationale"], "rationale", 25)
        _validate_evidence(entry["evidence"], ident)
        _validate_check(entry, ident, entry["review_stage"])
        rep = entry["representative_id"]
        if entry["disposition"] == "group_secondary":
            if type(rep) is not int or rep == ident:
                raise ValueError("group_secondary must name a distinct integer representative")
        elif rep is not None:
            raise ValueError("non-group decision cannot claim representative")
        by_id[ident] = entry

    for ident, entry in by_id.items():
        if entry["disposition"] != "group_secondary":
            continue
        rep = by_id.get(entry["representative_id"])
        if rep is None or rep["disposition"] not in ("retain_primary", "retain_context"):
            raise ValueError("secondary record %d needs reviewed retained representative" % ident)
        if entry["review_stage"] == "owner_approved" and rep["review_stage"] != "owner_approved":
            raise ValueError("approved secondary points to unapproved representative")

    china = sum(r["desk"] == "china" for r in records.values())
    statuses = Counter(e["review_stage"] for e in decisions)
    dispositions = Counter(e["disposition"] for e in decisions)
    protected = sum(records[i]["trail"] for i in by_id)
    return {
        "purpose": "internal_review_status_not_publication",
        "publication_enabled": False,
        "index_snapshot": snapshot,
        "ledger_baseline": baseline,
        "snapshot_advanced": snapshot != baseline,
        "china_preserved": china,
        "china_with_review_dockets": len(by_id),
        "china_unreviewed_preserved": china - len(by_id),
        "brief_trail_records_with_review_dockets": protected,
        "proposed": statuses["triage"],
        "source_checked": statuses["source_checked"],
        "owner_approved": statuses["owner_approved"],
        "dispositions": dict(sorted(dispositions.items())),
        "approved_primary_or_context_candidates": sum(
            e["review_stage"] == "owner_approved"
            and e["disposition"] in ("retain_primary", "retain_context")
            for e in decisions),
        "safety_note": "No renderer integration. This is not approval or a publication allowlist.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--ledger", type=Path, required=True)
    args = parser.parse_args(argv)
    report = validate_ledger(json.loads(args.index.read_text(encoding="utf-8")),
                             json.loads(args.ledger.read_text(encoding="utf-8")))
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
