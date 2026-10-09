"""Offline owner-reviewed mixed production + typed research editorial slate.

This only builds and validates a private *manual* regional slate. It does not
produce an external AI prompt, invoke a model, send email, write source state,
or grant rights, production promotion, manuscript or publication permission.
"""
from __future__ import annotations

import hashlib
import json

from core.regional_editorial_slate import SlateError, validate_slate, heuristic_score
from core.regional_theme_selector import fixed_context
from core.regional_typed_machine_receipts import reconcile_machine_receipts
from core.regional_typed_research_holds import audit_typed_holds
from core.regional_typed_source_use_decision import verify_owner_decision

SCHEMA = "ipr-regional-reviewed-mixed-slate-context/1"
PREVIEW_SCHEMA = "ipr-regional-reviewed-mixed-manual-theme-preview/1"
MAX_CAPTURE_BYTES = 12 * 1024 * 1024
MAX_ALL_SYNOPS = 26

MACHINE_CLASSES = {
    "publisher_metadata_only_original_body_missing",
    "historical_extracted_text_digest_machine_checked_only",
    "queue_version_machine_eligible_not_human_approved",
}


class ReviewedTypedSlateError(ValueError):
    """Source, permission or manual proposal data lacks a current trusted pin."""


def need(ok, reason):
    if not ok:
        raise ReviewedTypedSlateError(reason)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def build_reviewed_mixed_context(
        inventory, signed_production_review, production_key,
        typed_research_rows, signed_typed_decisions, typed_key,
        *, japan_machine_receipt=None, vietnam_queues=None,
        current_official_captures=None):
    """Build a reviewed *human-only* mixed desk context, not model eligibility.

    The source bytes MUST be independently captured from the official
    publisher by the operator. This function checks their digests against the
    HMAC-signed human observation, but cannot independently prove provenance
    of caller-supplied bytes, interpretation or legal rights.
    """
    try:
        base, production, production_packet = fixed_context(
            inventory, signed_production_review, production_key)
        holds = audit_typed_holds(inventory, typed_research_rows)
        machine = reconcile_machine_receipts(
            holds, japan=japan_machine_receipt,
            vietnam_queues=vietnam_queues)
        signed = verify_owner_decision(
            signed_typed_decisions, inventory, typed_research_rows, typed_key)
    except (ValueError, KeyError, TypeError) as exc:
        raise ReviewedTypedSlateError(
            "fresh production/typed owner or machine source review refused"
        ) from exc
    need(machine["regional_inventory_digest_sha256"] ==
         signed["source_metadata_digest_sha256"] ==
         inventory["source_metadata_digest_sha256"] ==
         production_packet["source_metadata_digest_sha256"],
         "reviewed source snapshots disagree")
    need(machine["typed_hold_roster_sha256"] ==
         signed["typed_research_roster_sha256"] ==
         holds["typed_research_roster_sha256"],
         "typed research roster changed")
    need(signed["owner_signature_verified"] is True
         and signed["model_input_authorized"] is False
         and machine["model_input_authorized"] is False
         and signed["publication_authorized"] is False
         and machine["publication_authorized"] is False,
         "signed typed review unexpectedly claims dispatch or publication")

    all_holds = {row["id"]: row for row in holds["items"]}
    machine_by_id = {row["id"]: row for row in machine["items"]}
    research_by_id = {row["id"]: row for row in typed_research_rows}
    signed_by_id = {
        row["id"]: row for row in signed_typed_decisions["review"]["decisions"]
    }
    approved = signed["source_ids_human_approved_in_signed_docket"]
    need(isinstance(approved, list) and len(approved) <= 8
         and len(set(approved)) == len(approved)
         and all(isinstance(x, str) and x in all_holds for x in approved),
         "unexpected approved research ID roster")
    need(isinstance(current_official_captures, dict),
         "fresh verified publisher bytes must be explicitly supplied as a map")
    need(set(current_official_captures) == set(approved),
         "fresh official publisher captures must match approved typed IDs exactly")
    need(len(production) + len(approved) <= MAX_ALL_SYNOPS,
         "combined synopsis packet exceeds private editorial bounds")

    used_urls = {row["publisher_url"] for row in production}
    typed_offered = []
    evidence = list(base["evidence"])
    covered = set()
    for ident in approved:
        hold = all_holds[ident]
        row = research_by_id[ident]
        decision = signed_by_id[ident]
        machine_item = machine_by_id.get(ident)
        need(isinstance(machine_item, dict)
             and machine_item.get("machine_reconciliation") in MACHINE_CLASSES
             and machine_item.get("human_original_or_reuse_review_pending") is True
             and machine_item.get("eligible_for_regional_model") is False,
             "selected typed source missing independent historical machine receipt")
        blob = current_official_captures[ident]
        need(type(blob) is bytes and 0 < len(blob) <= MAX_CAPTURE_BYTES,
             "approved publisher source bytes missing or oversized")
        observed = hashlib.sha256(blob).hexdigest()
        need(observed == decision["current_publisher_observation_sha256"],
             "current official capture bytes do not match human-signed digest")
        url = row["source_url"]
        need(url not in used_urls, "duplicate typed/production official publisher URL")
        used_urls.add(url)
        need(hold["publisher_url_sha256"] ==
             hashlib.sha256(url.encode("utf-8")).hexdigest()
             and decision["publisher_url_sha256"] == hold["publisher_url_sha256"],
             "human approval does not match held publisher identity")
        need(decision["decision"] == "private_analyst_synopsis_reviewed"
             and decision["private_synopsis_use_scope_confirmed"] is True
             and decision["publisher_body_copy_authorized"] is False
             and decision["dylan_editor_email_authorized"] is False
             and decision["publication_authorized"] is False,
             "typed research decision scope changed")
        covered.add(row["desk"])
        typed_offered.append({
            "id": ident,
            "desk": row["desk"],
            "publisher": row["source_name"],
            "publisher_url": url,
            "published_date": row["published_date"],
            "original_language": row["language"],
            "title_original": row["title_original"],
            "analyst_synopsis": decision["independent_analyst_synopsis"],
            "accuracy_limitations": decision["evidence_limitations"],
            "capture_sha256": observed,
            "source_scope": "reviewed_typed_analyst_synopsis_only_not_publisher_body",
        })
        evidence.append({
            "id": ident, "desk": row["desk"],
            "lane": "private_research", "scope": "private_drafting_candidate",
            "source_url": url, "published_date": row["published_date"],
            "role": "new_week", "topic_suggestions": [],
        })
    coverage = []
    for item in base["coverage"]:
        if item["desk"] in covered:
            coverage.append({
                "desk": item["desk"], "state": "reviewable",
                "reason": "Selected owner-reviewed private synopsis only; not a live production desk",
            })
        else:
            coverage.append(dict(item))
    slate = dict(base, coverage=coverage, evidence=evidence)
    empty = dict(slate, candidates=[], provisional_lead=None,
                 lead_rationale="No manually selected theme yet; awaiting owner editorial judgment.")
    try:
        validate_slate(empty, expected_desks=[
            row["desk"] for row in inventory["coverage"]])
    except SlateError as exc:
        raise ReviewedTypedSlateError(
            "owner-reviewed mixed slate failed independent source contract") from exc
    return {
        "schema": SCHEMA,
        "week_ending": inventory["week_ending"],
        "source_metadata_digest_sha256": inventory["source_metadata_digest_sha256"],
        "typed_hold_roster_sha256": holds["typed_research_roster_sha256"],
        "production_review_seal_sha256": production_packet["review_seal_sha256"],
        "typed_owner_decision_seal_sha256": signed_typed_decisions["hmac_sha256"],
        "editorial_slate": empty,
        "reviewed_synopses": list(production) + typed_offered,
        "approved_typed_ids": sorted(approved),
        "held_typed_ids": sorted(set(all_holds) - set(approved)),
        "publisher_body_text_included": False,
        "publisher_capture_bytes_included": False,
        "historical_edition_fidelity_automatically_proven": False,
        "publisher_permission_independently_proven_by_software": False,
        "eligible_for_private_manual_theme_review_only": True,
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "japan_vietnam_production_activated": False,
    }


