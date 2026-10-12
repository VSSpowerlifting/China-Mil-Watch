"""Bounded PUBLIC navigation to official Indonesian publisher pages.

This is a source-directory aid, NOT a reviewed reference registry, content
license, archive/collection admission, or endorsement of publisher statements.
The four publisher titles/dates link outward; no original bodies are loaded.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "research" / "indonesia_official_source_links.json"
SCHEMA = "ipr-indonesia-external-source-links/1"
PINNED = "17dfae7e6e1e9e1142d81c89764f022ebf03552f"
IDS = ("id-01", "id-02", "id-03", "id-04")
FIELDS = {"id", "url", "title_original", "published_date", "language"}
EXPECTED = {"schema", "source_family", "publisher", "snapshot_date",
            "pinned_shadow_commit", "editorial_status", "collection_status",
            "references"}
PATH = re.compile(r"/([0-9]{4})/([0-9]{2})/([0-9]{2})/[a-z0-9-]+\.html\Z")


class PublicIndexError(ValueError):
    """Unexpected or unverified source-directory shape. Refuse to publish."""


def require(ok, reason):
    if not ok:
        raise PublicIndexError(reason)


def distinct(pairs):
    values = {}
    for key, value in pairs:
        require(key not in values, "repeated JSON field")
        values[key] = value
    return values


def validate(data):
    require(type(data) is dict and set(data) == EXPECTED, "unexpected index fields")
    require(data["schema"] == SCHEMA and data["source_family"] == "id_kemhan_news"
            and data["publisher"] == "Kementerian Pertahanan Republik Indonesia"
            and data["snapshot_date"] == "2026-10-11"
            and data["pinned_shadow_commit"] == PINNED
            and data["editorial_status"] == "publisher_links_not_independently_human_reviewed"
            and data["collection_status"] == "shadow_not_public_corpus",
            "public source-index provenance or status changed")
    entries = data["references"]
    require(type(entries) is list and len(entries) == 4,
            "this frozen pilot permits exactly four external publisher links")
    require([p.get("id") for p in entries if type(p) is dict] == list(IDS),
            "unrecognized or reordered pilot reference")
    seen = set()
    result = []
    for item in entries:
        require(type(item) is dict and set(item) == FIELDS,
                "unexpected metadata field (possibly private article data)")
        require(item["language"] == "id", "original title is not Indonesian")
        title = item["title_original"]
        require(type(title) is str and 8 <= len(title.strip()) <= 260
                and title == title.strip()
                and not any(ord(ch) < 32 or ch in "<>" for ch in title),
                "unsafe or missing Indonesian title")
        url = item["url"]
        require(type(url) is str and len(url) <= 350
                and not any(ord(ch) <= 32 or ord(ch) == 127 for ch in url),
                "unsafe official URL")
        try:
            parsed = urlsplit(url)
            exact_host = (parsed.scheme == "https"
                          and parsed.netloc == "www.kemhan.go.id"
                          and not parsed.username and not parsed.password
                          and not parsed.query and not parsed.fragment)
        except ValueError as exc:
            raise PublicIndexError("invalid official URL") from exc
        require(exact_host, "only exact first-party Kemhan HTTPS links are allowed")
        m = PATH.fullmatch(parsed.path)
        require(m is not None, "not a canonical dated Kemhan Berita link")
        try:
            url_date = date(*map(int, m.groups())).isoformat()
            meta_date = date.fromisoformat(item["published_date"]).isoformat()
        except (TypeError, ValueError) as exc:
            raise PublicIndexError("invalid official publication date") from exc
        require(url_date == item["published_date"] == meta_date,
                "publication date disagrees with official URL")
        require(url not in seen, "duplicate official publication")
        seen.add(url)
        result.append({
            "id": item["id"], "source_url": url, "title_original": title,
            "published_date": meta_date, "language": "id",
        })
    return result


def load(path=DEFAULT):
    path = Path(path)
    require(path.is_file() and not path.is_symlink()
            and path.stat().st_size <= 16384,
            "public source-index is absent, symlinked, or oversized")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=distinct)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicIndexError("cannot parse source index") from exc
    return validate(raw)
