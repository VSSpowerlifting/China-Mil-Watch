"""Render the immutable, approved-for-send worksheet as a clean email for prose editing.

The long original TXT stays attached and its exact SHA review is unchanged.
This is strictly a presentation transform: no source selection, LLM, SMTP,
approval, citations reassignment, publishing, or external HTML dependencies.
"""
from __future__ import annotations

import html
import re

BEGIN = "=== EDITABLE MANUSCRIPT ==="
APPENDIX = "=== SOURCE APPENDIX — DO NOT EDIT ==="
HEADINGS = (
    "WORKING TITLE", "DEK", "CONCRETE DEVELOPMENT", "OPENING NOTE",
    "WHAT STOOD OUT", "WHY IT MATTERS", "WHAT WAS ROUTINE",
    "WHAT I'M WATCHING NEXT", "CROSS-DESK COMPARISON",
)
INTERNAL = frozenset(("EDITORIAL FOCUS", "EDITORIAL QUESTIONS / SATURDAY FOLLOW-UP"))
IDS = ("SOURCE RECORD IDS:", "EXTERNAL SOURCE IDS:")
SECTION_RE = re.compile(r"^## ([^\r\n]+)$", re.MULTILINE)
PROSE_TITLES = {
    "CONCRETE DEVELOPMENT": "The development",
    "OPENING NOTE": "Overview",
    "WHAT STOOD OUT": "What stood out",
    "WHY IT MATTERS": "Why it matters",
    "WHAT WAS ROUTINE": "What was routine",
    "WHAT I'M WATCHING NEXT": "What we're watching",
    "CROSS-DESK COMPARISON": "Across the region",
}
INTRO = (
    "Hi Dylan,\n\n"
    "Here's this week's working IPR Brief in a cleaner reading format. "
    "Could you focus on the language, flow, clarity, and whether the argument "
    "sounds natural? Feel free to rewrite paragraphs or suggest cuts. "
    "If a claim strikes you as questionable, just flag it—I’ll handle the "
    "source verification and final publication review.\n\n"
    "You can reply with your edits in the email or send back a document. "
    "No need to work through the record IDs or technical appendix in the "
    "reference .txt attachment. This is still a provisional draft.\n\n"
)
CLOSING = "\n\nThanks,\nBen\n"


class ReadableEditorError(ValueError):
    """Refuse malformed manuscript or non-manuscript source packet."""


def editable_sections(original):
    """Only prose within the already reviewed editable boundary; never sources.

    Omit the editorial-only focus/queries and source ID display from Dylan's
    reading copy. The ORIGINAL immutable TXT remains the citation reference.
    """
    if not isinstance(original, str) or original.count(BEGIN) != 1 or original.count(APPENDIX) != 1:
        raise ReadableEditorError("missing or duplicated exact manuscript boundaries")
    before, remainder = original.split(BEGIN, 1)
    draft, _ = remainder.split(APPENDIX, 1)
    if "Status: UNNUMBERED DRAFT — NOT APPROVED OR PUBLISHED" not in before:
        raise ReadableEditorError("source worksheet does not state unapproved status")
    if "## " not in draft:
        raise ReadableEditorError("no model manuscript in worksheet")
    headings = list(SECTION_RE.finditer(draft))
    if not headings:
        raise ReadableEditorError("no article headings found")
    sections = {}
    for i, match in enumerate(headings):
        key = match.group(1)
        end = headings[i + 1].start() if i + 1 < len(headings) else len(draft)
        if key not in HEADINGS and key not in INTERNAL:
            raise ReadableEditorError("unknown source worksheet heading")
        if key in sections:
            raise ReadableEditorError("duplicate manuscript heading")
        raw = draft[match.end():end].strip()
        if any(line.startswith("===") for line in raw.splitlines()):
            raise ReadableEditorError("unexpected envelope marker in article")
        cleaned = "\n".join(
            line for line in raw.splitlines()
            if not line.startswith(IDS)
        ).strip()
        if not cleaned:
            raise ReadableEditorError("empty manuscript section")
        sections[key] = cleaned
    if not all(key in sections for key in HEADINGS):
        raise ReadableEditorError("incomplete or truncated manuscript")
    return [(key, sections[key]) for key in HEADINGS]


def prose_only_text(original):
    """Readable plain-text editorial copy for the multipart email fallback."""
    sections = editable_sections(original)
    out = [INTRO.rstrip(), ""]
    for key, text in sections:
        if key == "WORKING TITLE":
            out.append(text)
        elif key == "DEK":
            out.append(text)
        else:
            out.extend((PROSE_TITLES[key], text))
        out.append("")
    out.append(CLOSING.strip())
    return "\n".join(out) + "\n"


def _paragraph_html(text):
    """Render only escaped paragraphs and simple bold; no raw publisher HTML."""
    safe = html.escape(text, quote=True)
    safe = re.sub(r"\*\*([^\n*]+)\*\*", r"<strong>\1</strong>", safe)
    return "".join(
        '<p style="margin:0 0 14px;line-height:1.65;">' +
        para.replace("\n", " ") + "</p>"
        for para in safe.split("\n\n") if para.strip()
    )


def prose_only_html(original):
    """Professional article-first HTML; all technical source data stays out."""
    sections = editable_sections(original)
    out = [
        '<!doctype html><html><body style="margin:0;padding:0;background:#ffffff;">',
        '<div style="max-width:680px;margin:20px auto;padding:24px 20px;'
        'font-family:Georgia,Times New Roman,serif;color:#1b2b36;font-size:16px;">',
        '<div style="font:700 12px Arial,sans-serif;letter-spacing:1px;'
        'text-transform:uppercase;color:#607887;margin-bottom:20px;">'
        "Indo-Pacific Record / Working Brief</div>",
        '<div style="font:14px Arial,sans-serif;color:#435664;line-height:1.6;'
        'padding:0 0 18px;border-bottom:1px solid #d8e1e6;margin-bottom:20px;">'
        + html.escape(INTRO.strip()).replace("\n\n", "<p>").replace("\n", " ") +
        "</div>",
    ]
    for key, text in sections:
        if key == "WORKING TITLE":
            out.append('<h1 style="font-size:28px;line-height:1.25;margin:0 0 14px;">'
                       + html.escape(text, quote=True) + "</h1>")
        elif key == "DEK":
            out.append('<div style="font-size:17px;color:#425663;line-height:1.55;'
                       'margin:0 0 26px;">' + _paragraph_html(text) + "</div>")
        else:
            out.append('<h2 style="font:700 17px Arial,sans-serif;'
                       'margin:26px 0 12px;color:#233a49;">' +
                       html.escape(PROSE_TITLES[key], quote=True) + "</h2>")
            out.append(_paragraph_html(text))
    out.append('<p style="font:14px Arial,sans-serif;margin:22px 0 0;">'
               "Thanks,<br>Ben</p></div></body></html>")
    return "".join(out)
