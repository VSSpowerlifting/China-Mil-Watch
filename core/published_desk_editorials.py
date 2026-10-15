"""Explicit source-pinned catalogue of already published IPR Briefs on country desks.

This reader does not consume shadow originals, approve editorials or ingest source
material. It links an exact previously owner-approved Brief that is already part
of the published IPR Briefs collection. New editorial work still needs its own
pre-existing guarded approval and publication route before being indexed here.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
# Curated editorial routing, not source collector coverage or issue-wide tagging.
# Each addition requires a reviewed diff: exact manuscript digest, approval,
# source family and already-published page. Never infer from place name alone.
RELEASED = {
    "vietnam": (
        ("briefs/what-is-being-built-in-laos.json",
         "briefs/what-is-being-built-in-laos.html",
         "43ec5cc44ba724401235d976c73af6485566026d24114146878e0152cce3d0c1"),
    ),
}
ALLOWED_PUBLICATION = "Indo-Pacific Record"


class DeskEditorialError(ValueError):
    """A catalogue entry is not a previously approved published editorial."""


def require(value, reason):
    if not value:
        raise DeskEditorialError(reason)


def published_desk_editorials(desk_slug: str):
    """Return only compact public editorial metadata from pre-approved Briefs."""
    require(isinstance(desk_slug, str), "desk must be a string")
    rows = []
    for filename, route, sha in RELEASED.get(desk_slug, ()):
        require(filename.startswith("briefs/") and filename.endswith(".json")
                and route.startswith("briefs/") and route.endswith(".html")
                and ".." not in filename and ".." not in route,
                "invalid editorial file/route")
        manifest = ROOT / filename
        page = ROOT / "output" / route
        require(manifest.is_file() and not manifest.is_symlink(),
                "published Brief manifest unavailable")
        require(page.is_file() and not page.is_symlink(),
                "approved Brief is not actually in the public output tree")
        require(manifest.stat().st_size < 65536, "unexpected Brief metadata size")
        data = json.loads(manifest.read_text(encoding="utf-8"))
        require(isinstance(data, dict) and
                data.get("publication") == ALLOWED_PUBLICATION and
                data.get("editorial_status") == "approved" and
                data.get("manuscript_sha256") == sha and
                data.get("title") == "What Is Being Built in Laos?" and
                data.get("issue_number") == 18,
                "approved editorial identity does not match pinned manuscript")
        approval = data.get("approval")
        require(isinstance(approval, dict) and
                approval.get("approved_by") == "Benjamin Yang" and
                approval.get("approved_on") == "2026-10-13" and
                approval.get("reference") ==
                "https://github.com/VSSpowerlifting/China-Mil-Watch/pull/485#issuecomment-6138538619",
                "owner/editorial approval is not the pinned signed record")
        source_rows = data.get("publisher_references")
        require(isinstance(source_rows, list), "missing approved source trail")
        vn = [v for v in source_rows
              if isinstance(v, dict) and v.get("issuer") == "Government of Vietnam"
              and isinstance(v.get("url"), str)
              and urlsplit(v["url"]).scheme == "https"
              and urlsplit(v["url"]).hostname == "baochinhphu.vn"]
        require(len(vn) >= 2, "Vietnam source trail changed or missing")
        title, dek = data["title"], data.get("dek")
        require(isinstance(dek, str) and 30 <= len(dek) <= 500,
                "brief lacks a published editorial description")
        # Never export article-body paragraphs, source-body captures or images.
        rows.append({
            "title": title,
            "dek": dek,
            "route": route,
            "issue_number": data["issue_number"],
            "editorial_status": "approved",
            "source_note": "Vietnamese government originals; publisher claims attributed",
        })
    return rows
