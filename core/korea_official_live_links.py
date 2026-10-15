"""Read public Korea official-link metadata from the production SQLite table.

This is deliberately not the article feed. No title, body, media, translation,
analysis, original HWPX, signed reviewer or source Git path is returned.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from core.korea_official_metadata_admission import PREFIX

def load_live_korea_official_links(db_path, *, exclude=()):
    path = Path(db_path)
    if not path.is_file():
        raise ValueError("production_metadata_database_missing")
    excluded = set(exclude)
    if any(not isinstance(k, str) for k in excluded):
        raise ValueError("invalid_fixed_reference_id")
    db = sqlite3.connect("file:%s?mode=ro" % quote(str(path.resolve()), safe="/"), uri=True)
    try:
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='korea_official_source_records'").fetchone():
            # Existing deployed production database, before schema migration.
            return []
        rows = db.execute(
            "SELECT source_identity,canonical_official_url,publisher_posted_date, "
            "official_issuer,official_republisher "
            "FROM korea_official_source_records "
            "WHERE public_scope='official_link_only' "
            "ORDER BY publisher_posted_date DESC,source_identity DESC"
        ).fetchall()
    finally:
        db.close()
    out = []
    seen = set()
    for ident, url, day, issuer, republisher in rows:
        if (not isinstance(ident, str)
                or not ident.startswith("korea-policy:")
                or not ident[13:].isdigit() or len(ident[13:]) != 9
                or url != PREFIX + ident[13:]
                or issuer != "kr_mnd" or republisher != "kr_policy_briefing"
                or ident in seen):
            raise ValueError("admitted_official_link_provenance_invalid")
        seen.add(ident)
        if ident not in excluded:
            out.append({
                "source_identity": ident, "source_url": url,
                "published_date": day,
                "issuer_label": "Republic of Korea Ministry of National Defense",
                "republisher_label": "Republic of Korea Policy Briefing",
                "neutral_label": "MND official press release " + ident[13:],
            })
    return out
