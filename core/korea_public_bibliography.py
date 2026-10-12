"""Public Korea Desk: fixed official-source bibliography, NEVER a source archive.

No shadow reader, unreviewed source text, rights approvals, external fetch,
automatic English summaries or sidecar generation. The single admission here
is the owner's authorization to display metadata + outbound first-party links.
"""
from __future__ import annotations

from pathlib import Path

from core.korea_reference_gate import (
    ROOT, STATE_SHA, ALLOWED_IDS, KoreaGateHold,
    load_candidates, load_json, require,
)

INDEX = ROOT / "research" / "korea_public_reference_ids.json"
SCHEMA = "ipr-korea-bibliography-only/1"
EXPECTED = tuple(sorted(ALLOWED_IDS))


def load_public_korea_links(path=INDEX):
    """Return precisely five original Korean titles and canonical government links.

    The linked source ID, title and date are independently bound to the
    frozen HWPX-text source inventory. Neither publisher body, full HWPX,
    hashes nor reviewer identities are returned to the public website.
    """
    path = Path(path)
    require(path == INDEX and not path.is_symlink(),
            "public Korea manifest path must be the canonical repository file")
    source = load_json(path, size=4096)
    require(isinstance(source, dict) and set(source) ==
            {"schema", "state_commit", "release_mode", "source_ids"},
            "Korea public link manifest has unsafe fields")
    require(source["schema"] == SCHEMA
            and source["release_mode"] == "official-links-only"
            and source["state_commit"] == STATE_SHA,
            "Korea public link manifest must be the fixed metadata-only scope")
    require(type(source["source_ids"]) is list and
            tuple(source["source_ids"]) == EXPECTED,
            "Korea public link IDs must be exactly the five frozen pilot IDs")
    originals = load_candidates()
    rows = []
    for entry in originals:
        ident = entry["source_identity"].partition(":")[2]
        require(ident in ALLOWED_IDS and entry["issuer"] == "국방부" and
                entry["publisher"] == "대한민국 정책브리핑" and
                entry["language"] == "ko",
                "Korea entry missing exact government source provenance")
        rows.append({
            "source_identity": entry["source_identity"],
            "source_url": entry["source_url"],
            "title_original": entry["title_original"],
            "published_date": entry["published_date"],
            "document_distribution_date": entry["document_distribution_date"],
        })
    require(len(rows) == 5, "Korea bibliography cannot be empty or expanded")
    return sorted(rows,
                  key=lambda r: (r["published_date"], r["source_identity"]),
                  reverse=True)
