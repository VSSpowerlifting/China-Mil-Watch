"""Prepare a metadata-only human SOURCE-USE review agenda from current MPS.

This is NOT an authorization, article-body export, translation, synopsis,
publisher-use interpretation, model call, publication or email operation.
An agenda is structurally incompatible with any synopsis permission grant.
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from datetime import timedelta
from pathlib import Path

from core.collection.vietnam_sources import SOURCES
from scripts import prepare_vietnam_mps_review_queue as queues
from scripts import review_vietnam_shadow_state as formal
from scripts.audit_vietnam_weekly_model_readiness import (
    NOTE_SCHEMA, audit, parse_notes,
)
from scripts.draft_vietnam_private_synopses import BRANCH
from scripts.prepare_vietnam_briefs_evidence import (
    SOURCE, VietnamFeederError, canonical_json, load, require,
    verified_queue, window,
)

ROOT = Path(__file__).resolve().parents[1].resolve()
SCHEMA = "vietnam-unapproved-model-source-use-review-agenda/1"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
MAX_CANDIDATES = 20


def build_agenda(queue, notes, week_ending):
    """Produce only missing/stale version-pinned research leads; no source text."""
    saturday = window(week_ending)
    report, _ = audit(queue, notes, week_ending)
    indexed = parse_notes(notes)
    start = saturday - timedelta(days=6)
    todo = []
    for row in verified_queue(queue):
        published = row["published_date"]
        if not start.isoformat() <= published <= week_ending:
            continue
        if row["machine_review_candidate"] is not True or row["machine_blockers"]:
            # Do not invite authorization of machine-held or corrupt material.
            continue
        ident = row["source_identity"]
        url = row["canonical_url"]
        require(SOURCES[SOURCE].identity(url) == ident,
                "source-review agenda contains noncanonical publisher URL")
        title = row["title_original"]
        digest = row["content_sha256"]
        require(isinstance(title, str) and 8 <= len(title.strip()) <= 350
                and "\n" not in title and
                isinstance(digest, str) and HEX64.fullmatch(digest),
                "unsigned review agenda lacks exact original-source metadata")
        note = indexed.get(ident)
        if note is not None and (
                note["content_sha256"] == digest and
                note["source_url"] == url and
                note["published_date"] == published):
            continue  # Already has a matching, still UNAPPROVED private note.
        todo.append({
            "source_identity": ident,
            "publisher_name": "Vietnam Ministry of Public Security",
            "source_url": url,
            "original_title": title,
            "published_date": published,
            "current_content_sha256": digest,
            "shadow_state_commit": queue["state_commit"],
            "research_note_state": ("missing-source-specific-note"
                                    if note is None else "stale-source-version-note"),
            "prior_note_sha256": None if note is None else note["content_sha256"],
            "source_use_review_state": "not-authorized",
            "external_excerpt_authorized": False,
            "ready_for_private_model": False,
            "original_text_in_agenda": False,
            "public_citation_approved": False,
        })
    todo.sort(key=lambda r: (r["published_date"], r["source_identity"]),
              reverse=True)
    require(len(todo) <= MAX_CANDIDATES,
            "bounded agenda capacity exceeded; manual investigation required")
    counts = report["counts"]
    require(len(todo) == counts["awaiting_source_specific_synopsis"] +
            counts["stale_source_version_synopsis"],
            "review agenda and independent readiness counts differ")
    require(isinstance(queue["state_commit"], str)
            and HEX40.fullmatch(queue["state_commit"]),
            "untrusted shadow state commit")
    return {
        "schema": SCHEMA,
        "week_ending": week_ending,
        "verified_shadow_state_commit": queue["state_commit"],
        "source_family": SOURCE,
        "status": "private-human-source-use-review-needed",
        "in_window_machine_eligible": counts["in_window_machine_eligible"],
        "already_has_matching_private_notes": counts["ready_private_model"],
        "missing_or_stale_source_notes": len(todo),
        "machine_held_not_eligible_for_review": counts["machine_held_in_window"],
        "source_version_review_leads": todo,
        "automatically_authorized_source_count": 0,
        "publisher_silence_verified": False,
        "full_week_collection_verified": False,
        "original_article_bodies_included": False,
        "third_party_model_called": False,
        "human_source_use_review_completed": False,
        "production_or_publication_approved": False,
        "editorial_email_sent": False,
    }


def prepare(state_repo, state_commit, week_ending, notes, output):
    """Require current isolated Git tip and full archive-chain validation."""
    require(isinstance(state_commit, str) and HEX40.fullmatch(state_commit),
            "exact MPS state commit required")
    path = Path(output)
    target = path.resolve()
    require(not path.exists() and not path.is_symlink() and
            path.parent.is_dir() and not path.parent.is_symlink() and
            target != ROOT and ROOT not in target.parents,
            "private output must be a new file outside tracked checkout")
    root = formal.resolve_state_repo(state_repo)
    proof = formal.verify_state_commit(root, state_commit, BRANCH)
    require(proof["state_ref_tip"] == state_commit,
            "source-use review must use current MPS shadow branch tip")
    if notes is None:
        authored = {"schema": NOTE_SCHEMA, "entries": []}
    else:
        authored = load(notes, 30000)
    with tempfile.TemporaryDirectory(prefix="ipr-vn-source-use-review-") as tmp:
        qdir = Path(tmp) / "verified-queue"
        queues.prepare(root, state_commit, qdir)
        queue = load(qdir / "review_queue.json", 100000)
    agenda = build_agenda(queue, authored, week_ending)
    path.write_text(canonical_json(agenda), encoding="utf-8")
    return agenda


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state-repo", required=True, type=Path)
    parser.add_argument("--state-commit", required=True)
    parser.add_argument("--week-ending", required=True)
    parser.add_argument("--notes", type=Path,
                        help="optional existing version-pinned notes; an invalid present file fails")
    parser.add_argument("--out", required=True, type=Path)
    a = parser.parse_args(argv)
    result = prepare(a.state_repo, a.state_commit, a.week_ending, a.notes, a.out)
    print(json.dumps({
        "week_ending": result["week_ending"],
        "verified_machine_eligible": result["in_window_machine_eligible"],
        "missing_or_stale": result["missing_or_stale_source_notes"],
        "model_permission_granted": False,
        "email_sent": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
