"""Optional *human-reviewed* external official references in IPR Briefs.

These references are publisher-hosted official documents, not a new corpus:
no archived article body, synthetic DB record, automatic collection, model
translation, production desk count, or inferred license. Editors may use them
only after manually verifying the original and its captured version.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urlsplit

SCHEMA = "brief-external-official-source/1"
SOURCE_SLUG = "vn_mps_foreign_affairs_vi"
SOURCE_NAME = "Vietnam Ministry of Public Security"
HOST = "bocongan.gov.vn"
SCOPE = "publisher-link-and-original-analyst-summary-only"
CHECKS = {
    "source_page_opened", "original_title_matches", "publication_date_matches",
    "issuing_institution_matches", "complete_original_body_reviewed",
    "pinned_content_version_checked", "original_summary_fact_checked",
    "no_copied_article_body",
}
IDENTITY = re.compile(r"mps-vi:([1-9][0-9]{6,20})\\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\\Z")
REFERENCE = re.compile(r"\\[External ([^\\]\\r\\n]+)\\]")
MAX_ITEMS = 5
FIELDS = {
    "schema", "source_identity", "desk", "source_slug", "source_name",
    "url", "original_title", "lang", "date", "state_commit",
    "content_sha256", "original_summary", "human_review",
}
REVIEW_FIELDS = {"reviewed_by", "reviewed_on", "checks", "scope"}


def _day(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _text(value, min_len, max_len):
    return (isinstance(value, str) and min_len <= len(value.strip()) <= max_len
            and value == value.strip()
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))


def external_anchor(identity):
    """A predictable safe anchor. Call only after schema validation."""
    return "ext-" + identity.replace(":", "-")


def validate_external_evidence(sidecar, registry, *, require_citations=True):
    """Return all material validation errors; never assume human approval.

    Explicit review checkboxes are signed assertions, not independently
    verified facts. The publisher pages / archived captures must actually
    be compared by a human reviewer before the sidecar receives these fields.
    """
    if "external_evidence" not in sidecar:
        return []
    values = sidecar["external_evidence"]
    if not isinstance(values, list) or len(values) > MAX_ITEMS:
        return ["external_evidence must be a list of at most five reviewed entries"]
    if not values:
        return []
    desks = {getattr(d, "slug", None) for d in registry}
    start, end = _day(sidecar.get("week_start")), _day(sidecar.get("week_ending"))
    approval = sidecar.get("approval") or {}
    approved_on = _day(approval.get("approved_on")) if isinstance(approval, dict) else None
    approved = sidecar.get("editorial_status") == "approved"
    problems, seen_ids, seen_urls = [], set(), set()
    production_urls = {e.get("url") for e in sidecar.get("source_trail", [])
                       if isinstance(e, dict)}
    for index, item in enumerate(values):
        prefix = "external_evidence[%d]" % index
        if not isinstance(item, dict) or set(item) != FIELDS:
            problems.append(prefix + ": invalid fields")
            continue
        ident = item["source_identity"]
        match = IDENTITY.fullmatch(ident) if isinstance(ident, str) else None
        if not match:
            problems.append(prefix + ": malformed MPS source identity")
        elif ident in seen_ids:
            problems.append(prefix + ": duplicated source identity")
        else:
            seen_ids.add(ident)
        if item["schema"] != SCHEMA or item["desk"] != "vietnam" or "vietnam" not in desks:
            problems.append(prefix + ": must identify a declared Vietnam source")
        if item["desk"] in (sidecar.get("desks") or []):
            problems.append(prefix + ": external evidence cannot masquerade as corpus coverage")
        if item["source_slug"] != SOURCE_SLUG or item["source_name"] != SOURCE_NAME:
            problems.append(prefix + ": unsupported publisher family")
        if item["lang"] != "vi" or not _text(item["original_title"], 8, 350):
            problems.append(prefix + ": source title must be original Vietnamese metadata")
        url = item["url"]
        try:
            p = urlsplit(url if isinstance(url, str) else "")
            allowed_port = p.port is None
        except ValueError:
            p, allowed_port = None, False
        if (not _text(url, 40, 1800) or p is None or p.scheme != "https"
                or p.hostname != HOST or not allowed_port or p.username or p.password
                or p.query or p.fragment or not match or not p.path.startswith("/bai-viet/")
                or not p.path.endswith("-" + match.group(1))):
            problems.append(prefix + ": official URL/identity does not match")
        elif url in seen_urls or url in production_urls:
            problems.append(prefix + ": URL is duplicated or already archived")
        else:
            seen_urls.add(url)
        published = _day(item["date"])
        if not published or not start or not end or not start <= published <= end:
            problems.append(prefix + ": published outside reporting week or invalid window")
        if not isinstance(item["state_commit"], str) or not HEX40.fullmatch(item["state_commit"]):
            problems.append(prefix + ": missing pinned Git commit")
        if not isinstance(item["content_sha256"], str) or not HEX64.fullmatch(item["content_sha256"]):
            problems.append(prefix + ": missing captured original version SHA-256")
        if not _text(item["original_summary"], 40, 700):
            problems.append(prefix + ": missing short original analyst summary")
        review = item["human_review"]
        if not isinstance(review, dict) or set(review) != REVIEW_FIELDS:
            problems.append(prefix + ": missing human source review")
            continue
        reviewed = _day(review["reviewed_on"])
        if (not _text(review["reviewed_by"], 3, 120) or not reviewed or
                (published is not None and reviewed < published) or
                (approved and (not approved_on or reviewed > approved_on))):
            problems.append(prefix + ": invalid reviewer/date or review occurred after approval")
        if review["scope"] != SCOPE:
            problems.append(prefix + ": only source link and original analyst synopsis permitted")
        checks = review["checks"]
        if not isinstance(checks, dict) or set(checks) != CHECKS or any(
                checks[k] is not True for k in CHECKS):
            problems.append(prefix + ": each source and no-copy check must be affirmed")
    # The source is actually used rather than parked in the Brief as decoration.
    if require_citations:
        prose = [sidecar.get(field) for field in (
            "title", "dek", "signal", "opening_note", "what_stood_out",
            "why_it_matters", "what_was_routine", "what_im_watching_next")]
        development = sidecar.get("development")
        if isinstance(development, dict):
            prose.append(development.get("summary"))
        for claim in sidecar.get("cross_desk_claims") or []:
            if isinstance(claim, dict):
                prose.append(claim.get("claim"))
        refs = []
        for paragraph in prose:
            refs.extend(REFERENCE.findall(str(paragraph or "")))
        for ref in refs:
            if ref not in seen_ids:
                problems.append("external source citation %r has no verified reference" % ref)
        for ident in seen_ids:
            if ident not in refs:
                problems.append("external source %r is never cited in the brief's prose" % ident)
    return problems
