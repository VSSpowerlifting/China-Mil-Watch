"""Human owner-signed, source-pinned typed research decisions: NO dispatch.

A separate future selector must independently reverify these decisions against
fresh original publisher/version evidence and enforce its own dispatch gates.
Neither a successful signature nor a human checkmark proves rights or fact.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, datetime

from core.regional_reviewed_evidence import _key
from core.regional_typed_human_review_prep import create_unsigned_worksheet
from core.regional_typed_research_holds import canonical

SCHEMA = "ipr-typed-private-synopsis-human-decision/1"
DOMAIN = b"IPR-TYPED-PRIVATE-SYNOPSIS-HUMAN-DECISION-v1\n"
PURPOSE = "future_regional_theme_private_analyst_synopsis_only"
RIGHTS = frozenset(("explicit_official_reuse_terms", "written_rights_owner_permission"))
SHA256 = re.compile(r"[a-f0-9]{64}\Z")


class TypedSourceDecisionError(ValueError):
    """Missing explicit owner source-use decision or changed provenance."""


def need(value, reason):
    if not value:
        raise TypedSourceDecisionError(reason)


def day(value):
    need(isinstance(value, str), "review date must be a string")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise TypedSourceDecisionError("invalid date") from exc
    need(result.isoformat() == value, "noncanonical decision date")
    return result


def line(value, low, high):
    return (isinstance(value, str) and value == value.strip()
            and low <= len(value) <= high
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


def _fresh(inventory, research_rows):
    try:
        worksheet = create_unsigned_worksheet(inventory, research_rows)
    except (ValueError, TypeError, KeyError) as exc:
        raise TypedSourceDecisionError("fresh source inventory or research roster invalid") from exc
    need(inventory.get("source_as_of") == inventory.get("week_ending")
         and worksheet["source_as_of"] == worksheet["week_ending"],
         "full Saturday source snapshot required; partial-week review refused")
    need(inventory.get("model_input_authorized") is False
         and inventory.get("editor_email_authorized") is False
         and inventory.get("publication_authorized") is False,
         "source inventory may not claim inherited operational authority")
    return worksheet


def _entry(pin):
    return {
        "id": pin["id"],
        "desk": pin["desk"],
        "published_date": pin["published_date"],
        "publisher_url_sha256": pin["publisher_url_sha256"],
        "historical_state_commit": pin["historical_state_commit"],
        "historical_source_content_sha256": pin["historical_source_content_sha256"],
        "source_kind": pin["source_kind"],
        "decision": "hold",
        "original_language_human_checked": False,
        "current_publisher_version_human_checked": False,
        "current_publisher_observation_sha256": None,
        "current_publisher_observed_utc": None,
        "current_publisher_edition_reference": None,
        "translation_and_attribution_cautions": None,
        "rights_basis_type": "unreviewed",
        "rights_basis_reference": None,
        "private_synopsis_use_scope_confirmed": False,
        "independent_analyst_synopsis": None,
        "evidence_limitations": None,
        "publisher_body_copy_authorized": False,
        "dylan_editor_email_authorized": False,
        "publication_authorized": False,
    }


def make_unsigned_decision(inventory, research_rows, *, owner, decided_on):
    """Make an explicitly non-approved all-HOLD form; no signer is called."""
    worksheet = _fresh(inventory, research_rows)
    need(line(owner, 3, 100), "owner identity required")
    reviewed = day(decided_on)
    need(day(worksheet["week_ending"]) <= reviewed
         <= day(inventory.get("review_local_day")),
         "decisions must be after week end and before/at review execution")
    return {
        "schema": SCHEMA,
        "week_ending": worksheet["week_ending"],
        "source_metadata_digest_sha256": worksheet["source_metadata_digest_sha256"],
        "typed_research_roster_sha256": worksheet["typed_research_roster_sha256"],
        "unsigned_worksheet_sha256": worksheet["unsigned_template_sha256"],
        "purpose": PURPOSE,
        "owner": owner,
        "decided_on": decided_on,
        "decisions": [_entry(row) for row in worksheet["records"]],
        "does_not_authorize_source_body_copy": True,
        "does_not_authorize_model_dispatch": True,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "japan_vietnam_production_activated": False,
    }


def _observation_stamp(value, review_date, publication_date):
    need(isinstance(value, str) and len(value) <= 40,
         "explicit current publisher observation UTC timestamp missing")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TypedSourceDecisionError("invalid publisher observation date-time") from exc
    need(stamp.tzinfo is not None and stamp.utcoffset() is not None
         and stamp.utcoffset().total_seconds() == 0
         and stamp.isoformat().replace("+00:00", "Z") == value,
         "publisher observation must use canonical UTC Z instant")
    need(day(publication_date) <= stamp.date() <= day(review_date),
         "publisher observation outside published/reviewed date range")


def _check_decisions(document, inventory, research_rows):
    base = _fresh(inventory, research_rows)
    need(isinstance(document, dict), "owner decision must be a dictionary")
    original = make_unsigned_decision(
        inventory, research_rows, owner=document.get("owner"),
        decided_on=document.get("decided_on"))
    need(set(document) == set(original),
         "missing or unexpected owner-decision fields")
    for field in (
        "schema", "week_ending", "source_metadata_digest_sha256",
        "typed_research_roster_sha256", "unsigned_worksheet_sha256", "purpose",
        "does_not_authorize_source_body_copy", "does_not_authorize_model_dispatch",
        "editor_email_authorized", "publication_authorized",
        "japan_vietnam_production_activated",
    ):
        need(type(document[field]) is type(original[field])
             and document[field] == original[field],
             "owner decision source pins or scope/permission modified")
    need(line(document["owner"], 3, 100), "invalid signer identity")
    reviewed = day(document["decided_on"])
    need(day(base["week_ending"]) <= reviewed
         <= day(inventory.get("review_local_day")),
         "owner decision cannot be premature or future-dated")
    rows = document["decisions"]
    expected_rows = [_entry(row) for row in base["records"]]
    need(isinstance(rows, list) and len(rows) == len(expected_rows),
         "source decision roster incomplete")
    approved = []
    for chosen, expected in zip(rows, expected_rows):
        need(isinstance(chosen, dict) and set(chosen) == set(expected),
             "per-source decision schema changed")
        for key in (
            "id", "desk", "published_date", "publisher_url_sha256",
            "historical_state_commit", "historical_source_content_sha256",
            "source_kind", "publisher_body_copy_authorized",
            "dylan_editor_email_authorized", "publication_authorized",
        ):
            need(type(chosen[key]) is type(expected[key])
                 and chosen[key] == expected[key],
                 "publisher identity/version or source-body rights altered")
        choice = chosen["decision"]
        need(choice in ("hold", "private_analyst_synopsis_reviewed"),
             "unknown per-source editorial use decision")
        if choice == "hold":
            need(chosen == expected,
                 "held source may not inherit review or approval values")
            continue
        for key in (
            "original_language_human_checked",
            "current_publisher_version_human_checked",
            "private_synopsis_use_scope_confirmed",
        ):
            need(chosen[key] is True, "positive source-use decision lacks human review: " + key)
        digest = chosen["current_publisher_observation_sha256"]
        need(isinstance(digest, str) and SHA256.fullmatch(digest),
             "current official publisher capture digest required")
        _observation_stamp(chosen["current_publisher_observed_utc"],
                           document["decided_on"], chosen["published_date"])
        need(line(chosen["current_publisher_edition_reference"], 12, 500),
             "issuer edition/capture reference must be documented")
        need(line(chosen["translation_and_attribution_cautions"], 30, 400),
             "source interpretation and limitations must be explicit")
        need(isinstance(chosen["rights_basis_type"], str)
             and chosen["rights_basis_type"] in RIGHTS,
             "mere attribution/footer or unreviewed rights cannot authorize synopsis")
        need(line(chosen["rights_basis_reference"], 12, 500),
             "official license/rights-owner permission reference needed")
        need(line(chosen["independent_analyst_synopsis"], 65, 650)
             and line(chosen["evidence_limitations"], 30, 350),
             "bounded original analyst synopsis and accuracy caveats required")
        approved.append(chosen["id"])
    return base, approved


def sign_owner_decision(document, inventory, research_rows, owner_secret):
    """Only an owner-operated offline signing process should call this."""
    _check_decisions(document, inventory, research_rows)
    signature = hmac.new(_key(owner_secret), DOMAIN + canonical(document),
                         hashlib.sha256).hexdigest()
    return {"review": document, "hmac_sha256": signature}


def verify_owner_decision(sealed, inventory, research_rows, owner_secret):
    """Revalidate after a fresh snapshot; NEVER dispatch or publish."""
    need(isinstance(sealed, dict) and set(sealed) == {"review", "hmac_sha256"},
         "signed research decision envelope malformed")
    digest = sealed["hmac_sha256"]
    need(isinstance(digest, str) and SHA256.fullmatch(digest),
         "invalid owner decision signature")
    want = hmac.new(_key(owner_secret),
                    DOMAIN + canonical(sealed["review"]), hashlib.sha256).hexdigest()
    need(hmac.compare_digest(digest, want), "human owner decision signature invalid")
    base, approved = _check_decisions(sealed["review"], inventory, research_rows)
    return {
        "schema": "ipr-typed-private-synopsis-signed-decision-receipt/1",
        "week_ending": base["week_ending"],
        "source_metadata_digest_sha256": base["source_metadata_digest_sha256"],
        "typed_research_roster_sha256": base["typed_research_roster_sha256"],
        "source_ids_human_approved_in_signed_docket": approved,
        "held_source_ids": [
            row["id"] for row in base["records"] if row["id"] not in approved
        ],
        "owner_signature_verified": True,
        "publisher_permission_independently_proven_by_software": False,
        "model_input_authorized": False,
        "dylan_editor_email_authorized": False,
        "publication_authorized": False,
        "japan_vietnam_production_activated": False,
        "future_selector_integration_required": True,
    }
