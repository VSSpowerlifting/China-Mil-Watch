"""
Safe local re-render for The PLA Watch.

Loads existing JSON sidecars from output/the-pla-watch/posts/ and re-renders
HTML using the current Jinja templates. Also (re)generates the editorial
issue cover PNG for each sidecar.

Does NOT call the Anthropic API, does NOT scrape, does NOT run the daily
pipeline.

Usage:
    python scripts/rerender_pla_watch.py [--force-covers] [--no-covers]
"""

import argparse
import json
import re
import sys
from datetime import date as date_cls
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import SITE_ORIGIN

from scripts.pw_env import (
    build_atom_feed,
    copy_editorial_assets,
    editorial_items_for_edition,
    ensure_editorial_derivatives,
    ensure_source_veils,
    make_pw_env,
    veil_for_edition,
)

# Author identity comes from `core/edition_identity.py`, which is stdlib-only
# and imports neither `anthropic` nor `config` — so there is no import to guard
# against and no fallback copy to drift.
#
# The previous fallback here hard-coded the predecessor identity, which meant a
# failed import silently rebranded every edition it touched to "Principal
# Analyst, China Mil Watch" — the exact stale branding this contract exists to
# stop reintroducing. A duplicated identity is a second source of truth; there
# is now one.
from core.edition_identity import (
    AUTHOR_NAME, IdentityError, current_identity_fields, resolve_identity,
)

_CURRENT_IDENTITY = current_identity_fields()
AUTHOR_TITLE = _CURRENT_IDENTITY["author_title"]
AUTHOR_BIO = _CURRENT_IDENTITY["author_bio"]
AUTHOR_LINKS = _CURRENT_IDENTITY["author_links"]
from scripts.generate_pla_watch_cover import (
    render_cover,
    render_thumbnail,
    resolve_background_image,
)


POSTS_DIR = ROOT / "output" / "the-pla-watch" / "posts"
PLA_WATCH_DIR = ROOT / "output" / "the-pla-watch"
MEDIA_DIR = ROOT / "output" / "the-pla-watch" / "media"
COVERS_DIR = ROOT / "output" / "the-pla-watch" / "covers"
TEMPLATES_DIR = ROOT / "site" / "templates"


def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host or url
    except Exception:
        return url


def _flatten_term(sidecar: dict) -> tuple[str, str]:
    """
    Sidecar may carry term_to_know as {term, term_translation, explanation}
    or as the flat fields term_to_know_term / term_to_know_explanation.
    Return (term_word, explanation) suitable for the template.
    """
    if "term_to_know" in sidecar and isinstance(sidecar["term_to_know"], dict):
        t = sidecar["term_to_know"]
        word = t.get("term", "")
        trans = t.get("term_translation", "")
        if word and trans:
            display = f"{word} — {trans}"
        else:
            display = word or trans
        return display, t.get("explanation", "")
    return (
        sidecar.get("term_to_know_term", ""),
        sidecar.get("term_to_know_explanation", ""),
    )


def _days_covered(sidecar: dict) -> int:
    """Compute days covered from week_start/week_ending if not explicit."""
    explicit = sidecar.get("days_covered")
    if explicit:
        return int(explicit)
    start = sidecar.get("week_start", "")
    end = sidecar.get("week_ending", "") or sidecar.get("date", "")
    try:
        ds = date_cls.fromisoformat(start)
        de = date_cls.fromisoformat(end)
        return max(1, (de - ds).days + 1)
    except Exception:
        return 0


def _articles_from_sidecar(sidecar: dict) -> list[dict]:
    """
    Map source_trail entries (label/url) into the shape the post template
    expects (title/url/source/date/is_significant). Falls back to an
    already-shaped articles list if present.
    """
    if sidecar.get("articles"):
        return sidecar["articles"]
    out = []
    sources_seen = sidecar.get("sources_seen") or []
    default_source = sources_seen[0] if sources_seen else ""
    for entry in sidecar.get("source_trail", []) or []:
        out.append({
            "title": entry.get("label") or entry.get("title") or _domain_from_url(entry.get("url", "")),
            "title_zh": entry.get("title_zh") or "",
            "url":   entry.get("url", ""),
            "source": entry.get("source") or default_source,
            "date":   entry.get("date") or "",
            "is_significant": bool(entry.get("is_significant", False)),
        })
    return out


