"""Offline, fail-closed structural gate for Singapore Gazette metadata-only review.

Not a collector, source archive, source-use legal approval or human classifier.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PACKET = ROOT / "research/topic_v2_singapore_strategic_goods/source_admission.json"
VOCAB = ROOT / "taxonomy/regional_topics.v2.json"
EXPECTED = {
    "SGEC25": ("S 660/2025", "2025-09-30", "2025-10-01", "2025-12-01",
               "S 641/2024", 519, "effective_predecessor",
               "https://assets.egazette.gov.sg/2025/Legislative%20Supplements/Subsidiary%20Legislation%20Supplement/660.pdf"),
    "SGEC26": ("S 741/2026", "2026-09-24", "2026-10-01", "2026-12-01",
               "S 660/2025", 523, "made_and_published_future_effective",
               "https://assets.egazette.gov.sg/2026/Legislative%20Supplements/Subsidiary%20Legislation%20Supplement/26sls741.pdf"),
}
ROOT_FIELDS = {
    "packet_id", "schema_version", "research_date", "purpose", "selection_origin",
    "desk_candidate", "topic_under_review", "taxonomy_id", "taxonomy_version",
    "source_document_count", "distinct_regulatory_succession_count",
    "production_manifest", "source_use_review", "archived_bodies_in_this_packet",
    "human_source_review_complete", "human_topic_approvals",
    "topic_attachments_authorized", "production_or_shadow_collection_authorized",
    "documents",
}
DOC_FIELDS = {
    "candidate_id", "title_original", "gazette_number", "official_pdf_url",
    "language", "gazette_publisher", "legal_maker",
    "administrative_guidance_institution", "source_document_type",
    "made_on", "first_published_on", "first_published_local_time",
    "source_timezone", "commences_on", "revokes_gazette_number",
    "page_count", "source_page_anchors", "regulatory_context_key",
    "status_as_of_research_date", "editor_only_role_hypothesis",
    "archival_status", "archive_record_id", "captured_pdf_sha256",
    "captured_body_sha256", "captured_at_utc", "archived_quote_offsets",
    "owner_source_admission_approval", "human_topic_approval",
}
RIGHTS_FIELDS = {
    "terms_url", "terms_last_updated", "provisional_reading",
    "relevant_clauses", "observed_conditions", "ipr_use_compliance_adjudicated",
    "full_body_retention_approved", "public_body_display_approved",
    "automated_collection_approved", "website_caching_scope_adjudicated",
}
CONDITIONS = {
    "singapore_government_copyright_acknowledgment",
    "notice_of_government_permission_for_reproduction",
    "direct_users_to_latest_egazette",
    "producer_responsible_for_reproduction_accuracy",
    "avoid_government_affiliation_implication",
    "non_abusive_non_disruptive_non_deceptive_automated_extraction",
    "permission_revocable_or_modifiable",
    "hyperlink_without_embedding_or_framing",
}


class MetadataReviewError(ValueError):
    """A source-only metadata contract was violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MetadataReviewError(message)


def day(raw: str) -> date:
    require(type(raw) is str, "date type")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise MetadataReviewError("invalid date") from exc


