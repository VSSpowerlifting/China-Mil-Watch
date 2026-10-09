"""Fail-closed owner-reviewed synopsis packet for *private* regional AI triage.

This is a narrow Stage-3A boundary; NOT a source-license, publisher-version,
collection-completeness, manuscript-quality, or public-publication attestation.
It sends NOTHING. Verification only passes with an owner-held secret, a
source-pinned review docket, and a freshly produced read-only inventory.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date

REVIEW_SCHEMA = "ipr-regional-source-review/1"
PACKET_SCHEMA = "ipr-regional-private-model-candidates/1"
SCOPE = "private_model_analyst_synopsis_only"
MAX_SELECTED = 20
MIN_KEY_BYTES = 32
MAX_SYNOPSIS_CHARS = 650


class ReviewGateError(ValueError):
    """Private model input gate failed. No fallback/partial release."""


def _need(ok, why):
    if not ok:
        raise ReviewGateError(why)


def _keys(obj, names, what):
    _need(isinstance(obj, dict) and set(obj) == set(names),
          what + ": incorrect or extra fields")


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _key(secret):
    _need(isinstance(secret, bytes) and len(secret) >= MIN_KEY_BYTES,
          "an independent 32-byte-or-longer owner review secret is required")
    return secret


def _iso(value):
    _need(isinstance(value, str), "reviewed date must be YYYY-MM-DD")
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise ReviewGateError("invalid review date") from exc
    _need(day.isoformat() == value, "review date must be canonical YYYY-MM-DD")
    return day


def _note(value, name, min_len, max_len):
    _need(isinstance(value, str) and value == value.strip()
          and min_len <= len(value) <= max_len
          and not any(ord(c) < 32 or ord(c) == 127 for c in value),
          name + ": invalid or unbounded text")


def _inventory(inventory):
    _need(isinstance(inventory, dict)
          and inventory.get("schema") == "ipr-regional-weekly-evidence/1",
          "unsupported inventory")
    _need(inventory.get("source_trust_status") ==
          "inventory_only_not_attested_for_model_or_publication",
          "inventory trust state changed unexpectedly")
    _need(inventory.get("model_input_authorized") is False
          and inventory.get("publication_authorized") is False
          and inventory.get("editor_email_authorized") is False,
          "inventory must have no inherited model/publication permission")
    _need(inventory.get("production_preflight") ==
          "candidate_for_no_send_model_preview_not_approved"
          and inventory.get("unmet_production_gates") == [],
          "reporting week or Sunday corpus health is not ready for private model preview")
    _iso(inventory.get("week_ending"))
    _iso(inventory.get("review_local_day"))
    _need(inventory.get("source_as_of") == inventory.get("week_ending"),
          "partial-week sources cannot enter the full-week model input")
    _need(isinstance(inventory.get("source_metadata_digest_sha256"), str)
          and len(inventory["source_metadata_digest_sha256"]) == 64
          and all(x in "0123456789abcdef"
                  for x in inventory["source_metadata_digest_sha256"]),
          "missing metadata snapshot pin")
    evid = inventory.get("production_evidence")
    _need(isinstance(evid, list), "missing production inventory")
    sources = {}
    for source in evid:
        _need(isinstance(source, dict)
              and type(source.get("id")) is int and source["id"] > 0
              and source.get("lane") == "production_record"
              and source.get("scope") == "production_evidence"
              and source.get("role") == "new_week"
              and isinstance(source.get("stored_text_sha256"), str)
              and len(source["stored_text_sha256"]) == 64,
              "malformed production pointer")
        _need(source["id"] not in sources, "duplicate production identity")
        sources[source["id"]] = source
    return sources


def _review_payload(unsigned, inventory):
    _keys(unsigned, (
        "schema", "week_ending", "source_metadata_digest_sha256",
        "reviewer", "reviewed_on", "scope", "decisions",
    ), "review")
    _need(unsigned["schema"] == REVIEW_SCHEMA
          and unsigned["week_ending"] == inventory["week_ending"]
          and unsigned["source_metadata_digest_sha256"] ==
          inventory["source_metadata_digest_sha256"]
          and unsigned["scope"] == SCOPE,
          "review is not pinned to exact week/snapshot/private scope")
    _note(unsigned["reviewer"], "reviewer", 3, 100)
    today = _iso(unsigned["reviewed_on"])
    _need(_iso(inventory["week_ending"]) <= today <=
          _iso(inventory["review_local_day"]),
          "review cannot precede reporting close or postdate review execution")
    choices = unsigned["decisions"]
    _need(isinstance(choices, list) and 1 <= len(choices) <= MAX_SELECTED,
          "private model packet requires 1..20 explicitly reviewed records")
    sources = _inventory(inventory)
    found = set()
    for choice in choices:
        _keys(choice, (
            "id", "desk", "source_url", "published_date",
            "stored_text_sha256", "disposition", "synopsis", "limitations",
            "original_language_checked", "publisher_version_checked",
            "not_a_quote_or_full_text",
        ), "source decision")
        ident = choice["id"]
        _need(type(ident) is int and ident not in found
              and ident in sources,
              "reviewed IDs must be unique numeric production pointers")
        found.add(ident)
        source = sources[ident]
        for name in ("desk", "source_url", "published_date",
                     "stored_text_sha256"):
            _need(choice[name] == source[name],
                  "reviewed source does not match pinned inventory: " + name)
        _need(choice["disposition"] == "privately_reviewed"
              and choice["original_language_checked"] is True
              and choice["publisher_version_checked"] is True
              and choice["not_a_quote_or_full_text"] is True,
              "each synopsis requires affirmative source and original-language review")
        _note(choice["synopsis"], "attributed synopsis", 65, MAX_SYNOPSIS_CHARS)
        _note(choice["limitations"], "source limitations", 30, 350)
    return sources


def sign_private_review(unsigned, inventory, secret):
    """Seal explicit manual decisions, WITHOUT invoking AI or collecting URLs.

    Only an editor-controlled, separate offline signing process should hold
    the secret. Merely creating an inventory is not permission to sign.
    """
    _review_payload(unsigned, inventory)
    seal = hmac.new(_key(secret), _canonical(unsigned), hashlib.sha256).hexdigest()
    return {"review": unsigned, "hmac_sha256": seal}


def verify_private_review(sealed, inventory, secret):
    """Verify reviewed manifest against a *freshly re-inspected* inventory.

    The caller is responsible for obtaining the inventory with inspect(),
    not a model-supplied or stale JSON file. A valid HMAC demonstrates
    owner-secret possession, not publisher consent or factual truth.
    """
    _keys(sealed, ("review", "hmac_sha256"), "signed review")
    digest = sealed["hmac_sha256"]
    _need(isinstance(digest, str) and len(digest) == 64
          and all(x in "0123456789abcdef" for x in digest),
          "invalid review seal")
    want = hmac.new(_key(secret), _canonical(sealed["review"]),
                    hashlib.sha256).hexdigest()
    _need(hmac.compare_digest(digest, want),
          "owner review signature missing or altered")
    return _review_payload(sealed["review"], inventory)


def private_model_packet(inventory, sealed, secret):
    """Produce an owner-reviewed SYNOPSIS-only packet; no API/SMTP side effects.

    No full source body, English machine translation or arbitrary item text
    from the untrusted inventory is included. Model invocation is a separate,
    explicitly controlled stage; manuscript publication is never implied.
    """
    sources = verify_private_review(sealed, inventory, secret)
    review = sealed["review"]
    entries = []
    for choice in review["decisions"]:
        source = sources[choice["id"]]
        entries.append({
            "id": choice["id"],
            "desk": choice["desk"],
            "publisher_url": choice["source_url"],
            "published_date": choice["published_date"],
            "original_language": source["language"],
            "publisher": source["source_name"],
            "title_original": source["title_original"],
            "analyst_synopsis": choice["synopsis"],
            "accuracy_limitations": choice["limitations"],
            "body_basis": source["body_basis"],
            "stored_text_sha256": choice["stored_text_sha256"],
            "trust_lane": "reviewed_production_analyst_synopsis_private_only",
        })
    return {
        "schema": PACKET_SCHEMA,
        "week_start": inventory["week_start"],
        "week_ending": inventory["week_ending"],
        "source_metadata_digest_sha256": inventory["source_metadata_digest_sha256"],
        "review_seal_sha256": sealed["hmac_sha256"],
        "review_scope": SCOPE,
        "production_sources": entries,
        "private_model_synopses_only": True,
        "not_an_official_publisher_attestation": True,
        "unreviewed_japan_vietnam_research_excluded": True,
        "publication_authorized": False,
        "editor_email_authorized": False,
        "delivery_scheduled": False,
    }