def _cover_paths(sidecar: dict) -> tuple[str, str, str]:
    """
    Compute the in-page src, thumbnail src, and absolute OG URL for the
    issue cover. Returns (cover_image, cover_thumb, cover_image_url).
    """
    sidecar_date = sidecar.get("date", "")
    if not sidecar_date:
        return "", "", ""
    rel = f"../covers/{sidecar_date}.png"
    thumb = f"../covers/{sidecar_date}-thumb.png"
    abs_url = (
        f"{SITE_ORIGIN}/the-pla-watch/covers/{sidecar_date}.png"
    )
    return rel, thumb, abs_url


def _on_current_origin(url: str) -> str:
    """
    Re-base a stored absolute cover URL onto the current site origin.

    Twelve sidecars record `cover_image_url` on `chinamilwatch.org`, captured
    when that was the live domain. The address is a fact about where the site
    lives, not a fact about the edition — the covers themselves moved with the
    rest of the tree, and the predecessor domain is now a redirect-only Pages
    site. Rendering that URL into `og:image` would point every link preview at
    a redirect, which is how a social card silently stops resolving.

    Only the origin is replaced; the path is the sidecar's. Sidecars are the
    canonical edition record and are not edited to fix this — the renderer
    reads them as published and states the current address itself.

    Editions keep their historical *identity*; they do not keep a stale host.
    """
    if not url:
        return url
    from urllib.parse import urlsplit, urlunsplit
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return url
    current = urlsplit(SITE_ORIGIN)
    if parts.netloc == current.netloc:
        return url
    return urlunsplit((current.scheme, current.netloc, parts.path,
                       parts.query, parts.fragment))


def _normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        host = parsed.netloc.lower()
        path = re.sub(r"/+$", "", parsed.path)
        return f"{parsed.scheme.lower()}://{host}{path}" if host else path
    except Exception:
        return url.strip()


def _resolve_media_path(raw_path: str):
    if not raw_path:
        return None
    parsed = urlparse(raw_path)
    if parsed.scheme and parsed.scheme != "file":
        return None
    candidate = Path(parsed.path if parsed.scheme == "file" else raw_path)
    if not candidate.is_absolute():
        if raw_path.startswith("../media/"):
            candidate = MEDIA_DIR / raw_path.removeprefix("../media/")
        else:
            candidate = ROOT / raw_path
    return candidate.resolve() if candidate.exists() else None


def _media_matches_cover(media_item: dict, cover_bg) -> bool:
    if not cover_bg:
        return False
    cover_bg = cover_bg.resolve()
    paths = [
        _resolve_media_path(str(media_item.get(key) or ""))
        for key in ("src", "local_path", "path", "optimized_path")
    ]
    if any(path == cover_bg for path in paths if path):
        return True

    cover_url = _normalize_url(cover_bg.as_uri())
    urls = [
        _normalize_url(str(media_item.get(key) or ""))
        for key in ("src", "source_url", "image_url", "url")
    ]
    if cover_url in urls:
        return True

    cover_name = cover_bg.name.lower()
    return any(
        Path(str(media_item.get(key) or "")).name.lower() == cover_name
        for key in ("src", "local_path", "path", "optimized_path", "image_url")
    )


def _media_label(media_item: dict) -> str:
    raw = (
        media_item.get("label")
        or media_item.get("media_label")
        or media_item.get("kind")
        or media_item.get("role")
        or ""
    )
    normalized = str(raw).strip().lower()
    labels = {
        "map": "Map",
        "source_image": "Source Image",
        "source image": "Source Image",
        "document_excerpt": "Document Excerpt",
        "document excerpt": "Document Excerpt",
        "chart": "Chart",
    }
    return labels.get(normalized, "Visual Context")


def _split_media_items(sidecar: dict):
    cover_bg = resolve_background_image(sidecar)
    body_media = []
    cover_credit = None
    for item in sidecar.get("media_items", []) or []:
        if not isinstance(item, dict):
            continue
        enriched = {**item, "display_label": _media_label(item)}
        if item.get("type") == "image" and _media_matches_cover(item, cover_bg):
            cover_credit = cover_credit or enriched
        else:
            body_media.append(enriched)
    return body_media, cover_credit


