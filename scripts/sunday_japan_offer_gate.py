"""Verify Japan research is actually offered to Sunday's unified AI writer.

This is model-input roster integrity, not Japan production activation,
publication approval, source-body fidelity or any license to send email.
The first Oct 10 pilot requires all three prepared source candidates.
Future weeks remain permissive but expressly disclose zero/partial Japan input.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.brief_editorial_evidence import load_editorial_evidence

FIRST_SATURDAY = "2026-10-10"
FIRST_JAPAN_IDS = frozenset(("JP-W41-01", "JP-W41-02", "JP-W41-06"))


class JapanOfferRefused(ValueError):
    """A falsely complete first-Sunday Japan source roster."""


def inspect_offer(*, week_ending, as_of, directory):
    # The source reader already refuses duplicate IDs, malformed unapproved
    # notes, cross-week material, unexpected publisher hosts and symlinks.
    rows = load_editorial_evidence(week_ending, as_of, directory=directory)
    japan_ids = frozenset(x["id"] for x in rows if x["desk"] == "japan")
    vietnam_ids = frozenset(x["id"] for x in rows if x["desk"] == "vietnam")
    if week_ending == FIRST_SATURDAY:
        if japan_ids != FIRST_JAPAN_IDS:
            raise JapanOfferRefused(
                "Oct10 private Sunday draft needs all three exact Japan "
                "research IDs in the current model packet; no model or email"
            )
        if not vietnam_ids:
            raise JapanOfferRefused(
                "Oct10 private Sunday draft needs Vietnam as well as Japan "
                "research; current Vietnam state audit is separate"
            )
    return {
        "week_ending": week_ending,
        "japan_research_offered": len(japan_ids),
        "vietnam_research_offered": len(vietnam_ids),
        "japan_research_state": (
            "exact_first_pilot_three_candidate_roster_not_approved"
            if week_ending == FIRST_SATURDAY else
            "no_japan_candidate_available_not_official_silence"
            if not japan_ids else
            "japan_candidates_available_unapproved"
        ),
        "all_offered_source_ids": sorted(japan_ids | vietnam_ids),
        "model_was_called": False,
        "archived_japan_original_pdf_fidelity_reviewed": False,
        "source_use_or_editorial_approved": False,
        "japan_production_activated": False,
        "email_sent": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--week-ending", required=True)
    p.add_argument("--as-of", required=True)
    p.add_argument("--packet", type=Path, required=True)
    args = p.parse_args(argv)
    if args.packet.name != args.week_ending + ".json":
        p.error("research packet must match reporting Saturday")
    try:
        result = inspect_offer(
            week_ending=args.week_ending, as_of=args.as_of,
            directory=args.packet.parent,
        )
    except (JapanOfferRefused, ValueError, OSError) as exc:
        p.error(str(exc))
    # No source bodies, research synopses, article headlines or URLs printed.
    print(json.dumps(result, sort_keys=True))
    if not result["japan_research_offered"]:
        print("::warning::Japan not offered to this week's AI writer; NOT official silence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
