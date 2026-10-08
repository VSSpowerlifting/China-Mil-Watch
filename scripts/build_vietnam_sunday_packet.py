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

from scripts import prepare_vietnam_mps_review_queue as queue_builder
from scripts.prepare_vietnam_briefs_evidence import (
    VietnamFeederError, canonical_json, load, make_packet, require, window,
)


def build(*, state_repo, state_commit, week_ending, notes, output,
          existing=None):
    """Build only after complete immutable state-tree, raw-capture and DB audit."""
    window(week_ending)
    out = Path(output)
    require(out.name == week_ending + ".json",
            "private research packet name must be exact reporting Saturday")
    require(not out.exists() and not out.is_symlink(),
            "refuse to overwrite previous country research")
    require(out.parent.is_dir() and not out.parent.is_symlink(),
            "output parent must already exist")
    previous = load(existing, 40000) if existing else None
    authored = load(notes, 20000)
    # The queue builder verifies exact shadow Git commit, source state tree,
    # raw capture receipts, SQLite identity and entire version chain before
    # generating its machine-only queue. No source text is serialized here.
    with tempfile.TemporaryDirectory(prefix="ipr-vn-sunday-") as temp:
        queue_dir = Path(temp) / "machine-queue"
        queue_builder.prepare(state_repo, state_commit, queue_dir)
        packet = make_packet(
            load(queue_dir / "review_queue.json", 90000),
            authored, week_ending, previous=previous)
    out.write_text(canonical_json(packet), encoding="utf-8")
    return {
        "week_ending": week_ending,
        "vietnam_sources": sum(item["desk"] == "vietnam"
                               for item in packet["items"]),
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
    p.add_argument("--notes", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--existing", type=Path)
    args = p.parse_args(argv)
    result = build(
        state_repo=args.state_repo, state_commit=args.state_commit,
        week_ending=args.week_ending, notes=args.notes, output=args.out,
        existing=args.existing)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
