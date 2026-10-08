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


def render_packet(sidecar, *, manuscript=None, as_of=None):
    if sidecar.get("editorial_status") != "draft" or sidecar.get("issue_number") is not None:
        raise ValueError("only unnumbered, unapproved draft scaffolds may be emailed")
    week_end = date.fromisoformat(sidecar["week_ending"])
    if week_end.weekday() != 5:
        raise ValueError("the Briefs editorial week must end on Saturday")
    desks = sidecar["desks"]
    trail = sidecar["source_trail"]
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
        (("AS-OF CUT-OFF: " + as_of + " (SATURDAY COMPLETE; CAPTURE COMPLETENESS UNVERIFIED)"
          if as_of == sidecar["week_ending"] else
          "AS-OF CUT-OFF: " + as_of + " (FRIDAY PROVISIONAL; SATURDAY NOT INCLUDED)")
         if as_of else "Complete-week editorial worksheet; still unapproved"),
        coverage_warning,
        "Desks: " + ", ".join(desks),
        "",
        "DYLAN: Edit the writing sections below and REPLY with this .txt attached.",
        "Keep the source appendix intact. Give record IDs for factual claims.",
        "Do not guess at translations, infer coordination, or assign an issue number.",
        "Source listings are candidates, not endorsed editorial selections.",
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
                lines.append("")
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
    lines.extend((
        "END OF SOURCE APPENDIX",
        "END OF UNAPPROVED WORKSHEET",
        "",
    ))
    return "\n".join(lines)


def single_address(value, name):
    if not value or "\r" in value or "\n" in value:
        raise ValueError(name + " must contain one valid email address")
    parsed = getaddresses([value])
    if len(parsed) != 1 or "@" not in parsed[0][1] or parsed[0][1].count("@") != 1:
        raise ValueError(name + " must contain one valid email address")
    return parsed[0][1]


def send_packet(path, week_ending, *, provisional=False, full_week=False):
    recipient = single_address(os.environ.get("IPR_EDITOR_TO", ""), "IPR_EDITOR_TO")
    sender = single_address(os.environ.get("IPR_SMTP_USER", ""), "IPR_SMTP_USER")
    password = "".join(os.environ.get("IPR_SMTP_APP_PASSWORD", "").split())
    if len(password) != 16 or not password.isascii() or not password.isalnum():
        raise ValueError("IPR_SMTP_APP_PASSWORD must be a Google-generated 16-character app password")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Reply-To"] = sender
    if full_week:
        message["Subject"] = (
            "IPR Briefs | week ending {} | Sunday editorial draft".format(week_ending)
        )
        message.set_content(
            "Hi Dylan,\n\nAttached is this week's AI-assisted Indo-Pacific Record "
            "Brief draft, including records dated through Saturday and a source "
            "appendix with section-level citation IDs. It still needs human "
            "fact-checking; the archived source corpus may not be exhaustive.\n\n"
            "Please edit the prose, check each citation, flag weak or uncertain "
            "claims, and preserve the source appendix. Reply to this message "
            "with your edited .txt attached by Monday at 8 p.m. Eastern "
            "so Ben can review it Tuesday. If the deadline is difficult, "
            "reply to let Ben know.\n\n"
            "This is not approved, numbered, or published. Ben retains final "
            "editorial and publication authority.\n"
        )
    else:
        message["Subject"] = (
            "IPR Briefs | week ending {} | provisional editor draft".format(week_ending)
        )
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
    parser.add_argument("--as-of", help="Friday or Saturday cut-off (YYYY-MM-DD), for automatic writing")
    parser.add_argument("--full-week", action="store_true",
                        help="Sunday delivery based on the Saturday-ending week, never Friday provisional")
    args = parser.parse_args(argv)
    sidecar = json.loads(args.sidecar.read_text(encoding="utf-8"))
    if args.full_week and (not args.write_automatic or args.as_of != sidecar["week_ending"]):
        parser.error("--full-week requires --write-automatic and --as-of equal to Saturday week_ending")
    manuscript = None
    if args.write_automatic:
        if not args.as_of:
            parser.error("--write-automatic requires --as-of Friday date")
        from scripts.weekly_briefs_auto_writer import compose
        # Raises on absent full-text evidence, missing API key, API errors or
        # invalid citations. No email or file is produced on these failures.
        manuscript = compose(sidecar, args.as_of)
    text = render_packet(sidecar, manuscript=manuscript, as_of=args.as_of)
    args.out.write_text(text, encoding="utf-8")
    print("Prepared unapproved {}: {} ({} record candidates)".format(
        "machine-drafted editorial manuscript" if manuscript is not None else "editorial worksheet",
        args.out.name, len(sidecar["source_trail"])))
    if args.send:
        send_packet(args.out, sidecar["week_ending"],
                    provisional=args.write_automatic, full_week=args.full_week)
        print("Editorial worksheet delivered via configured SMTP account.")
    else:
        print("Email not enabled: no delivery occurred.")


if __name__ == "__main__":
    main()
