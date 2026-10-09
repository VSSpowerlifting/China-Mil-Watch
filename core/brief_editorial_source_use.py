"""Private Sunday manuscript citation-use receipt, never source approval.

A source can be offered to a model without being cited in the generated
article. Publication of an original official record, later source verification,
and editor approval are separate activities. This module counts citation
*sections* and never infers factual accuracy, comprehensive collection,
institutional intent, or that every cited paragraph is actually supported.
"""
from __future__ import annotations

SOURCE_FIELDS = (
    "development", "opening_note", "what_stood_out", "why_it_matters",
    "what_was_routine", "what_im_watching_next", "cross_desk_comparison",
)


class SourceUseError(ValueError):
    """Source identity, section citation or type mismatch."""


def summarize_source_use(manuscript, production_trail, research=()):
    """Return source-ID counts only, including explicit unused research items.

    The return value contains NO body text, translations, official URL,
    summary, model response or editorial note. External research never
    masquerades as a production record ID. Each source is counted once per
    distinct manuscript section where it appears.
    """
    if not isinstance(manuscript, dict):
        raise SourceUseError("a structured manuscript is required")
    if not isinstance(production_trail, (list, tuple)):
        raise SourceUseError("production source trail is not a list")
    if not isinstance(research, (list, tuple)):
        raise SourceUseError("research evidence is not a list")

    prod = {}
    for source in production_trail:
        if not isinstance(source, dict):
            raise SourceUseError("malformed production source")
        ident, desk = source.get("record_id"), source.get("desk")
        if type(ident) is not int or ident <= 0 or not isinstance(desk, str) or not desk:
            raise SourceUseError("invalid production identity or desk")
        if ident in prod:
            raise SourceUseError("duplicate production record ID")
        prod[ident] = desk

    external = {}
    for source in research:
        if not isinstance(source, dict):
            raise SourceUseError("malformed source-linked research")
        ident, desk = source.get("id"), source.get("desk")
        if (not isinstance(ident, str) or not ident or ident.isdecimal()
                or not isinstance(desk, str) or desk not in ("japan", "vietnam")):
            raise SourceUseError("invalid typed Japan/Vietnam research identity")
        if ident in external:
            raise SourceUseError("duplicate research source ID")
        if source.get("status") != "unapproved-source-linked-editorial-candidate":
            raise SourceUseError("research must remain unapproved")
        external[ident] = desk

    # The editor's full production source trail is not the model's bounded
    # prompt. Only the composer, after validation, attaches this private
    # exact-input roster. Missing metadata is UNATTESTED, never imputed from
    # the much larger editorial appendix.
    model_offered = None
    if "_model_offered_production_ids" in manuscript:
        roster = manuscript["_model_offered_production_ids"]
        if (not isinstance(roster, list)
                or not all(type(ident) is int and ident in prod for ident in roster)
                or len(set(roster)) != len(roster) or not roster):
            raise SourceUseError("invalid exact model-offered production roster")
        model_offered = set(roster)

    citations = manuscript.get("citations")
    extra_citations = manuscript.get("supplemental_citations")
    if (not isinstance(citations, dict) or set(citations) != set(SOURCE_FIELDS)):
        raise SourceUseError("manuscript lacks complete numeric citations")
    if external:
        if (not isinstance(extra_citations, dict) or
                set(extra_citations) != set(SOURCE_FIELDS)):
            raise SourceUseError("missing exact external source citation sections")
    elif extra_citations is not None:
        raise SourceUseError("unexpected research citations with no source packet")

    by_prod, by_external = {}, {}
    for field in SOURCE_FIELDS:
        ids = citations[field]
        eids = extra_citations[field] if external else []
        if (not isinstance(ids, list) or
                not all(type(ident) is int and ident in prod for ident in ids) or
                len(ids) != len(set(ids))):
            raise SourceUseError("unknown/duplicate production citation")
        if (not isinstance(eids, list) or
                not all(isinstance(ident, str) and ident in external for ident in eids) or
                len(eids) != len(set(eids))):
            raise SourceUseError("unknown/duplicate typed research citation")
        if not ids and not eids:
            raise SourceUseError("factual manuscript section has no source citations")
        for ident in ids:
            by_prod.setdefault(ident, []).append(field)
        for ident in eids:
            by_external.setdefault(ident, []).append(field)

    if model_offered is not None and not set(by_prod).issubset(model_offered):
        raise SourceUseError("production citation not in the model-offered roster")

    def counts(ids, cited, desks):
        result = {}
        for desk in sorted(set(desks.values())):
            offered = sorted((ident for ident, d in desks.items() if d == desk))
            used = sorted(ident for ident in offered if ident in cited)
            omitted = sorted(ident for ident in offered if ident not in cited)
            result[desk] = {
                "offered": len(offered),
                "cited": len(used),
                "unused_source_ids": omitted,
            }
        return result

    production_stats = counts(prod.keys(), by_prod, prod)
    for desk, item in production_stats.items():
        item["appendix_listed"] = item.pop("offered")
        item["model_offered"] = (
            sum(prod[ident] == desk for ident in model_offered)
            if model_offered is not None else None
        )

    return {
        "schema": "ipr-private-manuscript-source-use/1",
        "production_by_desk": production_stats,
        "research_by_desk": counts(external.keys(), by_external, external),
        "production_used": [
            {"record_id": ident, "desk": prod[ident],
             "sections": sorted(by_prod[ident])}
            for ident in sorted(by_prod)
        ],
        "research_used": [
            {"id": ident, "desk": external[ident],
             "sections": sorted(by_external[ident])}
            for ident in sorted(by_external)
        ],
        "production_sources_are_original_corpus": True,
        "external_research_is_not_production": True,
        "source_accuracy_or_rights_verified": False,
        "claim_level_support_verified": False,
        "coherent_theme_human_approved": False,
        "editorial_or_publication_approval": False,
    }


