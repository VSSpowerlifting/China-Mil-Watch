#!/usr/bin/env python3
"""Serial, bounded ministry batch; publication is the workflow's success step."""
import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.shadow_collect_vietnam import assert_isolated, host_gate
from scripts.shadow_collect_vietnam_ministry import collect, load_source
from scripts.review_vietnam_ministry_state import inventory, review, require
from scripts.review_vietnam_shadow_state import check_tree
from scripts.review_shadow_state import git, ReviewError

SOURCES = ("vn_mps_foreign_affairs_vi", "vn_moit_energy_vi", "vn_moit_foundational_industry_vi")


def preserved(state):
    return {n: h for n, h in inventory(state).items()
            if n == "clock.json" or n.startswith(("ledger/", "captures/"))}


def prepare(root, gate_dir):
    """Refuse foreign/malformed state, then seed all prior host completions."""
    before = {}
    for slug in SOURCES:
        repo, state = root / slug, root / slug / "state"
        assert_isolated(repo)
        require(not repo.is_symlink(), "symlink state repository")
        require(git(["branch", "--show-current"], repo).stdout.strip() == load_source(slug).state_branch,
                "wrong state branch")
        if git(["rev-parse", "--verify", "HEAD"], repo, check=False).returncode == 0:
            require(git(["ls-tree", "--name-only", "HEAD"], repo).stdout.strip() == "state",
                    "state branch contains unrelated files")
            require(not git(["status", "--porcelain"], repo).stdout.strip(), "dirty state checkout")
            check_tree(list(inventory(state)))
            review(state, slug)
        else:
            require(not state.exists(), "bootstrap cannot import rehearsal state")
        before[slug] = preserved(state)
        host_gate(state, gate_dir)
    return before


def run_batch(root, gate_dir, mps_target, moit_target, lookback, cap, run_id, commit,
              collector=collect):
    require(lookback in (0, 6) and cap in (2, 40), "unapproved remote budget")
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "full collector SHA required")
    before = prepare(root, gate_dir)
    for slug in SOURCES:
        state = root / slug / "state"
        target = mps_target if slug == SOURCES[0] else moit_target
        entry = collector(state, slug, target, lookback, cap, run_id, commit, gate_dir=gate_dir)
        require(entry["health"] == "ok", "batch stopped after %s: %s" % (slug, entry.get("result")))
        after = preserved(state)
        require(all(after.get(n) == h for n, h in before[slug].items()), "historical evidence changed")
        check_tree(list(inventory(state)))
        review(state, slug)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--gate-dir", type=Path, required=True)
    ap.add_argument("--mps-target", type=date.fromisoformat, required=True)
    ap.add_argument("--moit-target", type=date.fromisoformat, required=True)
    ap.add_argument("--lookback", type=int, choices=(0, 6), required=True)
    ap.add_argument("--cap", type=int, choices=(2, 40), required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--commit", required=True)
    args = ap.parse_args(argv)
    try:
        return run_batch(args.root, args.gate_dir, args.mps_target, args.moit_target,
                         args.lookback, args.cap, args.run_id, args.commit)
    except (ValueError, OSError, ReviewError) as exc:
        print("remote batch refused: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
