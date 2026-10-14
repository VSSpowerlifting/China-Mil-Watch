"""Audit output scope for the Briefs presentation release.

This allow-list covers the reviewed historical/native Brief shells, the
catalogue, No. 17 cover assets and the shared journal stylesheet/disclosure defaults. A Pages
deploy ships the entire output tree, so every changed, staged, untracked, and
ignored output path is checked before a release may commit or deploy.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

REVIEWED_OUTPUT_PATHS = frozenset({
    "output/analysis.html",
    "output/briefs.css",
    "output/shell.js",
    "output/briefs/what-is-being-built-in-laos.html",
    "output/briefs-catalog.css",
    "output/briefs/maritime-cooperation-2026.html",
    "output/briefs/xiangshan-security-frames-defense-ties.html",
    "output/briefs/trident-resolve-regional-scale-specific-chinese-tasks.html",
    "output/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.jpg",
    "output/assets/editorial/derivatives/trident-resolve-basarnas-drone-800.webp",
    "output/assets/editorial/derivatives/trident-resolve-basarnas-drone-1600.webp",
    "output/assets/catalogue/media/no-17-trident-resolve-basarnas-drone.jpg",
    "output/the-pla-watch/posts/2026-05-09.html",
    "output/the-pla-watch/posts/2026-05-16.html",
    "output/the-pla-watch/posts/2026-05-23.html",
    "output/the-pla-watch/posts/2026-05-30.html",
    "output/the-pla-watch/posts/2026-06-06.html",
    "output/the-pla-watch/posts/2026-06-13.html",
    "output/the-pla-watch/posts/2026-06-20.html",
    "output/the-pla-watch/posts/2026-06-27.html",
    "output/the-pla-watch/posts/2026-07-04.html",
    "output/the-pla-watch/posts/2026-07-11.html",
    "output/the-pla-watch/posts/2026-07-18.html",
    "output/the-pla-watch/posts/2026-08-01.html",
    "output/the-pla-watch/posts/2026-08-08.html",
    "output/the-pla-watch/posts/2026-08-15.html",
})


def is_reviewed_path(path: str) -> bool:
    """True only for a route explicitly reviewed for this release."""
    return path in REVIEWED_OUTPUT_PATHS


def _git_paths(root: Path, *args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args, "-z", "--", "output/"],
        cwd=root, check=True, capture_output=True,
    )
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0") if item
    }


def classify_output_changes(root: Path) -> tuple[set[str], set[str]]:
    """Return (all output deltas, paths not explicitly reviewed).

    Do not pass --exclude-standard to ls-files: ignored files are still shipped
    by the Pages deploy action and therefore count as part of the release.
    """
    root = Path(root)
    changed = (
        _git_paths(root, "diff", "--name-only", "--no-renames")
        | _git_paths(root, "diff", "--cached", "--name-only", "--no-renames")
        | _git_paths(root, "ls-files", "--others")
    )
    return changed, changed - REVIEWED_OUTPUT_PATHS



def restore_unreviewed_output(root: Path, paths) -> list[str]:
    """Return every unreviewed generated path to the exact HEAD baseline.

    Tracked paths are restored from HEAD. Newly generated, untracked or ignored
    files are removed. This is safe only in the release workflow's clean CI
    checkout: classify_output_changes is checked before rendering to prove no
    pre-existing output drift is being discarded. No allow-list is widened.
    """
    import shutil

    root = Path(root).resolve()
    restored = []
    for rel in sorted(set(paths)):
        parts = Path(rel).parts
        if not rel.startswith("output/") or not parts or parts[0] != "output" or ".." in parts:
            raise ValueError("refusing to restore a path outside output/: " + repr(rel))
        target = root / rel
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", rel],
            cwd=root, capture_output=True, text=True,
        )
        if tracked.returncode == 0:
            subprocess.run(
                ["git", "restore", "--source=HEAD", "--staged", "--worktree", "--", rel],
                cwd=root, check=True,
            )
            print("RESTORED TO HEAD BASELINE: " + rel)
        else:
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.exists():
                shutil.rmtree(target)
            print("REMOVED GENERATED UNTRACKED PATH: " + rel)
        restored.append(rel)
    return restored

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report-only", action="store_true",
        help="report unexpected output paths without failing; preview only",
    )
    args = parser.parse_args(argv)
    try:
        changed, unexpected = classify_output_changes(Path.cwd())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"BLOCKED: cannot audit generated output paths: {exc}")
        return 2

    print(f"Briefs release output deltas: {len(changed)}")
    for path in sorted(changed):
        print(("BLOCKED: " if path in unexpected else "REVIEWED: ") + path)
    if not changed and not args.report_only:
        print("BLOCKED: no generated output changes; refusing an empty release.")
        return 1
    if unexpected:
        print("BLOCKED: unrelated generated output would ship with the Briefs release.")
        print("Keep preview-only and reconcile the additional paths under separate review.")
        return 0 if args.report_only else 1
    print("Output scope is within the explicit Briefs release allow-list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
