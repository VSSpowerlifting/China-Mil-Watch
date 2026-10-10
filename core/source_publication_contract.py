"""Synthetic-only prototype of an IPR private-evidence/public-projection boundary.

This module is NOT wired to collection, publishing, the real archive, or any
source-use authority. Rights references in caller-supplied data are NOT grants.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from urllib.parse import urlsplit


PRIVATE_SCHEMA = "ipr-private-evidence/1"
PUBLIC_SCHEMA = "ipr-public-record/1"
MANIFEST_SCHEMA = "ipr-public-projection/1"
RECEIPT_SCHEMA = "ipr-source-action-review/1"

_PRIVATE_KEYS = frozenset({
    "schema", "record_id", "source_slug", "institution_id", "language_tag",
    "publisher_date", "captured_on", "source_url", "title_original",
    "text_original", "machine_summary", "original_sha256",
})
_RECEIPT_KEYS = frozenset({
    "schema", "source_slug", "action", "status", "reviewed_on", "reference",
})
_PUBLIC_KEYS = frozenset({
    "schema", "record_id", "source_slug", "institution_id", "language_tag",
    "publisher_date", "captured_on", "original_sha256", "text_access",
    "citation_path", "source_use", "original_url_public",
})
_ID_RE = re.compile(r"[a-z][a-z0-9_]{0,63}\Z", re.ASCII)
_LANG_RE = re.compile(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}\Z", re.ASCII)
_SHA_RE = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_ACTIONS = frozenset({"link", "brief_quote", "full_body", "photo", "private_retention"})
_STATUS = frozenset({"unreviewed", "requested", "approved", "denied", "expired"})


class ProjectionContractError(ValueError):
    """Safe fixed diagnostics: source text and supplied values are never echoed."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProjectionContractError(code)


def _exact_mapping(obj, keys, code):
    _require(type(obj) is dict and set(obj) == keys, code)


def _date(value):
    _require(type(value) is str and bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)),
             "invalid_date")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ProjectionContractError("invalid_date") from None


def _slug(value):
    _require(type(value) is str and bool(_ID_RE.fullmatch(value)), "invalid_identifier")


def _text(value, *, required=False, max_length=500000):
    _require(type(value) is str and len(value) <= max_length and
             not any(ord(char) < 32 and char not in "\n\r\t" for char in value) and
             (not required or bool(value.strip())), "invalid_text")


def original_digest(title: str, body: str) -> str:
    """S1-specific digest; does not replace the production corpus fingerprint."""
    _text(title, required=True, max_length=10000)
    _text(body)
    blob = b"IPR-S1-ORIGINAL-V1\0" + title.encode("utf-8") + b"\0" + body.encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def validate_private_record(record: dict) -> dict:
    """Validate one explicitly versioned fictional evidence record; never log values."""
    _exact_mapping(record, _PRIVATE_KEYS, "invalid_private_record_fields")
    _require(record["schema"] == PRIVATE_SCHEMA, "invalid_private_schema")
    _require(type(record["record_id"]) is int and record["record_id"] > 0,
             "invalid_record_id")
    _slug(record["source_slug"])
    _slug(record["institution_id"])
    _require(type(record["language_tag"]) is str and
             bool(_LANG_RE.fullmatch(record["language_tag"])), "invalid_language")
    _date(record["publisher_date"])
    _date(record["captured_on"])
    _require(record["captured_on"] >= record["publisher_date"], "invalid_capture_date")
    _require(type(record["source_url"]) is str and len(record["source_url"]) <= 2048,
             "invalid_source_url")
    try:
        parsed = urlsplit(record["source_url"])
        valid_url = (parsed.scheme == "https" and bool(parsed.hostname) and
                     parsed.username is None and parsed.password is None and
                     parsed.port in (None, 443) and not parsed.fragment and
                     not any(ord(c) < 33 for c in record["source_url"]))
    except ValueError:
        valid_url = False
    _require(valid_url, "invalid_source_url")
    _text(record["title_original"], required=True, max_length=10000)
    _text(record["text_original"])
    _text(record["machine_summary"], max_length=25000)
    _require(type(record["original_sha256"]) is str and
             bool(_SHA_RE.fullmatch(record["original_sha256"])), "invalid_digest")
    _require(record["original_sha256"] == original_digest(
        record["title_original"], record["text_original"]), "digest_mismatch")
    return record


