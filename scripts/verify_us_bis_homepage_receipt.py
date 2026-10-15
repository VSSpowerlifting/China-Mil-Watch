"""Validate an immutable BIS homepage metadata receipt before source Git admission.

This is a source-free, fail-closed data contract. It does NOT attest that a
scheduled GitHub run occurred; reviewers must independently confirm the event,
workflow run, commit SHA and original official source listing read.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

from scripts import collect_us_bis_homepage_metadata as bis

PACKET_KEYS = {
    "schema", "source_host", "source_family", "publisher", "issuer",
    "collection_mode", "observed_on_utc", "official_listing_url",
    "official_listing_sha256", "rows", "visible_dated_rows",
    "original_titles_copied", "bodies_copied", "document_media_copied",
    "analysis_performed", "publication_authorized_by_collector",
    "production_records_written", "complete_publisher_history_claimed",
}
ROW_KEYS = {
    "source_identity", "canonical_official_url", "publisher_posted_date",
    "official_issuer", "official_publisher", "publisher_listing_url",
}
FALSE_FLAGS = (
    "original_titles_copied", "bodies_copied", "document_media_copied",
    "analysis_performed", "publication_authorized_by_collector",
    "complete_publisher_history_claimed",
)
PUBLISHER = "U.S. Department of Commerce, Bureau of Industry and Security"


def iso_day(value):
    bis.need(type(value) is str and re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value),
             "invalid_receipt_day")
    try:
        actual = date.fromisoformat(value).isoformat()
    except ValueError:
        raise bis.BISHold("invalid_receipt_day") from None
    bis.need(actual == value, "invalid_receipt_day")
    return actual


def verify(packet, *, expected_day=None):
    """Reject foreign provenance, extra fields, date drift and invented source rows."""
    bis.need(type(packet) is dict and set(packet) == PACKET_KEYS,
             "receipt_schema_fields_disagree")
    expected = {
        "schema": bis.SCHEMA,
        "source_host": bis.HOST,
        "source_family": bis.FAMILY,
        "publisher": PUBLISHER,
        "issuer": bis.ISSUER,
        "collection_mode": "bounded_exact_homepage_metadata_only",
        "official_listing_url": bis.INDEX,
    }
    for key, value in expected.items():
        bis.need(packet[key] == value, "foreign_or_changed_" + key)
    day = iso_day(packet["observed_on_utc"])
    if expected_day is not None:
        bis.need(day == iso_day(expected_day), "source_day_disagrees")
    bis.need(type(packet["official_listing_sha256"]) is str and
             re.fullmatch(r"[0-9a-f]{64}", packet["official_listing_sha256"]) is not None,
             "invalid_listing_digest")
    for flag in FALSE_FLAGS:
        bis.need(packet[flag] is False, "publisher_content_or_publication_flag_" + flag)
    bis.need(type(packet["production_records_written"]) is int and
             packet["production_records_written"] == 0, "production_write_disclosed")
    rows = packet["rows"]
    bis.need(type(rows) is list and 1 <= len(rows) <= bis.MAX_ROWS,
             "invalid_bounded_row_count")
    bis.need(type(packet["visible_dated_rows"]) is int and
             packet["visible_dated_rows"] == len(rows), "row_count_mismatch")
    seen = set()
    for row in rows:
        bis.need(type(row) is dict and set(row) == ROW_KEYS,
                 "untrusted_row_fields")
        canonical = bis.canonical(row["canonical_official_url"])
        bis.need(canonical is not None and
                 row["canonical_official_url"] == canonical[0],
                 "untrusted_press_release_url")
        bis.need(row["source_identity"] == "us-bis-homepage-press:" + canonical[1],
                 "foreign_or_conflicting_identity")
        bis.need(row["source_identity"] not in seen, "duplicate_press_identity")
        seen.add(row["source_identity"])
        bis.need(row["official_issuer"] == bis.ISSUER and
                 row["official_publisher"] == bis.HOST and
                 row["publisher_listing_url"] == bis.INDEX,
                 "foreign_or_mismatched_source_provenance")
        posted = iso_day(row["publisher_posted_date"])
        bis.need("2025-01-01" <= posted <= day,
                 "source_posted_date_out_of_range")
    bis.need(rows == sorted(rows, key=lambda r:
             (r["publisher_posted_date"], r["source_identity"]), reverse=True),
             "noncanonical_row_order")
    return len(rows)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--expected-day", required=True)
    args = parser.parse_args(argv)
    try:
        bis.need(args.packet.is_file() and not args.packet.is_symlink(),
                 "missing_or_symlink_receipt")
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
        count = verify(packet, expected_day=args.expected_day)
    except (bis.BISHold, ValueError, OSError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, bis.BISHold) else "unreadable_receipt"
        print(json.dumps({"schema": bis.SCHEMA, "status": "HOLD",
                          "reason": reason, "source_day_qualified": False},
                         sort_keys=True))
        return 2
    print(json.dumps({"schema": bis.SCHEMA, "status": "PASS_SOURCE_METADATA_RECEIPT",
                      "verified_rows": count, "source_day_qualified": False,
                      "production_writes": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
