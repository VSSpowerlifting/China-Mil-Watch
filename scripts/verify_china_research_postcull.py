#!/usr/bin/env python3
"""Read-only post-retirement custody check for the frozen China research packet.

The October 14 source-review packet is a HISTORICAL, nonpublishing research
receipt. It must not be silently rebased onto the reduced October 15 corpus.
Instead, verify the exact original packet, prove retirement of removed cases,
and recheck genuinely surviving source anchors against current HTML.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

# Support both `python -m scripts.verify_china_research_postcull` and direct
# command-line execution in GitHub Actions' working directory.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_china_original_source_notes import ROOT, validate_packet

PACKET = ROOT / "research/china/original-source-review-2026-10-15.json"
INDEX = ROOT / "output/corpus-index.json"
DATABASE = ROOT / "pla_watch.db"
# Existing reviewed Git blob: freeze all 18 historical observations, including
# author/review limitations and the original 5,230-record snapshot.
PACKET_GIT_BLOB_SHA1 = "9557e585cf537ce37ec38e62565b9c307d837d5d"
HISTORICAL_SNAPSHOT = {"date": "2026-10-14", "records": 5230}
SURVIVING = frozenset((2849, 2391, 2265))
RETIRED = frozenset((
    2180, 4348, 4346, 946, 170, 419, 905, 792, 793,
    1246, 1630, 1954, 2753, 3180, 3181,
))


def validate_postcull(packet, index, tombstones, active_ids,
                      record_dir, article_dir):
    """Prove custody without treating deleted records as failed source checks."""
    if packet.get("baseline_snapshot") != HISTORICAL_SNAPSHOT:
        raise ValueError("historical research snapshot drift")
    if packet.get("purpose") != "assistant_research_preliminary_not_editorial_signoff":
        raise ValueError("historical research purpose drift")
    if packet.get("publication_enabled") is not False or packet.get("owner_approved") is not False:
        raise ValueError("historical preliminary receipt cannot authorize publication")
    checks = packet.get("checks")
    if not isinstance(checks, list) or len(checks) != len(RETIRED | SURVIVING):
        raise ValueError("historical source-check case cardinality drift")
    ids = [c.get("id") if isinstance(c, dict) else None for c in checks]
    if len(set(ids)) != len(ids) or set(ids) != (RETIRED | SURVIVING):
        raise ValueError("historical source-check identities drift")
    if index.get("fields") != ["id", "date", "source", "state", "title_en", "title_orig"]:
        raise ValueError("current corpus index schema drift")
    rows = index.get("records")
    if not isinstance(rows, list) or len(rows) != index.get("snapshot", {}).get("records"):
        raise ValueError("current corpus snapshot/count drift")
    current_ids = [r[0] for r in rows]
    if len(current_ids) != len(set(current_ids)):
        raise ValueError("current corpus contains duplicate IDs")

    if not RETIRED.issubset(tombstones):
        raise ValueError("historical retired source has no ledger tombstone")
    if (RETIRED & set(active_ids)) or (RETIRED & set(current_ids)):
        raise ValueError("retired source reentered active corpus")
    if (set(active_ids) & (RETIRED | SURVIVING)) != SURVIVING:
        raise ValueError("surviving source identity/active DB drift")
    if not SURVIVING.issubset(current_ids) or (SURVIVING & tombstones):
        raise ValueError("surviving source missing or incorrectly retired")
    for ident in RETIRED:
        for directory in (record_dir, article_dir):
            if (directory / ("%d.html" % ident)).exists():
                raise ValueError("retired source page was republished: %d" % ident)

    # Validate surviving cases through the original STRICT case validator on
    # current source HTML. This is only a transient current-state projection:
    # never save the projected packet, change the frozen research receipt, or
    # call its review/approval a new signoff on the current corpus.
    current_projection = copy.deepcopy(packet)
    current_projection["baseline_snapshot"] = copy.deepcopy(index["snapshot"])
    current_projection["checks"] = [
        copy.deepcopy(c) for c in checks if c["id"] in SURVIVING
    ]
    pages = {}
    for ident in SURVIVING:
        path = record_dir / ("%d.html" % ident)
        if not path.is_file():
            raise ValueError("surviving original-source page missing: %d" % ident)
        pages[ident] = path.read_text(encoding="utf-8")
    result = validate_packet(current_projection, index, pages)
    if result["research_cases"] != len(SURVIVING) or result["publication_enabled"]:
        raise ValueError("surviving receipt validation did not remain nonpublishing")
    return {
        "historical_packet_unchanged": True,
        "historical_snapshot": HISTORICAL_SNAPSHOT,
        "retired_cases_tombstoned_and_not_public": len(RETIRED),
        "surviving_cases_current_source_checked": len(SURVIVING),
        "publication_authorized": False,
        "human_reverification_of_retired_originals_required": True,
    }


def main():
    raw = PACKET.read_bytes()
    blob = b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    if hashlib.sha1(blob).hexdigest() != PACKET_GIT_BLOB_SHA1:
        raise ValueError("frozen historical packet bytes changed; require explicit new review")
    packet = json.loads(raw)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    from scripts.reconcile_db import read_only
    with read_only(DATABASE) as connection:
        tombstones = {r[0] for r in connection.execute(
            "SELECT original_article_id FROM retired_article_urls")}
        ids = sorted(RETIRED | SURVIVING)
        active = {r[0] for r in connection.execute(
            "SELECT id FROM articles WHERE id IN (" +
            ",".join("?" for _ in ids) + ")", ids)}
    print(json.dumps(validate_postcull(
        packet, index, tombstones, active,
        ROOT / "output/record", ROOT / "output/article",
    ), sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
