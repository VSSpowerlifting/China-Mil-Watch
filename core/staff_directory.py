"""Public editorial roster and exact published-Brief credit projection.

Staff membership is not an authorship claim. Historical attribution is never
rewritten; drafts and synthetic fixtures are never shown as published work.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


def load_staff(path: Path) -> tuple:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("staff roster must be a nonempty list")
    names, slugs, members = set(), set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"slug", "name", "role", "bio", "links"}:
            raise ValueError("staff record fields are invalid")
        slug = row["slug"]
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("invalid staff slug")
        if slug in slugs:
            raise ValueError("duplicate staff slug")
        for key in ("name", "role", "bio"):
            if not isinstance(row[key], str) or not row[key].strip():
                raise ValueError("missing staff " + key)
        if row["name"].casefold() in names:
            raise ValueError("duplicate staff name")
        if not isinstance(row["links"], dict):
            raise ValueError("invalid staff links")
        for label, url in row["links"].items():
            if (not isinstance(label, str) or not label.strip() or
                    not isinstance(url, str) or urlsplit(url).scheme != "https" or
                    not urlsplit(url).netloc):
                raise ValueError("public links must use HTTPS")
        names.add(row["name"].casefold())
        slugs.add(slug)
        members.append(dict(row, route="authors/" + slug + ".html"))
    return tuple(members)


def credited_works(collection, name: str) -> dict:
    """Exact named credits only, excluding private or synthetic entries."""
    authored, contributed = [], []
    for entry in collection.briefs:
        if entry.get("synthetic") or entry.get("is_review"):
            continue
        names = entry.get("author_names") or [entry.get("author_name")]
        if name in names:
            authored.append(entry)
            continue
        credit = (collection.sidecars.get(entry["slug"]) or {}).get("research_contributor") or {}
        if isinstance(credit, dict) and credit.get("name") == name:
            contributed.append(dict(entry, credit_role=credit.get("title") or
                                    "Research contributor"))
    return {"authored": tuple(authored), "contributed": tuple(contributed)}
