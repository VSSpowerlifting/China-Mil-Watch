"""Private, non-authorizing review-progress audit for held typed research.

Checks worksheet integrity against fresh source pins. Human-entered checkmarks
are only claims; this grants NO research admission, model, mail or publication.
"""
from __future__ import annotations

from core.regional_typed_human_review_prep import (
    REVIEW_FIELDS, create_unsigned_worksheet,
)

SCHEMA = "ipr-regional-typed-review-progress/1"
TEXT_FIELDS = frozenset((
    "reviewer_identity", "reviewed_source_version_or_capture",
    "rights_basis_url_or_document", "reuse_permission_scope",
    "editorial_claims_to_recheck", "discrepancies_and_omissions",
    "review_notes",
))
EDITABLE = TEXT_FIELDS | {"review_checks"}


class TypedReviewProgressError(ValueError):
    """Mutated provenance or unsupported reviewer assertions."""


def require(ok, reason):
    if not ok:
        raise TypedReviewProgressError(reason)


def bounded_note(value):
    return value is None or (
        isinstance(value, str) and value == value.strip()
        and 1 <= len(value) <= 1200
        and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
    )


def evaluate_progress(worksheet, inventory, research_rows):
    """Reconstruct exact worksheet pins before evaluating human completion."""
    expected = create_unsigned_worksheet(inventory, research_rows)
    require(isinstance(worksheet, dict) and set(worksheet) == set(expected),
            "unexpected worksheet field or schema")
    for name in expected:
        if name != "records":
            require(worksheet[name] == expected[name],
                    "immutable header, snapshot or permission flag changed")
    records = worksheet["records"]
    pins = expected["records"]
    require(isinstance(records, list) and len(records) == len(pins),
            "typed source roster mismatch")
    output = []
    for item, pin in zip(records, pins):
        require(isinstance(item, dict) and set(item) == set(pin),
                "unexpected per-source worksheet field")
        for name in pin:
            if name not in EDITABLE:
                require(item[name] == pin[name],
                        "source identity, version, status or permission changed")
        checks = item["review_checks"]
        require(isinstance(checks, dict) and set(checks) == set(REVIEW_FIELDS),
                "human review checklist schema changed")
        require(all(v is None or type(v) is bool for v in checks.values()),
                "review check must be bool or null")
        require(all(bounded_note(item[f]) for f in TEXT_FIELDS),
                "reviewer source or rights note is malformed")
        missing = [key for key in REVIEW_FIELDS if checks[key] is not True]
        missing += [key for key in sorted(TEXT_FIELDS) if item[key] is None]
        output.append({
            "id": pin["id"], "desk": pin["desk"],
            "state": ("reported_complete_but_unsigned_not_admitted"
                      if not missing else "human_review_entries_pending"),
            "missing_fields": sorted(missing),
            "reported_complete_unsigned": not missing,
            "independent_source_and_rights_review_attested": False,
            "model_input_authorized": False,
            "editor_email_authorized": False,
            "publication_authorized": False,
        })
    return {
        "schema": SCHEMA,
        "week_ending": expected["week_ending"],
        "source_metadata_digest_sha256": expected["source_metadata_digest_sha256"],
        "typed_research_roster_sha256": expected["typed_research_roster_sha256"],
        "unsigned_template_sha256": expected["unsigned_template_sha256"],
        "source_count": len(output),
        "reported_complete_unsigned": sum(x["reported_complete_unsigned"] for x in output),
        "items": output,
        "human_source_review_signed": False,
        "model_input_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "japan_vietnam_production_activated": False,
        "note": "Checklist completion is not authenticated source custody, source-use rights, a signature or operational permission.",
    }