def _build_post_context(sidecar: dict) -> dict:
    term_word, term_explanation = _flatten_term(sidecar)
    body_media_items, cover_media_item = _split_media_items(sidecar)
    sidecar_date = sidecar.get("date", "")
    pw_veil = veil_for_edition(sidecar_date, sidecar=sidecar)
    cover_image = sidecar.get("cover_image") or ""
    cover_thumb = sidecar.get("cover_thumb") or ""
    cover_image_url = _on_current_origin(sidecar.get("cover_image_url") or "")
    if not cover_image or not cover_image_url:
        derived_rel, derived_thumb, derived_abs = _cover_paths(sidecar)
        cover_image = cover_image or derived_rel
        cover_thumb = cover_thumb or derived_thumb
        cover_image_url = cover_image_url or derived_abs
    # If the PNG isn't on disk, blank both so the template falls back
    # to the sitewide og-image.png and skips the in-page figure.
    if cover_image:
        png_path = COVERS_DIR / f"{sidecar_date}.png"
        if not png_path.exists():
            cover_image = ""
            cover_thumb = ""
            cover_image_url = ""
    # The Signal Veil replaces the in-page cover figure when it renders
    # (og:image still uses cover_image_url, which stays untouched).
    if pw_veil:
        cover_image = ""
        cover_thumb = ""

    identity = resolve_identity(sidecar)

    return {
        # Hero / metadata
        "issue_number":  sidecar.get("issue_number"),
        "date":          sidecar.get("date", ""),
        "title":         sidecar.get("title", ""),
        "dek":           sidecar.get("dek", ""),
        "signal":        sidecar.get("signal", "") or "",
        "week_ending":   sidecar.get("week_ending", ""),
        "week_start":    sidecar.get("week_start", ""),
        "n_articles":    sidecar.get("n_articles", 0),
        "n_significant": sidecar.get("n_significant", 0),
        "days_covered":  _days_covered(sidecar),
        "edition_label": sidecar.get("edition_label", ""),
        "sources_seen":  sidecar.get("sources_seen", []),

        # Cover image
        "cover_image":     cover_image,
        "cover_thumb":     cover_thumb,
        "cover_image_url": cover_image_url,

        # Body
        "opening_note":          sidecar.get("opening_note", ""),
        "what_stood_out":        sidecar.get("what_stood_out", ""),
        "why_it_matters":        sidecar.get("why_it_matters", ""),
        "what_was_routine":      sidecar.get("what_was_routine", ""),
        "term_to_know_term":     term_word,
        "term_to_know_explanation": term_explanation,
        "what_im_watching_next": sidecar.get("what_im_watching_next", ""),

        # Source trail
        "articles": _articles_from_sidecar(sidecar),
        "source_trail_truncated": sidecar.get("source_trail_truncated", False),

        # Visual context (license-verified outside images, if any).
        # Sidecar media first, then render-time editorial-manifest items
        # matched to this edition — sidecars stay canonical and untouched.
        # exclude_id keeps the Signal Veil image from also repeating as a
        # Visual Context media card.
        "media_items": body_media_items
            + editorial_items_for_edition(
                sidecar_date, exclude_id=(pw_veil or {}).get("id")),
        "cover_media_item": cover_media_item,
        "pw_veil": pw_veil,

        # Publication identity, resolved from the edition itself. Falling back
        # to this module's *current* constants would rebrand every historical
        # edition this path rebuilds — editions 1 and 2 store no author fields
        # at all, so they would have taken the current identity wholesale.
        "author_name":  identity["author_name"],
        "author_title": identity["author_title"],
        "author_bio":   identity["author_bio"],
        "author_links": identity["author_links"],
        "publication":            identity["publication"],
        "publication_home_label": identity["publication_home_label"],
        "series_name":            identity["series_name"],
        "publication_timing":     identity["publication_timing"],
        "is_retrospective":       identity["is_retrospective"],
        "retrospective_label":    identity["retrospective_label"],

        "root_path": "../../",
        "page_url": (
            f"{SITE_ORIGIN}/the-pla-watch/posts/{sidecar.get('date', '')}.html"
            if sidecar.get("date") else f"{SITE_ORIGIN}/the-pla-watch/"
        ),
    }


