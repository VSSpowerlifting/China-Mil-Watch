"""Validate a *disabled* PCG-byline/PIA-host source discovery packet.

No web requests or archive admission. The source byline is a *claim* requiring
independent verification, never an automatic original-issuer attestation.
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
PACKET = ROOT / "research/philippines/pcg_pia/source_candidates.json"
FIXED = {
    "PCG-PIA-01": (
        "press-release",
        "https://pia.gov.ph/press-release/pcg-commandant-activates-coast-guard-auxiliary-district-in-kalayaan-island-group-kalayaan-mayor-leads-new-pcga-members-in-oath-taking/",
        "2026-10-07",
    ),
    "PCG-PIA-02": (
        "news",
        "https://pia.gov.ph/news/pcg-deploys-aircraft-and-brp-teresa-magbanua-to-challenge-china-coast-guard-vessel-near-cabra-island-pla-navy-warships-monitored-in-the-area/",
        "2026-09-28",
    ),
    "PCG-PIA-03": (
        "news",
        "https://pia.gov.ph/news/pcg-conducts-mda-flight-in-support-of-bfars-kbbm-at-bajo-de-masinloc/",
        "2026-09-18",
    ),
    "PCG-PIA-04": (
        "news",
        "https://pia.gov.ph/news/pla-fires-flares-at-unarmed-pcg-aircraft-during-maritime-domain-awareness-flight-over-kalayaan-island-group",
        "2026-09-10",
    ),
    "PCG-PIA-05": (
        "news",
        "https://pia.gov.ph/news/pcg-conducts-medical-evacuation-of-injured-afp-personnel-from-ayungin-shoal-despite-china-coast-guard-obstruction/",
        "2026-07-21",
    ),
}
EXCLUDED = {
    "https://pia.gov.ph/news/luzon/ncr/pnp-reaffirms-stronger-law-enforcement-ties-with-international-partners/":
        "pia_staff_reporting_about_pnp_not_pnp_original",
    "https://radyopilipinas.ph/2026/10/01/sinimulan-ng-pcg-afp-at-pnp-ang-tatlong-araw-na-inter-agency-disaster-response-exercise-na-pagsasanay-sanlakas-para-palakasin-ang-kahandaan-sa-posibleng-malakas-na-lindol/":
        "newsroom_report_about_pcg_not_pcg_original",
    "https://pco.gov.ph/news_releases/pbbm-to-new-pcg-leaders-lead-by-example-serve-with-courage/":
        "pco_original_not_pcg_original",
}
OPEN_CHECKS = {
    "host_access", "author_authentication", "rights_per_piece", "date_precision",
    "canonical_dedup", "text_parsing", "event_corroboration",
}
NO_APPROVAL = {
    "collection_enabled", "production_registered", "archive_capture_present",
    "archival_bytes_verified", "original_issuer_independently_authenticated",
    "html_extraction_reviewed", "full_body_capture_approved",
    "publisher_date_precision_verified", "republishing_rights_approved",
    "indexing_approved", "human_review_complete", "desk_qualification_granted",
}
EMPTY_PINS = {
    "archive_identity", "body_sha256", "payload_sha256", "origin_commit",
    "owner_approval",
}
PAGE_FIELDS = {
    "id", "page_kind", "url", "title", "host_page_date", "byline",
    "provisional_relevance", "review_status", *EMPTY_PINS,
}


class SourceAdmissionError(ValueError):
    """The PCG–PIA packet is not safe to present as research only."""


def require(ok, reason):
    if not ok:
        raise SourceAdmissionError(reason)


def valid_iso(d):
    require(type(d) is str and
            re.fullmatch(r"\d{4}-\d\d-\d\d", d) is not None,
            "source date must be YYYY-MM-DD with no invented time")
    try:
        value = date.fromisoformat(d)
    except ValueError as exc:
        raise SourceAdmissionError("invalid calendar date") from exc
    require(value.isoformat() == d, "noncanonical date")
    return value


def validate(packet):
    require(type(packet) is dict and
            packet.get("schema") == "ipr_ph_pcg_pia_source_admission_v1" and
            packet.get("state") == "discovery_only_not_archived_or_approved" and
            packet.get("desk") == "philippines" and
            packet.get("scope") == "pia_hosted_pages_explicitly_attributed_to_pcg" and
            packet.get("host_domain") == "pia.gov.ph" and
            packet.get("host_institution") == "Philippine Information Agency (PIA)" and
            packet.get("claimed_original_issuer") == "Philippine Coast Guard (PCG)",
            "packet provenance conflates original issuer with PIA publisher")
    require(type(packet.get("claimed_issuer_evidence")) is str and
            "By PCG" in packet["claimed_issuer_evidence"] and
            "authenticate" in packet["claimed_issuer_evidence"],
            "claimed issuer attribution cannot be represented as verified")
    require(valid_iso(packet.get("review_cutoff_date")) == date(2026, 10, 8),
            "packet cutoff date moved")
    rights = packet.get("rights_note")
    require(type(rights) is str and
            "unless otherwise stated" in rights and
            "Human" in rights and "required" in rights,
            "conditional PIA rights notice must remain unresolved")
    permissions = packet.get("assertions")
    require(type(permissions) is dict and set(permissions) == NO_APPROVAL and
            all(permissions[k] is False for k in NO_APPROVAL),
            "source admission cannot enable collector, archive, rights or desk approval")
    candidates = packet.get("candidates")
    require(type(candidates) is list and len(candidates) == len(FIXED),
            "missing or new PCG pages require separate evidence review")
    ids = set()
    urls = set()
    for row in candidates:
        require(type(row) is dict and set(row) == PAGE_FIELDS,
                "candidate metadata schema drift")
        ident = row.get("id")
        require(ident in FIXED and ident not in ids,
                "unrecognized/duplicate candidate ID")
        ids.add(ident)
        kind, url, published = FIXED[ident]
        require(row["page_kind"] == kind and row["url"] == url and
                row["host_page_date"] == published and
                row["byline"] == "PCG" and
                row["review_status"] == "awaiting_human_source_admission",
                ident + ": historical host attribution, date or URL changed")
        require(row["url"] not in urls, "duplicate candidate source URL")
        urls.add(row["url"])
        u = urlsplit(row["url"])
        require(u.scheme == "https" and u.netloc == "pia.gov.ph" and
                not u.fragment and not u.query and
                u.path.startswith(("/news/", "/press-release/")),
                "source pages must use exact public PIA canonical URLs")
        require(valid_iso(row["host_page_date"]) <=
                date(2026, 10, 8), "future content cannot be admitted")
        require(type(row["title"]) is str and
                len(row["title"]) >= 24 and
                type(row["provisional_relevance"]) is str and
                len(row["provisional_relevance"]) >= 20,
                "original-language title/research relevance missing")
        require(all(row[k] is None for k in EMPTY_PINS),
                "do not fabricate archived bytes, reviewer approval or source identifiers")
    require(ids == set(FIXED), "candidate coverage drift")
    excluded = packet.get("excluded_or_separately_classified_leads")
    require(type(excluded) is list and len(excluded) == len(EXCLUDED),
            "three false issuer cases must be preserved")
    seen = set()
    for row in excluded:
        require(type(row) is dict and
                set(row) == {"url", "host", "byline", "speaker_context",
                             "category", "do_not_admit_as_pcg_or_pnp_issued"},
                "false-issuer case schema changed")
        url = row.get("url")
        require(type(url) is str and url in EXCLUDED and url not in seen,
                "unrecognized or duplicate false-issuer lead")
        seen.add(url)
        require(row.get("category") == EXCLUDED[url] and
                row.get("do_not_admit_as_pcg_or_pnp_issued") is True and
                type(row.get("speaker_context")) is str and
                bool(row["speaker_context"].strip()) and
                type(row.get("host")) is str and
                bool(row["host"].strip()),
                "PIA, radio and PCO leads must not be relabeled as PCG/PNP originals")
        if "jimmyley-guzman" in url or url.startswith("https://pia.gov.ph/news/luzon/ncr/"):
            require(row.get("byline") == "Jimmyley Guzman",
                    "PIA reporter byline cannot become PNP")
    require(seen == set(EXCLUDED), "lost negative source controls")
    checks = packet.get("open_checks")
    require(type(checks) is list and len(checks) == len(OPEN_CHECKS),
            "missing owner source-admission gate")
    check_names = set()
    for entry in checks:
        require(type(entry) is dict and
                set(entry) == {"id", "status", "question"},
                "admission review gate schema changed")
        key = entry.get("id")
        require(type(key) is str and
                key in OPEN_CHECKS and key not in check_names and
                entry["status"] == "pending" and
                type(entry.get("question")) is str and
                len(entry["question"]) > 35,
                "admission gate must remain pending with meaningful criteria")
        check_names.add(key)
    require(check_names == OPEN_CHECKS, "incomplete admission gates")
    return {
        "source_candidates": len(candidates),
        "hosting_institution": "PIA",
        "claimed_original_issuer": "PCG (page byline only; unverified)",
        "negative_controls": len(excluded),
        "open_source_admission_gates": len(checks),
        "archived_source_records": 0,
        "collection_enabled": False,
        "human_original_issuer_authentication": False,
        "automatic_rights_clearance": False,
        "production_changes": 0,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--packet", type=Path, default=PACKET)
    args = p.parse_args()
    try:
        doc = json.loads(args.packet.read_text(encoding="utf-8"))
        print(json.dumps(validate(doc), indent=2, sort_keys=True))
    except (SourceAdmissionError, ValueError, OSError, TypeError) as exc:
        p.exit(1, "PCG-via-PIA source admission: %s\n" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
