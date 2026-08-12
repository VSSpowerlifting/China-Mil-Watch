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

from scripts.pw_env import (
    build_atom_feed,
    copy_editorial_assets,
    editorial_items_for_edition,
    ensure_editorial_derivatives,
    ensure_source_veils,
    make_pw_env,
    veil_for_edition,
)

# Reuse author identity from the generator module without calling its main().
# Guard against the anthropic import that generate_pla_watch.py performs at
# module level — this script never calls the API.
try:
    from scripts.generate_pla_watch import (
        AUTHOR_NAME, AUTHOR_TITLE, AUTHOR_BIO, AUTHOR_LINKS,
    )
except ImportError:
    AUTHOR_NAME = "Benjamin Yang"
    AUTHOR_TITLE = "Principal Analyst, China Mil Watch"
    AUTHOR_BIO = (
        "Benjamin Yang is the principal analyst at China Mil Watch and an incoming "
        "International Affairs student at George Washington University's "
        "Elliott School, focused on U.S.-China relations, public diplomacy, "
        "and security affairs."
    )
    AUTHOR_LINKS = {
        "LinkedIn":        "https://www.linkedin.com/in/benjamin-yang-42b525294",
        "Email":           "mailto:ben.yang@gwmail.gwu.edu",
        "China Mil Watch": "../../index.html",
    }
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
        f"https://chinamilwatch.org/the-pla-watch/covers/{sidecar_date}.png"
    )
    return rel, thumb, abs_url


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
    cover_image_url = sidecar.get("cover_image_url") or ""
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

        # Author identity (graceful fallbacks: missing keys → chip omitted)
        "author_name":  sidecar.get("author_name",  AUTHOR_NAME),
        "author_title": sidecar.get("author_title", AUTHOR_TITLE),
        "author_bio":   sidecar.get("author_bio",   AUTHOR_BIO),
        "author_links": sidecar.get("author_links", AUTHOR_LINKS),

        "root_path": "../../",
        "page_url": (
            f"https://chinamilwatch.org/the-pla-watch/posts/{sidecar.get('date', '')}.html"
            if sidecar.get("date") else "https://chinamilwatch.org/the-pla-watch/"
        ),
    }


BODY_FIELDS = (
    "opening_note", "what_stood_out", "why_it_matters",
    "what_was_routine", "what_im_watching_next",
)


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

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    ensure_editorial_derivatives()
    ensure_source_veils()
    copy_editorial_assets(ROOT / "output")

    # Render every post sidecar.
    sidecars = []
    skipped: list = []
    for json_path in sorted(POSTS_DIR.glob("*.json"), reverse=True):
        sidecar = json.loads(json_path.read_text(encoding="utf-8"))
        # Ensure the in-memory sidecar carries author metadata for the
        # landing-page byline, even if the on-disk JSON predates this layer.
        sidecar.setdefault("author_name", AUTHOR_NAME)
        sidecar.setdefault("author_title", AUTHOR_TITLE)

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
        page_url="https://chinamilwatch.org/the-pla-watch/",
        latest_veil=latest_veil,
    )
    (PLA_WATCH_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"Wrote {(PLA_WATCH_DIR / 'index.html').relative_to(ROOT)}")

    archive_html = archive_tmpl.render(
        posts=sidecars, root_path="../",
        page_url="https://chinamilwatch.org/the-pla-watch/archive.html",
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
        page_url="https://chinamilwatch.org/the-pla-watch/terms.html",
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
