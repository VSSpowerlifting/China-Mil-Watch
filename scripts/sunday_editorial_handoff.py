"""Build an unnumbered Indo-Pacific Record editorial worksheet, optionally email it.

The scaffold must come from scripts/author_brief.py. This script NEVER authors
analytical claims, changes the corpus, opens a PR, approves or publishes briefs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path

from scripts.sunday_pilot_owner_review import require_owner_review, require_exact_reviewed_manuscript


EDIT_SECTIONS = (
    ("WORKING TITLE", "One concrete development, not a regional roundup"),
    ("DEK", "One or two sentences; scope claims to the records"),
    ("DEVELOPMENT AND SOURCE RECORD IDS", "Name the development and cite its record IDs"),
    ("OPENING NOTE", "Open with the concrete development"),
    ("WHAT STOOD OUT", "Attribute details to specific source records"),
    ("WHY IT MATTERS", "Separate observations from interpretation"),
    ("WHAT WAS ROUTINE", "Be willing to say when little changed"),
    ("TERM TO KNOW", "Give the term, original language and cautious explanation"),
    ("WHAT I'M WATCHING NEXT", "A specific question or observable indicator"),
    ("CROSS-DESK COMPARISONS AND RECORD IDS", "Do not infer coordination from timing"),
    ("EDITORIAL QUESTIONS FOR BEN", "Unverified wording, corrections, uncertainties"),
)


def one_line(value):
    """Prevent source-supplied line breaks from masquerading as packet headings."""
    return " ".join(str(value or "").split())


def render_packet(sidecar, *, manuscript=None, as_of=None,
                  vietnam_candidates=(), research_evidence=()):
    if sidecar.get("editorial_status") != "draft" or sidecar.get("issue_number") is not None:
        raise ValueError("only unnumbered, unapproved draft scaffolds may be emailed")
    week_end = date.fromisoformat(sidecar["week_ending"])
    if week_end.weekday() != 5:
        raise ValueError("the Briefs editorial week must end on Saturday")
    desks = sidecar["desks"]
    trail = sidecar["source_trail"]
    if (vietnam_candidates or research_evidence) and not as_of:
        raise ValueError("research evidence requires an explicit reporting cutoff")
    if research_evidence and vietnam_candidates:
        raise ValueError("research evidence must be synthesized once, not duplicated as supplements")
    if vietnam_candidates and any(row["review_status"] !=
                                  "requires_independent_human_review"
                                  for row in vietnam_candidates):
        raise ValueError("candidate incorrectly claims human review")
    represented = {entry["desk"] for entry in trail}
    if not trail:
        raise ValueError("no source candidates in this week; refuse empty editorial email")
    coverage_warning = (
        "COVERAGE WARNING: fewer than two desks have source candidates. "
        "This worksheet is NOT eligible for an ordinary cross-desk Brief; "
        "a single-desk Brief would require Ben's separately recorded exception."
        if len(represented.intersection(desks)) < 2 else
        "Coverage: candidate records are present from at least two desks; not editorial approval."
    )
    lines = [
        "INDO-PACIFIC RECORD | BRIEFS EDITORIAL WORKSHEET",
        "Packet: IPR-" + week_end.isoformat(),
        "Week: " + one_line(sidecar["week_start"]) + " through " + week_end.isoformat(),
        "Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED",
        (("AS-OF CUT-OFF: " + as_of +
          " (SATURDAY COMPLETE; CAPTURE COMPLETENESS UNVERIFIED)"
          if as_of == sidecar["week_ending"] else
          "AS-OF CUT-OFF: " + as_of +
          " (FRIDAY PROVISIONAL; SATURDAY NOT INCLUDED)")
         if as_of else "Complete-week editorial worksheet; still unapproved"),
        coverage_warning,
        "Desks: " + ", ".join(desks),
        "",
        "DYLAN: Edit the writing sections below and REPLY with this .txt attached.",
        "Keep the source appendix intact. Give record IDs for factual claims.",
        "Do not guess at translations, infer coordination, or assign an issue number.",
        "Source listings are candidates, not endorsed editorial selections.",
        ("Private model research: {} source-linked Japan/Vietnam candidate(s) "
         "available for drafting; all require independent human verification. "
         "They are NOT production records, desk promotion, or publication approval."
         .format(len(research_evidence)) if research_evidence else
         ("Vietnam: {} isolated shadow-source link(s) require independent review; "
          "NOT model evidence, NOT production record IDs, NOT live desk coverage."
          .format(len(vietnam_candidates)) if vietnam_candidates else
          "Vietnam: no separately offered shadow-source candidates.")),
        "Ben retains final editorial, approval, numbering and publication authority.",
        "",
        "=== EDITABLE MANUSCRIPT ===",
    ]
    if manuscript is None:
        for name, instruction in EDIT_SECTIONS:
            lines.extend(("\n## " + name, "[" + instruction + "]", ""))
    else:
        # Only mechanically validated model output is interpolated here.
        from scripts.sunday_briefs_auto_writer import CITED_FIELDS, validate_prose_boundaries
        validate_prose_boundaries(manuscript)
        if research_evidence and not manuscript.get("editorial_focus"):
            raise ValueError("research-assisted manuscript has no single editorial focus")
        if research_evidence:
            lines.extend(("\n## EDITORIAL FOCUS", one_line(manuscript["editorial_focus"]), ""))
        # The caller validated against the full-text evidence selection;
        # do not silently convert the article into a release-ready sidecar.
        headings = (
            ("title", "WORKING TITLE"),
            ("dek", "DEK"),
            ("development", "CONCRETE DEVELOPMENT"),
            ("opening_note", "OPENING NOTE"),
            ("what_stood_out", "WHAT STOOD OUT"),
            ("why_it_matters", "WHY IT MATTERS"),
            ("what_was_routine", "WHAT WAS ROUTINE"),
            ("what_im_watching_next", "WHAT I'M WATCHING NEXT"),
            ("cross_desk_comparison", "CROSS-DESK COMPARISON"),
            ("editorial_questions", "EDITORIAL QUESTIONS / SATURDAY FOLLOW-UP"),
        )
        for key, heading in headings:
            lines.extend(("\n## " + heading, manuscript[key], ""))
            if key in CITED_FIELDS:
                production_ids = manuscript["citations"][key]
                external_ids = (manuscript["supplemental_citations"][key]
                                if research_evidence else [])
                if production_ids:
                    lines.append("SOURCE RECORD IDS: " + ", ".join(
                        str(i) for i in production_ids))
                if external_ids:
                    lines.append("EXTERNAL SOURCE IDS: " + ", ".join(external_ids))
                lines.append("")
    lines.extend((
        "=== SOURCE APPENDIX — DO NOT EDIT ===",
        "The appendix comes from the tracked production corpus; URLs and titles",
        "are pointers for verification, not full-text evidence or checked quotations.",
        "",
        "COVERAGE SNAPSHOT (per desk; do not infer institutional silence):",
    ))
    if manuscript is not None:
        # This source-use receipt is part of the IMMUTABLE editor appendix.
        # Dylan edits prose only, not the model's self-reported source use.
        # It never promotes research into a production source or obliges
        # the model to cite unrelated Japan/Vietnam evidence.
        from core.brief_editorial_source_use import format_private_source_use
        lines.extend(format_private_source_use(
            manuscript, trail, research_evidence))
        lines.append("")
    for desk in desks:
        stats = sidecar.get("coverage_by_desk", {}).get(desk, {})
        screened = stats.get("by_screening", {})
        lines.append(
            "- {}: {} stored records; {} offered candidates; screening: {}".format(
                desk, stats.get("records", 0),
                sum(1 for record in trail if record["desk"] == desk),
                ", ".join("{}={}".format(k, v) for k, v in sorted(screened.items())) or "none"))
    lines.append("")
    for entry in trail:
        lines.extend((
            "Record {} | {} | {} | {}".format(
                entry["record_id"], one_line(entry["desk"]),
                one_line(entry["date"]), one_line(entry["source"])),
            "Title: " + one_line(entry["title"]),
            "Original (" + one_line(entry["lang"]) + "): " + one_line(entry["title_original"]),
            "URL: " + one_line(entry["url"]),
            "Screening: " + one_line(entry["screening"]),
            "",
        ))
    lines.append("END OF SOURCE APPENDIX")
    if research_evidence:
        lines.extend((
            "",
            "=== MODEL-AVAILABLE OFFICIAL SOURCE RESEARCH — UNAPPROVED ===",
            "Private editorial candidate evidence, not IPR archived record IDs.",
            "Sources are publisher-hosted; original wording must be checked by",
            "Dylan and Ben before any source-backed claim enters a published Brief.",
            "Model inputs were cautious synopses, NOT article bodies or approved quotes.",
            "",
        ))
        for item in research_evidence:
            lines.extend((
                "External source {} | {} | {}".format(
                    one_line(item["id"]), one_line(item["desk"]),
                    one_line(item["published_date"])),
                "Original (" + one_line(item["language"]) + "): " +
                    one_line(item["title_original"]),
                "Publisher: " + one_line(item["source_name"]),
                "URL: " + one_line(item["source_url"]),
                "Evidence class: " + one_line(item["source_kind"]),
                "Pinned shadow commit: " + one_line(item["state_commit"] or "not archived"),
                "Version/content SHA-256: " + one_line(item["source_content_sha256"] or "not archived"),
                "Hash rule: " + one_line(item["hash_rule"] or "not archived"),
                "Research synopsis (not approved): " + one_line(item["summary"]),
                "Required source checks: " + one_line("; ".join(item["caveats"])),
                "",
            ))
        lines.append("END OF MODEL-AVAILABLE OFFICIAL SOURCE RESEARCH")
    if vietnam_candidates:
        lines.extend((
            "",
            "=== VIETNAM SHADOW CANDIDATES — HUMAN REVIEW REQUIRED ===",
            "NOT production record IDs, NOT model input, NOT reviewed or approved.",
            "These official-source pointers are for Dylan's independent source",
            "inspection. Cite the original publisher URL only after reviewing",
            "the original-language contents and confirming each factual claim.",
            "The editorial and publishing gates remain unchanged.",
            "",
        ))
        for item in vietnam_candidates:
            lines.extend((
                "Candidate identity: " + one_line(item["source_identity"]),
                "Published: " + one_line(item["published_date"]),
                "Publisher: " + one_line(item["source_name"]),
                "Original (vi): " + one_line(item["original_title"]),
                "URL: " + one_line(item["canonical_url"]),
                "Pinned source commit: " + one_line(item["state_commit"]),
                "Current content SHA-256: " + one_line(item["content_sha256"]),
                "Editorial question (not a verified claim): " + one_line(item["editorial_angle"]),
                "Review status: REQUIRES INDEPENDENT HUMAN REVIEW",
                "",
            ))
        lines.append("END OF VIETNAM SHADOW CANDIDATES")
    lines.extend(("END OF UNAPPROVED WORKSHEET", ""))
    return "\n".join(lines)


def single_address(value, name):
    if not value or "\r" in value or "\n" in value:
        raise ValueError(name + " must contain one valid email address")
    parsed = getaddresses([value])
    if len(parsed) != 1 or "@" not in parsed[0][1] or parsed[0][1].count("@") != 1:
        raise ValueError(name + " must contain one valid email address")
    return parsed[0][1]


def send_packet(path, week_ending, *, provisional=False, full_week=False,
                preview_to_owner=False):
    require_owner_review(
        week_ending=week_ending, sending=not preview_to_owner,
        approved_week=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_WEEK", ""),
    )
    # Fingerprint the SAME immutable bytes ultimately attached to the email.
    # A newly generated Sunday draft is not the file the owner reviewed.
    original_attachment = path.read_bytes()
    require_exact_reviewed_manuscript(
        week_ending=week_ending, sending=not preview_to_owner,
        manuscript_bytes=original_attachment,
        approved_sha256=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_SHA256", ""),
    )
    editor = single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO")
    if preview_to_owner:
        recipient = single_address(os.environ.get("IPR_PREVIEW_TO", ""), "IPR_PREVIEW_TO")
        if recipient.casefold() == editor.casefold():
            raise ValueError("preview recipient must differ from Dylan/editor address")
    else:
        recipient = editor
    sender = single_address(os.environ.get("IPR_SMTP_USER", ""), "IPR_SMTP_USER")
    password = "".join(os.environ.get("IPR_SMTP_APP_PASSWORD", "").split())
    if len(password) != 16 or not password.isascii() or not password.isalnum():
        raise ValueError("IPR_SMTP_APP_PASSWORD must be a Google-generated 16-character app password")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = sender
    if preview_to_owner:
        if not full_week:
            raise ValueError("owner previews require the complete Saturday-ending week")
        message["Subject"] = "IPR Briefs | OWNER-ONLY UNSENT EDITORIAL PREVIEW | {}".format(week_ending)
        message.set_content(
            "Private owner-only preview of the unapproved Sunday IPR Brief.\n\n"
            "This attachment was NOT delivered to Dylan. Inspect the generated "
            "single-theme manuscript, all numeric production record citations, "
            "Japan/Vietnam typed official-source references, their source-language "
            "meaning and any unsupported claims. You must separately authorize "
            "editor delivery after independent source verification.\n\n"
            "Do not publish, number or forward as an approved Brief.\n\n"
            "Exact attached manuscript SHA-256: "
            + hashlib.sha256(original_attachment).hexdigest() + "\n"
        )
    elif full_week:
        # The exact immutable TXT was already checked against the owner's
        # reviewed SHA above and is attached unchanged below. Present ONLY
        # the editorial prose in the message body so Dylan needn't edit
        # provenance hashes, source IDs, source appendices, or a .txt envelope.
        from scripts.sunday_editor_readable import prose_only_html, prose_only_text
        original_text = original_attachment.decode("utf-8")
        message["Subject"] = "IPR Briefs | week ending {} | Sunday draft for language edits".format(week_ending)
        message.set_content(prose_only_text(original_text))
        message.add_alternative(prose_only_html(original_text), subtype="html")
    else:
        message["Subject"] = "IPR Briefs | week ending {} | provisional editor draft".format(week_ending)
        message.set_content(
            "Hi Dylan,\n\nAttached is the provisional AI-assisted Indo-Pacific Record Brief "
            "with a source-record appendix and section-level citation IDs. "
            "The Friday draft is not the complete Saturday-ending week, so please "
            "check the citations and leave room for Saturday developments. "
            "Please edit the prose, flag questionable claims, preserve the source appendix, "
            "and reply with the edited .txt attached within 48 hours.\n\n"
            "This text is not approved or numbered for publication. Ben will "
            "verify the full-week sources and authorize any final publication.\n"
        )
    message.add_attachment(
        original_attachment, maintype="text", subtype="plain", filename=path.name
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--send", action="store_true",
                        help="send to Dylan only when explicitly authorized")
    parser.add_argument("--preview-to-owner", action="store_true",
                        help="explicit private owner-only preview; never send to Dylan")
    parser.add_argument("--write-automatic", action="store_true",
                        help="compose an AI-assisted provisional manuscript from source bodies")
    parser.add_argument("--as-of", help="Friday or Saturday source cutoff (YYYY-MM-DD)")
    parser.add_argument("--full-week", action="store_true",
                        help="Sunday full-week draft from records through Saturday")
    parser.add_argument("--include-research", action="store_true",
                        help="privately synthesize checked-format Japan/Vietnam official source notes")
    parser.add_argument("--research-packet", type=Path,
                        help="optional exact-week temporary private JSON from a separately validated shadow exporter")
    args = parser.parse_args(argv)
    if args.send and args.preview_to_owner:
        parser.error("owner-only preview and Dylan delivery are mutually exclusive")
    if args.preview_to_owner and (not args.write_automatic or not args.full_week):
        parser.error("owner-only preview requires automatic full-week manuscript")
    sidecar = json.loads(args.sidecar.read_text(encoding="utf-8"))
    # Require exact-week owner release BEFORE any source expansion, model
    # usage, attachment write, or possible SMTP call. Rechecked at send_packet.
    require_owner_review(
        week_ending=sidecar["week_ending"], sending=args.send,
        approved_week=os.environ.get("IPR_SUNDAY_OWNER_REVIEWED_WEEK", ""),
    )
    if args.full_week and (not args.write_automatic
                           or args.as_of != sidecar["week_ending"]):
        parser.error("--full-week requires Saturday --as-of and --write-automatic")
    if args.include_research and not (args.full_week and args.write_automatic):
        parser.error("--include-research is private Sunday automatic drafting only")
    if args.research_packet and not args.include_research:
        parser.error("--research-packet requires private --include-research")
    research = []
    if args.include_research:
        from core.brief_editorial_evidence import load_editorial_evidence
        if args.research_packet and (
                args.research_packet.name != sidecar["week_ending"] + ".json"):
            parser.error("--research-packet basename must match exact reporting Saturday")
        if args.research_packet and not args.research_packet.is_file():
            raise ValueError("explicit private research packet missing; refuse silent fallback")
        research_dir = (args.research_packet.parent if args.research_packet else None)
        research = (load_editorial_evidence(sidecar["week_ending"], args.as_of,
                                            directory=research_dir)
                    if research_dir is not None else
                    load_editorial_evidence(sidecar["week_ending"], args.as_of))
    manuscript = None
    if args.write_automatic:
        if not args.as_of:
            parser.error("--write-automatic requires --as-of source cutoff")
        from scripts.sunday_briefs_auto_writer import compose
        # Fail closed before file creation/email if any evidence or model check fails.
        manuscript = (compose(sidecar, args.as_of, supplemental=research)
                      if research else compose(sidecar, args.as_of))
    # These unapproved metadata pointers appear only in the PRIVATE human
    # handoff after the immutable production source appendix. Never send them
    # to the model or count them as live, production-backed desk evidence.
    vietnam_candidates = []
    if args.as_of and not research:
        from core.vietnam_briefs_handoff import load_candidates
        vietnam_candidates = load_candidates(sidecar["week_ending"], args.as_of)
    text = render_packet(sidecar, manuscript=manuscript, as_of=args.as_of,
                         vietnam_candidates=vietnam_candidates,
                         research_evidence=research)
    args.out.write_text(text, encoding="utf-8")
    print("Prepared unapproved {}: {} ({} production records; {} Vietnam shadow links requiring human review)".format(
        "machine-drafted editorial manuscript" if manuscript is not None else "editorial worksheet",
        args.out.name, len(sidecar["source_trail"]), len(vietnam_candidates)))
    if args.send or args.preview_to_owner:
        send_packet(args.out, sidecar["week_ending"],
                    provisional=args.write_automatic, full_week=args.full_week,
                    preview_to_owner=args.preview_to_owner)
        print("OWNER-ONLY PREVIEW emailed; Dylan was not contacted."
              if args.preview_to_owner else
              "Editorial worksheet delivered to configured editor.")
    else:
        print("Email not enabled: no delivery occurred.")


if __name__ == "__main__":
    main()