def format_private_source_use(manuscript, production_trail, research=()):
    """Human-readable triage lines to include in the PRIVATE editor worksheet."""
    audit = summarize_source_use(manuscript, production_trail, research)
    out = [
        "=== MANUSCRIPT SOURCE USE — EDITORIAL TRIAGE ONLY ===",
        "These counts describe citations supplied by the model, NOT verified claims.",
        "The editor's production appendix may include records never shown to the AI.",
        "Offered means shown to the model/editor; cited means used in at least one",
        "manuscript section. An omitted source is NOT evidence of issuer silence.",
        "Source text, paraphrases, translations and source reuse require review.",
        "",
        "PRODUCTION RECORD USE BY DESK:",
    ]
    for desk, item in audit["production_by_desk"].items():
        roster_count = (str(item["model_offered"]) if item["model_offered"] is not None
                        else "UNATTESTED")
        out.append("- {}: {} in human appendix; {} actually model-offered; {} cited.".format(
            desk, item["appendix_listed"], roster_count, item["cited"]))
    out.append("")
    out.append("NON-PRODUCTION JAPAN/VIETNAM RESEARCH USE:")
    for desk in ("japan", "vietnam"):
        item = audit["research_by_desk"].get(
            desk, {"offered": 0, "cited": 0, "unused_source_ids": []})
        out.append("- {}: {} offered; {} cited in manuscript.".format(
            desk, item["offered"], item["cited"]))
        if item["unused_source_ids"]:
            out.append("  Uncited research IDs: " +
                       ", ".join(item["unused_source_ids"]))
        if item["offered"] and not item["cited"]:
            out.append("  NOT INCORPORATED: do not describe this desk as contributing")
    out.append("")
    out.append("ACTUAL NON-PRODUCTION RESEARCH CITATIONS (by manuscript section):")
    for item in audit["research_used"]:
        out.append("- {} ({}): {}".format(
            item["id"], item["desk"], ", ".join(item["sections"])))
    if not audit["research_used"]:
        out.append("- None. The generated draft used production sources only.")
    out.extend((
        "",
        "GATE: This audit does not prove factual support, thematic coherence,",
        "human source review, reuse rights, approval or editorial delivery.",
        "END OF MANUSCRIPT SOURCE USE",
    ))
    return out
