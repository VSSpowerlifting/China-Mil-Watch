"""Render only explicitly registered Korean government text-only originals.

This is a read-only projection, NEVER an admission or publication-authority
validator. Release registration must occur separately, after authenticated
original, exact-license, exception, and owner-release checks. Empty registry
always creates zero new original pages.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "research" / "korea_published_original_texts.json"
ORIGINAL_DIR = ROOT / "research" / "korea_published_original_texts"
SCHEMA = "ipr-korea-public-original-text-index/1"
ROUTE_PREFIX = "korea-originals/"
URL_PREFIX = "https://www.korea.kr/briefing/pressReleaseView.do?newsId="
ARTICLE = re.compile(r"korea-policy:([0-9]{9})\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
GIT = re.compile(r"[0-9a-f]{40}\Z")
FIELDS = frozenset((
    "source_identity", "official_url", "publisher_posted_date",
    "source_git_commit", "original_text_sha256", "policy_sha256",
    "source_html_sha256", "release_decision_sha256", "released_at_utc",
))


class PublishedKoreaHold(ValueError):
    """Static safe machine codes only, no Korean source content."""


def require(ok, reason):
    if not ok:
        raise PublishedKoreaHold(reason)


def read_release_index(index=INDEX, original_dir=ORIGINAL_DIR):
    """Return pinned published texts, or no texts when the index is empty."""
    index = Path(index)
    original_dir = Path(original_dir)
    require(index.is_file() and not index.is_symlink()
            and index.stat().st_size <= 250_000,
            "korea_public_original_registry_unavailable")
    try:
        payload = json.loads(index.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise PublishedKoreaHold("korea_public_original_registry_invalid") from None
    require(type(payload) is dict and set(payload) == {"schema", "records"}
            and payload["schema"] == SCHEMA and type(payload["records"]) is list
            and len(payload["records"]) <= 1000,
            "korea_public_original_registry_invalid")
    results, known = [], set()
    for rec in payload["records"]:
        require(type(rec) is dict and set(rec) == FIELDS,
                "korea_public_original_row_unrecognized")
        ident = rec["source_identity"]
        matched = ARTICLE.fullmatch(ident) if type(ident) is str else None
        require(matched is not None and ident not in known,
                "korea_public_original_identity_invalid")
        known.add(ident)
        rid = matched.group(1)
        require(rec["official_url"] == URL_PREFIX + rid,
                "korea_public_original_official_url_mismatch")
        require(all(type(rec[key]) is str and HEX.fullmatch(rec[key])
                    for key in ("original_text_sha256", "policy_sha256",
                                "source_html_sha256", "release_decision_sha256"))
                and type(rec["source_git_commit"]) is str
                and GIT.fullmatch(rec["source_git_commit"]),
                "korea_public_original_digest_or_custody_missing")
        try:
            d = datetime.strptime(rec["publisher_posted_date"], "%Y-%m-%d")
            t = datetime.strptime(rec["released_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            raise PublishedKoreaHold("korea_public_original_date_invalid") from None
        require(d.strftime("%Y-%m-%d") == rec["publisher_posted_date"]
                and t >= d,
                "korea_public_original_date_invalid")
        path = original_dir / (rid + ".txt")
        require(path.is_file() and not path.is_symlink()
                and 80 <= path.stat().st_size <= 200000,
                "korea_public_original_text_missing_or_oversize")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == rec["original_text_sha256"],
                "korea_public_original_text_hash_drift")
        try:
            body = raw.decode("utf-8", "strict")
        except UnicodeError:
            raise PublishedKoreaHold("korea_public_original_text_not_utf8") from None
        require(body.strip() and not any(
            ord(ch) < 32 and ch not in "\r\n\t" for ch in body),
            "korea_public_original_text_unsafe")
        results.append({
            **rec,
            "news_id": rid,
            "route": ROUTE_PREFIX + rid + ".html",
            "text_original": body,
            "issuer_label": "Republic of Korea Ministry of National Defense",
            "publisher_label": "Republic of Korea Policy Briefing",
        })
    return sorted(results, key=lambda r: (r["publisher_posted_date"], r["news_id"]),
                  reverse=True)


# Rendering and independent deployed-readback verification share this exact
# deterministic source-page projection. It deliberately uses the SAME base.html
# template as the rest of the site rather than inventing a second website shell.
TEMPLATES = ROOT / "site" / "preview" / "templates"
PUBLIC_ORIGIN = "https://indopacificrecord.org"
NOINDEX_TAG = '<meta name="robots" content="noindex, nofollow">'
TAGLINE = ("Official defense and security texts, preserved as published and "
           "analyzed in context.")


def render_original_page(record, *, site_origin=PUBLIC_ORIGIN):
    """Render qualified original inside shared IPR chrome.

    A missing origin is a safe, noindex private/candidate preview. The public
    origin replaces the SAME noindex tag and adds the SAME canonical/social
    metadata as the ordinary site builder. No registration or rights grant
    happens here; source text is only emitted after read_release_index().
    """
    rid = record["news_id"]
    require(type(rid) is str and re.fullmatch(r"[0-9]{9}", rid)
            and record["route"] == ROUTE_PREFIX + rid + ".html"
            and record["official_url"] == URL_PREFIX + rid
            and type(record["text_original"]) is str
            and record["text_original"].strip(),
            "korea_original_page_identity_mismatch")
    require(site_origin is None or site_origin == PUBLIC_ORIGIN,
            "korea_original_page_origin_unrecognized")
    # Import templating only for actual HTML projection. Source-identity and
    # hash verification remain stdlib-only for lightweight collector jobs.
    from jinja2 import Environment, FileSystemLoader
    from core.edition_identity import COLLECTION_NAME
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=True, trim_blocks=True, lstrip_blocks=True)
    # base.html is compiled in full even if the snapshot-only branch is not
    # active on this source page; register its custom filter deterministically.
    env.filters["reader_date"] = lambda day: str(day)
    page = env.get_template("korea_original.html").render(
        original=record, page=record["route"], nested=True,
        title="Indo-Pacific Record", tagline=TAGLINE,
        mode="indo-pacific-record",
        maintainer={"name": "Benjamin Yang", "email": "ben.yang@gwmail.gwu.edu"},
        collection_name=COLLECTION_NAME,
        live_base=PUBLIC_ORIGIN, desks=[], timelines=[],
        review_mode=False, run_status=None,
    )
    require(page.count(NOINDEX_TAG) == 1,
            "korea_original_page_preview_indexability_invalid")
    if site_origin is None:
        return page
    # Byte-for-byte equivalent to the single origin switch in
    # site/preview/generate_preview.py. The readback verifier can thus re-render
    # the exact production HTML without a mutable build or production DB.
    canonical = site_origin + "/" + record["route"]
    card = site_origin + "/social-card.png"
    metadata = "\n".join([
        '<link rel="canonical" href="%s">' % html.escape(canonical, quote=True),
        '<meta property="og:url" content="%s">' % html.escape(canonical, quote=True),
        '<meta property="og:image" content="%s">' % card,
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="Indo-Pacific Record">',
        '<meta name="twitter:image" content="%s">' % card,
        '<meta name="twitter:image:alt" content="Indo-Pacific Record">',
    ])
    return page.replace(NOINDEX_TAG, metadata, 1)
