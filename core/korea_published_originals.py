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


def render_original_page(record):
    """Re-render verified Korean original bytes as escaped, attributable text."""
    e = lambda value: html.escape(str(value), quote=True)
    rid = record["news_id"]
    require(type(rid) is str and re.fullmatch(r"[0-9]{9}", rid)
            and record["route"] == ROUTE_PREFIX + rid + ".html"
            and record["official_url"] == URL_PREFIX + rid,
            "korea_original_page_identity_mismatch")
    title = "Korean MND official release " + rid
    canonical = "https://indopacificrecord.org/" + record["route"]
    markup = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + e(title) + ' — Indo-Pacific Record</title>'
        '<meta name="description" content="Licensed Korean-language official source text, attributed to the Republic of Korea government.">'
        '<link rel="canonical" href="' + e(canonical) + '">'
        '<link rel="stylesheet" href="../styles.css">'
        '</head><body><main style="max-width:76ch;margin:2rem auto;padding:1rem;">'
        '<p><a href="../korea.html">← South Korea Desk</a></p>'
        '<h1 lang="en">' + e(title) + '</h1>'
        '<p lang="en"><strong>Official Korean government source text</strong> '
        '— not an IPR fact-check or independent endorsement of the claims.</p>'
        '<p lang="en">Issuer: Republic of Korea Ministry of National Defense; '
        'republication: Republic of Korea Policy Briefing.</p>'
        '<p lang="en">Publisher posted: ' + e(record["publisher_posted_date"])
        + ' · <a href="' + e(record["official_url"])
        + '" rel="noopener noreferrer">Original official release</a></p>'
        '<p lang="en">Text reproduced with attribution under the article-specific '
        '<a href="https://www.korea.kr/guide/copyRight.do">KOGL Type 1 text-use '
        'notice and publisher terms</a>. English translations, photographs, '
        'HWPX attachments and other media are not included. '
        'The Korean text is presented without editorial changes.</p>'
        '<p lang="en">Source version SHA-256: <code>'
        + e(record["original_text_sha256"]) + '</code></p>'
        '<article aria-label="Verbatim Korean-language original"><pre lang="ko" '
        'style="white-space:pre-wrap;overflow-wrap:anywhere;">'
        + e(record["text_original"]) + '</pre></article>'
        '</main></body></html>'
    )
    return markup
