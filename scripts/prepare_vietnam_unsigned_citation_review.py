"""Create an UNSIGNED human-source review worksheet for cited Vietnam records.

Draft citation IDs select exact original-source versions. This tool DOES NOT
review a source, infer legal permission, copy article bodies, call a model or
authorize a publication. Every human check is forced False, never inherited.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

from core.brief_external_evidence import CHECKS, REFERENCE, SOURCE_NAME
from scripts.bridge_vietnam_reviewed_brief_citations import (
    HEX40, HEX64, ID, MAX_ITEMS, PACKET_FIELDS, PACKET_SCHEMA,
    PACKET_SCOPE, PACKET_STATUS, SCHEMA, _date, _prose,
    _published_mps_url, _text, load, require,
)

ROOT = Path(__file__).resolve().parents[1].resolve()


def build_unsigned(draft, packet):
    """Generate exactly the cited IDs, pinned to a private research packet."""
    require(isinstance(draft, dict) and
            draft.get("editorial_status") == "draft" and
            draft.get("issue_number") is None,
            "only an unnumbered draft may request a human-source worksheet")
    saturday = _date(draft.get("week_ending"))
    require(saturday.weekday() == 5 and
            _date(draft.get("week_start")) == saturday - timedelta(days=6),
            "human-source worksheet requires a Saturday-ending week")
    cited = REFERENCE.findall(_prose(draft))
    require(cited and 1 <= len(set(cited)) <= MAX_ITEMS,
            "draft has no bounded Vietnam external source citations")
    # Do not silently accept a generic or ambiguous external-source citation.
    require(all(isinstance(x, str) and x.startswith("mps-vi:") for x in cited),
            "only cited Vietnam MPS identities can enter this worksheet")
    require(isinstance(packet, dict) and
            set(packet) == {"schema", "status", "week_ending", "items"} and
            packet["schema"] == PACKET_SCHEMA and
            packet["status"] == PACKET_STATUS and
            packet["week_ending"] == saturday.isoformat() and
            isinstance(packet["items"], list) and len(packet["items"]) <= 8,
            "private packet is not the exact-week research roster")

    available = {}
    for row in packet["items"]:
        require(isinstance(row, dict) and set(row) == PACKET_FIELDS,
                "private research packet has unexpected fields")
        if row["desk"] != "vietnam":
            continue
        ident = row["id"]
        match = ID.fullmatch(ident) if isinstance(ident, str) else None
        require(match is not None and row["source_kind"] == "shadow-extracted-original"
                and row["source_name"] == SOURCE_NAME and row["language"] == "vi"
                and row["hash_rule"] == "mps-vi-content-v1"
                and row["status"] == PACKET_STATUS
                and row["copy_scope"] == PACKET_SCOPE,
                "Vietnam source not bound to unapproved original-language research")
        source_identity = "mps-vi:" + match.group(1)
        require(source_identity not in available and
                _published_mps_url(row["source_url"], match.group(1))
                and isinstance(row["state_commit"], str)
                and HEX40.fullmatch(row["state_commit"])
                and isinstance(row["source_content_sha256"], str)
                and HEX64.fullmatch(row["source_content_sha256"])
                and _text(row["title_original"], 8, 350),
                "invalid or duplicate original MPS source identity/version")
        published = _date(row["published_date"])
        require(saturday - timedelta(days=6) <= published <= saturday,
                "cited research publication not in reporting week")
        available[source_identity] = row

    selected = set(cited)
    require(selected <= set(available),
            "draft cites an unknown or unversioned Vietnam MPS source")
    records = []
    for ident in sorted(selected):
        row = available[ident]
        records.append({
            "external_id": row["id"],
            "source_identity": ident,
            "source_url": row["source_url"],
            "published_date": row["published_date"],
            "original_title": row["title_original"],
            "state_commit": row["state_commit"],
            "source_content_sha256": row["source_content_sha256"],
            "reviewed_by": None,
            "reviewed_on": None,
            "link_and_summary_use_basis": None,
            "original_summary": None,
            "checks": {name: False for name in sorted(CHECKS)},
        })
    return {"schema": SCHEMA, "week_ending": saturday.isoformat(),
            "records": records}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--draft-sidecar", required=True, type=Path)
    ap.add_argument("--private-research-packet", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)
    target = args.out
    resolved = target.resolve()
    require(not target.exists() and not target.is_symlink()
            and target.parent.is_dir() and not target.parent.is_symlink()
            and resolved != ROOT and ROOT not in resolved.parents,
            "write a new private worksheet outside the tracked repository only")
    worksheet = build_unsigned(
        load(args.draft_sidecar), load(args.private_research_packet))
    target.write_text(json.dumps(worksheet, indent=2, ensure_ascii=False,
                                 sort_keys=True) + "\n", encoding="utf-8")
    print("Prepared {} UNSIGNED cited Vietnam review row(s): no original source "
          "review, rights authorization, publication or email."
          .format(len(worksheet["records"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
