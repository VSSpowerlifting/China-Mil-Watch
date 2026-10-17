"""Reconcile AFP's first 22 captured originals with the Oct 15 23rd original.

Read only a literal original Git commit chain via existing per-run capture+SQLite
verifiers. Produces an unsigned metadata-only 23-source review docket, never a
rights/source approval, collector activation, DB write or public-site input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from scripts.prepare_ph_afp_review_docket import build_docket
from scripts.prepare_ph_afp_run_review import FrozenState, make_packet
from scripts.private_country_desk_reader import build as private_read

LATEST = "8a63ba423818e30d147096fd1a32949cf6905ee5"
BATCHES = (
    ("492001f34ba6176169b6acc96a237f05592a3395", "37631681338-1", 13, "2026-10-07"),
    ("c668790ce3be88b08b3300b945bad58589b3a5b1", "37788547061-1", 5, "2026-10-08"),
    ("4dd40b9655ec53fe4fae829eb12ba21032946b25", "38562843186-1", 4, "2026-10-14"),
    (LATEST, "38731523240-1", 1, "2026-10-15"),
)
TOTAL = sum(n for _, _, n, _ in BATCHES)


class ReviewReconciliationHold(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise ReviewReconciliationHold(reason)


def _safe_git(repo, *args):
    try:
        return subprocess.run(["git", "-C", str(repo), *args], timeout=25,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              check=True).stdout.decode("utf-8").strip()
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise ReviewReconciliationHold("pinned_source_git_history_unavailable") from exc


def validate_git(repo):
    repo = Path(repo)
    need(repo.is_dir() and not repo.is_symlink(), "missing_shadow_git_checkout")
    branch_head = _safe_git(repo, "rev-parse", "HEAD")
    need(len(branch_head) == 40, "invalid_shadow_git_head")
    for commit, _, _, _ in BATCHES:
        need(_safe_git(repo, "cat-file", "-t", commit) == "commit",
             "missing_frozen_afp_git_commit")
        # A newer source state is allowed, but cannot be substituted for the
        # frozen Oct 15 data. The actual original commits must remain reachable.
        _safe_git(repo, "merge-base", "--is-ancestor", commit, branch_head)
        need(_safe_git(repo, "ls-tree", "--name-only", commit) == "state",
             "afp_source_branch_contains_other_files")
    for previous, following in zip(BATCHES, BATCHES[1:]):
        _safe_git(repo, "merge-base", "--is-ancestor", previous[0], following[0])
    return branch_head


def reconcile(docket, private):
    """Pure reconciliation of source-verified, still-unsigned metadata reports."""
    need(type(docket) is dict and
         docket.get("protocol") == "ipr_ph_afp_metadata_review_docket_v1" and
         docket.get("source") == "philippines_afp_shadow" and
         docket.get("total_source_records") == TOTAL and
         docket.get("body_unavailable_records") == 0 and
         docket.get("source_bodies_or_raw_api_responses_included") is False and
         docket.get("human_review_completed") is False and
         docket.get("source_reuse_approved") is False and
         docket.get("production_eligible") is False and
         docket.get("weekly_ai_writer_eligible") is False and
         docket.get("automated_review_decisions") == 0,
         "docket_scope_or_authorization_drift")
    batches = docket.get("batches")
    need(type(batches) is list and len(batches) == len(BATCHES),
         "missing_historical_capture_batch")
    reviewed_by_id = {}
    for batch, (sha, run, count, day) in zip(batches, BATCHES):
        need(type(batch) is dict and
             batch.get("historical_state_commit") == sha and
             batch.get("run_id") == run and
             batch.get("target_date") == day and
             batch.get("new_records") == count and
             type(batch.get("records")) is list and len(batch["records"]) == count,
             "historical_capture_batch_changed")
        for rec in batch["records"]:
            need(type(rec) is dict and rec.get("review_status") == "not_started"
                 and rec.get("human_review_authenticated") is False
                 and rec.get("source_identity") not in reviewed_by_id
                 and isinstance(rec.get("source_url"), str)
                 and isinstance(rec.get("published_date"), str)
                 and isinstance(rec.get("title_original"), str)
                 and isinstance(rec.get("capture_sha256"), str)
                 and isinstance(rec.get("text_sha256"), str),
                 "source_review_record_or_capture_missing")
            reviewed_by_id[rec["source_identity"]] = (rec, run)
    need(len(reviewed_by_id) == TOTAL, "duplicate_or_missing_original_capture")
    need(type(private) is dict and
         private.get("schema") == "ipr-private-shadow-desk-reader/1" and
         private.get("status") == "private_research_not_source_admitted" and
         private.get("desk_filter") == "philippines" and
         private.get("query") == "" and private.get("truncated") is False and
         private.get("source_body_text_exported") is False and
         private.get("automated_source_rights_approved") is False and
         private.get("human_source_review_completed") is False and
         private.get("public_release_authorized") is False and
         private.get("production_records_changed") is False and
         private.get("country_desks_promoted") is False,
         "source_reader_approval_or_scope_drift")
    sources, records = private.get("sources"), private.get("results")
    need(type(sources) is list and len(sources) == 1 and
         sources[0].get("source_slug") == "ph_afp_articles" and
         sources[0].get("country") == "philippines" and
         sources[0].get("state_commit") == LATEST and
         sources[0].get("stored_records") == TOTAL and
         sources[0].get("query_matches") == TOTAL and
         type(records) is list and len(records) == TOTAL and
         private.get("matched_total") == TOTAL,
         "incomplete_current_afp_state")
    current_ids = set()
    for r in records:
        need(type(r) is dict and
             r.get("source_slug") == "ph_afp_articles" and
             r.get("state_commit") == LATEST and
             r.get("country") == "philippines" and
             r.get("review_status") == "not_human_reviewed_for_public_use",
             "untrusted_current_source_row")
        identity = r.get("identity")
        need(identity not in current_ids and identity in reviewed_by_id,
             "new_or_missing_identity_not_in_review_docket")
        current_ids.add(identity)
        original, original_run = reviewed_by_id[identity]
        need(r.get("url") == original["source_url"] and
             r.get("title") == original["title_original"] and
             r.get("published_date") == original["published_date"] and
             r.get("first_seen_run") == original_run,
             "current_source_version_disagrees_with_original_capture")
    need(current_ids == set(reviewed_by_id), "missing_original_from_current_state")
    new_record = batches[-1]["records"][0]
    need(new_record["source_identity"] not in {
        r["source_identity"] for b in batches[:-1] for r in b["records"]},
        "latest_record_already_in_22_original_cohort")
    return {
        "protocol": "ipr_afp_23_originals_reconciled_unsigned/1",
        "source_commit": LATEST,
        "previously_pinned_originals": TOTAL - 1,
        "new_originals": 1,
        "total_pinned_originals": TOTAL,
        "new_original_run_id": BATCHES[-1][1],
        "new_original_source_identity": new_record["source_identity"],
        "new_original_capture_sha256": new_record["capture_sha256"],
        "new_original_text_sha256": new_record["text_sha256"],
        "all_bodies_present_in_captured_review_packets": True,
        "all_human_reviews_complete": False,
        "source_rights_approved": False,
        "production_admission_authorized": False,
        "publication_authorized": False,
    }


def build(repo):
    validate_git(repo)
    packets = [make_packet(FrozenState(repo, sha), run)
               for sha, run, _, _ in BATCHES]
    docket = build_docket(packets)
    reader = private_read(
        ["ph_afp_articles,%s,%s" % (Path(repo).absolute(), LATEST)],
        country="philippines", max_results=300)
    receipt = reconcile(docket, reader)
    return receipt, docket


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state-repo", required=True, type=Path)
    p.add_argument("--docket-out", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        receipt, docket = build(args.state_repo)
        dest = args.docket_out
        need(dest.is_absolute() and dest.parent.is_dir() and
             not dest.is_symlink() and not dest.exists(),
             "unsafe_metadata_only_output_destination")
        with dest.open("x", encoding="utf-8") as f:
            json.dump(docket, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.write("\n")
        print(json.dumps(receipt, sort_keys=True))
    except (ReviewReconciliationHold, OSError, ValueError, TypeError) as exc:
        # No raw original, title or URL in error diagnostics.
        print(json.dumps({"status": "HOLD",
                          "reason": (str(exc) if isinstance(exc, ReviewReconciliationHold)
                                     else "pinned_source_read_failed"),
                          "production_admission_authorized": False}),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
