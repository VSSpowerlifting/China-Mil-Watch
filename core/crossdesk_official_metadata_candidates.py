"""Held official-link intake for AFP and Kemhan from verified, pinned shadow Git.

This is a first-class deterministic preparation boundary, NOT authorization for
production admission or publication. The upstream private_country_desk_reader
must re-open the literal source Git commit and validate source-specific records.
No original titles, bodies, images, translations or model output leave here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from urllib.parse import urlsplit

SCHEMA = "ipr-afp-kemhan-held-metadata-candidates/1"
READER_SCHEMA = "ipr-private-shadow-desk-reader/1"
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
RUN = re.compile(r"[1-9][0-9]*-[1-9][0-9]*\Z")
AFP = re.compile(r"afp:([1-9][0-9]*)\Z")
AFP_PATH = re.compile(r"/news/[a-z0-9]+(?:-[a-z0-9]+)*\Z")
KEMHAN_PATH = re.compile(
    r"/([0-9]{4})/([0-9]{2})/([0-9]{2})/[a-z0-9]+(?:-[a-z0-9]+)*\.html\Z"
)
KEMHAN_HELD = (
    "/2026/10/02/kunker-ke-kaltara-menhan-sjafrie-tinjau-yonif-tp-880-banuanta-"
    "di-bulungan-tegaskan-kemampuan-tempur-dan-teritorial-pembangunan-"
    "untuk-kedaulatan-perbatasan.html"
)
FAMILIES = {
    "ph_afp_articles": {
        "desk": "philippines", "issuer": "ph_afp", "publisher": "ph_afp",
        "republisher": None,
        "host": "www.afp.mil.ph", "identity_prefix": "afp:"
    },
    "id_kemhan_news": {
        "desk": "indonesia", "issuer": None, "publisher": "id_kemhan",
        "republisher": None,
        "host": "www.kemhan.go.id", "identity_prefix": "kemhan:"
    },
}
READER_KEYS = frozenset({
    "schema", "status", "query", "desk_filter", "sources", "matched_total",
    "results", "truncated", "source_body_text_exported",
    "automated_source_rights_approved", "human_source_review_completed",
    "production_records_changed", "country_desks_promoted",
    "public_release_authorized"
})
ROW_KEYS = frozenset({
    "country", "institution", "source_slug", "identity", "url", "title",
    "published_date", "first_seen_run", "state_commit", "review_status"
})


class IntakeHold(ValueError):
    """Fixed error code only; source text never included in errors."""


def need(ok, reason):
    if not ok:
        raise IntakeHold(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def canonical_date(value):
    need(type(value) is str, "date_not_string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise IntakeHold("invalid_publisher_date") from None
    need(parsed.isoformat() == value, "noncanonical_publisher_date")
    return value


def exact_source_url(identity, url, day, family):
    """Restrict each family to its own official canonical URL grammar."""
    need(type(identity) is str and type(url) is str and len(url) < 2000,
         "invalid_official_identity_or_url")
    parts = urlsplit(url)
    spec = FAMILIES[family]
    need(parts.scheme == "https" and parts.netloc == spec["host"]
         and not parts.username and not parts.password and parts.port is None
         and not parts.query and not parts.fragment
         and all(ord(char) > 32 for char in url),
         "noncanonical_or_foreign_official_url")
    if family == "ph_afp_articles":
        need(AFP.fullmatch(identity) is not None
             and AFP_PATH.fullmatch(parts.path) is not None,
             "invalid_afp_official_identity")
    else:
        found = KEMHAN_PATH.fullmatch(parts.path)
        need(found is not None and identity == "kemhan:" + parts.path,
             "invalid_kemhan_official_identity")
        try:
            path_day = date(*map(int, found.groups())).isoformat()
        except ValueError:
            raise IntakeHold("invalid_kemhan_path_date") from None
        need(path_day == day, "kemhan_date_and_url_disagree")
    return parts.path


def build(report, family):
    """Transform one complete authenticated private-reader report into HELD rows.

    This does not independently authenticate Git, source capture bytes, Actions
    histories, reuse rights, or human review. Those must be established by the
    producer and independent production activation gate, not by JSON flags.
    """
    need(family in FAMILIES, "unapproved_metadata_source_family")
    spec = FAMILIES[family]
    need(type(report) is dict and set(report) == READER_KEYS,
         "private_reader_schema_drift")
    need(report["schema"] == READER_SCHEMA
         and report["status"] == "private_research_not_source_admitted"
         and report["query"] == ""
         and report["desk_filter"] == spec["desk"]
         and report["truncated"] is False
         and report["source_body_text_exported"] is False
         and report["automated_source_rights_approved"] is False
         and report["human_source_review_completed"] is False
         and report["production_records_changed"] is False
         and report["country_desks_promoted"] is False
         and report["public_release_authorized"] is False,
         "private_reader_not_full_held_evidence")
    sources, records = report["sources"], report["results"]
    need(type(sources) is list and len(sources) == 1
         and type(sources[0]) is dict
         and set(sources[0]) == {
             "source_slug", "country", "institution", "state_commit",
             "stored_records", "query_matches"}
         and sources[0]["source_slug"] == family
         and sources[0]["country"] == spec["desk"]
         and type(records) is list
         and type(report["matched_total"]) is int
         and type(sources[0]["stored_records"]) is int
         and 1 <= len(records) <= 300
         and report["matched_total"] == len(records)
         and sources[0]["stored_records"] == len(records)
         and sources[0]["query_matches"] == len(records),
         "incomplete_source_family_snapshot")
    sha = sources[0]["state_commit"]
    need(type(sha) is str and SHA40.fullmatch(sha) is not None,
         "source_git_commit_not_pinned")
    seen_ids, seen_urls, proposed = set(), set(), []
    for raw in records:
        need(type(raw) is dict and set(raw) == ROW_KEYS,
             "unexpected_source_record_fields")
        ident, url, day = raw["identity"], raw["url"], raw["published_date"]
        canonical_date(day)
        path = exact_source_url(ident, url, day, family)
        need(raw["source_slug"] == family and raw["country"] == spec["desk"]
             and raw["state_commit"] == sha
             and raw["institution"] == sources[0]["institution"]
             and raw["review_status"] == "not_human_reviewed_for_public_use"
             and type(raw["title"]) is str and bool(raw["title"].strip())
             and type(raw["first_seen_run"]) is str
             and (RUN.fullmatch(raw["first_seen_run"]) is not None or
                  (family == "id_kemhan_news" and
                   raw["first_seen_run"] == "local-native-20261006-indonesia")),
             "source_version_or_review_state_drift")
        need(ident not in seen_ids and url not in seen_urls,
             "duplicate_source_identity_or_url")
        seen_ids.add(ident)
        seen_urls.add(url)
        exception = "publisher_geography_discrepancy" if (
            family == "id_kemhan_news" and path == KEMHAN_HELD) else None
        source = {
            "desk": spec["desk"],
            "source_family": family,
            "source_identity": ident,
            "canonical_official_url": url,
            "publisher_posted_date": day,
            "official_issuer": spec["issuer"],
            "official_publisher": spec["publisher"],
            "official_republisher": spec["republisher"],
            "source_git_commit": sha,
            "first_seen_run": raw["first_seen_run"],
        }
        proposed.append({
            **source,
            "metadata_version_sha256": hashlib.sha256(canonical(source)).hexdigest(),
            "review_state": "held",
            "semantic_exception_hold": exception,
            "production_admission_authorized": False,
            "automatic_public_link_authorized": False,
            "publisher_body_reuse_authorized": False,
        })
    proposed.sort(key=lambda r: (r["source_identity"], r["canonical_official_url"]))
    result = {
        "schema": SCHEMA,
        "source_family": family,
        "desk": spec["desk"],
        "source_git_commit": sha,
        "candidate_count": len(proposed),
        "semantic_exception_count": sum(r["semantic_exception_hold"] is not None
                                        for r in proposed),
        "all_candidates_held": True,
        "production_import_enabled": False,
        "public_release_enabled": False,
        "source_capture_bytes_authenticated_by_this_projection": False,
        "seven_scheduled_days_authenticated_by_this_projection": False,
        "source_specific_reuse_authorized_by_this_projection": False,
        "original_title_or_body_exported": False,
        "records": proposed,
    }
    result["metadata_manifest_sha256"] = hashlib.sha256(canonical(proposed)).hexdigest()
    return result
