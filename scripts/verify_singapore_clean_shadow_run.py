"""Verify a genuine successful Singapore MINDEF shadow slot, read-only.

Unlike the old green workflow status, this checks the *source attempt counters*
and the pinned media-only infographic from the new extraction-parity path.
It is an evidence/qualification verifier, not production or publication.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

URL = ("https://www.mindef.gov.sg/news-and-events/"
       "latest-releases/22sep26-infographic/")
TITLE = "Infographic: Ex Trident Resolve 2026"
EMPTY_SHA = hashlib.sha256(b"").hexdigest()
COMMIT = re.compile(r"[a-f0-9]{40}\Z")
RUN = re.compile(r"[0-9]{9,16}\Z")
CANONICAL = re.compile(
    r"https://www\.mindef\.gov\.sg/news-and-events/latest-releases/"
    r"[a-zA-Z0-9_-]+/\Z"
)


class ShadowHold(ValueError):
    """No source body or hidden state in human-readable refusal messages."""


def require(test, reason):
    if not test:
        raise ShadowHold(reason)


def _nonnegative(row, name):
    value = row.get(name)
    require(type(value) is int and value >= 0, "invalid_" + name)
    return value


def verify(state_checkout, *, run_id, collector_sha):
    root = Path(state_checkout).resolve()
    require(RUN.fullmatch(str(run_id)) is not None,
            "expected_scheduled_run_id_required")
    require(type(collector_sha) is str and COMMIT.fullmatch(collector_sha),
            "expected_collector_commit_required")
    require(root.is_dir() and root.name != "repo", "shadow_checkout_unavailable")
    state = root / "state"
    ledger = state / "ledger"
    require(state.is_dir() and not state.is_symlink()
            and ledger.is_dir() and not ledger.is_symlink(),
            "shadow_state_or_ledger_missing")
    matches = sorted(ledger.glob("*-" + str(run_id) + ".json"))
    require(len(matches) == 1 and matches[0].is_file()
            and not matches[0].is_symlink(), "exact_scheduled_ledger_missing")
    try:
        data = json.loads(matches[0].read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        raise ShadowHold("unreadable_scheduled_ledger") from None
    require(type(data) is dict and data.get("run_id") == str(run_id),
            "run_identity_mismatch")
    require(data.get("collector_commit") == collector_sha,
            "collector_commit_does_not_match_github_actions")
    require(data.get("health") == "ok"
            and data.get("result") in ("ok", "ok_all_duplicates"),
            "shadow_attempt_not_successful")
    require(data.get("robots_status") == "allowed"
            and data.get("listing_status") == "ok",
            "official_singapore_listing_not_confirmed")
    selected = _nonnegative(data, "selected")
    discovered = _nonnegative(data, "discovered")
    retrieved = _nonnegative(data, "retrieved")
    inserted = _nonnegative(data, "inserted")
    duplicates = _nonnegative(data, "duplicates")
    stored = _nonnegative(data, "stored_total")
    unavailable = _nonnegative(data, "text_unavailable")
    require(0 < selected <= 40 and selected <= discovered
            and retrieved == selected
            and inserted + duplicates == selected,
            "selected_originals_not_completely_accounted_for")
    for key in ("access_failures", "fetch_failures", "extraction_failures"):
        require(_nonnegative(data, key) == 0, "incomplete_" + key)
    require(data.get("failure_log") == [],
            "unreported_or_tampered_source_failures")
    urls = data.get("media_only_urls")
    require(type(urls) is list and len(urls) == unavailable
            and len(urls) == len(set(urls)) and URL in urls
            and all(type(u) is str and CANONICAL.fullmatch(u) for u in urls),
            "image_only_release_not_identified_from_real_collection")
    logical_date = data.get("target_date")
    require(type(logical_date) is str
            and date.fromisoformat(logical_date).isoformat() == logical_date,
            "invalid_logical_collection_date")
    require(data.get("target_date_source") == "schedule-slot",
            "manual_or_replayed_run_not_a_genuine_scheduled_slot")
    # Do not open the original shadow DB read-write: even a SELECT can leave
    # a WAL/SHM beside this Git-backed evidence snapshot.
    db_file = state / "shadow.db"
    require(db_file.is_file() and not db_file.is_symlink(),
            "original_state_database_unavailable")
    con = None
    try:
        con = sqlite3.connect(db_file.as_uri() + "?mode=ro&immutable=1",
                              uri=True)
        require(con.execute("PRAGMA quick_check").fetchone()[0] == "ok",
                "shadow_database_integrity_failure")
        count = con.execute("SELECT COUNT(*) FROM shadow_records").fetchone()[0]
        require(count == stored, "stored_original_count_disagrees_with_ledger")
        for u in urls:
            row = con.execute(
                "SELECT title_original,text_original,published_date,"
                "content_sha256,source_slug FROM shadow_records WHERE url=?",
                (u,),
            ).fetchone()
            require(row is not None and row[1] == ""
                    and row[3] == EMPTY_SHA
                    and row[4] == "sg_mindef_releases",
                    "media_only_publisher_original_not_preserved")
            if u == URL:
                require(row[0] == TITLE and row[2] == "2026-09-22",
                        "real_infographic_title_or_date_drift")
    except sqlite3.Error:
        raise ShadowHold("inaccessible_or_incompatible_shadow_database") from None
    finally:
        if con is not None:
            con.close()
    return {
        "status": "VERIFIED_SINGAPORE_SCHEDULED_SHADOW_SLOT",
        "source": "sg_mindef_releases",
        "run_id": str(run_id),
        "collector_commit": collector_sha,
        "logical_date": logical_date,
        "selected_originals": selected,
        "fully_retrieved_originals": retrieved,
        "new_originals": inserted,
        "duplicates": duplicates,
        "stored_originals": stored,
        "publisher_media_only_without_invented_text": unavailable,
        "known_infographic_verified": True,
        "collection_failures": 0,
        "production_rows_admitted": 0,
        "publication_authorized": False,
        "new_reliability_day_proven": True,
        "historical_failed_days_reclassified": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state-checkout", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--collector-sha", required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(verify(args.state_checkout, run_id=args.run_id,
                                collector_sha=args.collector_sha),
                         sort_keys=True))
        return 0
    except (ShadowHold, OSError, ValueError) as exc:
        reason = (str(exc) if isinstance(exc, ShadowHold)
                  else "unavailable_or_invalid_shadow_evidence")
        print(json.dumps({"status": "HOLD", "reason": reason,
                          "production_rows_admitted": 0,
                          "publication_authorized": False},
                         sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
