"""Fail-closed, offline research-state consistency check for Vietnam journal.

This validates the CURRENT non-activation posture only. It cannot grant
copyright permissions, approve a source, or substitute for a production
collector's own enforcement. Deliberately no network, DB or output writes.
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA = "ipr-vietnam-journal-readiness/1"
SOURCE = "vn_national_defence_journal_en"
GATES = {
    "desktop_robots_tested_paths": "bounded_proof",
    "canonical_identity": "offline_verified",
    "article_extraction": "two_pages_in_memory",
    "four_category_discovery": "live_identity_parity_observed",
    "historical_enumeration": "unproven",
    "forward_listing_reliability": "not_started",
    "metadata_retention_rights": "unreviewed",
    "full_text_retention_rights": "unapproved",
    "public_republication_rights": "unapproved",
    "owner_shadow_activation": "not_authorized",
    "owner_production_promotion": "not_authorized",
}
EVIDENCE = {
    "desktop_access": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37712715499",
    "article_parser": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37715526834",
    "listing_parser": "https://github.com/VSSpowerlifting/China-Mil-Watch/actions/runs/37721439408",
    "historical_investigation": "https://github.com/VSSpowerlifting/China-Mil-Watch/issues/154",
    "source_use_decision": "https://github.com/VSSpowerlifting/China-Mil-Watch/issues/155",
}
DENIED_ACTIONS = (
    "automatic_collection",
    "shadow_source_activation",
    "metadata_persistence",
    "article_text_retention",
    "public_excerpt_or_translation",
    "public_full_text",
    "production_promotion",
)
PENDING = (
    "historical_enumeration",
    "forward_listing_reliability",
    "metadata_retention_rights",
    "full_text_retention_rights",
    "public_republication_rights",
    "owner_shadow_activation",
    "owner_production_promotion",
)


class ReadinessRefused(ValueError):
    pass


def _exact_fields(value, fields, context):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ReadinessRefused("%s missing or unexpected fields" % context)


def validate_research_hold(manifest, readiness):
    """Refuse any drift from the owner-declared disabled research posture.

    This frozen v1 is deliberately *not* a generic permission-grant schema:
    authorizing any action requires a new explicit decision, schema review
    and caller-side enforcement, not flipping a permissive Boolean here.
    """
    _exact_fields(readiness, ("schema", "source_slug", "source_role",
                  "authority_tier", "content_kind", "gates", "evidence",
                  "derived_permissions", "note"), "readiness")
    if (readiness["schema"] != SCHEMA
            or readiness["source_slug"] != SOURCE
            or readiness["source_role"] != "disabled_research_candidate"
            or readiness["authority_tier"] != "B"
            or readiness["content_kind"] != "military_journal_editorial"):
        raise ReadinessRefused("wrong journal source identity or authority")
    if readiness["gates"] != GATES:
        raise ReadinessRefused("journal evidence/rights gate changed without a new contract")
    if readiness["evidence"] != EVIDENCE:
        raise ReadinessRefused("journal evidence references changed without review")
    permissions = readiness["derived_permissions"]
    _exact_fields(permissions, DENIED_ACTIONS, "journal permissions")
    if any(value is not False for value in permissions.values()):
        raise ReadinessRefused("a disabled research candidate cannot authorize any use")
    if not isinstance(readiness["note"], str) or not readiness["note"].strip():
        raise ReadinessRefused("research limits must be disclosed")

    if not isinstance(manifest, dict):
        raise ReadinessRefused("missing source manifest")
    if (manifest.get("manifest_version") != 1
            or manifest.get("_shadow") is not True
            or not isinstance(manifest.get("desk"), dict)
            or manifest["desk"].get("active") is not False
            or manifest["desk"].get("desk_id") != "vietnam"):
        raise ReadinessRefused("journal manifest is not a disabled Vietnam research desk")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or len(sources) != 1:
        raise ReadinessRefused("one journal source expected, not multiple feeds")
    source = sources[0]
    if (not isinstance(source, dict)
            or source.get("slug") != SOURCE
            or source.get("enabled") is not False
            or source.get("authority_tier") != "B"
            or source.get("source_type") != "military_journal_editorial"
            or source.get("institution_id") != "vn_national_defence_journal"
            or source.get("language_tag") != "en"):
        raise ReadinessRefused("journal manifest source activated or misclassified")
    institutions = manifest.get("institutions")
    if (not isinstance(institutions, list) or len(institutions) != 1
            or institutions[0].get("institution_type") != "state_linked_media"):
        raise ReadinessRefused("journal cannot be treated as a ministry directive feed")
    if not isinstance(manifest.get("rights"), str) or "All rights reserved" not in manifest["rights"]:
        raise ReadinessRefused("source rights hold was weakened")
    return {
        "source_slug": SOURCE,
        "status": "research_disabled",
        "all_reuse_and_activation_actions": "not_authorized",
        "pending_decision_gates": list(PENDING),
        "historical_completeness_proven": False,
        "day_zero_started": False,
    }


def check_repository(root=None):
    root = Path(__file__).resolve().parents[1] if root is None else Path(root)
    base = root / "shadow" / "vietnam_journal"
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    readiness = json.loads((base / "readiness.v1.json").read_text(encoding="utf-8"))
    return validate_research_hold(manifest, readiness)


if __name__ == "__main__":
    print(json.dumps(check_repository(), sort_keys=True, indent=2))
