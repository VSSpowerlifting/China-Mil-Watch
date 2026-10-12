"""Fail closed if a Korea-only release would publish other generated files.

The Pages action uploads the entire output/ directory, including ignored or
untracked files. Audit that entire tree; staging only approved paths is not
sufficient to prevent unwanted publication.
"""
from __future__ import annotations

from pathlib import Path

from scripts.guard_country_research_output_scope import classify_output_changes

KOREA_OUTPUT_PATHS = frozenset({
    "output/korea.html",
    "output/desk-references.css",
})


def audit_korea_output(root: Path) -> tuple[set[str], set[str]]:
    """Return all output deltas and those that prohibit a Korea-only release."""
    root = Path(root)
    changed, unexpected = classify_output_changes(root, KOREA_OUTPUT_PATHS)
    # Both approved files must already be regular, tracked site outputs.
    # Do not silently approve a deleted page or newly created/symlinked file.
    for rel in KOREA_OUTPUT_PATHS:
        path = root / rel
        if not path.is_file() or path.is_symlink():
            unexpected.add(rel)
    return changed, unexpected


def main() -> int:
    try:
        changed, unexpected = audit_korea_output(Path.cwd())
    except (OSError, RuntimeError) as exc:
        print(f"BLOCKED: Korea output audit could not run: {exc}")
        return 2
    print(f"Korea release generated output deltas: {len(changed)}")
    for path in sorted(changed | unexpected):
        print(("BLOCKED: " if path in unexpected else "REVIEWED: ") + path)
    if unexpected:
        print("BLOCKED: unrelated output, missing output or unapproved media detected.")
        print("Do not publish the full Pages tree under the Korea-only release.")
        return 1
    if not changed:
        print("NOOP: no generated Korea output changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
