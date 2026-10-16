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
from urllib.parse import urlsplit

from jinja2 import Environment, FileSystemLoader

from config import SITE_ORIGIN
from core.article_media import historical_article_media
from core.brief_collection import (CollectionError, brief_after_issue,
                                   continuity_items, load_collection)
from core.brief_collection import display_title as series_display_title
from core.desk_registry import load_registry
from core.edition_identity import COLLECTION_NAME, resolve_identity
from core.topography import topography_style
from scripts.pw_env import format_date, inline_markup, load_editorial_manifest

ROOT = Path(__file__).resolve().parent.parent
BRIEFS_DIR = ROOT / "briefs"
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


def _historical_author_links(links: dict) -> list[dict]:
    """Carry historical links forward without admitting unsafe schemes."""
    if not isinstance(links, dict):
        return []
    safe = []
    for label, url in links.items():
        if not isinstance(label, str) or not isinstance(url, str):
            continue
        if not label.strip() or not url or any(c in url for c in "\r\n\t"):
            continue
        parsed = urlsplit(url)
        external = parsed.scheme.lower() in ("https", "http") and bool(parsed.netloc)
        email = parsed.scheme.lower() == "mailto" and bool(parsed.path) and not parsed.netloc
        local = url == "../../index.html"
        if external or email or local:
            safe.append({"label": label, "url": url, "external": bool(external)})
    return safe


def _manifest_entry(veil) -> dict:
    """The editorial manifest entry behind a curated veil, read only."""
    if not veil or veil.get("kind") != "curated":
        return {}
    return next((e for e in load_editorial_manifest()
                 if e.get("id") == veil.get("id")), {})


def _issue_link(post) -> dict:
    """An adjacent issue for the shared previous/next navigation."""
    if not post:
        return None
    return {"href": f"{post['date']}.html", "number": post.get("issue_number"),
            "date": post.get("week_ending"),
            "title": series_display_title(post.get("title"))}


def _historical_collection(sidecars, briefs_dir=BRIEFS_DIR):
    """Read the shared published collection; historical titles remain intact."""
    editions = [{
        "slug": s["date"], "date": s["date"],
        "issue": s.get("issue_number"),
        "title": s.get("title") or "",
        "label": s.get("edition_label") or "",
        "url": f"{SITE_ORIGIN}/the-pla-watch/posts/{s['date']}.html",
        "rendered_locally": True,
    } for s in sidecars]
    return load_collection(editions, load_registry(), briefs_dir=briefs_dir)


def continuity_for_historical(sidecars, briefs_dir=BRIEFS_DIR):
    """Per-page links back to the one approved, cross-era Brief collection."""
    if not sidecars:
        return {}
    try:
        collection = _historical_collection(sidecars, briefs_dir)
    except CollectionError as exc:
        print(f"WARN: no Brief continuity strip: {exc}")
        return {}
    return {
        s["date"]: continuity_items(
            collection, f"the-pla-watch/posts/{s['date']}.html",
            current_slug=s["date"])
        for s in sidecars
    }


def next_brief_after(sidecars, briefs_dir=BRIEFS_DIR):
    """
    The newest earlier issue's "Next" link: the published brief that follows
    it in the Briefs collection order, as `{"slug", "link"}`, or None.

    Older issues keep their sidecar neighbours; only the newest issue has no
    next issue, so only it is bridged. The order and the approval gate are
    the collection's own (`core.brief_collection.load_collection`): drafts
    are never loaded and no synthetic fixture is allowed. A collection that
    cannot be loaded gives no link and a warning, never a guessed one.
    """
    if not sidecars:
        return None
    try:
        collection = _historical_collection(sidecars, briefs_dir)
    except CollectionError as exc:
        print(f"WARN: no Next Brief link from the newest issue: {exc}")
        return None
    newest = max(s["date"] for s in sidecars)
    link = brief_after_issue(collection, newest)
    return {"slug": newest, "link": link} if link else None


def render_historical_brief(context: dict, *, next_brief=None, continuity=None) -> str:
    """
    Accept the existing resolved post context; only presentation changes.
    `next_brief` is a `next_brief_after` link, shown only when the context
    has no next issue.
    """
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
    display_title = series_display_title(edition.get("title", ""))
    veil = edition.get("pw_veil")
    page_url = edition.get("page_url") or (
        f"{SITE_ORIGIN}/the-pla-watch/posts/{edition['date']}.html")
    rendered = env.get_template("historical-brief.html").render(
        title=gp.PUBLIC_TITLE, tagline=gp.TAGLINE, maintainer=gp.MAINTAINER,
        collection_name=COLLECTION_NAME, mode=gp.BUILD_MODE,
        live_base=SITE_ORIGIN, page="analysis.html", root_path="../../",
        brief={}, desks=[], timelines=[], review_mode=False,
        edition=edition, display_title=display_title,
        article_media=historical_article_media(
            veil, edition.get("cover_media_item"), _manifest_entry(veil),
            root="../../"),
        adjacent={"previous": _issue_link(edition.get("prev_post")),
                  "next": _issue_link(edition.get("next_post")) or next_brief},
        continuity=continuity or [],
        historical_author_links=_historical_author_links(edition.get("author_links")),
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


def render_historical_utility(title: str, route: str, **context) -> str:
    """Current shell for existing series utility URLs; verbatim sidecar fields."""
    if 'posts' in context:
        context['posts'] = [{**post, **resolve_identity(post)} for post in context['posts']]
    gp = _site_definition()
    env = Environment(loader=FileSystemLoader(str(gp.TEMPLATES)),
                      autoescape=True, trim_blocks=True, lstrip_blocks=True)
    env.filters.update(reader_date=format_date, inline_markup=inline_markup,
                       count=lambda n: format(n, ',') if isinstance(n, int) else n,
                       has_cjk=lambda value: bool(re.search(r'[一-鿿㐀-䶿]', value or '')))
    env.globals['topography_style'] = topography_style
    rendered = env.get_template('historical-utility.html').render(
        title=gp.PUBLIC_TITLE, tagline=gp.TAGLINE, maintainer=gp.MAINTAINER,
        collection_name=COLLECTION_NAME, mode=gp.BUILD_MODE,
        live_base=SITE_ORIGIN, page='analysis.html', root_path='../',
        desks=[], timelines=[], review_mode=False, historical_utility=True,
        utility_title=title, **context)
    url = html.escape(f'{SITE_ORIGIN}/{route}', quote=True)
    metadata = '\n'.join([
        f'<link rel="canonical" href="{url}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{html.escape(SITE_ORIGIN, quote=True)}/social-card.png">',
        f'<meta name="twitter:image" content="{html.escape(SITE_ORIGIN, quote=True)}/social-card.png">',
        f'<link rel="alternate" type="application/atom+xml" title="The PLA Watch — original feed" href="{html.escape(SITE_ORIGIN, quote=True)}/the-pla-watch/feed.xml">',
    ])
    if rendered.count('<meta name="robots" content="noindex, nofollow">') != 1:
        raise ValueError('current IPR shell must carry exactly one preview marker')
    return rendered.replace('<meta name="robots" content="noindex, nofollow">', metadata, 1)
