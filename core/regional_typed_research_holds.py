"""Read-only regional Japan/Vietnam typed-source *hold* audit.

No source review, source permission, publication, production promotion, model
input, sender, or source body. Designed as Issue #271's first provenance
reconciliation gate, entirely separate from the live Sunday writer.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from urllib.parse import urlsplit

SCHEMA = "ipr-regional-typed-research-holds/1"
INVENTORY_SCHEMA = "ipr-regional-weekly-evidence/1"
STATUS = "unapproved-source-linked-editorial-candidate"
COPY_SCOPE = "private-model-drafting-only-no-source-body"
FIRST_SATURDAY = "2026-10-10"
FIRST_JAPAN = frozenset({"JP-W41-01", "JP-W41-02", "JP-W41-06"})
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")


class TypedResearchHoldError(ValueError):
    """Unverifiable source metadata cannot be joined to regional inventory."""


def demand(condition, message):
    if not condition:
        raise TypedResearchHoldError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def valid_day(value):
    demand(isinstance(value, str), "invalid research date")
    try:
        day = date.fromisoformat(value)
    except ValueError as exc:
        raise TypedResearchHoldError("invalid calendar date") from exc
    demand(day.isoformat() == value, "noncanonical research date")
    return day


def valid_https(url):
    demand(isinstance(url, str), "missing source publisher URL")
    try:
        parsed = urlsplit(url)
        no_port = parsed.port is None
    except ValueError as exc:
        raise TypedResearchHoldError("invalid publisher URL") from exc
    demand(parsed.scheme == "https" and parsed.hostname is not None
           and no_port and not parsed.username and not parsed.password
           and not parsed.fragment,
           "untrusted source publisher URL")
    return parsed


def audit_typed_holds(inventory, research_rows):
    """Reconcile prior validated typed research notes to inventory holds only.

    research_rows MUST originate from load_editorial_evidence() for the exact
    reporting week. Structural SHA/commit presence does NOT rehash source
    content, confirm version currency, or grant even private-model source use.
    """
    demand(isinstance(inventory, dict)
           and inventory.get("schema") == INVENTORY_SCHEMA,
           "missing regional source-inventory contract")
    demand(inventory.get("model_input_authorized") is False
           and inventory.get("publication_authorized") is False
           and inventory.get("editor_email_authorized") is False
           and inventory.get("source_trust_status") ==
           "inventory_only_not_attested_for_model_or_publication",
           "source inventory must not claim approval")
    week = inventory.get("week_ending")
    valid_day(week)
    valid_day(inventory.get("week_start"))
    valid_day(inventory.get("source_as_of"))
    demand(isinstance(research_rows, list) and len(research_rows) <= 8,
           "typed research must be bounded and already validated")
    pending = inventory.get("pending_private_research")
    demand(isinstance(pending, list), "missing pending research inventory")
    listed = {}
    for item in pending:
        demand(isinstance(item, dict)
               and set(item) == {"id", "desk", "source_url",
                                 "published_date", "reason"}
               and item["reason"] ==
               "independent_shadow_attestation_and_source_use_pending",
               "invalid regional pending-source pointer")
        ident = item["id"]
        demand(isinstance(ident, str) and ident not in listed,
               "duplicate or non-typed pending source")
        valid_https(item["source_url"])
        valid_day(item["published_date"])
        listed[ident] = item
    production_urls = set()
    for x in inventory.get("production_evidence", []):
        demand(isinstance(x, dict) and isinstance(x.get("source_url"), str),
               "invalid production evidence")
        production_urls.add(x["source_url"])
    observed, urls, outputs = set(), set(), []
    for item in research_rows:
        demand(isinstance(item, dict) and
               all(name in item for name in (
                   "id", "desk", "source_url", "published_date",
                   "source_name", "source_kind", "status", "copy_scope",
                   "source_content_sha256", "state_commit", "hash_rule")),
               "malformed typed research input")
        ident, desk, url = item["id"], item["desk"], item["source_url"]
        demand(isinstance(ident, str) and ident not in observed
               and ident in listed, "unknown or duplicate typed source")
        observed.add(ident)
        demand(desk in ("japan", "vietnam")
               and desk == listed[ident]["desk"]
               and url == listed[ident]["source_url"]
               and item["published_date"] == listed[ident]["published_date"]
               and item["status"] == STATUS
               and item["copy_scope"] == COPY_SCOPE,
               "research claims approval or differs from private inventory hold")
        parsed = valid_https(url)
        demand(url not in urls and url not in production_urls,
               "typed source duplicates research/production publisher URL")
        urls.add(url)
        if desk == "japan":
            demand(re.fullmatch(r"JP-W[0-9]{2}-[0-9]{2}", ident) is not None
                   and parsed.hostname == "www.mod.go.jp"
                   and item["source_name"] == "Japan Ministry of Defense",
                   "unsupported Japan research family")
        else:
            match = re.fullmatch(r"VN-MPS-([1-9][0-9]{6,20})", ident)
            demand(match is not None and parsed.hostname == "bocongan.gov.vn"
                   and item["source_name"] == "Vietnam Ministry of Public Security"
                   and parsed.path.endswith("-" + match.group(1)),
                   "unsupported Vietnam research family")
        kind, commit, content_hash = (
            item["source_kind"], item["state_commit"],
            item["source_content_sha256"])
        if kind == "shadow-extracted-original":
            demand(isinstance(commit, str) and HEX40.fullmatch(commit)
                   and isinstance(content_hash, str)
                   and HEX64.fullmatch(content_hash)
                   and item["hash_rule"] in (
                       "sha256-text-original-utf8", "mps-vi-content-v1"),
                   "missing immutable shadow original identity")
            reason = "historical_shadow_pin_present_current_capture_not_attested"
            version_pin = True
        elif kind == "official-publisher-page-reviewed-for-research":
            demand(commit is None and content_hash is None
                   and item["hash_rule"] is None,
                   "publisher-page source cannot claim preserved original")
            reason = "publisher_page_immutable_original_missing_requires_review"
            version_pin = False
        else:
            raise TypedResearchHoldError("unknown research provenance family")
        # Deliberately NO article title/synopsis/source body in this hold report.
        outputs.append({
            "id": ident,
            "desk": desk,
            "publisher_url_sha256": hashlib.sha256(url.encode("utf-8")).hexdigest(),
            "published_date": item["published_date"],
            "source_kind": kind,
            "historical_version_pin_structurally_present": version_pin,
            "state_commit": commit,
            "source_content_sha256": content_hash,
            "hash_rule": item["hash_rule"],
            "state": "hold_independent_original_version_and_source_use_review",
            "reason": reason,
            "private_model_input_authorized": False,
            "production_record": False,
            "publication_authorized": False,
        })
    demand(set(listed) == observed,
           "source packet and inventory have different typed research rosters")
    outputs.sort(key=lambda x: (x["desk"], x["id"]))
    japan = {row["id"] for row in outputs if row["desk"] == "japan"}
    vietnam = {row["id"] for row in outputs if row["desk"] == "vietnam"}
    missing = sorted(FIRST_JAPAN - japan) if week == FIRST_SATURDAY else []
    unexpected = sorted(japan - FIRST_JAPAN) if week == FIRST_SATURDAY else []
    violations = []
    if week == FIRST_SATURDAY and missing:
        violations.append("first_pilot_missing_japan_research_ids")
    if week == FIRST_SATURDAY and unexpected:
        violations.append("first_pilot_unexpected_japan_research_ids")
    if week == FIRST_SATURDAY and not vietnam:
        violations.append("first_pilot_missing_vietnam_research")
    return {
        "schema": SCHEMA,
        "week_ending": week,
        "source_as_of": inventory["source_as_of"],
        "source_metadata_digest_sha256": inventory["source_metadata_digest_sha256"],
        "typed_research_roster_sha256": hashlib.sha256(
            canonical(outputs)).hexdigest(),
        "items": outputs,
        "counts": {
            "japan": len(japan),
            "vietnam": len(vietnam),
            "historical_pin_present_not_revalidated": sum(
                x["historical_version_pin_structurally_present"] for x in outputs),
            "missing_original_capture": sum(
                not x["historical_version_pin_structurally_present"] for x in outputs),
        },
        "first_pilot_roster_gaps": violations,
        "first_pilot_missing_japan_ids": missing,
        "first_pilot_unexpected_japan_ids": unexpected,
        "all_items_held_for_human_review": True,
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "japan_vietnam_production_activated": False,
    }
