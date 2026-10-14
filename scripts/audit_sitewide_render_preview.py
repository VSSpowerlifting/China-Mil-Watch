"""Read-only inventory of a sitewide IPR render candidate; NEVER authorizes publication.

Run after scripts.run_briefs_render_release --scope report-only in a clean,
disposable checkout. Count tracked, staged, untracked and ignored output drift.
Unknown, source/data and media changes block a cosmetic-only preview.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

from scripts.guard_briefs_render_scope import classify_output_changes

COSMETIC_CSS = frozenset({
    "output/styles.css", "output/home.css", "output/record.css",
    "output/briefs.css", "output/relief.css",
})
HTML_SINGLE = frozenset({"output/index.html", "output/analysis.html"})
HTML_ROUTES = (
    re.compile(r"^output/(?:record/[^/]+|briefs/[^/]+|the-pla-watch/posts/[^/]+)\.html$"),
)
SHA_PATTERN = re.compile(r"^[a-f0-9]{64}$")


def classify(path: str) -> str:
    """Even an allowed path requires human review, not publication."""
    if path in COSMETIC_CSS:
        return "css-review"
    if path in HTML_SINGLE or any(rule.fullmatch(path) for rule in HTML_ROUTES):
        return "html-manual-review"
    return "blocked-noncosmetic"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 18), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path, expected_db_sha: str) -> dict:
    root = Path(root).resolve()
    if not SHA_PATTERN.fullmatch(expected_db_sha):
        raise ValueError("expected DB SHA must be exactly 64 lowercase hex characters")
    db = root / "pla_watch.db"
    if sha256(db) != expected_db_sha:
        raise RuntimeError("tracked database hash changed during render")
    if any((root / ("pla_watch.db" + suffix)).exists()
           for suffix in ("-wal", "-shm")):
        raise RuntimeError("tracked database acquired a WAL or SHM sidecar")
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all", "-z"], cwd=root)
    outside = []
    for entry in status.split(b"\0"):
        if not entry:
            continue
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        # A rename's second -z path is conservatively treated as outside.
        if path and not path.startswith("output/"):
            outside.append(path)
    changed, _ = classify_output_changes(root)
    rows = []
    for path in sorted(changed):
        target = root / path
        kind = "blocked-symlink" if target.is_symlink() else classify(path)
        rows.append({
            "path": path, "kind": kind,
            "sha256": sha256(target) if target.is_file() and not target.is_symlink() else None,
            "bytes": target.stat().st_size if target.is_file() and not target.is_symlink() else None,
        })
    return {
        "schema": "ipr-sitewide-render-preview-v1",
        "reviewed_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "db_sha256_unchanged": expected_db_sha,
        "total_changed": len(rows),
        "css_to_review": sum(r["kind"] == "css-review" for r in rows),
        "html_to_review": sum(r["kind"] == "html-manual-review" for r in rows),
        "blocked": [r["path"] for r in rows if r["kind"].startswith("blocked-")],
        "outside_output": outside,
        "requires_human_output_review": True,
        "publish_authorized": False,
        "changes": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--expected-db-sha", required=True)
    parser.add_argument("--report", required=True)
    opts = parser.parse_args(argv)
    report = inventory(Path(opts.root), opts.expected_db_sha)
    destination = Path(opts.report).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Sitewide preview: %d CSS, %d HTML, %d blocked, %d outside output" % (
        report["css_to_review"], report["html_to_review"],
        len(report["blocked"]), len(report["outside_output"])))
    print("Review receipt:", destination)
    if report["blocked"] or report["outside_output"]:
        print("BLOCKED: a cosmetic-only release cannot include these paths.")
        return 2
    if report["total_changed"] == 0:
        print("NO CHANGE: review would be empty; check source and output baseline.")
        return 3
    print("PREVIEW ONLY: human diff/visual review and separate authorization required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
