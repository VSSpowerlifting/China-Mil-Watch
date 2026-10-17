"""Offline DAPA government open-data catalogue identity and scope qualification.

This accepts ONLY an owner-supplied, read-only copy of the official
schema.org catalogue JSON. Never fetches any host, requests source files,
counts article rows, admits source text or grants publication rights.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "ipr-korea-dapa-government-catalogue-lead/1"
OFFICIAL_URL = "https://www.data.go.kr/data/15118819/fileData.do"
CATALOGUE_JSON_URL = "https://www.data.go.kr/catalog/15118819/fileData.json"
DATASET_NAME = "방위사업청_보도자료"
DATASET_VERSION = "방위사업청_보도자료_20260910"
DAPA = "방위사업청"
ATTRIBUTION_LICENSE = "공공저작물 : 출처표시 (제 1유형)"
MAX_INPUT_BYTES = 65536


class CatalogueHold(ValueError):
    """Safe fixed error codes only; never dump untrusted metadata."""


def require(condition, reason):
    if not condition:
        raise CatalogueHold(reason)


def qualify(payload):
    """Accept only known metadata VERSION, not publication eligibility."""
    require(type(payload) is dict, "dapa_catalogue_invalid_schema")
    require(payload.get("@type") == "Dataset"
            and payload.get("name") == DATASET_NAME
            and payload.get("alternateName") == DATASET_VERSION,
            "dapa_catalogue_incorrect_dataset_identity")
    require(payload.get("url") == OFFICIAL_URL,
            "dapa_catalogue_unverified_official_url")
    require(type(payload.get("creator")) is dict
            and payload["creator"].get("@type") == "Organization"
            and payload["creator"].get("name") == DAPA,
            "dapa_catalogue_issuer_unverified")
    require(payload.get("encodingFormat") == "HWPX",
            "dapa_catalogue_encoding_changed")
    require(payload.get("datasetTimeInterval") == "연간",
            "dapa_catalogue_schedule_changed")
    require(payload.get("license") == ATTRIBUTION_LICENSE,
            "dapa_catalogue_licence_changed")
    require(payload.get("dateCreated") == "2026-09-12"
            and payload.get("datePublished") == "2026-09-12"
            and payload.get("dateModified") == "2026-09-12",
            "dapa_catalogue_version_changed")
    # No file count appears in this schema.org view, and an external
    # catalogue's 699 "rows" are NOT evidence of 699 press originals.
    return {
        "schema": SCHEMA,
        "status": "OFFICIAL_DAPA_CATALOGUE_METADATA_ONLY",
        "publisher": DAPA,
        "catalogue_url": CATALOGUE_JSON_URL,
        "dataset_url": OFFICIAL_URL,
        "verified_dataset_version": DATASET_VERSION,
        "verified_format_claim": "HWPX",
        "verified_cadence_claim": "annual",
        "verified_licence_claim": "KOGL_TYPE_1_ATTRIBUTION",
        "declared_rows_independently_verified": False,
        "individual_articles_verified": 0,
        "individual_source_identities_verified": 0,
        "original_hwp_bytes_verified": False,
        "document_body_reuse_cleared": False,
        "third_party_media_cleared": False,
        "article_collection_enabled": False,
        "publication_authorized": False,
    }


def read_local_metadata(filename):
    source = Path(filename)
    require(source.is_file() and not source.is_symlink()
            and source.stat().st_size <= MAX_INPUT_BYTES,
            "dapa_catalogue_metadata_file_invalid")
    try:
        return json.loads(source.read_text(encoding="utf-8", errors="strict"))
    except (ValueError, UnicodeError, OSError):
        raise CatalogueHold("dapa_catalogue_metadata_decode_failed") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--metadata-file", required=True,
                        help="Offline owner-supplied JSON only; no network")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(qualify(read_local_metadata(args.metadata_file)),
                         ensure_ascii=False, sort_keys=True))
        return 0
    except (CatalogueHold, OSError):
        print(json.dumps({"schema": SCHEMA, "status": "HOLD",
                          "publication_authorized": False}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
