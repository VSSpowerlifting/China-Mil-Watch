"""Exact-source verified Korea metadata admission under standing owner policy.

Only government source identity, URL, date, issuer and SHA provenance are
admitted or released. Never read untrusted review seals as publication grants.
No original titles/bodies/media, model calls, analysis or editor emails.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config/korea_official_link_automatic_admission.json"
TABLE = "korea_official_source_records"
IDENT = re.compile(r"korea-policy:[0-9]{9}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
GIT_SHA = re.compile(r"[0-9a-f]{40}\Z")
PREFIX = "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
FIELDS = ["canonical_official_url", "publisher_posted_date", "official_issuer",
          "official_republisher", "source_identity"]
FLAGS = ("publish_original_korean_titles", "publish_original_text",
         "publish_document_media", "publish_translations_or_analysis",
         "publish_to_model_or_email")
EXPECTED_POLICY_FIELDS = {
    "schema", "approved_on_utc", "issuer", "republisher",
    "collector_source_slug", "source_url_prefix",
    "automatic_metadata_admission", "automatic_public_official_link_only",
    "public_fields", "independent_human_signoff_required_for_links_only",
    "documented_exception_holds", *FLAGS,
}


class MetadataHold(ValueError):
    """Fixed operator-safe refusal code; never include original text."""


def need(ok, reason):
    if not ok:
        raise MetadataHold(reason)


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def read_policy(path=POLICY):
    path = Path(path)
    need(path == POLICY and not path.is_symlink(),
         "standing_metadata_policy_must_be_repository_pinned")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise MetadataHold("standing_metadata_policy_unavailable") from None
    need(type(value) is dict and set(value) == EXPECTED_POLICY_FIELDS,
         "standing_metadata_policy_schema_drift")
    need(value["schema"] == "ipr-korea-standing-official-links-policy/1"
         and value["approved_on_utc"] == "2026-10-15"
         and value["issuer"] == "kr_mnd"
         and value["republisher"] == "kr_policy_briefing"
         and value["collector_source_slug"] == "kr_policy_mnd_releases"
         and value["source_url_prefix"] == PREFIX
         and type(value["automatic_metadata_admission"]) is bool
         and value["automatic_metadata_admission"] is True
         and type(value["automatic_public_official_link_only"]) is bool
         and value["automatic_public_official_link_only"] is True
         and type(value["independent_human_signoff_required_for_links_only"]) is bool
         and value["independent_human_signoff_required_for_links_only"] is False
         and value["public_fields"] == FIELDS
         and value["documented_exception_holds"] == ["korea-policy:156785161"]
         and all(value[k] is False for k in FLAGS),
         "standing_metadata_policy_not_narrowly_authorized")
    return value


def validate(packet, policy):
    need(type(packet) is dict and type(policy) is dict,
         "invalid_verified_packet")
    need(set(policy) == EXPECTED_POLICY_FIELDS
         and policy["public_fields"] == FIELDS
         and all(policy[k] is False for k in FLAGS)
         and policy["automatic_metadata_admission"] is True
         and policy["automatic_public_official_link_only"] is True
         and policy["documented_exception_holds"] == ["korea-policy:156785161"]
         and policy["issuer"] == "kr_mnd"
         and policy["republisher"] == "kr_policy_briefing",
         "not_an_authorized_metadata_policy")
    need(packet.get("schema") == "ipr-korea-versioned-production-candidates/1"
         and packet.get("source_original_count") == packet.get("candidate_count")
         and type(packet.get("source_original_count")) is int
         and 5 <= packet["source_original_count"] <= 5000
         and type(packet.get("records")) is list
         and len(packet["records"]) == packet["source_original_count"]
         and type(packet.get("source_git_commit")) is str
         and GIT_SHA.fullmatch(packet["source_git_commit"])
         and type(packet.get("source_db_sha256")) is str
         and SHA.fullmatch(packet["source_db_sha256"])
         and packet.get("production_import_enabled") is False
         and packet.get("approved_count") == 0
         and type(packet.get("approved_count")) is int
         and packet.get("public_body_count") == 0
         and type(packet.get("public_body_count")) is int,
         "unverifiable_source_candidate_packet")
    for flag in ("model_email_or_publication_authorized",
                 "reviewer_identity_authenticated", "per_source_rights_granted"):
        need(packet.get(flag) is False, "source_packet_rights_scope_changed")

    rows = []
    seen = set()
    for candidate in packet["records"]:
        need(type(candidate) is dict, "malformed_official_candidate")
        ident = candidate.get("source_identity")
        need(type(ident) is str and IDENT.fullmatch(ident)
             and ident not in seen, "duplicate_or_invalid_source_identity")
        seen.add(ident)
        date_string = candidate.get("publisher_posted_date")
        need(type(date_string) is str, "invalid_official_publication_date")
        try:
            parsed = date.fromisoformat(date_string)
        except ValueError:
            raise MetadataHold("invalid_official_publication_date") from None
        need(parsed.isoformat() == date_string,
             "invalid_official_publication_date")
        need(candidate.get("canonical_source_url") == PREFIX + ident[13:]
             and candidate.get("source_slug") == "kr_policy_mnd_releases"
             and candidate.get("institution_id") == "kr_mnd"
             and candidate.get("publisher_institution_id") == "kr_policy_briefing"
             and candidate.get("authority_tier") == "B"
             and candidate.get("originality") == "syndicated"
             and candidate.get("language_tag") == "ko"
             and candidate.get("approved_for_production") is False
             and candidate.get("approved_for_publication") is False
             and candidate.get("original_text_included") is False
             and candidate.get("original_title_included") is False
             and candidate.get("original_media_included") is False,
             "korea_source_or_rights_scope_changed")
        pins = ("candidate_version_sha256", "original_title_sha256",
                "original_text_sha256", "publisher_html_sha256",
                "original_hwpx_sha256")
        need(all(type(candidate.get(k)) is str and SHA.fullmatch(candidate[k])
                 for k in pins), "original_capture_provenance_missing")
        # Source-version pin is derived from the same exact original hashes as
        # stage_korea_production_candidates._normalized. Caller must ALSO call
        # stage.build against the actual clean, archived Git checkout.
        v = hashlib.sha256(canon({
            "source_identity": ident, "source_url": PREFIX + ident[13:],
            "published_date": date_string,
            "original_text_sha256": candidate["original_text_sha256"],
            "publisher_html_sha256": candidate["publisher_html_sha256"],
            "original_hwpx_sha256": candidate["original_hwpx_sha256"],
        })).hexdigest()
        need(candidate["candidate_version_sha256"] == v,
             "candidate_version_cannot_be_authenticated")
        hold = ident in policy["documented_exception_holds"]
        need((candidate.get("editorial_exception") is not None) == hold,
             "editorial_exception_scope_changed")
        if hold:
            continue
        rows.append((
            ident, PREFIX + ident[13:], date_string,
            packet["source_git_commit"], packet["source_db_sha256"], v,
            candidate["original_title_sha256"],
            candidate["original_text_sha256"],
            candidate["publisher_html_sha256"],
            candidate["original_hwpx_sha256"],
            "kr_mnd", "kr_policy_briefing", "ko", "B", "syndicated",
            "official_link_only",
        ))
    return sorted(rows)


def admit(conn: sqlite3.Connection, packet, policy, *, as_of_utc):
    """Atomic, no-copy import. All source originals MUST be reverified first."""
    need(type(as_of_utc) is str
         and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", as_of_utc),
         "untrusted_admission_clock")
    rows = validate(packet, policy)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE)}
    need("candidate_version_sha256" in columns
         and "public_scope" in columns
         and "released_at_utc" in columns,
         "metadata_production_schema_not_migrated")
    added = unchanged = 0
    # Savepoint allows transaction-level rollback even when the caller owns
    # other pending writes. No SQL ever includes original Korean bodies.
    conn.execute("SAVEPOINT korea_official_metadata_admission")
    try:
        for row in rows:
            old = conn.execute(
                "SELECT canonical_official_url, publisher_posted_date, "
                "candidate_version_sha256, public_scope "
                "FROM korea_official_source_records WHERE source_identity=?",
                (row[0],)).fetchone()
            if old is not None:
                need(tuple(old) == (row[1], row[2], row[5], "official_link_only"),
                     "reviewed_source_version_or_status_changed")
                unchanged += 1
                continue
            conn.execute(
                "INSERT INTO korea_official_source_records "
                "(source_identity,canonical_official_url,publisher_posted_date,"
                "source_git_commit,source_db_sha256,candidate_version_sha256,"
                "original_title_sha256,original_text_sha256,publisher_html_sha256,"
                "original_hwpx_sha256,official_issuer,official_republisher,"
                "source_language,authority_tier,originality,public_scope,"
                "admitted_at_utc,released_at_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*row, as_of_utc, as_of_utc),
            )
            added += 1
        need(conn.execute("PRAGMA foreign_key_check").fetchall() == [],
             "korea_metadata_foreign_key_violation")
        conn.execute("RELEASE SAVEPOINT korea_official_metadata_admission")
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT korea_official_metadata_admission")
        conn.execute("RELEASE SAVEPOINT korea_official_metadata_admission")
        raise
    return {
        "schema": "ipr-korea-official-link-production-admission/1",
        "source_git_commit": packet["source_git_commit"],
        "new_official_links_admitted": added,
        "unchanged_official_links": unchanged,
        "explicit_exception_held": len(packet["records"]) - len(rows),
        "source_bodies_copied": False, "titles_or_media_copied": False,
        "analysis_or_model_performed": False,
    }
