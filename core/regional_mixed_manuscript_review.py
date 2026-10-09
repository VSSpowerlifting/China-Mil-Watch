"""No-send private mixed-source IPR manuscript review and citation worksheet.

The existing Sunday prose/citation validator is reused, but with exactly
the mixed numeric/typed source IDs selected by the independent signed owner
theme decision. This module never calls a model, copies publisher body text,
writes a file, emails Dylan, approves a Brief or changes publication state.
"""
from __future__ import annotations

import hashlib
import json

from core.regional_mixed_theme_choice import verify_owner_mixed_theme_choice
from core.regional_reviewed_typed_slate import (
    build_reviewed_mixed_context, canonical,
)
from scripts.sunday_briefs_auto_writer import (
    CITED_FIELDS, PROSE_FIELDS, validate_manuscript,
)

SCHEMA = "ipr-private-reviewed-mixed-manuscript-audit/1"
PACKET_HEADER = "INDO-PACIFIC RECORD | BRIEFS PRIVATE MANUSCRIPT REVIEW"
MAX_PACKET_BYTES = 35000
MAX_DRAFT_BYTES = 23000


class PrivateMixedManuscriptError(ValueError):
    """An ungrounded draft, changed owner choice or unsafe output must not pass."""


def need(ok, why):
    if not ok:
        raise PrivateMixedManuscriptError(why)


def one_line(value):
    return " ".join(str(value or "").split())


def _preflight(inputs, signed_run, run_key, proposal, signed_choice, choice_key):
    try:
        choice = verify_owner_mixed_theme_choice(
            inputs, signed_run, run_key, proposal, signed_choice, choice_key)
        ctx = build_reviewed_mixed_context(**inputs)
    except (ValueError, KeyError, TypeError) as exc:
        raise PrivateMixedManuscriptError(
            "signed owner focus or fresh source review failed") from exc
    need(choice["private_manuscript_model_authorized"] is False
         and choice["editor_email_authorized"] is False
         and choice["publication_authorized"] is False,
         "owner theme focus cannot grant production/publication privileges")
    chosen_ids = choice["source_ids"]
    by_id = {row["id"]: row for row in ctx["reviewed_synopses"]}
    need(set(chosen_ids).issubset(by_id), "owner-selected source is not reviewed")
    source_basis = {row["id"]: row for row in choice["source_basis"]}
    need(len(source_basis) == len(chosen_ids)
         and list(source_basis) == chosen_ids, "changed owner source order")
    for ident in chosen_ids:
        row, basis = by_id[ident], source_basis[ident]
        need(row["desk"] == basis["desk"]
             and row["published_date"] == basis["published_date"]
             and basis["lane"] == ("production_record" if type(ident) is int
                                   else "private_research"),
             "owner theme citation differs from reviewed source pin")
    return choice, [by_id[ident] for ident in chosen_ids]


def validate_private_mixed_manuscript(
        inputs, signed_run, run_key, proposal, signed_choice, choice_key,
        manuscript):
    """Return only a metadata-only citation/audit receipt, never draft prose."""
    choice, rows = _preflight(
        inputs, signed_run, run_key, proposal, signed_choice, choice_key)
    need(isinstance(manuscript, dict), "private manuscript must be an object")
    prod = [row for row in rows if type(row["id"]) is int]
    typed = [row for row in rows if type(row["id"]) is str]
    required = set(PROSE_FIELDS) | {"citations"}
    if typed:
        required |= {"editorial_focus", "supplemental_citations"}
    need(set(manuscript) == required,
         "unexpected private manuscript fields or missing citation structure")
    try:
        draft_bytes = canonical(manuscript)
    except (TypeError, ValueError) as exc:
        raise PrivateMixedManuscriptError("malformed manuscript JSON") from exc
    need(len(draft_bytes) <= MAX_DRAFT_BYTES, "private manuscript exceeds bounded length")
    need(isinstance(manuscript["citations"], dict)
         and set(manuscript["citations"]) == set(CITED_FIELDS),
         "manuscript must supply exact numeric citation sections")
    if typed:
        need(isinstance(manuscript["supplemental_citations"], dict)
             and set(manuscript["supplemental_citations"]) == set(CITED_FIELDS),
             "manuscript must supply exact typed citation sections")
        need(isinstance(manuscript["editorial_focus"], str)
             and choice["approved_focus"] ==
                 manuscript["editorial_focus"],
             "mixed manuscript must reproduce exact owner-signed editorial focus")
    # The old Sunday validator expects (SQL-like row, body) pairs.
    # DO NOT fill fake publisher body text: only desk/ID are ever inspected.
    chosen = [({"id": row["id"], "desk_id": row["desk"]}, None)
              for row in prod]
    supplemental = [{"id": row["id"], "desk": row["desk"]}
                    for row in typed]
    try:
        validate_manuscript(manuscript, chosen, supplemental=supplemental)
    except (ValueError, KeyError, TypeError) as exc:
        raise PrivateMixedManuscriptError(
            "Sunday manuscript prose/citation validation failed") from exc
    if not typed:
        need("editorial_focus" not in manuscript,
             "unrecognized non-typed focus field")
    cited, by_section = set(), {}
    for field in CITED_FIELDS:
        production = list(manuscript["citations"][field])
        research = list(manuscript["supplemental_citations"][field]) if typed else []
        by_section[field] = {
            "production_record_ids": production,
            "private_research_ids": research,
        }
        cited.update(production)
        cited.update(research)
    cited_desks = sorted({row["desk"] for row in rows if row["id"] in cited})
    need(len(cited_desks) >= 2,
         "fewer than two selected desks are actually represented in citations")
    return {
        "schema": SCHEMA,
        "week_ending": choice["week_ending"],
        "theme_slug": choice["theme_slug"],
        "owner_approved_focus_sha256":
            hashlib.sha256(choice["approved_focus"].encode("utf-8")).hexdigest(),
        "owner_choice_hmac_sha256": signed_choice["hmac_sha256"],
        "owner_model_request_hmac_sha256": choice["owner_model_run_hmac_sha256"],
        "reviewed_synopsis_packet_sha256":
            choice["reviewed_synopsis_packet_sha256"],
        "manuscript_sha256": hashlib.sha256(draft_bytes).hexdigest(),
        "selected_source_ids": list(choice["source_ids"]),
        "actually_cited_source_ids": [ident for ident in choice["source_ids"]
                                      if ident in cited],
        "selected_but_not_cited_ids": [ident for ident in choice["source_ids"]
                                       if ident not in cited],
        "cited_desks": cited_desks,
        "section_citations": by_section,
        "review_required_for_every_factual_claim": True,
        "mechanical_citation_presence_not_claim_verification": True,
        "source_reuse_rights_not_software_proven": True,
        "private_preview_only": True,
        "manuscript_model_authorized": False,
        "editor_email_authorized": False,
        "publication_authorized": False,
        "production_desk_promotion_authorized": False,
    }


