#!/usr/bin/env python3
"""Offline schema and preserved-source parity check. Does not approve or render."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.timelines import TIMELINES_DIR, read_timeline, reconcile_sources


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    parser.add_argument("--db", type=Path, default=ROOT / "pla_watch.db")
    args = parser.parse_args(argv)
    try:
        paths = [args.path] if args.path else sorted(TIMELINES_DIR.glob("*.json"))
        for path in paths:
            sc = read_timeline(path)
            records = reconcile_sources(sc, args.db)
            from core.brief_collection import load_briefs
            from core.desk_registry import load_registry
            import json
            numbers = [json.loads(p.read_text(encoding="utf-8"))["issue_number"]
                       for p in (ROOT / "output/the-pla-watch/posts").glob("*.json")]
            published, _ = load_briefs(ROOT / "briefs", load_registry(), historical_numbers=numbers)
            approved = {slug for slug, _ in published}
            if not set(sc["related_briefs"]) <= approved:
                raise ValueError("related Brief must be approved")
            print("%s: %s; %s entries; %s preserved records; source parity passed (not editorial approval)" %
                  (sc["slug"], sc["editorial_status"], len(sc["entries"]), len(records)))
    except (ValueError, OSError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
