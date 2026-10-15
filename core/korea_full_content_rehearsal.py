"""Exact-source Korea full-content PRIVATE rehearsal, never public admission.

The existing shadow-stage verifier authenticates original HWPX and captures.
This module separately validates source/rights/draft identity and alignment.
All outputs remain unapproved, even with a KOGL notice observation.
No code in this module opens the production DB, sends a model request, or publishes.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "ipr-korea-private-full-content-rehearsal/1"
RIGHTS_SCHEMA = "ipr-korea-source-rights-observation/1"
DRAFT_SCHEMA = "ipr-korea-machine-source-draft/1"
POLICY_URL = "https://www.korea.kr/guide/copyRight.do"
SOURCE_PREFIX = "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
IDENT = re.compile(r"korea-policy:[0-9]{9}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
STAMP = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
PUBLICATION_HOLDS = (
    "rights_observation_is_not_independent_authorization",
    "source_language_and_translation_need_semantic_review",
    "model_source_notes_are_not_human_editorial_judgment",
    "no_full_content_production_or_publication_authority",
)


class ContentHold(ValueError):
    """Static safe codes only: never print publisher bodies or model outputs."""


def require(condition, code):
    if not condition:
        raise ContentHold(code)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def exact(obj, fields, code):
    require(type(obj) is dict and set(obj) == set(fields), code)


def digest(value, code):
    require(type(value) is str and SHA.fullmatch(value) is not None, code)


def bounded(value, code, limit=20000):
    require(type(value) is str and bool(value.strip()) and len(value) <= limit
            and not any(ord(c) < 32 and c not in "\n\r\t" for c in value), code)


def utc(value):
    require(type(value) is str and STAMP.fullmatch(value) is not None,
            "draft_timestamp_invalid")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        raise ContentHold("draft_timestamp_invalid") from None


def original_paragraphs(original):
    # Preserve the text bytes within each nonblank line. Never conflate
    # two publisher paragraphs to manufacture plausible model alignment.
    parts = [part for part in original.replace("\r\n", "\n").split("\n")
             if part.strip()]
    require(1 <= len(parts) <= 2000, "original_paragraph_count_out_of_bounds")
    require(all(len(part) <= 20000 for part in parts),
            "original_paragraph_exceeds_limit")
    return parts


def check_candidate(stage_row, original, rights, draft):
    """Strict exact-version/paragraph/citation checks, never rights approval.

    stage_row MUST be obtained from stage_korea_production_candidates.build()
    on a clean, independently HWPX-verified shadow checkout. Passing arbitrary
    caller-supplied stage_row is only useful for synthetic offline tests.
    """
    required_stage = (
        "source_identity", "candidate_version_sha256", "original_text_sha256",
        "original_title_sha256", "publisher_html_sha256", "original_hwpx_sha256",
        "canonical_source_url", "publisher_posted_date", "editorial_exception",
        "source_slug", "institution_id", "publisher_institution_id",
    )
    require(type(stage_row) is dict and all(k in stage_row for k in required_stage),
            "incomplete_verified_stage_identity")
    identity = stage_row["source_identity"]
    require(type(identity) is str and IDENT.fullmatch(identity) is not None
            and stage_row["canonical_source_url"] == SOURCE_PREFIX + identity[13:]
            and stage_row["source_slug"] == "kr_policy_mnd_releases"
            and stage_row["institution_id"] == "kr_mnd"
            and stage_row["publisher_institution_id"] == "kr_policy_briefing",
            "source_family_outside_korea_pilot")
    require(stage_row["editorial_exception"] is None,
            "existing_korean_editorial_exception_hold")
    for name in ("candidate_version_sha256", "original_text_sha256",
                 "original_title_sha256", "publisher_html_sha256",
                 "original_hwpx_sha256"):
        digest(stage_row[name], "stage_source_digest_invalid")

    fields = ("source_identity", "url", "title_original",
              "text_original", "published_date")
    require(type(original) is dict and all(k in original for k in fields),
            "source_original_incomplete")
    bounded(original["title_original"], "source_original_title_invalid", 3000)
    bounded(original["text_original"], "source_original_body_invalid", 200000)
    require(original["source_identity"] == identity
            and original["url"] == stage_row["canonical_source_url"]
            and original["published_date"] == stage_row["publisher_posted_date"]
            and sha(original["title_original"]) == stage_row["original_title_sha256"]
            and sha(original["text_original"]) == stage_row["original_text_sha256"],
            "original_text_not_pinned_to_verified_hwpx_stage")
    paragraphs = original_paragraphs(original["text_original"])

    exact(rights, (
        "schema", "source_identity", "candidate_version_sha256",
        "publisher_html_sha256", "notice_sha256", "publisher_policy_url",
        "notice_marker", "notice_scope", "notice_observed_at_utc",
        "media_reuse_allowed", "hwpx_file_redistribution_allowed",
        "independently_approved",
    ), "rights_observation_fields_invalid")
    require(rights["schema"] == RIGHTS_SCHEMA
            and rights["source_identity"] == identity
            and rights["candidate_version_sha256"] == stage_row["candidate_version_sha256"]
            and rights["publisher_html_sha256"] == stage_row["publisher_html_sha256"]
            and rights["publisher_policy_url"] == POLICY_URL,
            "rights_observation_not_source_version_bound")
    digest(rights["notice_sha256"], "rights_notice_digest_missing")
    utc(rights["notice_observed_at_utc"])
    require(rights["notice_marker"] == "KOGL_TYPE_1"
            and rights["notice_scope"] == "publisher_text_only"
            and rights["media_reuse_allowed"] is False
            and rights["hwpx_file_redistribution_allowed"] is False
            and rights["independently_approved"] is False,
            "rights_pilot_scope_overstated")

    exact(draft, (
        "schema", "source_identity", "candidate_version_sha256",
        "original_text_sha256", "generated_at_utc", "model_id",
        "content_label", "translation_paragraphs", "source_notes",
    ), "machine_draft_fields_invalid")
    require(draft["schema"] == DRAFT_SCHEMA
            and draft["source_identity"] == identity
            and draft["candidate_version_sha256"] == stage_row["candidate_version_sha256"]
            and draft["original_text_sha256"] == stage_row["original_text_sha256"]
            and draft["content_label"] == "unreviewed_machine_draft",
            "machine_draft_not_source_version_bound")
    utc(draft["generated_at_utc"])
    bounded(draft["model_id"], "machine_model_identity_missing", 128)
    translations = draft["translation_paragraphs"]
    require(type(translations) is list and len(translations) == len(paragraphs),
            "translation_paragraph_count_mismatch")
    for index, (ko, entry) in enumerate(zip(paragraphs, translations), 1):
        exact(entry, ("source_index", "source_paragraph_sha256",
                      "text_en", "language", "status"),
              "translation_paragraph_fields_invalid")
        require(type(entry["source_index"]) is int
                and entry["source_index"] == index
                and entry["source_paragraph_sha256"] == sha(ko)
                and entry["language"] == "en"
                and entry["status"] == "machine_unreviewed",
                "translation_alignment_or_label_invalid")
        bounded(entry["text_en"], "translation_body_missing_or_invalid")

    notes = draft["source_notes"]
    require(type(notes) is list and 1 <= len(notes) <= 12,
            "source_note_count_invalid")
    for note in notes:
        exact(note, ("kind", "text_en", "source_indices", "status"),
              "source_note_fields_invalid")
        require(note["kind"] == "attributed_official_source_observation"
                and note["status"] == "machine_unreviewed",
                "machine_note_cannot_claim_editorial_judgment")
        bounded(note["text_en"], "machine_source_note_invalid", 3000)
        indices = note["source_indices"]
        require(type(indices) is list and 1 <= len(indices) <= 8
                and all(type(n) is int and 1 <= n <= len(paragraphs)
                        for n in indices)
                and indices == sorted(set(indices)),
                "machine_note_citation_not_supported_by_source_indices")

    return {
        "schema": SCHEMA,
        "status": "PRIVATE_REVIEW_ONLY",
        "source_identity": identity,
        "candidate_version_sha256": stage_row["candidate_version_sha256"],
        "source_git_capture_bound": True,
        "source_text_sha256": stage_row["original_text_sha256"],
        "observed_rights_marker": "KOGL_TYPE_1_TEXT_ONLY_UNAPPROVED",
        "translation_paragraph_count": len(translations),
        "machine_note_count": len(notes),
        "paragraph_alignment_structurally_verified": True,
        "translation_semantics_verified": False,
        "claims_fact_checked": False,
        "rights_clearance_verified": False,
        "original_document_redistribution_authorized": False,
        "translation_publication_authorized": False,
        "substantive_analysis_publication_authorized": False,
        "media_publication_authorized": False,
        "model_invocation_performed": False,
        "public_files_written": 0,
        "production_records_written": 0,
        "publication_holds": list(PUBLICATION_HOLDS),
    }


def render_private_html(stage_row, original, rights, draft):
    """Return escaped, noindex, non-public HTML; no attached HWPX or media."""
    receipt = check_candidate(stage_row, original, rights, draft)
    esc = lambda value: html.escape(value, quote=True)
    rows = original_paragraphs(original["text_original"])
    dual = "".join(
        "<section><p lang='ko'>" + esc(ko) + "</p><p lang='en'>"
        + esc(en["text_en"]) + "</p></section>"
        for ko, en in zip(rows, draft["translation_paragraphs"]))
    notes = "".join("<li>" + esc(note["text_en"]) + " (source paragraphs "
                    + ", ".join(str(i) for i in note["source_indices"])
                    + ")</li>" for note in draft["source_notes"])
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='robots' content='noindex,nofollow,noarchive'>"
        "<title>PRIVATE Korea source review</title></head><body>"
        "<h1>PRIVATE / UNAPPROVED / DO NOT PUBLISH</h1>"
        "<p>Publisher: Republic of Korea Policy Briefing; issuer: "
        "Ministry of National Defense. This is a government statement, "
        "not independent confirmation of its claims.</p>"
        "<p>Text-only KOGL Type 1 observation is NOT rights approval. "
        "Never rehost HWPX attachments, images or embedded media.</p>"
        "<p><a rel='noopener noreferrer' href='"
        + esc(stage_row["canonical_source_url"]) + "'>Official release</a> "
        "<a rel='noopener noreferrer' href='" + esc(POLICY_URL)
        + "'>Publisher copyright policy</a></p>"
        "<p>Exact source version: " + esc(receipt["candidate_version_sha256"])
        + "</p><h2>Source text and unreviewed machine translation</h2>"
        + dual + "<h2>Unreviewed, machine-generated source notes</h2><ol>"
        + notes + "</ol><p>Human rights review, semantic review and "
        "editorial approval remain required. No public archive publication "
        "is authorized by this preview.</p></body></html>"
    )
