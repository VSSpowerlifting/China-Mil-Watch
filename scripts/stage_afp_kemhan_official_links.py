"""Read-only AFP/Kemhan held metadata staging from exact preserved Git commit.

Reads real pinned source evidence through the existing private research reader.
No public archive, production database, Pages, collector or source branch writes.
"""
from __future__ import annotations

import argparse
import json
import sys

from core.crossdesk_official_metadata_candidates import IntakeHold, FAMILIES, build
from scripts.private_country_desk_reader import ReaderHold, build as private_build


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--family", choices=sorted(FAMILIES), required=True)
    parser.add_argument("--source-checkout", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--count-only", action="store_true",
                        help="Only emit non-sensitive totals and digest; no URLs")
    args = parser.parse_args(argv)
    try:
        desk = FAMILIES[args.family]["desk"]
        report = private_build(
            [",".join((args.family, args.source_checkout, args.source_commit))],
            country=desk, max_results=300)
        packet = build(report, args.family)
        if args.count_only:
            print(json.dumps({
                "schema": packet["schema"],
                "source_family": packet["source_family"],
                "source_git_commit": packet["source_git_commit"],
                "candidate_count": packet["candidate_count"],
                "semantic_exception_count": packet["semantic_exception_count"],
                "metadata_manifest_sha256": packet["metadata_manifest_sha256"],
                "all_candidates_held": True,
                "production_import_enabled": False,
                "public_release_enabled": False,
                "source_originals_authenticated_by_this_stage": False,
            }, sort_keys=True))
        else:
            print(json.dumps(packet, ensure_ascii=False, sort_keys=True))
    except (IntakeHold, ReaderHold, OSError, ValueError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, (IntakeHold, ReaderHold)) else (
            "source_checkout_or_snapshot_unavailable")
        # Do not expose source URLs, publisher titles or text in error output.
        if reason not in {
            "unapproved_metadata_source_family", "private_reader_schema_drift",
            "private_reader_not_full_held_evidence",
            "incomplete_source_family_snapshot", "source_git_commit_not_pinned",
            "date_not_string", "invalid_publisher_date", "noncanonical_publisher_date",
            "invalid_official_identity_or_url", "noncanonical_or_foreign_official_url",
            "invalid_afp_official_identity", "invalid_kemhan_official_identity",
            "invalid_kemhan_path_date", "kemhan_date_and_url_disagree",
            "source_version_or_review_state_drift",
            "duplicate_source_identity_or_url",
        }:
            reason = "pinned_source_validation_failed"
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_changed": False,
                          "publication_performed": False}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
