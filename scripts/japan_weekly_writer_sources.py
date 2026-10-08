"""Explicitly bounded Japan research for a provisional Friday AI editor draft.

This is a NON-PRODUCTION research lane. Source claims are analyst paraphrases
from externally observed MOD pages, not archived originals or human approvals.
The model may use the claims to propose prose and a concept for Dylan to check;
release, source-admission and desk-eligibility gates are completely unchanged.
Only the October 9, 2026 Friday handoff is supported by this initial packet.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from scripts.render_japan_friday_supplement import (
    DEFAULT_PACKET, JapanBriefError, validate,
)

FRIDAY = date(2026, 10, 9)
SATURDAY = date(2026, 10, 10)
SOURCE_IDS = ("JP-W41-01", "JP-W41-05")
STATUS = "unreviewed_official_source_research_not_an_ipr_record"


def load_japan_writer_sources(week_ending, as_of, *, packet_path=DEFAULT_PACKET):
    """Return source-labeled provisional Japan claims for *this* Friday only.

    No network, no shadow-DB access, no human-review attestation and no writer
    permission for other Fridays. A missing/malformed exact-week packet fails
    closed. Different weeks return [] and retain the existing production flow.
    """
    try:
        ending, cutoff = date.fromisoformat(week_ending), date.fromisoformat(as_of)
    except (ValueError, TypeError) as exc:
        raise JapanBriefError("invalid Friday/Saturday dates") from exc
    if ending != SATURDAY:
        return []
    if cutoff != FRIDAY or cutoff.weekday() != 4 or ending != cutoff + timedelta(days=1):
        raise JapanBriefError("Japan source packet is restricted to October 9 Friday")
    path = Path(packet_path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 45000:
        raise JapanBriefError("missing or unsafe bounded Japan research packet")
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        raise JapanBriefError("invalid research packet encoding/JSON") from exc
    validate(packet)
    indexed = {row["candidate_id"]: row for row in packet["source_candidates"]}
    html = packet["linked_public_mod_tsuiki_training_notice"]
    if html["candidate_id"] != SOURCE_IDS[1]:
        raise JapanBriefError("unexpected Japan supplementary identity")
    kunisaki = indexed[SOURCE_IDS[0]]
    rows = (
        (SOURCE_IDS[0], kunisaki["public_source_url"],
         kunisaki["publisher_date"], kunisaki["title"],
         kunisaki["provisional_claims"], kunisaki["caveats"],
         kunisaki["institution"], kunisaki["source_language"]),
        (SOURCE_IDS[1], html["url"],
         html["publication_date"], html["subject"],
         html["provisional_claims"], html["caveats"],
         html["institution"], html["language"]),
    )
    result = []
    for identity, url, day, title, claims, cautions, issuer, lang in rows:
        if (date.fromisoformat(day) > cutoff or
                not isinstance(claims, list) or len(claims) < 2):
            raise JapanBriefError("Japan research date or claims are invalid")
        result.append({
            "id": identity, "desk": "japan", "issuer": issuer,
            "url": url, "published_date": day, "title": title,
            "source_language": lang,
            "evidence_representation": "bounded_analyst_paraphrase_not_original_body",
            "status": STATUS, "claims": list(claims), "caveats": list(cautions),
        })
    return result
