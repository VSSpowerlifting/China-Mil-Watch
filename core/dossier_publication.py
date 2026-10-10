"""B2.1 Living Dossier release-boundary prototype — intentionally nonpublishing.

The B1 schema and archive reconciler check mechanically verifiable inputs.
This module keeps those facts separate from *external* claim/source review,
action-scoped reuse clearance, authenticated editor approval, and an actual
publication decision. No production trust provider is implemented here:
eligible_for_publication is ALWAYS False.

Only explicitly marked, completely fictional example.org sidecars may become
private synthetic-preview candidates. Never use this module to publish data,
render a public route, send emails, or infer permissions from JSON strings.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from core.dossier_contract import dossier_content_digest, validate_dossier_shape

SCHEMA = "ipr-dossier-publication-gate/1"
ARCHIVE_REPORT_SCHEMA = "ipr-dossier-source-review/1"
SYNTHETIC_MARKER = "IPR_SYNTHETIC_PRIVATE_PREVIEW_ONLY_V1"
SOURCE_DECISION_KEYS = frozenset({
    "admitted", "screening_reviewed", "metadata_use", "publisher_link",
    "publisher_origin_reviewed", "local_record_link", "local_record_body_use_cleared",
})
AUTHORITY_KEYS = frozenset({
    "marker", "content_sha256", "revision", "editor_reviewed",
    "claim_ids", "sources", "history_checked",
})


def _code(name, record_id=None, claim_id=None):
    entry = {"code": name}
    if type(record_id) is int and 0 < record_id < 2**63:
        entry["record_id"] = record_id
    # Claim IDs are validated ASCII slugs by the B1 contract.
    if type(claim_id) is str and claim_id.isascii() and len(claim_id) <= 80:
        entry["claim_id"] = claim_id
    return entry


def _report(slug=None, digest=None, *, issues=(), synthetic_ready=False, allowed_links=None):
    return {
        "schema": SCHEMA,
        "dossier_slug": slug,
        "content_sha256": digest,
        "eligible_for_publication": False,
        "production_authority_configured": False,
        "private_synthetic_preview_ready": bool(synthetic_ready),
        "issues": list(issues),
        # This policy is ONLY for fictional private preview, not a
        # licence, source-body URL, or publishing permission.
        "synthetic_preview_link_policy": allowed_links or [],
    }


def _is_synthetic_fixture(sidecar):
    """Do not allow real corpus subjects through the simulation escape hatch."""
    if not sidecar["slug"].startswith("fictional-"):
        return False
    if not sidecar["sources"]:
        return False
    for source in sidecar["sources"]:
        # Existing production record IDs are outside the synthetic fixture
        # namespace: never accept a relabelled live archive record ID.
        rid = source["record_id"]
        if type(rid) is not int or not 900000 <= rid <= 999999:
            return False
        if not source["desk"].startswith("fixture-"):
            return False
        try:
            url = urlsplit(source["url"])
        except ValueError:
            return False
        if url.scheme != "https" or url.hostname not in {"example.org", "example.invalid"}:
            return False
    return True


def _claim_ids(sidecar):
    return sorted(c["id"] for section in sidecar["sections"] for c in section["claims"])


def _valid_archive(sidecar, archive, digest, issues):
    """Treat supplied B1.2 output as a reported observation, NOT authority."""
    if type(archive) is not dict or archive.get("schema") != ARCHIVE_REPORT_SCHEMA:
        issues.append(_code("archive-report-missing-or-invalid"))
        return None
    ids = [src["record_id"] for src in sidecar["sources"]]
    if (archive.get("dossier_slug") != sidecar["slug"]
            or archive.get("content_sha256") != digest
            or archive.get("editorial_status") != sidecar["editorial_status"]
            or archive.get("selected_record_ids") != ids
            or archive.get("archive_reconciled") is not True
            or archive.get("eligible_for_publication") is not False
            or type(archive.get("errors")) is not list
            or archive["errors"]):
        issues.append(_code("archive-parity-or-digest-not-verified"))
        return None
    evidence = archive.get("evidence")
    if type(evidence) is not list or len(evidence) != len(ids):
        issues.append(_code("archive-evidence-incomplete"))
        return None
    records = {}
    for item in evidence:
        if type(item) is not dict:
            issues.append(_code("archive-evidence-invalid"))
            return None
        rid = item.get("record_id")
        if (type(rid) is not int or rid in records or rid not in ids
                or item.get("archive_identity_reconciled") is not True
                or item.get("model_screening") not in ("selected", "not_selected", "pending")):
            issues.append(_code("archive-evidence-invalid"))
            return None
        records[rid] = item["model_screening"]
    if set(records) != set(ids):
        issues.append(_code("archive-evidence-incomplete"))
        return None
    return records


def assess_dossier_release(sidecar, archive_review, *, synthetic_authority=None,
                           private_synthetic_preview=False):
    """Report independent holds; NEVER return a production-publication grant.

    The synthetic_authority object is NOT an authenticated receipt; it is
    accepted only for private fictional demonstrations. The default path and
    any real-world Dossier always fail closed. No source body is inspected or
    emitted. Caller must never treat preview readiness as public eligibility.
    """
    try:
        validate_dossier_shape(sidecar)
        digest = dossier_content_digest(sidecar)
    except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError):
        return _report(issues=[_code("dossier-contract-invalid")])
    slug = sidecar["slug"]
    issues = []
    screenings = _valid_archive(sidecar, archive_review, digest, issues)
    if sidecar["editorial_status"] != "approved":
        issues.append(_code("dossier-not-approved"))

    if not private_synthetic_preview:
        issues.append(_code("independent-production-authority-not-implemented"))
        return _report(slug, digest, issues=issues)
    if not _is_synthetic_fixture(sidecar):
        issues.append(_code("nonfictional-preview-refused"))
        return _report(slug, digest, issues=issues)

    auth = synthetic_authority
    if type(auth) is not dict or set(auth) != AUTHORITY_KEYS:
        issues.append(_code("synthetic-review-packet-missing-or-invalid"))
        return _report(slug, digest, issues=issues)
    if (auth["marker"] != SYNTHETIC_MARKER
            or auth["content_sha256"] != digest
            or type(auth["revision"]) is not int
            or auth["revision"] != sidecar["revision"]):
        issues.append(_code("synthetic-review-version-drift"))
    if auth["editor_reviewed"] is not True:
        issues.append(_code("synthetic-editor-review-missing"))
    if (sidecar["revision"] >= 2 and auth["history_checked"] is not True):
        issues.append(_code("prior-version-evidence-missing"))
    claims = _claim_ids(sidecar)
    if type(auth["claim_ids"]) is not list or auth["claim_ids"] != claims:
        issues.append(_code("synthetic-claim-review-incomplete"))

    decisions = auth["sources"]
    if type(decisions) is not dict or set(decisions) != {str(x["record_id"]) for x in sidecar["sources"]}:
        issues.append(_code("synthetic-source-decisions-incomplete"))
        return _report(slug, digest, issues=issues)

    allowed = []
    for src in sidecar["sources"]:
        rid = src["record_id"]
        policy = decisions[str(rid)]
        if type(policy) is not dict or set(policy) != SOURCE_DECISION_KEYS:
            issues.append(_code("synthetic-source-decision-invalid", rid))
            continue
        if any(type(v) is not bool for v in policy.values()):
            issues.append(_code("synthetic-source-decision-invalid", rid))
            continue
        if not policy["admitted"]:
            issues.append(_code("source-human-admission-missing", rid))
        if screenings is None:
            continue
        if screenings[rid] != "selected" and not policy["screening_reviewed"]:
            issues.append(_code("source-screening-disposition-missing", rid))
        if not policy["metadata_use"]:
            issues.append(_code("source-metadata-use-not-cleared", rid))
        publisher_link = policy["publisher_link"] and policy["publisher_origin_reviewed"]
        local_link = policy["local_record_link"] and policy["local_record_body_use_cleared"]
        if policy["publisher_link"] and not policy["publisher_origin_reviewed"]:
            issues.append(_code("publisher-origin-not-reviewed", rid))
        if policy["local_record_link"] and not policy["local_record_body_use_cleared"]:
            issues.append(_code("local-record-body-use-not-cleared", rid))
        if not (publisher_link or local_link):
            issues.append(_code("claim-citation-navigation-not-cleared", rid))
        # Only booleans and synthetic IDs, never source URLs, source text or
        # private clearance correspondence.
        allowed.append({"record_id": rid, "publisher_link": publisher_link,
                        "local_record_link": local_link})

    # Both supporting and counterevidence citations must have safe navigable
    # destinations; a contrary source cannot bypass the action-scoped policy.
    cleared = {x["record_id"] for x in allowed if x["publisher_link"] or x["local_record_link"]}
    for section in sidecar["sections"]:
        for claim in section["claims"]:
            all_citations = set(claim["source_record_ids"] + claim["counterevidence_ids"])
            if not all_citations <= cleared:
                issues.append(_code("claim-has-uncleared-citation", claim_id=claim["id"]))

    issues.append(_code("public-release-disabled-by-design"))
    # Only the final fixed public-release hold may remain for a private preview.
    preview = all(x["code"] == "public-release-disabled-by-design" for x in issues)
    return _report(slug, digest, issues=issues, synthetic_ready=preview,
                   allowed_links=allowed if preview else [])