def validate_review_receipt(receipt: dict) -> dict:
    """Shape only. A self-authored receipt cannot confer publisher permission."""
    _exact_mapping(receipt, _RECEIPT_KEYS, "invalid_receipt_fields")
    _require(receipt["schema"] == RECEIPT_SCHEMA, "invalid_receipt_schema")
    _slug(receipt["source_slug"])
    _require(type(receipt["action"]) is str and receipt["action"] in _ACTIONS,
             "invalid_action")
    _require(type(receipt["status"]) is str and receipt["status"] in _STATUS,
             "invalid_review_status")
    _date(receipt["reviewed_on"])
    _require(type(receipt["reference"]) is str and
             bool(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9:./_-]{1,127}",
                               receipt["reference"])), "invalid_review_reference")
    return receipt


def validate_public_record(record: dict) -> dict:
    """Strict v1 reader for a mechanically projected, still-unapproved item."""
    _exact_mapping(record, _PUBLIC_KEYS, "invalid_public_record_fields")
    _require(record["schema"] == PUBLIC_SCHEMA, "invalid_public_schema")
    _require(type(record["record_id"]) is int and record["record_id"] > 0,
             "invalid_record_id")
    _slug(record["source_slug"])
    _slug(record["institution_id"])
    _require(type(record["language_tag"]) is str and
             bool(_LANG_RE.fullmatch(record["language_tag"])), "invalid_language")
    _date(record["publisher_date"])
    _date(record["captured_on"])
    _require(record["captured_on"] >= record["publisher_date"], "invalid_capture_date")
    _require(type(record["original_sha256"]) is str and
             bool(_SHA_RE.fullmatch(record["original_sha256"])), "invalid_digest")
    _require(record["text_access"] in
             ("withheld_pending_rights_review", "no_captured_body"),
             "invalid_text_access")
    _require(record["citation_path"] == "record/%d.html" % record["record_id"],
             "invalid_citation_path")
    _require(record["source_use"] == "not_authorized_by_projection" and
             record["original_url_public"] is False, "unverified_public_authorization")
    return record


def validate_public_manifest(manifest: dict) -> dict:
    """Reject changed, re-ordered or falsely approved public manifests."""
    _exact_mapping(manifest, frozenset({"schema", "records", "record_count",
                                      "public_projection_sha256",
                                      "eligible_for_publication"}),
                   "invalid_public_manifest_fields")
    _require(manifest["schema"] == MANIFEST_SCHEMA and
             manifest["eligible_for_publication"] is False,
             "unverified_manifest_authorization")
    records = manifest["records"]
    _require(type(records) is list and type(manifest["record_count"]) is int and
             manifest["record_count"] == len(records), "invalid_public_record_count")
    for record in records:
        validate_public_record(record)
    ids = [item["record_id"] for item in records]
    _require(ids == sorted(set(ids)), "unsorted_or_duplicate_public_records")
    encoded = json.dumps(records, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    _require(manifest["public_projection_sha256"] == hashlib.sha256(encoded).hexdigest(),
             "public_projection_digest_mismatch")
    return manifest


def project_public_record(private: dict, reviews=()) -> dict:
    """Strict public allowlist; all body, title, summary and links are held.

    Even a syntactically 'approved' receipt is untrusted. S1 has no verified
    grant authority, so caller-provided review data NEVER enables disclosure.
    """
    validate_private_record(private)
    _require(type(reviews) in (list, tuple), "invalid_receipts")
    for receipt in reviews:
        validate_review_receipt(receipt)
        _require(receipt["source_slug"] == private["source_slug"],
                 "receipt_source_mismatch")
    result = {
        "schema": PUBLIC_SCHEMA,
        "record_id": private["record_id"],
        "source_slug": private["source_slug"],
        "institution_id": private["institution_id"],
        "language_tag": private["language_tag"],
        "publisher_date": private["publisher_date"],
        "captured_on": private["captured_on"],
        "original_sha256": private["original_sha256"],
        "text_access": ("withheld_pending_rights_review" if private["text_original"].strip()
                        else "no_captured_body"),
        "citation_path": "record/%d.html" % private["record_id"],
        "source_use": "not_authorized_by_projection",
        "original_url_public": False,
    }
    validate_public_record(result)
    return result


def project_public_manifest(private_records: list, reviews=()) -> dict:
    """Deterministic ordered public metadata projection, independent of input order."""
    _require(type(private_records) in (list, tuple), "invalid_collection")
    projections = []
    seen = set()
    for record in private_records:
        projected = project_public_record(record, reviews)
        _require(projected["record_id"] not in seen, "duplicate_record_id")
        seen.add(projected["record_id"])
        projections.append(projected)
    projections.sort(key=lambda item: item["record_id"])
    encoded = json.dumps(projections, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    result = {
        "schema": MANIFEST_SCHEMA,
        "records": projections,
        "record_count": len(projections),
        "public_projection_sha256": hashlib.sha256(encoded).hexdigest(),
        "eligible_for_publication": False,
    }
    return validate_public_manifest(result)
