"""One-command PRIVATE Philippines/Vietnam/Korea/Indonesia desk search.

An explicit owner opt-in fetches ONLY already-existing shadow-state Git refs
from the fixed IPR GitHub repository into a disposable local directory.
It never requests publishers, runs collection, modifies state/production,
retains original bytes after exit, or publishes a desk.

Outputs only human-readable metadata, official links and immutable source SHAs,
using scripts.private_country_desk_reader. No publisher body enters the report.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from scripts.private_country_desk_reader import (
    ROOT, SHA, ReaderHold, SOURCES, build, render_html, require,
)

REMOTE = "https://github.com/VSSpowerlifting/China-Mil-Watch.git"
BRANCHES = {
    "ph_afp_articles": "shadow/ph-afp",
    "ph_nsc_official_statements": "shadow/ph-nsc",
    "vn_mps_foreign_affairs_vi": "shadow/vietnam-mps-foreign-affairs",
    "vn_moit_energy_vi": "shadow/vietnam-moit-energy",
    "vn_moit_foundational_industry_vi": "shadow/vietnam-moit-foundational-industry",
    "kr_policy_mnd_releases": "shadow/korea-policy-briefing",
    "id_kemhan_news": "shadow/indonesia-kemhan",
}
ORDERED = tuple(BRANCHES)
CAPTURE = 8000


def safe_git(repo, *args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], env=env,
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=75,
        )
    except (OSError, subprocess.SubprocessError):
        raise ReaderHold("GitHub shadow-ref read unavailable; no publisher fallback") from None
    require(len(result.stdout) <= CAPTURE, "unexpected Git command output size")
    return result.stdout.decode("utf-8").strip()


def exact_state_inputs(local_repo, desk):
    """Read fresh immutable refs in a disposable local Git repository."""
    require(desk in ("philippines", "vietnam", "korea", "indonesia", "both", "all"),
            "unknown private research country")
    slugs = tuple(s for s in ORDERED if desk == "all" or SOURCES[s][0] == desk or
                  (desk == "both" and SOURCES[s][0] in ("philippines", "vietnam")))
    require(slugs, "no source family selected")
    safe_git(local_repo, "init", "-q")
    safe_git(local_repo, "remote", "add", "origin", REMOTE)
    got = []
    for source in slugs:
        branch = BRANCHES[source]
        alias = "refs/heads/local-review-" + source.replace("_", "-")
        safe_git(local_repo, "fetch", "--quiet", "--no-tags", "--depth=1",
                 "origin", "refs/heads/" + branch + ":" + alias)
        commit = safe_git(local_repo, "rev-parse", alias)
        require(SHA.fullmatch(commit) is not None, "malformed pinned source revision")
        got.append(",".join((source, str(local_repo), commit)))
    return got


def create(desk, *, output=None, query="", limit=100, fmt="html",
           fetched_state=None):
    """Use an injected fetcher in tests; never call public source publishers."""
    if fmt not in ("json", "html"):
        raise ReaderHold("unknown reader output")
    # Caller checks explicit opt-in BEFORE any network/fetch is possible.
    with tempfile.TemporaryDirectory(prefix="ipr-private-shadow-reader-") as temp:
        repo = Path(temp) / "source-state-git"
        repo.mkdir()
        state_inputs = (fetched_state(repo, desk) if fetched_state is not None
                        else exact_state_inputs(repo, desk))
        require(isinstance(state_inputs, list) and bool(state_inputs),
                "source snapshot inventory empty")
        report = build(state_inputs, term=query,
                       country=desk if desk not in ("both", "all") else None,
                       max_results=limit)
        if fmt == "html":
            require(output is not None, "HTML needs absolute private output destination")
            path = Path(output).expanduser()
            require(path.is_absolute() and path.parent.is_dir() and
                    not path.is_symlink() and not path.exists() and
                    ROOT not in path.resolve().parents and path.resolve() != ROOT,
                    "refuse public-repository output, existing file or unsafe destination")
            page = render_html(report)
            # Exclusive creation avoids accidentally overwriting private work.
            try:
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(page)
            except FileExistsError:
                raise ReaderHold("private report already exists") from None
            return {"path": str(path), "country": desk,
                    "source_families": len(report["sources"]),
                    "matched_total": report["matched_total"],
                    "metadata_only": True,
                    "no_publisher_requests": True,
                    "production_activated": False}
        require(output is None, "JSON is stdout only: redirect to private location")
        return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--desk", choices=("philippines", "vietnam", "korea", "indonesia", "both", "all"), required=True)
    p.add_argument("--approve-github-shadow-fetch", action="store_true",
                   help="explicitly allow fetching existing source-state Git refs; NO publisher fetch")
    p.add_argument("--format", choices=("html", "json"), default="html")
    p.add_argument("--output", help="absolute private HTML file outside repo; never overwrite")
    p.add_argument("--query", default="")
    p.add_argument("--limit", type=int, default=100)
    args = p.parse_args(argv)
    if not args.approve_github_shadow_fetch:
        p.error("GitHub source-state download disabled absent explicit owner opt-in")
    try:
        result = create(args.desk, output=args.output, query=args.query,
                        limit=args.limit, fmt=args.format)
    except (ReaderHold, UnicodeError, OSError) as exc:
        p.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
