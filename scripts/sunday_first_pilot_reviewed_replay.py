"""Manually deliver exact owner-reviewed first-Sunday TXT; NEVER regenerate AI.

Operator-only local/private replay. This is not a scheduled workflow, does not
access GitHub/Gmail history or artifacts, and prints no manuscript/source text.

After owner-only preview, store the EXACT attached TXT outside the repo, inspect
and approve its digest/week, configure existing SMTP secrets locally, then:
  python -m scripts.sunday_first_pilot_reviewed_replay --file /private/approved.txt
  python -m scripts.sunday_first_pilot_reviewed_replay --file /private/approved.txt --send

--send additionally requires IPR_SUNDAY_EDITOR_DELIVERY_ENABLED=true and all
existing owner-week / exact SHA authorizations. Do not retry an uncertain
SMTP result without inspecting Sent; this manual path is not idempotent.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
from datetime import date, timedelta
from pathlib import Path

from scripts.sunday_editor_readable import editable_sections, ReadableEditorError
from scripts.sunday_pilot_owner_review import (
    PILOT_SATURDAY, require_owner_review, require_exact_reviewed_manuscript,
)

MAX_BYTES = 2_000_000
REQUIRED_FOOTER = "END OF UNAPPROVED WORKSHEET"
RECEIPT = "=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ==="
APPENDIX = "=== SOURCE APPENDIX — DO NOT EDIT ==="


class ReplayRefused(ValueError):
    """Owner/attachment/corpus boundary mismatch; refuse before SMTP."""


def inspect_file(path: Path, week_ending: str = PILOT_SATURDAY):
    """Validate only format and exact original bytes, NOT claim accuracy/rights."""
    if week_ending != PILOT_SATURDAY:
        raise ReplayRefused("replay helper is scoped to the October 10 pilot only")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ReplayRefused("expected one bounded regular private reviewed file")
    original = path.read_bytes()
    if not original or b"\x00" in original or len(original) > MAX_BYTES:
        raise ReplayRefused("empty, binary or oversized reviewed file")
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReplayRefused("reviewed file must be UTF-8") from exc
    if "\r" in text:
        raise ReplayRefused("reviewed file bytes cannot be newline-normalized")
    start = (date.fromisoformat(week_ending) - timedelta(days=6)).isoformat()
    if (text.count("Packet: IPR-" + week_ending + "\n") != 1
            or text.count("Week: " + start + " through " + week_ending + "\n") != 1):
        raise ReplayRefused("reporting week or packet identity mismatch")
    if text.count(RECEIPT) != 1 or text.count(APPENDIX) != 1:
        raise ReplayRefused("original complete source-use receipt or appendix missing")
    if text.count("END OF SOURCE APPENDIX") != 1:
        raise ReplayRefused("source appendix boundary missing")
    if not text.rstrip().endswith(REQUIRED_FOOTER):
        raise ReplayRefused("incomplete original packet footer")
    try:
        sections = editable_sections(text)
    except ReadableEditorError as exc:
        raise ReplayRefused("original manuscript is not a valid article") from exc
    # Refuse suspicious unreviewed blank/editor-scaffold input: all article
    # sections must exist, and section-level citation receipts remain in TXT.
    if text.count("SOURCE RECORD IDS:") + text.count("EXTERNAL SOURCE IDS:") < 2:
        raise ReplayRefused("original factual citations are missing")
    if "END OF MANUSCRIPT SOURCE USE" not in text:
        raise ReplayRefused("source-use audit is incomplete")
    return original, {
        "week": week_ending,
        "sha256": hashlib.sha256(original).hexdigest(),
        "article_sections": len(sections),
        "bytes": len(original),
    }


def replay(path: Path, *, send: bool = False, week_ending: str = PILOT_SATURDAY):
    original, info = inspect_file(path, week_ending)
    if not send:
        return {"state": "review-only", **info}
    if os.environ.get("IPR_SUNDAY_EDITOR_DELIVERY_ENABLED", "") != "true":
        raise ReplayRefused("explicit editor delivery opt-in missing")
    require_owner_review(
        week_ending=week_ending, sending=True,
        approved_week=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_WEEK", ""),
    )
    require_exact_reviewed_manuscript(
        week_ending=week_ending, sending=True,
        manuscript_bytes=original,
        approved_sha256=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_SHA256", ""),
    )
    # Existing SMTP adapter independently rechecks week + exact bytes.
    from scripts.sunday_editorial_handoff import send_packet
    send_packet(path, week_ending, full_week=True)
    return {"state": "handed-to-SMTP", **info}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, type=Path,
                        help="private ORIGINAL owner-preview TXT; never a new draft")
    parser.add_argument("--week-ending", default=PILOT_SATURDAY)
    parser.add_argument("--send", action="store_true",
                        help="explicitly send the exact owner-approved file")
    args = parser.parse_args(argv)
    info = replay(args.file, send=args.send, week_ending=args.week_ending)
    print("Original Sunday manuscript: {} | {} bytes | {} sections | SHA-256 {}"
          .format(info["state"], info["bytes"], info["article_sections"], info["sha256"]))
    if not args.send:
        print("DRY RUN ONLY — no model call, SMTP or publication.")
    else:
        print("Check the SMTP account Sent folder before any retry; duplicate delivery "
              "protection across machines is not provided.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
