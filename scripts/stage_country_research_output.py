"""Stage only approved country-presentation files from an isolated full-site render.

The normal renderer replaces the entire output tree. A country-only release
must not silently include unrelated pending Briefs, catalogue, analysis or
media changes. Build into scratch, then copy only the seven already reviewed
paths. The existing git-scope guard still audits ALL output changes before
publishing and rejects any other path, including gitignored files.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.guard_country_research_output_scope import REVIEWED_OUTPUT_PATHS


def stage_country_output(source: Path, destination: Path) -> tuple[str, ...]:
    """Copy an exact allowlist from a fresh render, without touching other files.

    Refuse missing, empty, non-UTF8 or symlink inputs before writing *anything*.
    This does not approve publishing: the workflow still validates, audits the
    git diff, checks the immutable DB and requires the owner-reviewed main SHA.
    """
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or destination.is_symlink():
        raise ValueError("source/destination roots must not be symlinks")
    src = source.resolve(strict=True)
    dst = destination.resolve(strict=True)
    if src == dst or src in dst.parents or dst in src.parents:
        raise ValueError("country render and production output must be disjoint")
    if not src.is_dir() or not dst.is_dir():
        raise ValueError("country render and production output must be directories")

    expected_prefix = "output/"
    if not REVIEWED_OUTPUT_PATHS or any(
        not p.startswith(expected_prefix) for p in REVIEWED_OUTPUT_PATHS
    ):
        raise ValueError("invalid reviewed output allowlist")

    pending: list[tuple[Path, bytes]] = []
    for name in sorted(REVIEWED_OUTPUT_PATHS):
        relative = Path(name.removeprefix(expected_prefix))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe country output path")
        rendered = source / relative
        target = destination / relative
        if rendered.is_symlink() or target.is_symlink():
            raise ValueError("country output path is a symlink: " + name)
        if not rendered.is_file() or not target.is_file():
            raise ValueError("missing approved source or target: " + name)
        if rendered.resolve().parent != src or target.resolve().parent != dst:
            raise ValueError("unexpected country output file location: " + name)
        payload = rendered.read_bytes()
        if not payload:
            raise ValueError("empty approved rendered output: " + name)
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("non-UTF8 approved rendered output: " + name) from exc
        pending.append((target, payload))

    # Preflight all seven files before touching tracked output.
    for target, payload in pending:
        if target.read_bytes() != payload:
            target.write_bytes(payload)
    return tuple(sorted(REVIEWED_OUTPUT_PATHS))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-dir", required=True, type=Path)
    parser.add_argument("--to-dir", default=Path("output"), type=Path)
    args = parser.parse_args(argv)
    try:
        files = stage_country_output(args.from_dir, args.to_dir)
    except (OSError, ValueError) as exc:
        parser.exit(2, "BLOCKED: " + str(exc) + "\n")
    for path in files:
        print("Country staging allowlist: " + path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
