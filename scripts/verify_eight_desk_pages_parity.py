"""Read-only Git-blob witness for all eight public IPR desk routes.

Checks exact committed main:output vs gh-pages HTML at two immutable commit
SHAs. This is NOT a production SQLite/source-run or live HTTPS attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROUTES = (
    "china.html", "singapore.html", "korea.html", "japan.html",
    "vietnam.html", "indonesia.html", "philippines.html",
    "us-indopacific.html",
)
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_HTML_BYTES = 1_000_000


class ParityHold(ValueError):
    """No parity assertion can be made from these exact Git objects."""


def require(ok, reason):
    if not ok:
        raise ParityHold(reason)


def git(repo, *args):
    try:
        p = subprocess.run(
            ["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=25,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ParityHold("git_read_unavailable") from exc
    require(p.returncode == 0, "git_object_unavailable")
    return p.stdout


def checked_commit(repo, sha):
    require(type(sha) is str and SHA.fullmatch(sha), "invalid_commit_sha")
    require(git(repo, "cat-file", "-t", sha).strip() == b"commit",
            "ref_is_not_commit")


def read_page(repo, sha, path, route):
    listing = git(repo, "ls-tree", sha, "--", path).decode("utf-8")
    match = re.fullmatch(r"100644 blob ([0-9a-f]{40})\t" +
                         re.escape(path) + r"\n?", listing)
    require(match is not None, "missing_or_nonregular_page:" + path)
    blob = match.group(1)
    size = int(git(repo, "cat-file", "-s", blob).strip())
    require(128 <= size <= MAX_HTML_BYTES, "unbounded_page:" + path)
    raw = git(repo, "cat-file", "blob", blob)
    require(len(raw) == size, "blob_size_mismatch:" + path)
    route_pattern = (rb'<html\b[^>]*\bdata-route="' +
                     re.escape(route.encode("ascii")) + rb'"')
    require(raw.lstrip().lower().startswith(b"<!doctype html>") and
            re.search(route_pattern, raw, re.IGNORECASE) is not None and
            b"<main" in raw.lower() and b"</html>" in raw.lower(),
            "unrecognized_desk_html:" + path)
    return raw


def verify(repo, main_sha, pages_sha):
    repo = Path(repo)
    checked_commit(repo, main_sha)
    checked_commit(repo, pages_sha)
    rows = []
    for route in ROUTES:
        main = read_page(repo, main_sha, "output/" + route, route)
        deployed_git = read_page(repo, pages_sha, route, route)
        require(main == deployed_git, "main_pages_drift:" + route)
        rows.append({
            "route": route, "bytes": len(main),
            "sha256": hashlib.sha256(main).hexdigest(),
        })
    return {
        "schema": "ipr-eight-desk-git-parity/1",
        "status": "PASS_EIGHT_DESK_GIT_PARITY",
        "main_sha": main_sha,
        "pages_sha": pages_sha,
        "desk_pages_verified": len(rows),
        "pages": rows,
        "production_db_verified": False,
        "collector_history_verified": False,
        "public_https_verified": False,
        "source_rights_or_publication_authorized": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--pages-sha", required=True)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    try:
        report = verify(args.repo, args.main_sha, args.pages_sha)
        code = 0
    except (ParityHold, ValueError, UnicodeError) as exc:
        report = {
            "schema": "ipr-eight-desk-git-parity/1",
            "status": "HOLD_EIGHT_DESK_GIT_PARITY",
            "reason": str(exc),
            "main_sha": args.main_sha,
            "pages_sha": args.pages_sha,
            "desk_pages_verified": 0,
            "production_db_verified": False,
            "collector_history_verified": False,
            "public_https_verified": False,
            "source_rights_or_publication_authorized": False,
        }
        code = 2
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    print(encoded, end="")
    if args.json:
        args.json.write_text(encoded, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
