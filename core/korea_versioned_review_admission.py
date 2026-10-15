"""Signed, exact-version Korea METADATA-ONLY review gate; no dispatch.

This module verifies possession of separately provisioned reviewer and owner
HMAC keys, not a human's identity or the underlying legal rights assertion.
Only a separate, source-aware importer could ever consume an eligible result.
No original body/title, model prompt, email or production file is written.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, datetime, timezone

from scripts import stage_korea_production_candidates as intake

SCHEMA = "ipr-korea-version-bound-metadata-human-decision/1"
SEAL = "ipr-korea-sealed-metadata-admission/1"
OUTPUT = "ipr-korea-signed-metadata-admission-check/1"
REVIEW_DOMAIN = b"IPR-KOREA-REVIEWER-METADATA-REVIEW-v1\x00"
OWNER_DOMAIN = b"IPR-KOREA-OWNER-METADATA-RELEASE-v1\x00"
HASH = re.compile(r"[0-9a-f]{64}\Z")
STAMP = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
CHECKS = (
    "rendered_hwpx_compared_to_complete_original_text",
    "issuer_publisher_article_id_and_dates_verified",
    "announcement_plan_discussion_vs_action_verified",
    "publisher_link_and_attribution_scope_verified",
    "embedded_media_and_unapproved_reproduction_excluded",
)
DECISION_KEYS = frozenset({
    "schema", "source_git_commit", "source_db_sha256",
    "source_identity", "candidate_version_sha256",
    "original_text_sha256", "original_hwpx_sha256",
    "publisher_html_sha256", "publisher_posted_date",
    "reviewer", "reviewed_at_utc", "review_checks",
    "rights_basis", "rights_reference",
    "disposition", "discrepancies",
    "original_body_use_authorized", "original_title_use_authorized",
    "media_use_authorized", "model_or_email_authorized",
})
OWNER_KEYS = frozenset({
    "purpose", "source_git_commit", "source_identity",
    "candidate_version_sha256", "owner", "decided_at_utc",
    "explicit_metadata_link_rehearsal_only",
    "source_body_redistribution_authorized", "translation_authorized",
    "media_authorized", "production_import_authorized",
    "site_publication_authorized", "model_or_email_authorized",
})
PACKET_KEYS = frozenset({
    "schema", "source_git_commit", "frozen_fourteen_ancestor",
    "source_db_sha256", "source_original_count", "records",
    "candidate_count", "approved_count", "public_body_count",
    "production_import_enabled", "reviewer_identity_authenticated",
    "per_source_rights_granted",
    "private_custody_and_independent_restore_verified",
    "collection_window_qualified",
    "model_email_or_publication_authorized",
})
RECORD_KEYS = frozenset({
    "candidate_version_sha256", "desk_id", "source_identity", "source_slug",
    "institution_id", "publisher_institution_id", "authority_tier",
    "originality", "language_tag", "canonical_source_url",
    "publisher_posted_date", "original_title_sha256", "original_text_sha256",
    "publisher_html_sha256", "original_hwpx_sha256", "first_seen_run",
    "editorial_exception", "disposition", "original_text_included",
    "original_title_included", "original_media_included",
    "approved_for_production", "approved_for_publication",
    "approved_for_model_or_email",
})
METADATA = "reviewed_official_link_metadata_only"
HOLD = "hold"
RIGHTS = "official_government_outbound_link_with_attribution_reviewed"


class AdmissionHold(ValueError):
    """Fixed diagnostics; never expose original source bodies or secrets."""


def need(test, reason):
    if not test:
        raise AdmissionHold(reason)


def _sha(value):
    need(type(value) is str and HASH.fullmatch(value) is not None,
         "source_pin_missing")
    return value


def _time(value):
    need(type(value) is str and STAMP.fullmatch(value) is not None,
         "review_time_invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise AdmissionHold("review_time_invalid") from None


def _key(secret):
    need(type(secret) is bytes and len(secret) >= 32,
         "trusted_key_unavailable")
    return secret


def _sign(payload, *, secret, domain):
    return hmac.new(_key(secret), domain + intake.canonical(payload),
                    hashlib.sha256).hexdigest()


def _packet(packet):
    need(type(packet) is dict and set(packet) == PACKET_KEYS
         and packet.get("schema") == intake.SCHEMA
         and packet.get("production_import_enabled") is False
         and packet.get("reviewer_identity_authenticated") is False
         and packet.get("per_source_rights_granted") is False
         and packet.get("model_email_or_publication_authorized") is False
         and type(packet.get("approved_count")) is int
         and packet["approved_count"] == 0
         and type(packet.get("public_body_count")) is int
         and packet["public_body_count"] == 0
         and packet.get("private_custody_and_independent_restore_verified") is False
         and packet.get("collection_window_qualified") is False
         and type(packet.get("records")) is list
         and 1 <= len(packet["records"]) <= intake.ROWS
         and type(packet.get("candidate_count")) is int
         and packet["candidate_count"] == len(packet["records"])
         and type(packet.get("source_original_count")) is int
         and packet["source_original_count"] == len(packet["records"]),
         "untrusted_or_activated_candidate_packet")
    gitsha = packet.get("source_git_commit")
    need(type(gitsha) is str and re.fullmatch(r"[0-9a-f]{40}", gitsha)
         is not None, "candidate_state_not_version_pinned")
    _sha(packet.get("source_db_sha256"))
    need(packet.get("frozen_fourteen_ancestor") == intake.FROZEN_14,
         "original_korea_archive_ancestor_changed")
    by_id = {}
    for row in packet["records"]:
        need(type(row) is dict and set(row) == RECORD_KEYS
             and row.get("desk_id") == "korea"
             and row.get("source_slug") == intake.SOURCE
             and row.get("authority_tier") == "B"
             and row.get("originality") == "syndicated"
             and row.get("language_tag") == "ko"
             and row.get("disposition") ==
                 "held_pending_exact_version_human_and_rights_review"
             and all(row.get(k) is False for k in (
                 "original_text_included", "original_title_included",
                 "original_media_included", "approved_for_production",
                 "approved_for_publication", "approved_for_model_or_email")),
             "untrusted_or_activated_candidate_record")
        sid = row.get("source_identity")
        need(type(sid) is str and intake.ARTICLE.fullmatch(sid) is not None
             and sid not in by_id
             and row.get("canonical_source_url") ==
                 intake.URL + sid.partition(":")[2],
             "unknown_duplicate_or_changed_korea_source")
        for key in ("candidate_version_sha256", "original_text_sha256",
                    "original_title_sha256", "original_hwpx_sha256",
                    "publisher_html_sha256"):
            _sha(row.get(key))
        need(row.get("publisher_posted_date") ==
             intake._date(row.get("publisher_posted_date"))
             and row.get("institution_id") == "kr_mnd"
             and row.get("publisher_institution_id") == "kr_policy_briefing"
             and type(row.get("first_seen_run")) is str
             and intake.RUN.fullmatch(row["first_seen_run"]) is not None,
             "malformed_source_candidate")
        check_version = intake.digest(intake.canonical({
            "source_identity": sid,
            "source_url": row["canonical_source_url"],
            "published_date": row["publisher_posted_date"],
            "original_text_sha256": row["original_text_sha256"],
            "publisher_html_sha256": row["publisher_html_sha256"],
            "original_hwpx_sha256": row["original_hwpx_sha256"],
        }))
        need(row["candidate_version_sha256"] == check_version,
             "candidate_version_digest_changed")
        need(row.get("editorial_exception") ==
             ("unresolved_2025_2026_excavation_year_issue_601"
              if sid == "korea-policy:156785161" else None),
             "source_editorial_exception_removed")
        by_id[sid] = row
    return by_id


def blank(packet, source_identity):
    rows = _packet(packet)
    need(source_identity in rows, "unknown_korea_record_for_review")
    row = rows[source_identity]
    return {
        "schema": SCHEMA,
        "source_git_commit": packet["source_git_commit"],
        "source_db_sha256": packet["source_db_sha256"],
        "source_identity": source_identity,
        "candidate_version_sha256": row["candidate_version_sha256"],
        "original_text_sha256": row["original_text_sha256"],
        "original_hwpx_sha256": row["original_hwpx_sha256"],
        "publisher_html_sha256": row["publisher_html_sha256"],
        "publisher_posted_date": row["publisher_posted_date"],
        "reviewer": None,
        "reviewed_at_utc": None,
        "review_checks": {name: False for name in CHECKS},
        "rights_basis": "unreviewed",
        "rights_reference": None,
        "disposition": HOLD,
        "discrepancies": None,
        "original_body_use_authorized": False,
        "original_title_use_authorized": False,
        "media_use_authorized": False,
        "model_or_email_authorized": False,
    }


def reviewer_sign(decision, *, secret):
    """Sign one already-prepared human statement, without judging its truth."""
    return {
        "decision": decision,
        "reviewer_hmac_sha256": _sign(
            decision, secret=secret, domain=REVIEW_DOMAIN),
    }


def owner_blank(decision):
    return {
        "purpose": "metadata_link_only_no_dispatch",
        "source_git_commit": decision["source_git_commit"],
        "source_identity": decision["source_identity"],
        "candidate_version_sha256": decision["candidate_version_sha256"],
        "owner": None,
        "decided_at_utc": None,
        "explicit_metadata_link_rehearsal_only": False,
        "source_body_redistribution_authorized": False,
        "translation_authorized": False,
        "media_authorized": False,
        "production_import_authorized": False,
        "site_publication_authorized": False,
        "model_or_email_authorized": False,
    }


def owner_sign(sealed_reviewer, owner, *, secret):
    """Sign owner decision plus exact reviewer document and signature."""
    payload = {"schema": SEAL, "review": sealed_reviewer, "owner": owner}
    return {
        **payload,
        "owner_hmac_sha256": _sign(
            payload, secret=secret, domain=OWNER_DOMAIN),
    }


def verify(packet, seal, *, reviewer_key, owner_key, as_of_utc):
    """Return bounded, metadata-only candidate receipt. Never publish."""
    rows = _packet(packet)
    need(type(seal) is dict and set(seal) ==
         {"schema", "review", "owner", "owner_hmac_sha256"}
         and seal["schema"] == SEAL, "invalid_review_seal")
    reviewed = seal["review"]
    owner = seal["owner"]
    need(type(reviewed) is dict and set(reviewed) ==
         {"decision", "reviewer_hmac_sha256"},
         "invalid_reviewer_seal")
    d = reviewed["decision"]
    need(type(d) is dict and set(d) == DECISION_KEYS
         and d.get("schema") == SCHEMA, "invalid_review_fields")
    sid = d["source_identity"]
    need(sid in rows, "unknown_review_source")
    expected = blank(packet, sid)
    pinned = (
        "source_git_commit", "source_db_sha256", "source_identity",
        "candidate_version_sha256", "original_text_sha256",
        "original_hwpx_sha256", "publisher_html_sha256",
        "publisher_posted_date",
    )
    need(all(d[k] == expected[k] for k in pinned),
         "review_source_version_drift")
    need(type(d["review_checks"]) is dict
         and set(d["review_checks"]) == set(CHECKS)
         and all(type(d["review_checks"][k]) is bool for k in CHECKS),
         "invalid_individual_human_checks")
    now = _time(as_of_utc)
    future = d["reviewed_at_utc"]
    reviewer = d["reviewer"]
    need(type(reviewer) is str and 3 <= len(reviewer) <= 100
         and reviewer == reviewer.strip()
         and not any(ord(ch) < 32 or ord(ch) == 127 or ch in "<>" for ch in reviewer),
         "reviewer_identity_statement_missing")
    stamp = _time(future)
    need(stamp <= now and stamp.date().isoformat() >= d["publisher_posted_date"],
         "reviewer_timestamp_before_source_or_future")
    need(type(d["discrepancies"]) in (str, type(None))
         and (d["discrepancies"] is None or
              (len(d["discrepancies"]) <= 800
               and not any(ord(ch) < 32 or ord(ch) == 127
                           for ch in d["discrepancies"]))),
         "invalid_discrepancies")
    need(d["disposition"] in (HOLD, METADATA),
         "review_disposition_invalid")
    need(d["rights_basis"] in ("unreviewed", RIGHTS),
         "invalid_rights_basis")
    need(type(d["rights_reference"]) in (str, type(None))
         and (d["rights_reference"] is None or
              (8 <= len(d["rights_reference"]) <= 300
               and not any(ord(ch) < 32 or ord(ch) == 127
                           or ch in "<>" for ch in d["rights_reference"]))),
         "invalid_rights_reference")
    for k in ("original_body_use_authorized", "original_title_use_authorized",
              "media_use_authorized", "model_or_email_authorized"):
        need(d[k] is False, "prohibited_original_or_model_permission")
    sig = reviewed["reviewer_hmac_sha256"]
    _sha(sig)
    want = _sign(d, secret=reviewer_key, domain=REVIEW_DOMAIN)
    need(hmac.compare_digest(sig, want), "untrusted_reviewer_signature")

    need(type(owner) is dict and set(owner) == OWNER_KEYS
         and owner["purpose"] == "metadata_link_only_no_dispatch"
         and owner["source_git_commit"] == d["source_git_commit"]
         and owner["source_identity"] == sid
         and owner["candidate_version_sha256"] ==
             d["candidate_version_sha256"],
         "owner_review_version_or_scope_mismatch")
    owner_name = owner["owner"]
    need(type(owner_name) is str and 3 <= len(owner_name) <= 100
         and owner_name == owner_name.strip()
         and not any(ord(ch) < 32 or ord(ch) == 127 or ch in "<>" for ch in owner_name)
         and owner_name != reviewer,
         "separate_named_owner_missing")
    owner_time = _time(owner["decided_at_utc"])
    need(stamp <= owner_time <= now, "owner_approval_before_review_or_future")
    for k in ("source_body_redistribution_authorized",
              "translation_authorized", "media_authorized",
              "production_import_authorized", "site_publication_authorized",
              "model_or_email_authorized"):
        need(owner[k] is False, "unauthorized_production_or_public_use")
    owner_sig = seal["owner_hmac_sha256"]
    _sha(owner_sig)
    want = _sign({k: seal[k] for k in ("schema", "review", "owner")},
                 secret=owner_key, domain=OWNER_DOMAIN)
    need(hmac.compare_digest(owner_sig, want), "untrusted_owner_signature")
    need(not hmac.compare_digest(_key(reviewer_key), _key(owner_key)),
         "reviewer_and_owner_keys_must_differ")
    is_ready = d["disposition"] == METADATA
    if is_ready:
        need(sid != "korea-policy:156785161"
             and rows[sid]["editorial_exception"] is None,
             "unresolved_original_year_dispute_blocks_admission")
        need(all(d["review_checks"].values())
             and d["rights_basis"] == RIGHTS
             and d["rights_reference"] is not None
             and owner["explicit_metadata_link_rehearsal_only"] is True
             and d["discrepancies"] in (None, ""),
             "exact_source_rights_human_or_owner_review_incomplete")
    else:
        need(owner["explicit_metadata_link_rehearsal_only"] is False,
             "held_source_cannot_be_owner_admitted")
    return {
        "schema": OUTPUT,
        "source_identity": sid,
        "candidate_version_sha256": d["candidate_version_sha256"],
        "source_git_commit": d["source_git_commit"],
        "metadata_only_disposable_db_rehearsal_candidate": is_ready,
        "recovered_original_text_included": False,
        "rights_claim_authenticated_by_signature": False,
        "human_identity_verified_beyond_key_possession": False,
        "production_rows_written": 0,
        "source_body_or_media_authorized": False,
        "site_publication_authorized": False,
        "model_or_email_authorized": False,
    }