def validate(packet: dict, vocabulary: dict) -> dict:
    require(type(packet) is dict and set(packet) == ROOT_FIELDS, "packet schema")
    require(vocabulary.get("taxonomy_id") == "ipr_regional_topics"
            and vocabulary.get("taxonomy_version") == 2
            and "export_controls_sanctions" in {
                t["slug"] for t in vocabulary.get("topics", [])
            }, "v2 taxonomy")
    require(packet["packet_id"] == "ipr_singapore_strategic_goods_metadata_review_20261008"
            and type(packet["schema_version"]) is int and packet["schema_version"] == 1
            and packet["research_date"] == "2026-10-08"
            and packet["purpose"] == "curator_metadata_only_source_admission_review"
            and packet["desk_candidate"] == "singapore"
            and packet["topic_under_review"] == "export_controls_sanctions"
            and packet["taxonomy_id"] == "ipr_regional_topics"
            and packet["taxonomy_version"] == 2
            and "Assistant-curated" in packet["selection_origin"], "scope")
    require(packet["human_source_review_complete"] is False
            and packet["topic_attachments_authorized"] is False
            and packet["production_or_shadow_collection_authorized"] is False
            and packet["human_topic_approvals"] == []
            and packet["archived_bodies_in_this_packet"] == 0, "approval/archive gate")
    m = packet["production_manifest"]
    require(type(m) is dict and set(m) == {
        "path", "observed_git_blob", "registered_source_slugs",
        "gazette_source_registered", "customs_source_registered",
    } and m["path"] == "desks/singapore/manifest.json"
            and m["observed_git_blob"] == "8b0cdf32159c6c385a070153fa282428221fe695"
            and m["registered_source_slugs"] == ["sg_mindef_releases"]
            and m["gazette_source_registered"] is False
            and m["customs_source_registered"] is False, "manifest boundary")
    r = packet["source_use_review"]
    require(type(r) is dict and set(r) == RIGHTS_FIELDS
            and r["terms_url"] == "https://www.egazette.gov.sg/terms-of-use/"
            and r["terms_last_updated"] == "2026-07-10"
            and "Clause 11" in r["provisional_reading"]
            and "clause 16" in r["provisional_reading"]
            and r["relevant_clauses"] == ["6", "11", "12", "16", "17"]
            and type(r["observed_conditions"]) is list
            and set(r["observed_conditions"]) == CONDITIONS
            and len(r["observed_conditions"]) == len(CONDITIONS),
            "Gazette terms gate")
    require(all(r[k] is False for k in (
        "ipr_use_compliance_adjudicated", "full_body_retention_approved",
        "public_body_display_approved", "automated_collection_approved",
        "website_caching_scope_adjudicated"
    )), "source-use signoff gate")
    docs = packet["documents"]
    require(packet["source_document_count"] == 2
            and packet["distinct_regulatory_succession_count"] == 1
            and type(docs) is list and len(docs) == 2, "two orders one succession")
    seen = set()
    for doc in docs:
        require(type(doc) is dict and set(doc) == DOC_FIELDS, "document schema")
        ident = doc["candidate_id"]
        require(ident in EXPECTED and ident not in seen, "document identity")
        seen.add(ident)
        gazette, made, published, effective, revokes, pages, status, url = EXPECTED[ident]
        require((doc["gazette_number"], doc["made_on"], doc["first_published_on"],
                 doc["commences_on"], doc["revokes_gazette_number"],
                 doc["page_count"], doc["status_as_of_research_date"],
                 doc["official_pdf_url"]) == EXPECTED[ident],
                 "pinned original Gazette source and chronology")
        uri = urlparse(doc["official_pdf_url"])
        require(uri.scheme == "https" and uri.hostname == "assets.egazette.gov.sg"
                and uri.username is None and uri.password is None
                and not uri.query and not uri.fragment, "official publisher URL")
        require(doc["title_original"] == "Strategic Goods (Control) Order " + ident[-2:].replace("25", "2025").replace("26", "2026")
                and doc["language"] == "en"
                and doc["source_document_type"] == "subsidiary_legislation_original_gazette"
                and doc["gazette_publisher"] == "Government of Singapore — Government Gazette"
                and doc["administrative_guidance_institution"] == "Singapore Customs"
                and doc["legal_maker"] == ("Minister for Trade and Industry" if ident == "SGEC25"
                                          else "Minister for Trade and Industry (Trade)")
                and doc["first_published_local_time"] == "17:00"
                and doc["source_timezone"] == "Asia/Singapore", "issuer metadata")
        require(doc["source_page_anchors"] == {
            "publication_commencement_revocation": 1, "maker_signature_date": pages,
        }, "source page anchors")
        require(day(made) <= day(published) < day(effective)
                and ((day(effective) > day(packet["research_date"])) == (ident == "SGEC26")),
                "effective date timing")
        require(doc["regulatory_context_key"] ==
                "singapore_strategic_goods_2025_to_2026_succession", "context grouping")
        require(doc["editor_only_role_hypothesis"] ==
                ("potential_positive_specific_control_in_force" if ident == "SGEC25"
                 else "potential_positive_formal_future_effective_control")
                and doc["archival_status"] == "unpreserved_for_this_admission_review"
                and all(doc[k] is None for k in (
                    "archive_record_id", "captured_pdf_sha256", "captured_body_sha256",
                    "captured_at_utc", "owner_source_admission_approval", "human_topic_approval"
                )) and doc["archived_quote_offsets"] == [], "fabricated evidence/approval")
    require(seen == set(EXPECTED), "missing original order")
    return {"scope": "metadata_only", "source_documents": 2,
            "regulatory_successions": 1, "source_bodies_stored": 0,
            "verified_archival_capture_hashes": 0, "human_approvals": 0,
            "collection_enabled": False, "right_to_reproduce_adjudicated_for_ipr": False}


def validate_files(packet_path: Path = PACKET, vocab_path: Path = VOCAB) -> dict:
    return validate(json.loads(packet_path.read_text(encoding="utf-8")),
                    json.loads(vocab_path.read_text(encoding="utf-8")))


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(json.dumps(validate_files(), indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit("Singapore strategic-goods metadata gate: " + str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
