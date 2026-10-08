"""Attest a fixed Sunday Vietnam research roster against CURRENT verified MPS state.

Read-only/offline to publishers. A verified shadow checkout, current immutable
capture/version chain and exact-week private source notes must rederive EVERY
Vietnam research row actually offered to the Sunday writer. This is not source
rights, human fact review, or publication approval. No Japan rows are rewritten.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path

from scripts import review_vietnam_shadow_state as formal
from scripts.build_vietnam_sunday_packet import build
from scripts.prepare_vietnam_briefs_evidence import (
    FIELDS, SCHEMA, STATUS, VietnamFeederError, canonical_json, load, require,
    window,
)

ROOT = Path(__file__).resolve().parents[1].resolve()
BRANCH = "shadow/vietnam-mps-foreign-affairs"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
MAX_VIETNAM = 3


def attest(*, state_repo, state_commit, week_ending, notes, offered_packet,
           require_all_eligible=False):
    """Refuse static/stale/uncited Vietnam roster; do not mutate the offered file."""
    window(week_ending)
    require(type(require_all_eligible) is bool,
            "all-eligible strictness must be an explicit boolean")
    offered = load(offered_packet, 40000)
    require(isinstance(offered, dict) and
            set(offered) == {"schema", "week_ending", "status", "items"} and
            offered["schema"] == SCHEMA and offered["status"] == STATUS and
            offered["week_ending"] == week_ending and
            isinstance(offered["items"], list) and len(offered["items"]) <= 8,
            "Sunday packet is not an exact-week bounded private evidence file")
    items = offered["items"]
    require(all(isinstance(x, dict) and set(x) == FIELDS for x in items),
            "Sunday research item has unexpected or incomplete fields")
    ids = [x["id"] for x in items]
    urls = [x["source_url"] for x in items]
    require(len(ids) == len(set(ids)) and len(urls) == len(set(urls)),
            "Sunday packet duplicates official research sources")
    offered_vn = [x for x in items if x["desk"] == "vietnam"]
    require(1 <= len(offered_vn) <= MAX_VIETNAM,
            "strict Vietnam Sunday preview requires one to three research rows")
    require(isinstance(state_commit, str) and HEX40.fullmatch(state_commit),
            "current exact shadow state commit required")

    # Existing audited builder checks complete Git ancestry, isolated branch,
    # original capture bytes, SQLite integrity and full content-version chain.
    # It does not fetch the ministry, send to a model, or approve source use.
    with tempfile.TemporaryDirectory(prefix="ipr-vn-roster-") as tmp:
        dest = Path(tmp) / (week_ending + ".json")
        result = build(
            state_repo=state_repo, state_commit=state_commit,
            week_ending=week_ending, notes=notes, output=dest,
            require_vietnam=True)
        current = load(dest, 40000)
    fresh = {x["id"]: x for x in current["items"] if x["desk"] == "vietnam"}
    snapshot = {x["id"]: x for x in offered_vn}
    require(len(fresh) == len(snapshot) and set(fresh) == set(snapshot),
            "static Sunday Vietnam IDs differ from current verified sources")
    repo = formal.resolve_state_repo(state_repo)
    for ident, old in snapshot.items():
        latest = fresh[ident]
        require(isinstance(old["state_commit"], str) and
                HEX40.fullmatch(old["state_commit"]),
                "unverified static Vietnam shadow SHA")
        # A research row may cite an older original capture commit, but that
        # commit must genuinely belong to this one MPS orphan state branch.
        formal.verify_state_commit(repo, old["state_commit"], BRANCH)
        # The only intentionally mutable property is the state-commit pointer:
        # latest may be newer even if the official article body is unchanged.
        keys = FIELDS - {"state_commit"}
        require(all(old[key] == latest[key] for key in keys),
                "static Sunday Vietnam facts or source digests are stale")
    observed = result["in_window_machine_eligible"]
    if require_all_eligible:
        require(observed == len(fresh),
                "eligible MPS publications lack version-matched private synopses")
    return {
        "schema": "vietnam-sunday-current-roster-attestation/1",
        "week_ending": week_ending,
        "verified_latest_mps_state_commit": state_commit,
        "offered_vietnam_sources": len(snapshot),
        "current_source_version_matches": len(fresh),
        "in_window_machine_eligible": observed,
        "all_eligible_notes_required": require_all_eligible,
        "new_or_missing_offered_ids": 0,
        "source_version_drift": 0,
        "other_desks_unmodified": True,
        "full_reporting_week_collection_verified": False,
        "publisher_silence_verified": False,
        "original_article_bodies_exported": False,
        "source_use_approved": False,
        "human_review_approved": False,
        "production_writes": 0,
        "model_called": False,
        "email_sent": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state-repo", required=True, type=Path)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--week-ending", required=True)
    p.add_argument("--notes", required=True, type=Path)
    p.add_argument("--offered-packet", required=True, type=Path)
    p.add_argument("--require-all-eligible", action="store_true")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    target = args.out
    resolved = target.resolve()
    require(not target.exists() and not target.is_symlink() and
            target.parent.is_dir() and not target.parent.is_symlink() and
            resolved != ROOT and ROOT not in resolved.parents,
            "private attestation output must be new and outside repository")
    report = attest(
        state_repo=args.state_repo, state_commit=args.state_commit,
        week_ending=args.week_ending, notes=args.notes,
        offered_packet=args.offered_packet,
        require_all_eligible=args.require_all_eligible)
    target.write_text(canonical_json(report), encoding="utf-8")
    print(json.dumps({
        "mps_sources_version_matched": report["current_source_version_matches"],
        "in_window_machine_eligible": report["in_window_machine_eligible"],
        "no_editorial_or_publication_approval": True,
        "email_sent": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
