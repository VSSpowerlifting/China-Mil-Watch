"""Fail closed on unrelated generated-site changes in country research releases.

The country release publishes the *whole* output directory to GitHub Pages,
even when only a few country pages were authorized. Check all tracked, staged,
untracked and gitignored output paths before any publication step.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# Exact reviewed presentation routes only. Do not silently add Korea, Briefs,
# analysis, catalogue images, scripts or general site assets to this list.
REVIEWED_OUTPUT_PATHS = frozenset({
    "output/philippines.html",
    "output/vietnam.html",
    "output/indonesia.html",
    "output/japan.html",
    "output/desks.html",
    "output/desk-references.js",
    "output/desk-references.css",
})


def _git_paths(root: Path, *args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args, "-z", "--", "output/"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return {
        entry.decode("utf-8", errors="surrogateescape")
        for entry in result.stdout.split(b"\0") if entry
    }


def classify_output_changes(root: Path) -> tuple[set[str], set[str]]:
    """Return (all generated output deltas, paths not reviewed for release).

    --no-exclude-standard intentionally includes gitignored generated files:
    peaceiris/actions-gh-pages publishes all files on disk, not just tracked
    paths. --no-renames prevents a rename from obscuring a deleted old path.
    """
    root = Path(root)
    changed = (
        _git_paths(root, "diff", "--name-only", "--no-renames")
        | _git_paths(root, "diff", "--cached", "--name-only", "--no-renames")
        | _git_paths(root, "ls-files", "--others")
    )
    return changed, changed - REVIEWED_OUTPUT_PATHS


def main() -> int:
    try:
        changed, unexpected = classify_output_changes(Path.cwd())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"BLOCKED: cannot audit generated output paths: {exc}")
        return 2
    print(f"Country release generated output deltas: {len(changed)}")
    for path in sorted(changed):
        print(("BLOCKED: " if path in unexpected else "REVIEWED: ") + path)
    if unexpected:
        print("BLOCKED: unrelated generated output would be published with country pages.")
        print("Reconcile it under an independently approved release; do not widen this allowlist.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
