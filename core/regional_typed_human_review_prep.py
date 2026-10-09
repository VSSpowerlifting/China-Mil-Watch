"""Produce UNSIGNED, non-operative source-review worksheets for held research.

This is an operator aid, NOT an approval format. Editing any field has no
effect on regional model inputs, Sunday authoring, SMTP or publication.
"""
from __future__ import annotations

import hashlib
import json
import re

from core.regional_typed_research_holds import audit_typed_holds, canonical

SCHEMA = "ipr-regional-typed-source-human-review-worksheet/1"
REVIEW_FIELDS = (
    "official_issuer_and_visible_date_checked",
    "current_publisher_version_checked",
    "complete_original_language_text_compared",
    "translation_accuracy_and_omissions_checked",
    "publisher_reuse_terms_independently_checked",
    "retention_and_private_model_scope_approved_by_rights_owner",
)


class HumanReviewWorksheetError(ValueError):
    """The private unsigned worksheet cannot be derived from these inputs."""


def create_unsigned_worksheet(inventory, research_rows):
    """Derive a reproducible worksheet from the EXACT existing source holds.

    Inputs must come from the separately validated editorial research packet
    and the read-only weekly inventory. No article body or synopsis is copied.
    """
    try:
        report = audit_typed_holds(inventory, research_rows)
    except (ValueError, TypeError, KeyError) as exc:
        raise HumanReviewWorksheetError("typed research or inventory not eligible for worksheet") from exc
    if report.get("all_items_held_for_human_review") is not True:
        raise HumanReviewWorksheetError("review report was not held")
    by_id = {r["id"]: r for r in research_rows}
    if len(by_id) != len(research_rows):
        raise HumanReviewWorksheetError("duplicate editorial research sources")
    records = []
    for hold in report["items"]:
        entry = by_id[hold["id"]]
        url = entry["source_url"]
        if hashlib.sha256(url.encode("utf-8")).hexdigest() != hold["publisher_url_sha256"]:
            raise HumanReviewWorksheetError("URL changed after inventory review")
        title = entry.get("title_original")
        language = entry.get("language")
        if (not isinstance(title, str) or not title.strip()
                or len(title) > 500 or "\n" in title or "\r" in title
                or not isinstance(language, str) or not re.fullmatch(
                    r"[a-z]{2,3}", language)):
            raise HumanReviewWorksheetError("source original-language metadata not bounded")
        if entry["desk"] == "japan":
            missing = ("complete_official_HTML_original_not_preserved"
                       if entry["source_kind"] ==
                       "official-publisher-page-reviewed-for-research"
                       else "original_PDF_bytes_and_fidelity_review_pending")
        else:
            missing = "current_Vietnamese_original_and_capture_version_comparison_pending"
        records.append({
            "id": hold["id"],
            "desk": hold["desk"],
            "publisher_url": url,
            "publisher_url_sha256": hold["publisher_url_sha256"],
            "publisher": entry["source_name"],
            "published_date": hold["published_date"],
            "title_original": title,
            "language": language,
            "historical_state_commit": hold["state_commit"],
            "historical_source_content_sha256": hold["source_content_sha256"],
            "source_kind": hold["source_kind"],
            "machine_source_gap": missing,
            "review_checks": {key: None for key in REVIEW_FIELDS},
            "reviewer_identity": None,
            "reviewed_source_version_or_capture": None,
            "rights_basis_url_or_document": None,
            "reuse_permission_scope": None,
            "editorial_claims_to_recheck": None,
            "discrepancies_and_omissions": None,
            "review_notes": None,
            "status": "UNREVIEWED_UNSIGNED_TEMPLATE_ONLY",
            "model_input_authorized": False,
            "publisher_body_copy_authorized": False,
            "editor_email_authorized": False,
            "publication_authorized": False,
        })
    worksheet = {
        "schema": SCHEMA,
        "week_ending": report["week_ending"],
        "source_as_of": report["source_as_of"],
        "source_metadata_digest_sha256": report["source_metadata_digest_sha256"],
        "typed_research_roster_sha256": report["typed_research_roster_sha256"],
        "source_count": len(records),
        "records": records,
        "reviewer_identity": None,
        "owner_release_signature": None,
        "is_signed_or_reusable_authorization": False,
        "all_records_remain_held": True,
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "japan_vietnam_production_activated": False,
        "instructions": (
            "Private worksheet for human source comparison only. A filled or "
            "renamed file is NOT source-use approval. Verify actual current "
            "publisher originals/rights separately. Never feed this worksheet "
            "to the model or into scheduled Sunday email/publication."
        ),
    }
    worksheet["unsigned_template_sha256"] = hashlib.sha256(
        canonical(worksheet)).hexdigest()
    return worksheet
