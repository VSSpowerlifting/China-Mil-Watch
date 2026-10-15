"""Read-only HTML presentation of actually admitted AFP/Kemhan official links.

This renderer never reads original headlines, bodies, translations or model
text. It never infers live status from a candidate packet or empty table.
A release producer must independently verify the DB and deployed HTML bytes.
"""
from __future__ import annotations

import html
import re
import sqlite3
from datetime import date
from urllib.parse import urlsplit

from core.crossdesk_official_metadata_candidates import FAMILIES, exact_source_url
from core.regional_official_link_release import (
    EXPECTED_TABLE_COLUMNS, TABLE,
)

DESK_TO_FAMILY = {
    "philippines": "ph_afp_articles",
    "indonesia": "id_kemhan_news",
}
NEUTRAL_LABELS = {
    "ph_afp_articles": "AFP official source",
    "id_kemhan_news": "Kemhan Berita official source",
}
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")


class RegionalRenderHold(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise RegionalRenderHold(reason)


def read_live_links(conn: sqlite3.Connection, desk: str):
    """Rows are drawn only from the production admission table, never shadow."""
    need(desk in DESK_TO_FAMILY, "not_a_supported_regional_live_desk")
    family = DESK_TO_FAMILY[desk]
    schema = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % TABLE)}
    need(schema == EXPECTED_TABLE_COLUMNS,
         "regional_source_index_unavailable_or_schema_drift")
    records = conn.execute(
        "SELECT source_identity,canonical_official_url,publisher_posted_date,"
        "official_issuer,official_publisher,official_republisher,"
        "source_git_commit,metadata_version_sha256,release_proof_sha256,"
        "release_scope FROM regional_official_source_links "
        "WHERE desk=? AND source_family=? "
        "ORDER BY publisher_posted_date DESC,source_identity ASC",
        (desk, family),
    ).fetchall()
    need(len(records) <= 5000, "unexpectedly_large_source_index")
    unique_ids, unique_urls, result = set(), set(), []
    for r in records:
        (ident, url, day, issuer, publisher, republisher, git_sha,
         meta_sha, proof_sha, scope) = tuple(r)
        need(type(ident) is str and type(url) is str and
             type(day) is str and type(git_sha) is str and
             SHA40.fullmatch(git_sha) is not None and
             type(meta_sha) is str and SHA256.fullmatch(meta_sha) is not None and
             type(proof_sha) is str and SHA256.fullmatch(proof_sha) is not None and
             scope == "official_link_only" and
             issuer == FAMILIES[family]["issuer"] and
             publisher == FAMILIES[family]["publisher"] and
             republisher == FAMILIES[family]["republisher"],
             "published_reference_missing_authenticity")
        try:
            need(date.fromisoformat(day).isoformat() == day,
                 "noncanonical_publisher_date")
        except ValueError:
            raise RegionalRenderHold("invalid_publisher_date") from None
        # Recheck URI grammar at render-time. DB SQL checks alone do not fully
        # establish official HTTPS canonical URLs.
        exact_source_url(ident, url, day, family)
        need(ident not in unique_ids and url not in unique_urls,
             "duplicate_published_source_reference")
        unique_ids.add(ident); unique_urls.add(url)
        result.append({
            "source_identity": ident,
            "canonical_official_url": url,
            "publisher_posted_date": day,
            "label": NEUTRAL_LABELS[family],
        })
    return result


def render_live_links(conn: sqlite3.Connection, desk: str) -> str:
    """Small accessible link-only desk rail for *admitted* production rows."""
    rows = read_live_links(conn, desk)
    if not rows:
        return ""
    label = "Philippines AFP" if desk == "philippines" else "Indonesia Kemhan"
    lines = [
        '<section class="regional-official-source-links" '
        'data-source-scope="official-link-only" '
        'aria-label="%s official source references">' % html.escape(label, quote=True),
        '<h2>Verified official source references</h2>',
        '<p>Source URLs and publisher dates only; original articles are linked at '
        'their official websites.</p>',
        '<ul class="regional-source-reference-list">',
    ]
    for r in rows:
        url = html.escape(r["canonical_official_url"], quote=True)
        ident = html.escape(r["source_identity"], quote=True)
        day = html.escape(r["publisher_posted_date"], quote=True)
        safe_label = html.escape(r["label"], quote=True)
        lines.append(
            '<li data-official-source-id="%s"><a href="%s" rel="noopener noreferrer">'
            '%s</a> <time datetime="%s">%s</time></li>'
            % (ident, url, safe_label, day, day))
    lines += ["</ul>", "</section>"]
    return "\n".join(lines)
