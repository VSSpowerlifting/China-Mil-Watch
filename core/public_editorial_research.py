"""Approved IPR-authored desk research, linking official originals without rehosting.

This is an *editorial publication index*, not a collector, publisher-original
archive, human approval substitute, or assertion of private preservation.
Every record must correspond to a separately approved and actually published
IPR-authored Brief. Returned rows contain bibliographic metadata only.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "research/approved_desk_research.json"
SCHEMA = "ipr-permanent-editorial-desk-research/1"
MAX_BYTES = 131072
SHA = re.compile(r"[a-f0-9]{40}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
BRIEF = re.compile(r"briefs/[a-z0-9][a-z0-9-]{2,110}\.html\Z")
HOSTS = {
    "ph_afp_articles": ("philippines", "www.afp.mil.ph"),
    "ph_nsc_official_statements": ("philippines", "nsc.gov.ph"),
    "id_kemhan_news": ("indonesia", "www.kemhan.go.id"),
    "kr_policy_mnd_releases": ("korea", "www.korea.kr"),
    "vn_government_news_editorial": ("vietnam", "baochinhphu.vn"),
    "vn_mps_foreign_affairs_vi": ("vietnam", "bocongan.gov.vn"),
    "vn_moit_energy_vi": ("vietnam", "moit.gov.vn"),
    "vn_moit_foundational_industry_vi": ("vietnam", "moit.gov.vn"),
    "jp_mod_news_ja": ("japan", "www.mod.go.jp"),
    "jp_jcg_news_en": ("japan", "www.kaiho.mlit.go.jp"),
}
EXACT_ENTRY = frozenset((
    "desk", "ipr_page", "ipr_title", "published_on", "approved_by",
    "approved_on", "approval_commit", "source_links",
))
EXACT_SOURCE = frozenset((
    "source_slug", "publisher_url", "title_original",
    "publisher_date", "issuer", "source_identity",
    "source_state_commit", "capture_sha256",
))


class PublicationHold(ValueError):
    pass


def demand(yes, reason):
    if not yes:
        raise PublicationHold(reason)


def no_duplicate_pairs(pairs):
    result = {}
    for name, value in pairs:
        demand(name not in result, "duplicate catalog JSON key")
        result[name] = value
    return result


def canonical_date(value):
    demand(type(value) is str, "publication date missing")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise PublicationHold("invalid publication date") from exc
    demand(d.isoformat() == value, "noncanonical publication date")
    return d


def official_url(value, host):
    demand(type(value) is str and 0 < len(value) <= 2048 and
           not any(ord(c) <= 32 or ord(c) == 127 for c in value),
           "invalid official source URL")
    try:
        p = urlsplit(value)
        ok = p.scheme == "https" and p.hostname == host and p.port is None
    except ValueError:
        ok = False
        p = None
    demand(ok and not p.username and not p.password and
           not p.fragment and p.path.startswith("/") and
           not p.path.startswith("//") and "\\" not in value,
           "official source host or path not allowlisted")
    return value


def readable(value, what, limit=350):
    demand(type(value) is str and 4 <= len(value.strip()) <= limit and
           value == value.strip() and "\x00" not in value,
           "invalid " + what)
    return value


def load_catalog(path=CATALOG, *, today=None):
    """Fail closed. No external reads; no writer, deployment or authorizer."""
    path = Path(path)
    demand(path.is_file() and not path.is_symlink() and
           path.stat().st_size <= MAX_BYTES, "missing or excessive catalog")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"),
                         object_pairs_hook=no_duplicate_pairs,
                         parse_constant=lambda _: (_ for _ in ()).throw(
                             PublicationHold("invalid numeric constant")))
    except (ValueError, UnicodeError) as exc:
        raise PublicationHold("unreadable publication catalog") from exc
    demand(type(raw) is dict and set(raw) == {"schema", "entries"}
           and raw["schema"] == SCHEMA, "unknown publication catalog schema")
    entries = raw["entries"]
    demand(type(entries) is list and len(entries) <= 40,
           "publication entries exceed reviewed limit")
    now = today or datetime.now(timezone.utc).date()
    seen_pages, accepted = set(), []
    for record in entries:
        demand(type(record) is dict and set(record) == EXACT_ENTRY,
               "record has unapproved publication fields")
        desk, page = record["desk"], record["ipr_page"]
        demand(desk in ("philippines", "indonesia", "korea", "vietnam", "japan")
               and type(page) is str and BRIEF.fullmatch(page) is not None,
               "unknown desk or non-IPR Brief route")
        demand(page not in seen_pages, "duplicate IPR publication route")
        seen_pages.add(page)
        title = readable(record["ipr_title"], "IPR-authored title")
        approved_by = readable(record["approved_by"], "named editor", 120)
        issued = canonical_date(record["published_on"])
        reviewed = canonical_date(record["approved_on"])
        demand(reviewed <= issued <= now, "publication approval chronology invalid")
        demand(type(record["approval_commit"]) is str and
               SHA.fullmatch(record["approval_commit"]),
               "publisher-approved Brief must be pinned to a reviewed commit")
        source_links = record["source_links"]
        demand(type(source_links) is list and 1 <= len(source_links) <= 20,
               "IPR Brief needs bounded official source links")
        seen_urls, citations = set(), []
        for source in source_links:
            demand(type(source) is dict and set(source) == EXACT_SOURCE,
                   "source contains original body, photograph or unknown field")
            slug = source["source_slug"]
            demand(slug in HOSTS and HOSTS[slug][0] == desk,
                   "publisher source not scoped to country")
            url = official_url(source["publisher_url"], HOSTS[slug][1])
            demand(url not in seen_urls, "duplicated official original")
            seen_urls.add(url)
            source_date = canonical_date(source["publisher_date"])
            demand(source_date <= issued, "original postdates IPR publication")
            original = readable(source["title_original"], "original title", 700)
            issuer = readable(source["issuer"], "issuer", 160)
            identity = readable(source["source_identity"], "source identity", 240)
            commit, digest = source["source_state_commit"], source["capture_sha256"]
            demand((commit is None and digest is None) or
                   (type(commit) is str and SHA.fullmatch(commit) and
                    type(digest) is str and DIGEST.fullmatch(digest)),
                   "capture digest must have exact immutable source revision")
            citations.append({
                "source_slug": slug, "publisher_url": url,
                "title_original": original, "publisher_date": source_date.isoformat(),
                "issuer": issuer, "source_identity": identity,
                # These are identities, NOT proof of a copy or of private custody.
                "source_state_commit": commit, "capture_sha256": digest,
            })
        accepted.append({
            "desk": desk, "ipr_page": page, "ipr_title": title,
            "published_on": issued.isoformat(), "approved_by": approved_by,
            "approved_on": reviewed.isoformat(), "approval_commit": record["approval_commit"],
            "source_links": citations,
        })
    return sorted(accepted, key=lambda row: (row["published_on"], row["ipr_page"]),
                  reverse=True)


def published_for_desk(desk, catalog=None):
    """Published IPR writing, never the private original-text source state."""
    entries = load_catalog() if catalog is None else catalog
    return [item for item in entries if item["desk"] == desk]
