"""No-send, metadata-only examination of the staged Korean Week-42 candidates.

Do not import or call Sunday writer, Anthropic, SMTP, source collectors or site.
"""
from __future__ import annotations

import argparse
import json

from core.korea_private_research_candidates import load, machine_receipt


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--week-ending", default="2026-10-17")
    p.add_argument("--as-of", default="2026-10-17")
    args = p.parse_args(argv)
    items = load(week_ending=args.week_ending, as_of=args.as_of)
    print(json.dumps(machine_receipt(items), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
