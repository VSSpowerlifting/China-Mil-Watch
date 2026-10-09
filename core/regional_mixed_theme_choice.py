"""Signed, exact-source owner choice of ONE mixed regional thematic proposal.

Offline pure validation only. Signing a nonbinding thematic FOCUS does not
invoke a model, create a manuscript, email an editor, clear reuse rights,
grant a publication exception, or authorize Sunday delivery. Model-output
authenticity cannot be inferred from an unsigned in-memory preview.
"""
from __future__ import annotations

import hashlib
import hmac
from datetime import date

from core.regional_mixed_theme_selector import (
    RESULT_SCHEMA, _verified_context,
)
from core.regional_reviewed_evidence import _key
from core.regional_reviewed_typed_slate import (
    canonical, validate_manual_mixed_theme,
)

SCHEMA = "ipr-regional-owner-mixed-theme-choice/1"
HANDOFF_SCHEMA = "ipr-regional-owner-mixed-private-manuscript-brief/1"
DOMAIN = b"IPR-MIXED-REGIONAL-OWNER-THEME-CHOICE-v1\n"
MIN_SOURCES = 2
MAX_SOURCES = 10


class MixedThemeChoiceError(ValueError):
    """Fail closed before any private manuscript briefing or owner choice."""


def need(ok, why):
    if not ok:
        raise MixedThemeChoiceError(why)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _day(value):
    need(isinstance(value, str), "missing owner decision date")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise MixedThemeChoiceError("invalid owner choice date") from exc
    need(d.isoformat() == value, "noncanonical owner decision date")
    return d


def _owner(value):
    need(isinstance(value, str) and value == value.strip()
         and 3 <= len(value) <= 100
         and all(ord(c) >= 32 and ord(c) != 127 for c in value),
         "explicit owner identity is required")


def checked_mixed_proposal(inputs, signed_run, run_key, model_preview):
    """Rebuild entire candidate slate from fresh source pins, not cached data.

    Proves provenance and structural admissibility of the *provided proposal*.
    Does NOT prove that this data was originally produced by the named model.
    """
    ctx, _prompt, approval = _verified_context(inputs, signed_run, run_key)
    need(isinstance(model_preview, dict)
         and model_preview.get("schema") == RESULT_SCHEMA,
         "mixed model proposal preview missing or wrong schema")
    proposed = model_preview.get("validated_model_proposed_slate")
    need(isinstance(proposed, dict), "missing structured proposed slate")
    response = {key: proposed.get(key) for key in (
        "candidates", "provisional_lead", "lead_rationale")}
    try:
        rebuilt = validate_manual_mixed_theme(response, **inputs)
    except (ValueError, KeyError, TypeError) as exc:
        raise MixedThemeChoiceError(
            "proposed thematic slate no longer matches reviewed sources") from exc
    expected = {
        "schema": RESULT_SCHEMA,
        "week_ending": ctx["week_ending"],
        "run_id": approval["run_id"],
        "model_id": approval["model_id"],
        "owner_run_hmac_sha256": signed_run["hmac_sha256"],
        "prompt_sha256": approval["prompt_sha256"],
        "reviewed_synopsis_packet_sha256": ctx["reviewed_synopsis_packet_sha256"],
        "validated_model_proposed_slate": rebuilt["proposal"],
        "candidate_analysis": rebuilt["candidate_analysis"],
        "model_proposal_not_owner_selected": True,
        "model_called_once_in_this_invocation": True,
        "not_a_global_single_use_token": True,
        "manual_theme_approval_required": True,
        "publication_authorized": False,
        "editor_email_authorized": False,
        "delivery_scheduled": False,
    }
    need(canonical(expected) == canonical(model_preview),
         "model preview was edited, broadened or has stale source provenance")
    return ctx, approval, expected


def _unsigned_choice(
        inputs, signed_run, run_key, model_preview, *,
        slug, owner, approved_on):
    ctx, run, preview = checked_mixed_proposal(
        inputs, signed_run, run_key, model_preview)
    _owner(owner)
    choice_day = _day(approved_on)
    need(_day(inputs["inventory"]["week_ending"]) < choice_day
         and _day(run["approved_on"]) <= choice_day
         <= _day(inputs["inventory"]["review_local_day"]),
         "choice must follow Saturday close, model approval, and not be future")
    slate = preview["validated_model_proposed_slate"]
    matches = [row for row in slate["candidates"]
               if row["slug"] == slug]
    need(len(matches) == 1, "owner must select precisely one existing candidate")
    selected = matches[0]
    ids = selected["source_ids"]
    need(isinstance(ids, list) and MIN_SOURCES <= len(ids) <= MAX_SOURCES
         and len(ids) == len(set(ids))
         and all(type(x) in (int, str) for x in ids),
         "private manuscript focus requires 2–10 unique typed/numeric sources")
    by_id = {row["id"]: row for row in slate["evidence"]}
    need(all(i in by_id for i in ids),
         "editor-selected source is missing from reviewed evidence")
    desks = sorted({by_id[i]["desk"] for i in ids})
    need(len(desks) >= 2,
         "single-desk theme needs separate exception and cannot enter this handoff")
    return {
        "schema": SCHEMA,
        "purpose": "private_no_send_mixed_regional_manuscript_planning_only",
        "week_ending": ctx["week_ending"],
        "source_metadata_digest_sha256": ctx["source_metadata_digest_sha256"],
        "typed_hold_roster_sha256": ctx["typed_hold_roster_sha256"],
        "reviewed_synopsis_packet_sha256": ctx["reviewed_synopsis_packet_sha256"],
        "production_review_seal_sha256": ctx["production_review_seal_sha256"],
        "typed_owner_decision_seal_sha256": ctx["typed_owner_decision_seal_sha256"],
        "owner_model_run_hmac_sha256": signed_run["hmac_sha256"],
        "model_proposal_digest_sha256": digest(preview),
        "theme_slug": slug,
        "approved_focus": selected["thesis"],
        "source_ids": list(ids),
        "source_desks": desks,
        "source_basis": [{
            "id": i, "desk": by_id[i]["desk"],
            "lane": by_id[i]["lane"],
            "published_date": by_id[i]["published_date"],
        } for i in ids],
        "owner": owner,
        "approved_on": approved_on,
        "model_output_origin_independently_attested": False,
        "human_claim_review_still_required": True,
        "private_manuscript_model_authorized": False,
        "one_country_publication_exception_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "japan_vietnam_production_activated": False,
    }


