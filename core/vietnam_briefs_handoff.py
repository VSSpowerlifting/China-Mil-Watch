"""Offline Vietnam shadow candidates for Friday or Sunday Briefs handoffs.

This stage offers official-source *links to a human editor*, not evidence to
the model, production records, a qualified desk, or pre-approved brief claims.
A separate file is required for each week, so old shadow captures cannot be
silently carried forward.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "research" / "vietnam_briefs_candidates"
SCHEMA = "vietnam-briefs-human-review-candidates/1"
SOURCE = "vn_mps_foreign_affairs_vi"
SOURCE_HOST = "bocongan.gov.vn"
MAX_CANDIDATES = 5
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
IDENTITY = re.compile(r"^mps-vi:([1-9][0-9]{6,20})$")
FIELDS = {
    "source_identity", "source_slug", "canonical_url", "published_date",
    "original_title", "content_sha256", "editorial_angle", "review_status",
}
REVIEW_STATUS = "requires_independent_human_review"


class VietnamCandidateError(ValueError):
    """Refuse an ambiguous, stale, or untrusted candidate packet."""


def _fail_if(condition, reason):
    if condition:
        raise VietnamCandidateError(reason)


def _parse_date(value):
    _fail_if(not isinstance(value, str), "date must be a string")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise VietnamCandidateError("date is not YYYY-MM-DD") from exc
    _fail_if(parsed.isoformat() != value, "date must be canonical")
    return parsed


def _strict_pairs(pairs):
    result = {}
    for key, value in pairs:
        _fail_if(key in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def _clean_text(value, limit, field):
    _fail_if(not isinstance(value, str) or not value.strip()
             or len(value) > limit or value != value.strip()
             or any(ord(ch) < 32 or ord(ch) == 127 for ch in value),
             "invalid " + field)
    return value


def _candidate(item, start, cutoff):
    _fail_if(not isinstance(item, dict) or set(item) != FIELDS,
             "candidate has unknown or missing fields")
    _fail_if(item["source_slug"] != SOURCE, "source is not approved for this lane")
    _fail_if(item["review_status"] != REVIEW_STATUS,
             "a shadow candidate may not claim human approval")
    identity = item["source_identity"]
    match = IDENTITY.fullmatch(identity) if isinstance(identity, str) else None
    _fail_if(match is None, "invalid ministry source identity")
    raw_url = _clean_text(item["canonical_url"], 1500, "official source URL")
    try:
        url = urlsplit(raw_url)
        no_port = url.port is None
    except ValueError as exc:
        raise VietnamCandidateError("invalid official source URL") from exc
    _fail_if(not (
        url.scheme == "https" and url.hostname == SOURCE_HOST
        and url.username is None and url.password is None
        and no_port and not url.fragment and not url.query
        and url.path.startswith("/bai-viet/")
        and url.path.endswith("-" + match.group(1))
    ), "URL is not the exact MPS article corresponding to the source identity")
    published = _parse_date(item["published_date"])
    _fail_if(not start <= published <= cutoff,
             "candidate publication date falls outside this packet's Sunday-Friday source window")
    title = _clean_text(item["original_title"], 350, "original-language title")
    angle = _clean_text(item["editorial_angle"], 400, "unapproved editorial question")
    _fail_if(HEX64.fullmatch(str(item["content_sha256"])) is None,
             "missing pinned current content SHA-256")
    return {
        "source_identity": identity,
        "source_slug": SOURCE,
        "source_name": "Vietnam Ministry of Public Security",
        "canonical_url": raw_url,
        "published_date": published.isoformat(),
        "original_title": title,
        "content_sha256": item["content_sha256"],
        "editorial_angle": angle,
        "review_status": REVIEW_STATUS,
    }


def load_candidates(week_ending, as_of, *, directory=PACKS_DIR):
    """Load this exact Saturday's *human-review* pack, or no candidates.

    A missing pack is normal. A malformed or out-of-window pack is a hard
    failure, never an excuse to use stale or fabricated source material.
    """
    saturday = _parse_date(week_ending)
    cutoff = _parse_date(as_of)
    friday = saturday - timedelta(days=1)
    _fail_if(saturday.weekday() != 5 or cutoff not in (friday, saturday),
             "Vietnam candidate pack requires this Friday or Saturday cutoff")
    # The Friday packet is pinned to source versions reviewed for the
    # provisional handoff. A Sunday full-week draft must not silently treat
    # this packet as covering Saturday publications it has not captured.
    # Saturday additions require a separate, version-checked editorial review.
    start = saturday - timedelta(days=6)
    path = Path(directory) / (week_ending + ".json")
    # Even a dangling symlink is a configuration error, not a missing packet.
    _fail_if(path.is_symlink(), "unsafe candidate file")
    if not path.exists():
        return []
    _fail_if(not path.is_file(), "unsafe candidate file")
    _fail_if(path.stat().st_size > 25000, "candidate pack over 25KB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_strict_pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(
                              VietnamCandidateError("non-finite JSON not permitted")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise VietnamCandidateError("candidate file is not valid UTF-8 JSON") from exc
    _fail_if(not isinstance(data, dict) or set(data) !=
             {"schema", "week_ending", "state_commit", "candidates"},
             "candidate pack has unexpected or missing fields")
    _fail_if(data["schema"] != SCHEMA or data["week_ending"] != week_ending,
             "pack belongs to another date/schema")
    _fail_if(not isinstance(data["state_commit"], str)
             or HEX40.fullmatch(data["state_commit"]) is None,
             "source-state commit must be a full Git SHA")
    rows = data["candidates"]
    _fail_if(not isinstance(rows, list) or not 1 <= len(rows) <= MAX_CANDIDATES,
             "candidate pack must hold one to five items")
    items = [_candidate(row, start, friday) for row in rows]
    ids = [r["source_identity"] for r in items]
    urls = [r["canonical_url"] for r in items]
    _fail_if(len(set(ids)) != len(ids) or len(set(urls)) != len(urls),
             "duplicate candidate identity or URL")
    for item in items:
        item["state_commit"] = data["state_commit"]
    return sorted(items, key=lambda r: (r["published_date"],
                                       r["source_identity"]), reverse=True)
