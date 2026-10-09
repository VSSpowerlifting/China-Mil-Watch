"""Owner-chosen, HMAC-sealed thematic focus for private Sunday manuscript trial.

This contract is NOT a publication exception, source-rights guarantee, approval
to email Dylan, or automatic Sunday schedule change.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date

from core.regional_reviewed_evidence import _key
from core.regional_theme_selector import fixed_context, validate_proposals

SCHEMA = "ipr-regional-owner-theme-choice/1"
MAX_MODEL_IDS = 10
DOMAIN = b"IPR-OWNER-THEME-CHOICE-v1\n"


class ThemeHandoffError(ValueError):
    """No signed, source-matched editor-selected theme."""


def require(ok, why):
    if not ok:
        raise ThemeHandoffError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _date(value):
    require(isinstance(value, str), "approval date not canonical")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ThemeHandoffError("approval date invalid") from exc
    require(parsed.isoformat() == value, "approval date not canonical")
    return parsed


def checked_proposal(inventory, signed_review, secret, preview):
    """Recompute and compare ALL model-output manifest fields, not just IDs."""
    base, offered, packet = fixed_context(inventory, signed_review, secret)
    require(isinstance(preview, dict) and
            isinstance(preview.get("model_proposed_slate"), dict),
            "missing model proposal preview")
    slate = preview["model_proposed_slate"]
    response = {
        "candidates": slate.get("candidates"),
        "provisional_lead": slate.get("provisional_lead"),
        "lead_rationale": slate.get("lead_rationale"),
    }
    regenerated = validate_proposals(base, offered, response, packet)
    require(canonical(regenerated) == canonical(preview),
            "theme preview differs from independently recomputed source manifest")
    return regenerated


def _choice(preview, slug, owner, approved_on, inventory):
    require(isinstance(owner, str) and owner == owner.strip()
            and 3 <= len(owner) <= 100 and
            not any(ord(ch) < 32 for ch in owner),
            "missing or invalid explicit owner identity")
    today = _date(approved_on)
    require(_date(inventory["week_ending"]) < today <=
            _date(inventory["review_local_day"]),
            "owner decision must follow Saturday close and not be future-dated")
    slate = preview["model_proposed_slate"]
    matches = [c for c in slate["candidates"] if c["slug"] == slug]
    require(len(matches) == 1, "choice must be one existing thematic candidate")
    selected = matches[0]
    ids = selected["source_ids"]
    require(isinstance(ids, list) and 2 <= len(ids) <= MAX_MODEL_IDS
            and all(type(i) is int for i in ids)
            and len(set(ids)) == len(ids),
            "Sunday writer requires 2–10 distinct reviewed numeric production records")
    covered = {row["id"]: row["desk"] for row in slate["evidence"]}
    require(all(i in covered for i in ids), "selected source ID not reviewed")
    desks = sorted({covered[i] for i in ids})
    require(len(desks) >= 2,
            "single-desk candidate is held for separate public exception; no automatic Sunday handoff")
    require(isinstance(selected["thesis"], str)
            and len(selected["thesis"]) <= 1000,
            "missing specific editorial thesis")
    return {
        "schema": SCHEMA,
        "week_ending": inventory["week_ending"],
        "source_metadata_digest_sha256": inventory["source_metadata_digest_sha256"],
        "source_review_seal_sha256": preview["source_review_seal_sha256"],
        "proposal_sha256": digest(preview),
        "theme_slug": slug,
        "approved_focus": selected["thesis"],
        "selected_source_ids": ids,
        "represented_desks": desks,
        "approved_by": owner,
        "approved_on": approved_on,
        "permission": "private_no_send_themed_sunday_manuscript_trial_only",
        "publication_authorized": False,
        "editor_email_authorized": False,
    }


def sign_choice(inventory, signed_review, secret, preview, *,
                slug, owner, approved_on):
    """Sign ONE human-selected candidate after validating all reviewed sources."""
    clean = checked_proposal(inventory, signed_review, secret, preview)
    choice = _choice(clean, slug, owner, approved_on, inventory)
    seal = hmac.new(_key(secret), DOMAIN + canonical(choice),
                    hashlib.sha256).hexdigest()
    return {"choice": choice, "hmac_sha256": seal}


def verify_choice(inventory, signed_review, secret, preview, signed_choice):
    """Reverify on fresh SQLite state before allowing the Sunday model call."""
    require(isinstance(signed_choice, dict)
            and set(signed_choice) == {"choice", "hmac_sha256"},
            "missing or malformed owner-signed theme choice")
    value = signed_choice["hmac_sha256"]
    require(isinstance(value, str) and len(value) == 64
            and all(ch in "0123456789abcdef" for ch in value),
            "invalid owner choice HMAC")
    expected = hmac.new(_key(secret),
                        DOMAIN + canonical(signed_choice["choice"]),
                        hashlib.sha256).hexdigest()
    require(hmac.compare_digest(value, expected),
            "owner-selected theme was altered or not signed")
    preview = checked_proposal(inventory, signed_review, secret, preview)
    choice = signed_choice["choice"]
    require(isinstance(choice, dict), "malformed owner choice")
    rebuilt = _choice(preview, choice.get("theme_slug"),
                      choice.get("approved_by"), choice.get("approved_on"),
                      inventory)
    require(canonical(rebuilt) == canonical(choice),
            "owner choice no longer agrees with the current approved proposal")
    return rebuilt
