"""Stage only reviewed Phase 4A Desks files from an isolated site render.

Build the full site OUTSIDE tracked output/, then copy exactly the named
Desks page, CSS and eight MIT-licensed country flags with notice. All other
generated routes remain at their existing, reviewed, committed baseline.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from scripts.guard_desks_p4a_output_scope import REVIEWED_PATHS


def stage(source: Path, destination: Path) -> list[str]:
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if source == destination or destination in source.parents or source in destination.parents:
        raise ValueError("Source and target render trees must be separate")
    names = sorted(path.removeprefix("output/") for path in REVIEWED_PATHS)
    for name in names:
        if not (source / name).is_file():
            raise FileNotFoundError("Unrendered required Desks asset: " + name)
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
