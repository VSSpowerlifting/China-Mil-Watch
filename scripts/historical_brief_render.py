"""Render unchanged historical edition context in the current IPR shell.

The legacy templates remain a rollback/reference surface. Production post
rendering uses this adapter in both authoring and sidecar re-render paths.
No database, source sidecar, feed identity or publication attribution is edited.
"""
from functools import lru_cache
import html
import importlib.util
from pathlib import Path
import re

from jinja2 import Environment, FileSystemLoader

from config import SITE_ORIGIN
from core.edition_identity import COLLECTION_NAME
from core.topography import topography_style
from scripts.pw_env import format_date, inline_markup

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = (
    ("opening_note", "s-opening", "Opening Note"),
    ("what_stood_out", "s-stood-out", "What Stood Out"),
    ("why_it_matters", "s-why", "Why It Matters"),
    ("what_was_routine", "s-routine", "Routine Baseline"),
)


@lru_cache(maxsize=1)
def _site_definition():
    # Reuse the publication's existing approved identity, not a second bio.
    spec = importlib.util.spec_from_file_location(
        "ipr_historical_shell_definition", ROOT / "site/preview/generate_preview.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_historical_brief(context: dict) -> str:
    """Accept the existing resolved post context; only presentation changes."""
    gp = _site_definition()
    env = Environment(loader=FileSystemLoader(str(gp.TEMPLATES)),
                      autoescape=True, trim_blocks=True, lstrip_blocks=True)
    env.filters.update(reader_date=format_date, inline_markup=inline_markup,
                       count=lambda n: format(n, ",") if isinstance(n, int) else n,
                       has_cjk=lambda text: bool(re.search(r"[一-鿿㐀-䶿]", text or "")))
    env.globals["topography_style"] = topography_style
    # Leave the resolved author/publication context intact. Current shell and
    # historical edition data deliberately have separate namespaces.
    edition = dict(context)
    display_title = edition.get("title", "")
    for prefix in ("The PLA Watch: ", "The PLA Watch — ", "The PLA Watch – "):
        if display_title.startswith(prefix):
            display_title = display_title[len(prefix):]
            break
    page_url = edition.get("page_url") or (
        f"{SITE_ORIGIN}/the-pla-watch/posts/{edition['date']}.html")
    rendered = env.get_template("historical-brief.html").render(
        title=gp.PUBLIC_TITLE, tagline=gp.TAGLINE, maintainer=gp.MAINTAINER,
        collection_name=COLLECTION_NAME, mode=gp.BUILD_MODE,
        live_base=SITE_ORIGIN, page="analysis.html", root_path="../../",
        brief={}, desks=[], timelines=[], review_mode=False,
        edition=edition, display_title=display_title,
        sections=[(key, anchor, heading) for key, anchor, heading in SECTIONS
                  if edition.get(key)],
    )
    # This is a published issue's render path, not a draft preview. As in the
    # production record renderer, replace the shell's private-preview marker
    # with the canonical and social address; preserve its original cover URL.
    cover = edition.get("cover_image_url") or f"{SITE_ORIGIN}/social-card.png"
    metadata = "\n".join([
        f'<link rel="canonical" href="{html.escape(page_url, quote=True)}">',
        f'<meta property="og:url" content="{html.escape(page_url, quote=True)}">',
        f'<meta property="og:image" content="{html.escape(cover, quote=True)}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta name="twitter:image" content="{html.escape(cover, quote=True)}">',
        f'<link rel="alternate" type="application/atom+xml" title="The PLA Watch — original feed" href="{html.escape(SITE_ORIGIN, quote=True)}/the-pla-watch/feed.xml">',
    ])
    marker = '<meta name="robots" content="noindex, nofollow">'
    if rendered.count(marker) != 1:
        raise ValueError("current IPR shell must carry exactly one preview marker")
    return rendered.replace(marker, metadata, 1)
