"""Validate an isolated Philippine MEPCOM discovery packet, without requesting URLs.

The article permalinks are *opaque identity strings*. Mathematical Unicode
in the publisher's WordPress slugs is percent-encoded; decoding, lowercasing,
or NFKC-normalizing it can silently alter URL identity. Never treat a visible
article or an extracted heading as proof of collection permission or source
completeness. This script is metadata-only and has no network calls.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "research/philippines/mepcom/discovery_2026-10-12.json"
PUBLISHER = "mepcom.coastguard.gov.ph"
INDEX = "https://mepcom.coastguard.gov.ph/news-2/"
ARCHIVE = "https://mepcom.coastguard.gov.ph/2026/07/page/8/"
FIXED = {
    "mepcom-observation-01": (
        "https://mepcom.coastguard.gov.ph/%F0%9D%90%8C%F0%9D%90%80%F0%9D%90%91%F0%9D%90%88%F0%9D%90%8D%F0%9D%90%84-%F0%9D%90%84%F0%9D%90%8D%F0%9D%90%95%F0%9D%90%88%F0%9D%90%91%F0%9D%90%8E%F0%9D%90%8D%F0%9D%90%8C%F0%9D%90%84%F0%9D%90%8D-8/", "2026-09-10", "2026-07-21", "2026-07-21",
        "MEPCOM", "marine_environmental_command_administration",
    ),
    "mepcom-observation-02": (
        "https://mepcom.coastguard.gov.ph/%F0%9D%91%B4%F0%9D%92%82%F0%9D%92%93%F0%9D%92%8A%F0%9D%92%8F%F0%9D%92%86-%F0%9D%91%AC%F0%9D%92%8F%F0%9D%92%97%F0%9D%92%8A%F0%9D%92%93%F0%9D%92%90%F0%9D%92%8F%F0%9D%92%8E%F0%9D%92%86%F0%9D%92%8F/", "2026-09-10", "2026-07-21", "2026-07-22",
        "MEPG-CV (MEPCOM subordinate)", "marine_pollution_response_training",
    ),
}
PACKET_KEYS = {
    "schema", "desk", "family", "mode", "publisher_host",
    "publisher_institution", "review_cutoff", "index_observation",
    "holds", "candidates",
}
INDEX_KEYS = {
    "url", "inspection", "complete_enumerator_verified",
    "homepage_has_article_links", "paginated_archive_example",
    "archive_completeness_verified",
}
HOLD_KEYS = {
    "robots_txt", "http_access_policy", "site_terms",
    "per_item_text_rights", "per_item_image_rights",
    "raw_capture_parity", "collector_authorized",
    "scheduled_collection_enabled", "archived_records_exist",
    "production_admission_approved",
}
ITEM_KEYS = {
    "id", "url", "visible_post_date", "reported_event_start",
    "reported_event_end", "issuing_unit", "label", "classification",
    "raw_response_sha256", "archive_record_id", "rights_approval",
}


class BoundaryError(ValueError):
    """Unapproved discovery has been represented as stronger evidence."""


def require(test, error):
    if not test:
        raise BoundaryError(error)


def iso(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            "date must be exact YYYY-MM-DD")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise BoundaryError("invalid calendar date") from exc
    require(result.isoformat() == value, "noncanonical date")
    return result


def publisher_url(value):
    """Return the *unchanged* source identity; never use a prettified slug."""
    require(type(value) is str and value.startswith("https://"), "HTTPS required")
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise BoundaryError("malformed source URL") from exc
    require(
        parts.scheme == "https" and parts.netloc == PUBLISHER
        and parts.hostname == PUBLISHER and parts.username is None
        and parts.password is None and parts.port is None
        and not parts.query and not parts.fragment
        and parts.path.startswith("/") and parts.path.endswith("/")
        and "//" not in parts.path and "\\" not in parts.path,
        "source must stay on exact first-party MEPCOM host and path",
    )
    return value


def validate(doc):
    require(type(doc) is dict and set(doc) == PACKET_KEYS,
            "discovery packet schema changed")
    require(doc["schema"] == "ph_mepcom_discovery_v1"
            and doc["desk"] == "philippines"
            and doc["family"] == "pcg_subcommand_mepcom_environment"
            and doc["mode"] == "offline_discovery_only"
            and doc["publisher_host"] == PUBLISHER
            and doc["publisher_institution"] ==
            "Philippine Coast Guard — Marine Environmental Protection Command",
            "publisher, desk or discovery-only boundary was changed")
    cutoff = iso(doc["review_cutoff"])
    require(cutoff == date(2026, 10, 12), "observation cutoff drift")
    index = doc["index_observation"]
    require(type(index) is dict and set(index) == INDEX_KEYS
            and index["url"] == INDEX
            and index["inspection"] == "readable_page_no_article_links_in_text_view"
            and index["complete_enumerator_verified"] is False
            and index["homepage_has_article_links"] is True
            and index["paginated_archive_example"] == ARCHIVE
            and index["archive_completeness_verified"] is False,
            "listing-page observation is not verified enumeration")
    holds = doc["holds"]
    require(type(holds) is dict and set(holds) == HOLD_KEYS,
            "missing a source-admission restriction")
    for k in HOLD_KEYS:
        expected = False if k.endswith(("authorized", "enabled", "exist", "approved")) else "unverified"
        require(holds[k] == expected and type(holds[k]) is type(expected),
                "MEPCOM source permission/coverage is not established: " + k)
    candidates = doc["candidates"]
    require(type(candidates) is list and len(candidates) == len(FIXED),
            "unreviewed MEPCOM articles cannot be auto-admitted")
    seen = set()
    urls = set()
    for row in candidates:
        require(type(row) is dict and set(row) == ITEM_KEYS,
                "candidate metadata drift or source body added")
        ident = row["id"]
        require(type(ident) is str and ident in FIXED and ident not in seen,
                "unknown or duplicate MEPCOM candidate")
        seen.add(ident)
        u, posted, event_start, event_end, issuer, kind = FIXED[ident]
        require(publisher_url(row["url"]) == u,
                "source URL identity changed (do not Unicode-normalize the slug)")
        require(row["url"] not in urls, "duplicate source identity")
        urls.add(row["url"])
        require(
            row["visible_post_date"] == posted
            and row["reported_event_start"] == event_start
            and row["reported_event_end"] == event_end
            and row["issuing_unit"] == issuer
            and row["classification"] == kind,
            "publisher versus event date, issuing unit, or article scope changed")
        require(iso(posted) <= cutoff and
                iso(event_start) <= iso(event_end) <= iso(posted),
                "event date is not the publication date")
        require(type(row["label"]) is str and
                15 <= len(row["label"].strip()) <= 120,
                "researcher-facing article label missing")
        for k in ("raw_response_sha256", "archive_record_id", "rights_approval"):
            require(row[k] is None,
                    "do not invent source bytes, record IDs or permission receipts")
    require(seen == set(FIXED), "bounded discovery inventory changed")
    return {
        "first_party_page_links": len(candidates),
        "verified_enumerators": 0,
        "raw_responses_attested": 0,
        "archived_records": 0,
        "collection_enabled": False,
        "source_reuse_cleared": False,
        "publication_gate": "held_pending_robots_access_enumeration_and_rights",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=PACKET)
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.packet.read_text(encoding="utf-8"))
        print(json.dumps(validate(data), indent=2, sort_keys=True))
    except (BoundaryError, TypeError, OSError, ValueError) as exc:
        parser.exit(1, "MEPCOM source discovery hold: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
