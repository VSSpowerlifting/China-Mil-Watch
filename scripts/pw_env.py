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


EDITORIAL_DIR = TEMPLATES_DIR.parent / "assets" / "editorial"
EDITORIAL_DERIV_DIR = EDITORIAL_DIR / "derivatives"


def load_editorial_manifest() -> list:
    """
    Curated editorial-image manifest (site/assets/editorial/manifest.json).

    The manifest is hand-maintained via scripts/fetch_editorial_image.py and
    is the only source of editorial imagery. Returns [] when the manifest is
    absent or malformed, and silently drops entries whose local asset file
    does not exist — imagery is always optional and can never break a build
    or point at a missing file.
    """
    import json

    path = EDITORIAL_DIR / "manifest.json"
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    ok = []
    for e in entries if isinstance(entries, list) else []:
        if not isinstance(e, dict):
            continue
        fname = e.get("file")
        if not fname or not (EDITORIAL_DIR / fname).exists():
            continue
        ok.append(e)
    return ok


def editorial_visual_fields(entry: dict) -> dict:
    """
    Normalized display fields for the Source-Derived Signal Graphics system,
    with backward-compatible defaults so older manifest entries (missing the
    optional treatment/mask_focus/source_id/subject fields) still render via
    the veil system without a template-side KeyError.
    """
    return {
        "treatment":   entry.get("treatment") or "veil",
        "mask_focus":  entry.get("mask_focus") or "",
        "source_id":   entry.get("source_id") or entry.get("license") or "SOURCE",
        "subject":     entry.get("subject") or "",
        "alt":         entry.get("alt") or "",
        "credit":      entry.get("credit") or "",
        "source_page": entry.get("source_page") or "",
        "license":     entry.get("license") or "",
        "license_url": entry.get("license_url") or "",
        "focal":       entry.get("focal") or "50% 50%",
    }


def derivative_name(entry: dict, kind: str) -> str:
    """Fixed naming contract (see §0 of the visual-system spec):
    {id}-duo-paper.jpg / {id}-duo-navy.jpg / {id}-dither-ink.png."""
    eid = entry.get("id") or ""
    if kind == "duo-paper":
        return f"{eid}-duo-paper.jpg"
    if kind == "duo-navy":
        return f"{eid}-duo-navy.jpg"
    if kind == "dither-ink":
        return f"{eid}-dither-ink.png"
    raise ValueError(f"unknown derivative kind: {kind!r}")


def ensure_editorial_derivatives() -> None:
    """Best-effort call into the derivative generator at build time. Never
    raises: a missing/broken generator must not break the site build, and
    any derivatives already committed to disk still get copied by
    copy_editorial_assets()."""
    try:
        from scripts.generate_editorial_derivatives import ensure_derivatives
        ensure_derivatives()
    except Exception as exc:  # noqa: BLE001 - build must never break here
        print(f"WARN: ensure_editorial_derivatives() failed: {exc!r}")


def copy_editorial_assets(output_root) -> int:
    """Copy manifest-listed images (and any generated derivatives) into
    output/assets/editorial/ (idempotent, mtime-checked)."""
    import shutil

    entries = load_editorial_manifest()
    if not entries:
        return 0
    dest = Path(output_root) / "assets" / "editorial"
    dest.mkdir(parents=True, exist_ok=True)
    for e in entries:
        src = EDITORIAL_DIR / e["file"]
        target = dest / e["file"]
        if not target.exists() or src.stat().st_mtime > target.stat().st_mtime:
            shutil.copy2(src, target)

    if EDITORIAL_DERIV_DIR.is_dir():
        dest_deriv = dest / "derivatives"
        dest_deriv.mkdir(parents=True, exist_ok=True)
        for src in EDITORIAL_DERIV_DIR.iterdir():
            if not src.is_file():
                continue
            target = dest_deriv / src.name
            if not target.exists() or src.stat().st_mtime > target.stat().st_mtime:
                shutil.copy2(src, target)

    return len(entries)


def editorial_veil_for_edition(date: str, manifest=None,
                               src_prefix: str = "../../assets/editorial/"):
    """
    The Night Desk "Signal Veil" image for a weekly edition: the first
    manifest entry routed to 'pw-post' for this edition date whose treatment
    is 'veil' and whose duo-navy derivative already exists on disk (site
    side). Returns None on any miss (no manifest, no match, non-veil
    treatment, or missing derivative) — the safe text-led fallback.
    """
    for e in (manifest if manifest is not None else load_editorial_manifest()):
        match = e.get("match") or {}
        if "pw-post" not in (match.get("routes") or []):
            continue
        if date not in (match.get("editions") or []):
            continue
        fields = editorial_visual_fields(e)
        if fields["treatment"] != "veil":
            continue
        deriv_name = derivative_name(e, "duo-navy")
        if not (EDITORIAL_DERIV_DIR / deriv_name).exists():
            continue
        return {
            "id":          e.get("id"),
            "duo":         f"{src_prefix}derivatives/{deriv_name}",
            "alt":         fields["alt"],
            "mask_focus":  fields["mask_focus"] or "52% 46%",
            "source_id":   fields["source_id"],
            "subject":     fields["subject"],
            "source_page": fields["source_page"],
            "credit":      fields["credit"],
            "license":     fields["license"],
        }
    return None


def editorial_items_for_edition(date: str, manifest=None,
                                src_prefix: str = "../../assets/editorial/",
                                exclude_id=None) -> list:
    """
    Render-time Visual Context items for a weekly edition, selected from the
    editorial manifest by edition date. Sidecar JSON stays canonical and
    untouched — these items are additive display context only, and drop out
    of the page automatically if the manifest entry or asset is removed.
    `exclude_id` skips the entry already rendered as the edition's Signal
    Veil, so it doesn't also repeat as a Visual Context media card.
    """
    items = []
    for e in (manifest if manifest is not None else load_editorial_manifest()):
        match = e.get("match") or {}
        if "pw-post" not in (match.get("routes") or []):
            continue
        if date not in (match.get("editions") or []):
            continue
        if exclude_id and e.get("id") == exclude_id:
            continue
        items.append({
            "type": "image",
            "src": f"{src_prefix}{e['file']}",
            "alt": e.get("alt") or "",
            "caption": e.get("caption") or "",
            "credit": e.get("credit") or "",
            "license": e.get("license") or "",
            "license_url": e.get("license_url") or "",
            "source_url": e.get("source_page") or "",
            "display_label": e.get("display_label") or "Visual context",
            "width": e.get("width"),
            "height": e.get("height"),
            "editorial_id": e.get("id"),
        })
    return items


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
