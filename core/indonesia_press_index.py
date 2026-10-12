"""Frozen, first-party Kemhan Siaran Pers *external links* only.

The two publisher originals were page-level spotchecked on October 12, 2026.
No underlying body bytes or media are stored. This is not an independently
human-approved citation, licensed republication, corpus record, or a collector.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from core.indonesia_official_index import distinct, PublicIndexError, require

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "research" / "indonesia_official_press_links.json"
SCHEMA = "ipr-indonesia-kemhan-press-links/1"
CATEGORY = "https://www.kemhan.go.id/category/siaran-pers"
FIELDS = {"id", "url", "title_original", "published_date", "language", "press_number"}
ROOT_FIELDS = {"schema", "source_family", "publisher", "category_url",
               "snapshot_date", "editorial_status", "collection_status", "references"}
DATED = re.compile(r"/([0-9]{4})/([0-9]{2})/([0-9]{2})/[a-z0-9-]+\.html\Z")
PRESS = re.compile(r"SP/[1-9][0-9]*/(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)/2026/ROINFOHAN\Z")

# Exact URLs, original publisher titles, publication dates and printed
# press-release numbers; changes need a separate source-specific code review.
RELEASES = (
    (
        "id-press-2026-08",
        "https://www.kemhan.go.id/2026/08/23/kemhan-tegaskan-tidak-ada-larangan-penggunaan-hijab-bagi-kadet-universitas-pertahanan.html",
        "Kemhan Tegaskan Tidak Ada Larangan Penggunaan Hijab bagi Kadet Universitas Pertahanan",
        "2026-08-23",
        "SP/17/VIII/2026/ROINFOHAN",
    ),
    (
        "id-press-2026-03",
        "https://www.kemhan.go.id/2026/03/23/kemhan-dan-tni-siapkan-langkah-efisiensi-bbm-secara-terukur-operasional-pertahanan-tetap-menjadi-prioritas.html",
        "Kemhan dan TNI Siapkan Langkah Efisiensi BBM Secara Terukur, Operasional Pertahanan Tetap Menjadi Prioritas",
        "2026-03-23",
        "SP/10/III/2026/ROINFOHAN",
    ),
)


def validate(raw):
    require(type(raw) is dict and set(raw) == ROOT_FIELDS, "unrecognized press index fields")
    for key, value in (
        ("schema", SCHEMA),
        ("source_family", "id_kemhan_press"),
        ("publisher", "Kementerian Pertahanan Republik Indonesia"),
        ("category_url", CATEGORY),
        ("snapshot_date", "2026-10-12"),
        ("editorial_status", "official_pages_spotchecked_independent_human_review_pending"),
        ("collection_status", "press_parser_unregistered_no_shadow_state"),
    ):
        require(raw[key] == value and type(raw[key]) is str,
                "press index classification or provenance mutated: " + key)
    refs = raw["references"]
    require(type(refs) is list and len(refs) == len(RELEASES),
            "exact two frozen Kemhan press links required")
    results = []
    for item, expected in zip(refs, RELEASES):
        require(type(item) is dict and set(item) == FIELDS,
                "unexpected field, possibly original body or publisher media")
        require(item["language"] == "id", "not original-language release metadata")
        fields = (item["id"], item["url"], item["title_original"],
                  item["published_date"], item["press_number"])
        require(fields == expected, "unapproved or changed press reference")
        url, title = item["url"], item["title_original"]
        require(type(url) is str and type(title) is str and
                title == title.strip() and 8 <= len(title) <= 260 and
                not any(c in "<>\x00\r\n" for c in title),
                "unsafe original publisher headline")
        require(len(url) <= 350 and all(ord(c) > 32 and ord(c) < 127 for c in url),
                "unsafe original publisher URL")
        try:
            parsed = urlsplit(url)
            good_host = (parsed.scheme == "https" and
                         parsed.netloc == "www.kemhan.go.id" and
                         not parsed.query and not parsed.fragment and
                         not parsed.username and not parsed.password)
        except ValueError as exc:
            raise PublicIndexError("invalid Kemhan press URL") from exc
        require(good_host, "first-party HTTPS original required")
        match = DATED.fullmatch(parsed.path)
        require(match is not None, "dated canonical Kemhan press URL required")
        try:
            date_in_url = date(*map(int, match.groups())).isoformat()
            stated = date.fromisoformat(item["published_date"]).isoformat()
        except (ValueError, TypeError) as exc:
            raise PublicIndexError("invalid published press date") from exc
        require(date_in_url == stated == item["published_date"],
                "printed press date disagrees with URL")
        require(PRESS.fullmatch(item["press_number"]) is not None,
                "invalid publisher press-release number")
        results.append({
            "id": item["id"], "source_url": url,
            "title_original": title, "published_date": stated,
            "press_number": item["press_number"], "language": "id",
        })
    return results


def load(path=DEFAULT):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= 8192, "missing or unsafe Kemhan press metadata register")
    try:
        obj = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=distinct)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise PublicIndexError("invalid publisher press metadata JSON") from exc
    return validate(obj)
