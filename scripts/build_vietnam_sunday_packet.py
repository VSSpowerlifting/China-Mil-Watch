"""Read-only Vietnam shadow Git state -> one private regional Sunday evidence packet.

A deliberately optional tool for the future Sunday workflow. The caller must
obtain a Git repository with the exact official shadow state commit. No fetch,
source-site network access, SMTP, model call or main-repository write occurs.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]

from scripts import prepare_vietnam_mps_review_queue as queue_builder
from scripts.prepare_vietnam_briefs_evidence import (
    VietnamFeederError, canonical_json, load, make_packet, require, window,
    verified_queue,
)


def build(*, state_repo, state_commit, week_ending, notes, output,
          existing=None, allow_missing_notes=False, require_vietnam=False):
    """Build only after complete immutable state-tree, raw-capture and DB audit."""
    saturday = window(week_ending)
    require(type(allow_missing_notes) is bool and type(require_vietnam) is bool,
            "missing-note and Vietnam-required policies must be explicit booleans")
    out = Path(output)
    require(out.name == week_ending + ".json",
            "private research packet name must be exact reporting Saturday")
    require(not out.exists() and not out.is_symlink(),
            "refuse to overwrite previous country research")
    require(out.parent.is_dir() and not out.parent.is_symlink(),
            "output parent must already exist")
    resolved_out = out.resolve()
    require(ROOT != resolved_out and ROOT not in resolved_out.parents,
            "refuse writing private editorial evidence inside checkout")
    previous = load(existing, 40000) if existing else None
    # Never confuse a genuinely absent catalog with a present but malformed,
    # symlinked or version-stale catalog. Only an EXPLICIT opt-in allows the
    # former to become zero Vietnam sources; the other cases remain fatal.
    note_path = Path(notes) if notes is not None else None
    require(note_path is None or not note_path.is_symlink(),
            "symlinked Vietnam research notes refused")
    missing_notes = note_path is None or not note_path.exists()
    if missing_notes:
        require(allow_missing_notes,
                "Vietnam notes absent; explicit allow_missing_notes required")
        authored = {"schema": "vietnam-editorial-notes/1", "entries": []}
    else:
        authored = load(note_path, 20000)
    # The queue builder verifies exact shadow Git commit, source state tree,
    # raw capture receipts, SQLite identity and entire version chain before
    # generating its machine-only queue. No source text is serialized here.
    with tempfile.TemporaryDirectory(prefix="ipr-vn-sunday-") as temp:
        queue_dir = Path(temp) / "machine-queue"
        queue_builder.prepare(state_repo, state_commit, queue_dir)
        queue = load(queue_dir / "review_queue.json", 90000)
        packet = make_packet(queue, authored, week_ending, previous=previous)
        # The machine-review queue is a first-party inventory, not proof of
        # publisher silence. Expose the actual number of eligible records
        # that were skipped due to a missing private synopsis catalog.
        start = saturday - timedelta(days=6)
        eligible_in_week = sum(
            bool(r.get("machine_review_candidate")) and
            not r.get("machine_blockers") and
            start.isoformat() <= r.get("published_date", "") <= week_ending
            for r in verified_queue(queue)
        )
    vietnam_count = sum(item["desk"] == "vietnam" for item in packet["items"])
    if require_vietnam:
        require(vietnam_count > 0,
                "Vietnam contribution explicitly required; no current approved-for-private-drafting source")
    # Explicitly distinguish two kinds of zero-source model inputs, neither
    # of which implies the ministry was quiet across its full publication scope.
    status = ("ready" if vietnam_count else
              "missing-notes-with-eligible-archives" if missing_notes and eligible_in_week else
              "missing-notes-no-eligible-archives" if missing_notes else
              "no-version-matched-notes" if eligible_in_week else
              "no-eligible-observed-publications")
    out.write_text(canonical_json(packet), encoding="utf-8")
    return {
        "week_ending": week_ending,
        "vietnam_sources": vietnam_count,
        "vietnam_readiness_status": status,
        "notes_catalog_missing": missing_notes,
        "in_window_machine_eligible": eligible_in_week,
        "publisher_silence_verified": False,
        "other_sources": sum(item["desk"] != "vietnam"
                             for item in packet["items"]),
        "production_writes": 0,
        "source_review_approved": False,
        "email_sent": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state-repo", type=Path, required=True)
    p.add_argument("--state-commit", required=True)
    p.add_argument("--week-ending", required=True)
    p.add_argument("--notes", type=Path,
                   help="version-bound synopsis catalog; required unless --allow-missing-notes")
    p.add_argument("--allow-missing-notes", action="store_true",
                   help="opt in to reporting zero Vietnam evidence while preserving other desks")
    p.add_argument("--require-vietnam", action="store_true",
                   help="strict no-send rehearsal: refuse output unless at least one current Vietnam source survives")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--existing", type=Path)
    args = p.parse_args(argv)
    result = build(
        state_repo=args.state_repo, state_commit=args.state_commit,
        week_ending=args.week_ending, notes=args.notes, output=args.out,
        existing=args.existing, allow_missing_notes=args.allow_missing_notes,
        require_vietnam=args.require_vietnam)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
