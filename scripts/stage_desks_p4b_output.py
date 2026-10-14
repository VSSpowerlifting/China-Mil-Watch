"""Stage exactly three owner-reviewed Source Atlas files, never a full-site deploy.

Phase 4A CSS and country flags are already live. Preserve them and every
Briefs/country page while adding the new Atlas HTML, stylesheet and glyph.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from scripts.guard_desks_p4b_output_scope import REVIEWED_PATHS


def stage(source: Path, destination: Path) -> list[str]:
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if (source == destination or destination in source.parents
            or source in destination.parents):
        raise ValueError("Staging source and target must be separate trees")
    names = sorted(p.removeprefix("output/") for p in REVIEWED_PATHS)
    for name in names:
        if not (source / name).is_file():
            raise FileNotFoundError("Missing rendered Atlas file: " + name)
    for name in names:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-dir", required=True, type=Path)
    parser.add_argument("--to-dir", required=True, type=Path)
    args = parser.parse_args()
    for name in stage(args.from_dir, args.to_dir):
        print("STAGED:", name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