def validate_manual_mixed_theme(context, proposal):
    """Validate typed/numeric citations in MANUAL proposals; never call an LLM."""
    need(isinstance(context, dict) and context.get("schema") == SCHEMA
         and context.get("model_input_authorized") is False
         and context.get("publication_authorized") is False,
         "not an offline reviewed mixed context")
    base = context.get("editorial_slate")
    need(isinstance(base, dict) and base.get("candidates") == []
         and base.get("provisional_lead") is None,
         "untrusted context is not an empty pre-model slate")
    need(isinstance(proposal, dict)
         and set(proposal) == {"candidates", "provisional_lead", "lead_rationale"},
         "manual proposal must have only editorial fields")
    source_ids = {row["id"] for row in base["evidence"]}
    selected_ids = set(context.get("approved_typed_ids", []))
    need(selected_ids.issubset(source_ids),
         "selected typed evidence is absent from trusted manifest")
    try:
        proposal_copy = json.loads(canonical(proposal))
        candidate = dict(base, **proposal_copy)
        for row in candidate["candidates"]:
            ids = row.get("source_ids")
            need(isinstance(ids, list) and all(
                (type(ident) is int or type(ident) is str) and ident in source_ids
                for ident in ids), "manually supplied candidate references unreviewed ID")
        validate_slate(candidate, expected_desks=[
            c["desk"] for c in base["coverage"]])
    except (SlateError, ValueError, KeyError, TypeError) as exc:
        raise ReviewedTypedSlateError("manual thematic proposal is not source-grounded") from exc
    by_id = {row["id"]: row["desk"] for row in base["evidence"]}
    digest = hashlib.sha256(canonical(context["editorial_slate"])).hexdigest()
    return {
        "schema": PREVIEW_SCHEMA,
        "week_ending": context["week_ending"],
        "reviewed_slate_sha256": digest,
        "proposal": candidate,
        "candidate_analysis": [{
            "slug": row["slug"],
            "represented_desks": sorted({by_id[x] for x in row["source_ids"]}),
            "uses_held_typed_source": False,
            "weighted_nonbinding_score": heuristic_score(row["scores"]),
            "requires_public_single_desk_exception": len(
                {by_id[x] for x in row["source_ids"]}) == 1,
        } for row in candidate["candidates"]],
        "manual_only_no_model_was_invoked": True,
        "editorial_selection_not_approved": True,
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
    }