BODY_FIELDS = (
    "opening_note", "what_stood_out", "why_it_matters",
    "what_was_routine", "what_im_watching_next",
)


def validate_sidecar_identities(sidecars: list) -> None:
    """
    Refuse the whole run before anything is written.

    `resolve_identity` raises on an unreadable `publication` or
    `publication_timing`. Checking every sidecar up front means one bad file
    stops the re-render before a single derivative, cover or HTML page is
    produced — a partial re-render would leave the published tree half in one
    identity and half in another, which is worse than not running.
    """
    for sidecar in sidecars:
        try:
            resolve_identity(sidecar)
        except IdentityError as exc:
            raise IdentityError(
                "sidecar %s: %s" % (sidecar.get("date") or "<undated>", exc))


def _sidecar_has_body(sidecar: dict) -> bool:
    return any((sidecar.get(f) or "").strip() for f in BODY_FIELDS)


def _parse_args():
    p = argparse.ArgumentParser(
        description="Re-render PLA Watch HTML and refresh issue cover PNGs from "
                    "existing JSON sidecars. No API calls, no scraping."
    )
    p.add_argument("--no-covers", action="store_true",
                   help="Skip cover-image (re)generation; only re-render HTML.")
    p.add_argument("--force-covers", action="store_true",
                   help="Overwrite existing cover PNGs even if up to date.")
    p.add_argument("--allow-empty-body", action="store_true",
                   help="Re-render posts even when the sidecar has no body text "
                        "(dangerous: overwrites published prose with an empty page).")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    env = make_pw_env()
    post_tmpl = env.get_template("pla-watch-post.html")
    index_tmpl = env.get_template("pla-watch-index.html")
    archive_tmpl = env.get_template("pla-watch-archive.html")

    # Read and validate every sidecar BEFORE creating a derivative, a cover or
    # a page. One unreadable identity stops the run here rather than leaving a
    # half-rebuilt tree in two identities.
    loaded = [(path, json.loads(path.read_text(encoding="utf-8")))
              for path in sorted(POSTS_DIR.glob("*.json"), reverse=True)]
    validate_sidecar_identities([sc for _, sc in loaded])

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_editorial_derivatives()
    ensure_source_veils()
    copy_editorial_assets(ROOT / "output")

    # Render every post sidecar.
    sidecars = []
    skipped: list = []
    for json_path, sidecar in loaded:
        # The index and archive cards read the byline off the in-memory
        # sidecar. Enrich it from *this edition's* resolved identity — seeding
        # from the current constants would put today's byline on every
        # historical card. Nothing here is written back to disk.
        _identity = resolve_identity(sidecar)
        sidecar.setdefault("author_name", _identity["author_name"])
        sidecar.setdefault("author_title", _identity["author_title"])

        # Cover image — generate or refresh PNG + thumbnail, then ensure
        # sidecar carries the path fields so index/archive templates show them.
        sidecar_date = sidecar.get("date", "")
        png_path = COVERS_DIR / f"{sidecar_date}.png" if sidecar_date else None
        thumb_path = COVERS_DIR / f"{sidecar_date}-thumb.png" if sidecar_date else None
        if not args.no_covers and png_path is not None:
            if args.force_covers or not png_path.exists():
                try:
                    render_cover(sidecar, png_path)
                    print(f"Wrote {png_path.relative_to(ROOT)}")
                except Exception as exc:
                    print(f"WARN: cover generation failed for "
                          f"{sidecar_date}: {exc!r}")
            if png_path.exists() and thumb_path is not None:
                if args.force_covers or not thumb_path.exists():
                    try:
                        render_thumbnail(png_path, thumb_path)
                        print(f"Wrote {thumb_path.relative_to(ROOT)}")
                    except Exception as exc:
                        print(f"WARN: thumbnail generation failed for "
                              f"{sidecar_date}: {exc!r}")
        rel, thumb_rel, abs_url = _cover_paths(sidecar)
        if png_path is not None and png_path.exists():
            # Always write canonical covers/ paths — overwrites any old
            # ../media/... paths that predate this directory scheme.
            sidecar["cover_image"] = rel
            sidecar["cover_thumb"] = thumb_rel
            sidecar["cover_image_url"] = abs_url
        sidecars.append(sidecar)

    # Second pass: render posts with prev/next neighbors resolved.
    by_date_asc = sorted(sidecars, key=lambda s: s.get("date", ""))
    for i, sidecar in enumerate(by_date_asc):
        # Never overwrite a published post with an empty body. Sidecars that
        # predate body-field storage would otherwise render prose-less pages.
        if not _sidecar_has_body(sidecar) and not args.allow_empty_body:
            print(f"ERROR: {sidecar.get('date', '?')}.json has no body fields "
                  f"(opening_note etc.) — post HTML left untouched. "
                  f"Backfill the sidecar or pass --allow-empty-body.")
            skipped.append(f"{sidecar.get('date', '?')}.json")
            continue

        ctx = _build_post_context(sidecar)
        ctx["prev_post"] = by_date_asc[i - 1] if i > 0 else None
        ctx["next_post"] = by_date_asc[i + 1] if i + 1 < len(by_date_asc) else None
        html = post_tmpl.render(**ctx)
        out_path = POSTS_DIR / f"{sidecar['date']}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"Wrote {out_path.relative_to(ROOT)}")

    # Sort newest-first for index/archive.
    sidecars.sort(key=lambda s: s.get("date", ""), reverse=True)

    latest = sidecars[0] if sidecars else None
    archive_posts = sidecars[1:] if len(sidecars) > 1 else []

    # index.html sits at the-pla-watch/index.html, one level shallower than
    # a post page, so the editorial-asset prefix drops one "../".
    latest_veil = (
        veil_for_edition(latest["date"], sidecar=latest,
                         editorial_prefix="../assets/editorial/",
                         media_prefix="media/")
        if latest else None
    )
    index_html = index_tmpl.render(
        latest_post=latest, archive_posts=archive_posts, root_path="../",
        page_url=f"{SITE_ORIGIN}/the-pla-watch/",
        latest_veil=latest_veil,
    )
    (PLA_WATCH_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"Wrote {(PLA_WATCH_DIR / 'index.html').relative_to(ROOT)}")

    archive_html = archive_tmpl.render(
        posts=sidecars, root_path="../",
        page_url=f"{SITE_ORIGIN}/the-pla-watch/archive.html",
    )
    (PLA_WATCH_DIR / "archive.html").write_text(archive_html, encoding="utf-8")
    print(f"Wrote {(PLA_WATCH_DIR / 'archive.html').relative_to(ROOT)}")

    # Terms-to-Know running glossary — verbatim reuse of each edition's
    # published term; nothing is re-derived at render time.
    terms = []
    for s in sidecars:  # newest-first
        word, explanation = _flatten_term(s)
        if word.strip() and s.get("date"):
            terms.append({
                "term": word,
                "explanation": explanation,
                "date": s["date"],
                "issue_number": s.get("issue_number"),
                "week_ending": s.get("week_ending", "") or s["date"],
            })
    terms_tmpl = env.get_template("pla-watch-terms.html")
    terms_html = terms_tmpl.render(
        terms=terms, root_path="../",
        page_url=f"{SITE_ORIGIN}/the-pla-watch/terms.html",
    )
    (PLA_WATCH_DIR / "terms.html").write_text(terms_html, encoding="utf-8")
    print(f"Wrote {(PLA_WATCH_DIR / 'terms.html').relative_to(ROOT)} "
          f"({len(terms)} terms)")

    # Atom feed — deterministic, sidecar-dated.
    (PLA_WATCH_DIR / "feed.xml").write_text(
        build_atom_feed(sidecars), encoding="utf-8")
    print(f"Wrote {(PLA_WATCH_DIR / 'feed.xml').relative_to(ROOT)}")

    if skipped:
        print(f"\n{len(skipped)} post(s) skipped for missing body text: "
              + ", ".join(skipped))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
