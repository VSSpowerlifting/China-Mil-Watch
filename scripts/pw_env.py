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


def make_pw_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["format_date"] = format_date
    env.filters["inline_markup"] = inline_markup
    return env
