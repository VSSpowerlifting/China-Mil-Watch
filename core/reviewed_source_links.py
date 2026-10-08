"""Human-reviewed, metadata-only source links for a non-live Vietnam Desk.

This is *not* a corpus ingest, archival record, qualification verdict, or Briefs
source-trail entry. The file contains manually verified bibliographic references
to the publisher's own pages. The renderer reads this separate surface without
changing desk status, counts, SQLite, shadow collection, or model selection.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "research" / "vietnam_reviewed_links.json"
SCHEMA = "vietnam-reviewed-source-links/1"
SOURCES = {
    "vn_mps_foreign_affairs_vi": ("bocongan.gov.vn", "Ministry of Public Security"),
    "vn_moit_energy_vi": ("moit.gov.vn", "Ministry of Industry and Trade"),
    "vn_moit_foundational_industry_vi": ("moit.gov.vn", "Ministry of Industry and Trade"),
}
CHECKS = ("source_page_opened", "title_checked", "publication_date_checked",
          "issuing_institution_checked", "link_publication_approved")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,80}$")


class ReviewedLinkError(ValueError):
    """Unsafe or unreviewed metadata cannot be displayed as verified."""


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReviewedLinkError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _require(condition, message):
    if not condition:
        raise ReviewedLinkError(message)


def _iso_date(value):
    _require(isinstance(value, str), "published/reviewed date must be a string")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ReviewedLinkError("invalid date") from exc
    _require(d.isoformat() == value, "date must be canonical YYYY-MM-DD")
    return d


def load_reviewed_links(path=DEFAULT_PATH, *, today=None):
    """Return display-ready, explicitly approved references, newest first.

    No field proves independent verification. An actual human must perform the
    stated checks; the schema makes their missing approvals fail closed.
    """
    path = Path(path)
    if not path.is_file():
        return []
    _require(not path.is_symlink(), "reviewed links file must not be a symlink")
    _require(path.stat().st_size <= 131072, "reviewed links file exceeds 128 KiB")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"),
                         object_pairs_hook=_no_duplicates,
                         parse_constant=lambda x: (_ for _ in ()).throw(
                             ReviewedLinkError("non-finite JSON constant")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewedLinkError("invalid reviewed links JSON") from exc
    _require(isinstance(raw, dict) and set(raw) == {"schema", "entries"},
             "file must contain schema and entries only")
    _require(raw["schema"] == SCHEMA, "unknown reviewed links schema")
    entries = raw["entries"]
    _require(isinstance(entries, list) and len(entries) <= 20,
             "entries must be a list of at most 20 reviewed links")
    current = today if today is not None else datetime.now(timezone.utc).date()
    seen_ids, seen_urls, accepted = set(), set(), []
    expected = {"id", "source_slug", "source_url", "title_original", "language",
                "published_date", "reviewed_by", "reviewed_on",
                "state_commit", "checks"}
    for item in entries:
        _require(isinstance(item, dict) and set(item) == expected,
                 "entry has missing or unexpected fields")
        ident = item["id"]
        _require(isinstance(ident, str) and _ID.fullmatch(ident),
                 "invalid entry identity")
        _require(ident not in seen_ids, "duplicate entry identity")
        seen_ids.add(ident)
        slug = item["source_slug"]
        _require(slug in SOURCES, "unregistered or research-disabled source")
        url = item["source_url"]
        _require(isinstance(url, str) and len(url) <= 2048, "invalid source URL")
        p = urlsplit(url)
        _require(p.scheme == "https" and p.hostname == SOURCES[slug][0]
                 and not p.username and not p.password and p.port is None
                 and p.path.startswith("/") and not p.fragment,
                 "URL must be an exact HTTPS official-source URL without fragment")
        _require(url not in seen_urls, "duplicate source URL")
        seen_urls.add(url)
        _require(isinstance(item["title_original"], str)
                 and 8 <= len(item["title_original"].strip()) <= 350
                 and item["title_original"] == item["title_original"].strip(),
                 "missing or invalid original-language title")
        _require(item["language"] == "vi", "source title must remain original Vietnamese")
        pub, reviewed = _iso_date(item["published_date"]), _iso_date(item["reviewed_on"])
        _require(pub <= reviewed <= current, "publication/review chronology is impossible")
        reviewer = item["reviewed_by"]
        _require(isinstance(reviewer, str) and 3 <= len(reviewer.strip()) <= 120,
                 "named human reviewer is required")
        _require(isinstance(item["state_commit"], str)
                 and _SHA.fullmatch(item["state_commit"]),
                 "pin the exact 40-character shadow state commit")
        checks = item["checks"]
        _require(isinstance(checks, dict) and set(checks) == set(CHECKS)
                 and all(checks[k] is True for k in CHECKS),
                 "five explicit human checks and publication approval required")
        accepted.append({
            "id": ident, "source_slug": slug,
            "source_name": SOURCES[slug][1], "source_url": url,
            "title_original": item["title_original"], "language": "vi",
            "published_date": item["published_date"],
            "reviewed_by": reviewer.strip(), "reviewed_on": item["reviewed_on"],
            "state_commit": item["state_commit"],
        })
    return sorted(accepted, key=lambda x: (x["published_date"], x["id"]), reverse=True)
