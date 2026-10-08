"""Build an unnumbered Indo-Pacific Record editorial worksheet, optionally email it.

The scaffold must come from scripts/author_brief.py. This script NEVER authors
analytical claims, changes the corpus, opens a PR, approves or publishes briefs.
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path


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
                  vietnam_candidates=(), japan_sources=(), indonesia_sources=()):
    if sidecar.get("editorial_status") != "draft" or sidecar.get("issue_number") is not None:
        raise ValueError("only unnumbered, unapproved draft scaffolds may be emailed")
    week_end = date.fromisoformat(sidecar["week_ending"])
    if week_end.weekday() != 5:
        raise ValueError("the Briefs editorial week must end on Saturday")
    desks = sidecar["desks"]
    trail = sidecar["source_trail"]
    if vietnam_candidates and not as_of:
        raise ValueError("Vietnam shadow candidates require a Friday as-of cutoff")
    if (japan_sources or indonesia_sources) and (not as_of or manuscript is None):
        raise ValueError("supplemental AI research requires an automatic provisional manuscript")
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
        ("AS-OF CUT-OFF: " + as_of + " (FRIDAY PROVISIONAL; SATURDAY NOT INCLUDED)"
         if as_of else "Complete-week editorial worksheet; still unapproved"),
        coverage_warning,
        "Desks: " + ", ".join(desks),
        ("Japan: {} external research source(s) offered to the AI writer; "
         "NOT production desk coverage or approved article facts."
         .format(len(japan_sources)) if japan_sources else
         "Japan: no external research submitted to the AI writer."),
        ("Indonesia: {} source-labeled shadow research item(s) offered to the AI writer; "
         "NOT production desk coverage or approved claims."
         .format(len(indonesia_sources)) if indonesia_sources else
         "Indonesia: no source-labeled shadow evidence offered to the AI writer."),
        "",
        "DYLAN: Edit the writing sections below and REPLY with this .txt attached.",
        "Keep the source appendix intact. Give record IDs for factual claims.",
        "Do not guess at translations, infer coordination, or assign an issue number.",
        "Source listings are candidates, not endorsed editorial selections.",
        ("Vietnam: {} isolated shadow-source link(s) require independent review; "
         "NOT model evidence, NOT production record IDs, NOT live desk coverage."
         .format(len(vietnam_candidates)) if vietnam_candidates else
         "Vietnam: no separately offered shadow-source candidates."),
        "Ben retains final editorial, approval, numbering and publication authority.",
        "",
        "=== EDITABLE MANUSCRIPT ===",
    ]
    if manuscript is None:
        for name, instruction in EDIT_SECTIONS:
            lines.extend(("\n## " + name, "[" + instruction + "]", ""))
    else:
        # Only mechanically validated model output is interpolated here.
        from scripts.weekly_briefs_auto_writer import CITED_FIELDS, validate_manuscript
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
                lines.append("SOURCE RECORD IDS: " + ", ".join(
                    str(i) for i in manuscript["citations"][key]))
                if japan_sources or indonesia_sources:
                    external = manuscript["supplemental_citations"][key]
                    if external:
                        label = ("EXTERNAL JAPAN SOURCE IDS (NOT IPR RECORD IDS): "
                                 if not indonesia_sources else
                                 "EXTERNAL NONPRODUCTION SOURCE IDS (NOT IPR RECORD IDS): ")
                        lines.append(label + ", ".join(external))
                lines.append("")
        if japan_sources or indonesia_sources:
            lines.extend((
                ("\n## AI-SYNTHESIZED JAPAN EDITORIAL CONCEPT (PROVISIONAL)"
                 if not indonesia_sources else
                 "\n## AI-SYNTHESIZED REGIONAL EDITORIAL CONCEPT (PROVISIONAL)"),
                manuscript["supplemental_angle"],
                ("EXTERNAL JAPAN SOURCE IDS (NOT IPR RECORD IDS): "
                 if not indonesia_sources else
                 "EXTERNAL NONPRODUCTION SOURCE IDS (NOT IPR RECORD IDS): ") +
                    ", ".join(manuscript["supplemental_angle_citations"]),
                "This is an optional research angle, not a separate approved brief.",
                "",
            ))
    lines.extend((
        "=== SOURCE APPENDIX — DO NOT EDIT ===",
        "The appendix comes from the tracked production corpus; URLs and titles",
        "are pointers for verification, not full-text evidence or checked quotations.",
        "",
        "COVERAGE SNAPSHOT (per desk; do not infer institutional silence):",
    ))
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
    if japan_sources:
        lines.extend((
            "",
            "=== JAPAN EDITORIAL RESEARCH APPENDIX — NOT PRODUCTION ===",
            "These are source-labeled analyst paraphrases of official MOD pages.",
            "They were shown to Claude for provisional synthesis, but are",
            "NOT archived IPR originals, NOT production record IDs, NOT a live desk.",
            "Independent full-source and translation checks remain with the editor.",
            "",
        ))
        for item in japan_sources:
            lines.extend((
                "External ID: " + one_line(item["id"]),
                "Official source: " + one_line(item["issuer"]),
                "Published: " + one_line(item["published_date"]),
                "Title/topic: " + one_line(item["title"]),
                "URL: " + one_line(item["url"]),
                "Representation: " + one_line(item["evidence_representation"]),
                "Source status: " + one_line(item["status"]),
                "Claims are provisional; review full original before publication.",
                "",
            ))
        lines.append("END OF JAPAN NON-PRODUCTION APPENDIX")
    if indonesia_sources:
        lines.extend((
            "",
            "=== INDONESIA SOURCE RESEARCH — NOT PRODUCTION ===",
            "Original-language Indonesian ministry claims were offered as",
            "attributed analyst paraphrases, never as production record IDs.",
            "The archived shadow bytes and complete source must be checked",
            "independently before any human-approved editorial use.",
            "",
        ))
        for item in indonesia_sources:
            lines.extend((
                "External ID: " + one_line(item["id"]),
                "Issuer: " + one_line(item["issuer"]),
                "Published: " + one_line(item["published_date"]),
                "Title: " + one_line(item["title"]),
                "Source URL: " + one_line(item["url"]),
                "Representation: " + one_line(item["evidence_representation"]),
                "Source status: " + one_line(item["status"]),
                "Review: NO human approval; source use and translations remain unchecked.",
                "",
            ))
        lines.append("END OF INDONESIA NON-PRODUCTION APPENDIX")
    if vietnam_candidates:
        lines.extend((
            "",
            "=== VIETNAM SHADOW CANDIDATES — HUMAN REVIEW REQUIRED ==="
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


def send_packet(path, week_ending, *, provisional=False):
    recipient = single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO")
    sender = single_address(os.environ.get("IPR_SMTP_USER", ""), "IPR_SMTP_USER")
    password = "".join(os.environ.get("IPR_SMTP_APP_PASSWORD", "").split())
    if len(password) != 16 or not password.isascii() or not password.isalnum():
        raise ValueError("IPR_SMTP_APP_PASSWORD must be a Google-generated 16-character app password")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = sender
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
        path.read_bytes(), maintype="text", subtype="plain", filename=path.name
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--send", action="store_true",
                        help="email via explicit SMTP secrets; otherwise write locally only")
    parser.add_argument("--write-automatic", action="store_true",
                        help="compose an AI-assisted provisional manuscript from source bodies")
    parser.add_argument("--as-of", help="Friday cut-off (YYYY-MM-DD), used only for automatic writing")
    parser.add_argument("--use-japan-research", action="store_true",
                        help="offer the exact-week non-production Japan source packet to AI")
    parser.add_argument("--use-indonesia-research", action="store_true",
                        help="offer the exact-week shadow-captured Indonesia source research to AI")
    args = parser.parse_args(argv)
    if (args.use_japan_research or args.use_indonesia_research) and (
            not args.write_automatic or not args.as_of):
        parser.error("supplemental research requires --write-automatic and --as-of")
    sidecar = json.loads(args.sidecar.read_text(encoding="utf-8"))
    manuscript = None
    japan_sources = []
    indonesia_sources = []
    if args.use_japan_research:
        from scripts.japan_weekly_writer_sources import load_japan_writer_sources
        japan_sources = load_japan_writer_sources(
            sidecar["week_ending"], args.as_of)
    if args.use_indonesia_research:
        from scripts.indonesia_weekly_writer_sources import load_indonesia_writer_sources
        indonesia_sources = load_indonesia_writer_sources(
            sidecar["week_ending"], args.as_of)
    if args.write_automatic:
        if not args.as_of:
            parser.error("--write-automatic requires --as-of Friday date")
        from scripts.weekly_briefs_auto_writer import compose
        # Raises on absent full-text evidence, missing API key, API errors or
        # invalid citations. No email or file is produced on these failures.
        supplemental_sources = japan_sources + indonesia_sources
        manuscript = (compose(sidecar, args.as_of, supplemental=supplemental_sources)
                      if supplemental_sources else compose(sidecar, args.as_of))
    # These unapproved metadata pointers appear only in the PRIVATE human
    # handoff after the immutable production source appendix. Never send them
    # to the model or count them as live, production-backed desk evidence.
    vietnam_candidates = []
    if args.as_of:
        from core.vietnam_briefs_handoff import load_candidates
        vietnam_candidates = load_candidates(sidecar["week_ending"], args.as_of)
    text = render_packet(sidecar, manuscript=manuscript, as_of=args.as_of,
                         vietnam_candidates=vietnam_candidates,
                         japan_sources=japan_sources,
                         indonesia_sources=indonesia_sources)
    args.out.write_text(text, encoding="utf-8")
    print("Prepared unapproved {}: {} ({} production records; {} Vietnam shadow links requiring human review; {} Japan research sources; {} Indonesia research sources)".format(
        "machine-drafted editorial manuscript" if manuscript is not None else "editorial worksheet",
        args.out.name, len(sidecar["source_trail"]), len(vietnam_candidates), len(japan_sources), len(indonesia_sources)))
    if args.send:
        send_packet(args.out, sidecar["week_ending"], provisional=args.write_automatic)
        print("Editorial worksheet delivered via configured SMTP account.")
    else:
        print("Email not enabled: no delivery occurred.")


if __name__ == "__main__":
    main()
