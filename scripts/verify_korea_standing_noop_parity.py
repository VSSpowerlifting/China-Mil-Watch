"""Read-only parity witness for a TRUE Korea standing-text no-op.

A moving main must not turn an already-converged, source-unchanged no-op into
a spurious red job. This witness is never used for a run with Korea write
candidates: that run retains strict source/main/Pages compare-and-swap.
Only git objects already fetched from official main and gh-pages are read;
no network or write permissions are needed here.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess

REGISTER = "ipr-korea-public-original-text-index/1"
ID = re.compile(r"korea-policy:([0-9]{9})\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
MAX_ROWS = 50


class NoopHold(ValueError):
    """Fixed public failure codes; never leak Korean source bytes."""


def need(condition, reason):
    if not condition:
        raise NoopHold(reason)


def git(*args):
    try:
        run = subprocess.run(["git", *args], check=False, capture_output=True,
                             timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise NoopHold("korea_noop_git_unavailable") from None
    need(run.returncode == 0, "korea_noop_git_object_missing")
    return run.stdout


def blob(ref, path):
    need(ref in ("origin/main", "origin/gh-pages")
         and ".." not in path and not path.startswith("/"),
         "korea_noop_git_ref_or_path_invalid")
    return git("show", ref + ":" + path)


def published_html_paths(ref):
    prefix = ("output/korea-originals/" if ref == "origin/main"
              else "korea-originals/")
    paths = git("ls-tree", "-r", "--name-only", ref, "--", prefix).decode(
        "utf-8", "strict").splitlines()
    need(all(x.startswith(prefix) and x.endswith(".html") for x in paths),
         "korea_noop_orphan_original_page")
    return set(paths)


def verify_parity():
    """Require exact CURRENT main -> gh-pages byte identity, including roster."""
    try:
        registry = json.loads(blob("origin/main",
                                   "research/korea_published_original_texts.json"))
    except (json.JSONDecodeError, UnicodeError):
        raise NoopHold("korea_noop_registry_invalid") from None
    need(type(registry) is dict and set(registry) == {"schema", "records"}
         and registry["schema"] == REGISTER and type(registry["records"]) is list
         and 1 <= len(registry["records"]) <= MAX_ROWS,
         "korea_noop_registry_invalid")
    ids = set()
    expected_main = set()
    expected_pages = set()
    for row in registry["records"]:
        need(type(row) is dict, "korea_noop_registry_invalid")
        ident = row.get("source_identity")
        match = ID.fullmatch(ident) if type(ident) is str else None
        digest = row.get("original_text_sha256")
        need(match is not None and ident not in ids
             and type(digest) is str and HASH.fullmatch(digest) is not None,
             "korea_noop_registry_invalid")
        ids.add(ident)
        pages_path = "korea-originals/" + match.group(1) + ".html"
        expected_pages.add(pages_path)
        expected_main.add("output/" + pages_path)
    need(published_html_paths("origin/main") == expected_main
         and published_html_paths("origin/gh-pages") == expected_pages,
         "korea_noop_original_roster_not_converged")
    for pages_path in sorted(expected_pages | {"korea.html"}):
        main_path = "output/" + pages_path
        need(blob("origin/main", main_path) == blob("origin/gh-pages", pages_path),
             "korea_noop_current_main_pages_byte_drift")
    return {"status": "KOREA_NO_NEW_TEXT_CURRENT_MAIN_PAGES_CONVERGED",
            "published_originals_verified": len(ids),
            "routes_byte_identical": 1 + len(expected_pages),
            "published": False, "new_original_texts": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args()
    try:
        print(json.dumps(verify_parity(), sort_keys=True))
    except NoopHold as exc:
        print(json.dumps({"status": "HOLD", "reason": str(exc),
                          "publication_authorized": False}, sort_keys=True))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
