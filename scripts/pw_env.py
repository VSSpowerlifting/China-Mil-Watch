"""
Shared Jinja2 environment for The PLA Watch renderers.

Both scripts/generate_pla_watch.py and scripts/rerender_pla_watch.py must
render with identical settings, or a re-render can silently diverge from the
original publish. Centralised here:

  - autoescape=True — post body text and source titles are plain text and
    must be escaped on output (site/generator.py already does this).
  - format_date filter — '2026-07-04' → '4 July 2026' for reader-facing
    labels. ISO dates stay in tabular/meta contexts.
"""

import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup, escape

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "site" / "templates"

# Inline tags allowed to pass through prose fields. Some early sidecars carry
# literal <strong> emphasis in body text; everything else stays escaped.
_ALLOWED_INLINE = ("strong", "em")


def format_date(date_str: str) -> str:
    """'2026-07-04' → '4 July 2026'. Falls back to the input on bad data."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%-d %B %Y")
    except (ValueError, TypeError, AttributeError):
        return date_str or ""


def inline_markup(text: str) -> Markup:
    """
    Escape prose, then restore whitelisted bare inline tags (<strong>, <em>).
    Keeps early-sidecar emphasis rendering while everything else — including
    attributes on those tags — stays escaped.
    """
    escaped = str(escape(text or ""))
    for tag in _ALLOWED_INLINE:
        escaped = escaped.replace(f"&lt;{tag}&gt;", f"<{tag}>")
        escaped = escaped.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    return Markup(escaped)


def first_cjk(text: str, max_chars: int = 2) -> str:
    """Leading run of CJK characters from a term string, capped at
    max_chars — used as a verbatim typographic backdrop on term plates.
    Returns '' when the term has no CJK opening, so the motif simply
    doesn't render rather than inventing a glyph."""
    match = re.match(r"[一-鿿㐀-䶿]+", (text or "").strip())
    return match.group(0)[:max_chars] if match else ""


def build_atom_feed(sidecars: list) -> str:
    """
    Atom feed for The PLA Watch from sidecar dicts (any order). Deterministic:
    timestamps come from sidecar dates, never the wall clock. Entries carry
    title, dek as summary, and the canonical post URL; no body text is
    duplicated into the feed — the page is the record.
    """
    from xml.sax.saxutils import escape as xml_escape

    site = "https://chinamilwatch.org/the-pla-watch"
    posts = sorted(
        [s for s in sidecars if s.get("date")],
        key=lambda s: s["date"], reverse=True,
    )
    updated = f"{posts[0]['date']}T00:00:00Z" if posts else "1970-01-01T00:00:00Z"
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        '  <title>The PLA Watch</title>',
        '  <subtitle>Weekly signals from Chinese military media — '
        'a publication of China Mil Watch</subtitle>',
        f'  <link href="{site}/feed.xml" rel="self" type="application/atom+xml"/>',
        f'  <link href="{site}/" rel="alternate" type="text/html"/>',
        f'  <id>{site}/</id>',
        f'  <updated>{updated}</updated>',
    ]
    for s in posts:
        url = f"{site}/posts/{s['date']}.html"
        title = xml_escape(s.get("title") or "The PLA Watch")
        summary = xml_escape((s.get("dek") or "").strip())
        author = xml_escape(s.get("author_name") or "China Mil Watch")
        stamp = f"{s.get('published_date') or s['date']}T00:00:00Z"
        lines += [
            "  <entry>",
            f"    <title>{title}</title>",
            f'    <link href="{url}" rel="alternate" type="text/html"/>',
            f"    <id>{url}</id>",
            f"    <updated>{stamp}</updated>",
            f"    <published>{stamp}</published>",
            f"    <author><name>{author}</name></author>",
        ]
        if summary:
            lines.append(f"    <summary>{summary}</summary>")
        lines.append("  </entry>")
    lines.append("</feed>")
    return "\n".join(lines) + "\n"


def make_pw_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["format_date"] = format_date
    env.filters["inline_markup"] = inline_markup
    env.filters["first_cjk"] = first_cjk
    return env