def render_private_mixed_manuscript_review(
        inputs, signed_run, run_key, proposal, signed_choice, choice_key,
        manuscript):
    """Render a PRIVATE in-memory worksheet with citations and original links.

    The human-written draft and external URLs are sensitive editorial text.
    Never place this output in public CI logs, GitHub comments or artifacts.
    """
    audit = validate_private_mixed_manuscript(
        inputs, signed_run, run_key, proposal, signed_choice, choice_key,
        manuscript)
    choice, sources = _preflight(
        inputs, signed_run, run_key, proposal, signed_choice, choice_key)
    # Defend against caller state mutation between two independent preflights.
    need(audit["owner_choice_hmac_sha256"] == signed_choice["hmac_sha256"]
         and audit["selected_source_ids"] == choice["source_ids"],
         "source/choice changed while preparing private review")
    lines = [
        PACKET_HEADER,
        "UNNUMBERED PRIVATE DRAFT — NOT APPROVED, SENT OR PUBLISHED",
        "Reporting week ending: " + choice["week_ending"],
        "Editor-selected thematic focus: " + one_line(choice["approved_focus"]),
        "Owner signed focus SHA-256: " + audit["owner_choice_hmac_sha256"],
        "Draft bytes SHA-256: " + audit["manuscript_sha256"],
        "Source use counts are mechanical, not fact checks or reuse permissions.",
        "No official publisher article body has been supplied to this worksheet.",
        "",
        "=== PRIVATE MANUSCRIPT — FOR HUMAN ORIGINAL-SOURCE REVIEW ===",
    ]
    headings = [
        ("title", "WORKING TITLE"), ("dek", "DEK"),
        ("development", "CONCRETE DEVELOPMENT"),
        ("opening_note", "OPENING NOTE"),
        ("what_stood_out", "WHAT STOOD OUT"),
        ("why_it_matters", "WHY IT MATTERS"),
        ("what_was_routine", "WHAT WAS ROUTINE"),
        ("what_im_watching_next", "WHAT TO WATCH NEXT"),
        ("cross_desk_comparison", "CROSS-DESK COMPARISON"),
        ("editorial_questions", "UNRESOLVED EDITORIAL QUESTIONS"),
    ]
    for key, heading in headings:
        lines.extend(("", "## " + heading, manuscript[key]))
        if key in CITED_FIELDS:
            use = audit["section_citations"][key]
            lines.append("PRODUCTION RECORD IDS: " + ", ".join(
                str(x) for x in use["production_record_ids"]))
            lines.append("TYPED RESEARCH IDS: " + ", ".join(
                use["private_research_ids"]))
    lines.extend((
        "", "=== IMMUTABLE REVIEW SOURCES — ORIGINAL LINKS ===",
        "Research IDs below remain private; they are not production archive records.",
    ))
    use = set(audit["actually_cited_source_ids"])
    for row in sources:
        ident = row["id"]
        lane = "production record" if type(ident) is int else "private research"
        lines.extend((
            "", one_line(ident) + " | " + lane + " | " + one_line(row["desk"]),
            "Date: " + one_line(row["published_date"]),
            "Issuer: " + one_line(row["publisher"]),
            "Original title: " + one_line(row["title_original"]),
            "Official source: " + one_line(row["publisher_url"]),
            "Used in draft: " + ("YES" if ident in use else "NO"),
            "Human original-language, rights and factual interpretation review still required.",
        ))
    lines.extend((
        "", "=== PRE-EDITORIAL CHECKS — NOT AUTOMATICALLY SATISFIED ===",
        "Check every factual claim against original issuer editions and events.",
        "Separately assess attribution, translation, reuse permission and contradictions.",
        "Recheck whether the regional thesis follows from the evidence.",
        "No Dylan delivery, issue numbering, site publication or AI invocation permitted.",
        "END OF PRIVATE UNAPPROVED MANUSCRIPT WORKSHEET",
    ))
    output = "\n".join(lines)
    need(len(output.encode("utf-8")) <= MAX_PACKET_BYTES,
         "private review packet exceeds safe bound")
    return output