def make_unsigned_theme_choice(
        inputs, signed_run, run_key, model_preview, *,
        slug, owner, approved_on):
    """A non-operative form: source identity pins, no owner signature yet."""
    return _unsigned_choice(
        inputs, signed_run, run_key, model_preview,
        slug=slug, owner=owner, approved_on=approved_on)


def sign_owner_mixed_theme_choice(
        unsigned, inputs, signed_run, run_key, model_preview, choice_key,
        *, owner_confirms_focus=False):
    """Owner signs only a human-selected focus after fresh source checks."""
    need(owner_confirms_focus is True,
         "specific editorial theme requires affirmative human owner selection")
    need(isinstance(unsigned, dict), "missing unsigned editorial theme choice")
    expected = _unsigned_choice(
        inputs, signed_run, run_key, model_preview,
        slug=unsigned.get("theme_slug"),
        owner=unsigned.get("owner"),
        approved_on=unsigned.get("approved_on"))
    need(canonical(unsigned) == canonical(expected),
         "owner theme choice or exact reviewed source basis was changed")
    _key(choice_key)
    need(choice_key not in (
        run_key, inputs["production_key"], inputs["typed_key"]),
        "owner theme choice requires fourth independent signing key")
    mac = hmac.new(
        choice_key, DOMAIN + canonical(expected), hashlib.sha256).hexdigest()
    return {"choice": expected, "hmac_sha256": mac}


def verify_owner_mixed_theme_choice(
        inputs, signed_run, run_key, model_preview, sealed, choice_key):
    """Verify owner selection and rebuild all source pins before planning."""
    need(isinstance(sealed, dict) and set(sealed) ==
         {"choice", "hmac_sha256"}, "malformed owner theme choice envelope")
    mac = sealed["hmac_sha256"]
    need(isinstance(mac, str) and len(mac) == 64
         and all(ch in "0123456789abcdef" for ch in mac),
         "invalid owner choice HMAC")
    _key(choice_key)
    need(choice_key not in (
        run_key, inputs["production_key"], inputs["typed_key"]),
        "owner focus HMAC key must be distinct from source/model keys")
    need(isinstance(sealed["choice"], dict),
         "owner choice must be an exact signed object")
    actual = hmac.new(
        choice_key, DOMAIN + canonical(sealed["choice"]),
        hashlib.sha256).hexdigest()
    need(hmac.compare_digest(mac, actual),
         "owner focus decision signature changed or missing")
    choice = sealed["choice"]
    expected = _unsigned_choice(
        inputs, signed_run, run_key, model_preview,
        slug=choice.get("theme_slug"),
        owner=choice.get("owner"),
        approved_on=choice.get("approved_on"))
    need(canonical(choice) == canonical(expected),
         "signed thematic selection is stale or mismatches source evidence")
    return expected


def private_manuscript_planning_receipt(
        inputs, signed_run, run_key, model_preview, sealed, choice_key):
    """Metadata-only planning receipt; absolutely no manuscript or dispatch."""
    choice = verify_owner_mixed_theme_choice(
        inputs, signed_run, run_key, model_preview, sealed, choice_key)
    return {
        "schema": HANDOFF_SCHEMA,
        "week_ending": choice["week_ending"],
        "theme_slug": choice["theme_slug"],
        "approved_focus": choice["approved_focus"],
        "selected_source_ids": choice["source_ids"],
        "represented_desks": choice["source_desks"],
        "source_basis": choice["source_basis"],
        "source_metadata_digest_sha256":
            choice["source_metadata_digest_sha256"],
        "reviewed_synopsis_packet_sha256":
            choice["reviewed_synopsis_packet_sha256"],
        "owner_theme_choice_hmac_sha256": sealed["hmac_sha256"],
        "model_proposal_digest_sha256": choice["model_proposal_digest_sha256"],
        "human_claim_and_reuse_review_required": True,
        "manuscript_content_included": False,
        "manuscript_model_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "delivery_scheduled": False,
    }
