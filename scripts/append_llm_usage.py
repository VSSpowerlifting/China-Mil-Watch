#!/usr/bin/env python3
"""
Append this run's runtime LLM usage record to the tracked history.

Usage: append_llm_usage.py <runtime-record> [<tracked-jsonl>]

The pipeline writes one record to a temp file (LLM_USAGE_RECORD_PATH) and never
touches the tracked history. The daily workflow's dedicated telemetry step calls
this script to turn that record into one appended line of
`.github/state/llm_usage.jsonl`. The record is validated first, so a missing,
empty, multi-line or wrong-schema file appends nothing and exits non-zero.
Operational accounting only; see analysis/usage.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.usage import USAGE_LOG_PATH, append_run_record, load_run_record  # noqa: E402


def main(argv: list) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    dest = argv[2] if len(argv) == 3 else USAGE_LOG_PATH
    try:
        record = load_run_record(argv[1])
    except (OSError, ValueError) as exc:
        print(f"LLM usage record not appended: {exc}", file=sys.stderr)
        return 1
    append_run_record(record, dest)
    print(f"Appended LLM usage record for {record['run_date']} to {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
