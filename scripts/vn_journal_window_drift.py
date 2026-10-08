"""Compare metadata-only National Defence Journal listing observations offline.

Never performs HTTP, reads production state, captures publisher text, or
establishes historical completeness. Each observation is a bounded view of
links visible on four English category pages at one measured instant.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "ipr-vndj-listing-observation/1"
SOURCE = "vn_national_defence_journal_en"
CATEGORIES = {
    "news": "https://tapchiqptd.vn/en/news-54.html",
    "theory-and-practice": "https://tapchiqptd.vn/en/theory-and-practice-56.html",
    "events-and-comments": "https://tapchiqptd.vn/en/events-and-comments-57.html",
    "research-and-discussion": "https://tapchiqptd.vn/en/research-and-discussion-58.html",
}
ID = re.compile(r"vndj-en:([0-9]{4,9})\Z")
ARTICLE = re.compile(r"/en/(news|theory-and-practice|events-and-comments|research-and-discussion)/[a-z0-9]+(?:-[a-z0-9]+)*/([0-9]{4,9})\.html\Z")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")
MAX_CANDIDATES_PER_CATEGORY = 150


class ObservationRefused(ValueError):
    """Input is ambiguous or could misrepresent its provenance."""


def _fields(obj, required, where):
    if not isinstance(obj, dict) or set(obj) != set(required):
        raise ObservationRefused("%s has unexpected or missing fields" % where)


def _iso_day(value):
    if not isinstance(value, str) or not DAY.fullmatch(value):
        raise ObservationRefused("malformed date hint")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise ObservationRefused("invalid date hint") from exc


def _stamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ObservationRefused("observed_at must be an explicit UTC second")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise ObservationRefused("invalid UTC observation instant") from exc
    return parsed


def _validate_candidate(candidate):
    _fields(candidate, ("source_identity", "canonical_url", "date_hint"), "candidate")
    ident, url, hint = candidate["source_identity"], candidate["canonical_url"], candidate["date_hint"]
    if not isinstance(ident, str) or not ID.fullmatch(ident):
        raise ObservationRefused("invalid journal identity")
    if not isinstance(url, str) or len(url) > 300:
        raise ObservationRefused("invalid canonical URL")
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "tapchiqptd.vn"
            or parts.query or parts.fragment or parts.username or parts.password or parts.port is not None):
        raise ObservationRefused("not a canonical desktop English permalink")
    match = ARTICLE.fullmatch(parts.path)
    if not match or match.group(2) != ID.fullmatch(ident).group(1):
        raise ObservationRefused("article ID and canonical URL disagree")
    # A recommendations sidebar may link the same URL from another category.
    # Permalink category is never inferred from listing page membership.
    if hint is not None:
        _iso_day(hint)
    return ident, url, hint


def validate_observation(payload):
    """Return validated sets by category, never infer source completeness."""
    _fields(payload, ("schema", "source_slug", "observed_at", "observation_id",
                      "sections", "source_html_retained", "article_text_retained",
                      "pagination_proven", "historical_completeness_proven"), "observation")
    if payload["schema"] != SCHEMA or payload["source_slug"] != SOURCE:
        raise ObservationRefused("wrong source/observation schema")
    instant = _stamp(payload["observed_at"])
    if not isinstance(payload["observation_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{5,80}", payload["observation_id"]):
        raise ObservationRefused("invalid observation identifier")
    for name in ("source_html_retained", "article_text_retained", "pagination_proven", "historical_completeness_proven"):
        if payload[name] is not False:
            raise ObservationRefused("observations may not claim content retention or completeness")
    if not isinstance(payload["sections"], list) or len(payload["sections"]) != len(CATEGORIES):
        raise ObservationRefused("require one observation per category")
    seen_pages, canonical_by_id, date_by_id, indexed = set(), {}, {}, {}
    for section in payload["sections"]:
        _fields(section, ("category", "listing_url", "response_sha256", "candidates"), "section")
        category = section["category"]
        if not isinstance(category, str) or category not in CATEGORIES or category in seen_pages:
            raise ObservationRefused("unexpected/repeated category")
        seen_pages.add(category)
        if section["listing_url"] != CATEGORIES[category]:
            raise ObservationRefused("unverified category URL")
        if not isinstance(section["response_sha256"], str) or not HASH.fullmatch(section["response_sha256"]):
            raise ObservationRefused("invalid response digest")
        candidates = section["candidates"]
        if not isinstance(candidates, list) or not candidates or len(candidates) > MAX_CANDIDATES_PER_CATEGORY:
            raise ObservationRefused("unbounded candidate list")
        ids = set()
        for candidate in candidates:
            ident, url, hint = _validate_candidate(candidate)
            if ident in ids:
                raise ObservationRefused("repeated identity in one category")
            ids.add(ident)
            if ident in canonical_by_id and canonical_by_id[ident] != url:
                raise ObservationRefused("one identity has two canonical URLs")
            canonical_by_id[ident] = url
            if hint and ident in date_by_id and date_by_id[ident] != hint:
                raise ObservationRefused("contradictory listing date hints")
            if hint:
                date_by_id[ident] = hint
        indexed[category] = ids
    if set(indexed) != set(CATEGORIES):
        raise ObservationRefused("four-category observation incomplete")
    return instant, indexed, canonical_by_id


def _ordered(ids):
    return sorted(ids, key=lambda v: int(ID.fullmatch(v).group(1)))


def compare_observations(observations):
    """Report visible-link turnover; absent IDs do not imply deleted articles."""
    if not isinstance(observations, list) or len(observations) < 2:
        raise ObservationRefused("need at least two observation snapshots")
    validated = [validate_observation(item) for item in observations]
    canonical_history = {}
    for _, _, canonical_by_id in validated:
        for ident, url in canonical_by_id.items():
            if ident in canonical_history and canonical_history[ident] != url:
                raise ObservationRefused("canonical URL changed for one ID across observations")
            canonical_history[ident] = url
    if len(set(x["observation_id"] for x in observations)) != len(observations):
        raise ObservationRefused("duplicate evidence snapshot identity")
    for i in range(1, len(validated)):
        if validated[i][0] <= validated[i - 1][0]:
            raise ObservationRefused("observations must have increasing UTC instants")
    history = {k: set(validated[0][1][k]) for k in CATEGORIES}
    history["union"] = set().union(*validated[0][1].values())
    transitions = []
    for i in range(1, len(validated)):
        before, after = validated[i - 1][1], validated[i][1]
        changes = {}
        for category in list(CATEGORIES) + ["union"]:
            old = before[category] if category != "union" else set().union(*before.values())
            new = after[category] if category != "union" else set().union(*after.values())
            added = new - old
            changes[category] = {
                "before_visible": len(old),
                "after_visible": len(new),
                "retained": len(new & old),
                "first_observed_ids": _ordered(added - history[category]),
                "reappeared_ids": _ordered(added & history[category]),
                "no_longer_visible_ids": _ordered(old - new),
            }
            history[category].update(new)
        transitions.append({
            "from": observations[i - 1]["observation_id"],
            "to": observations[i]["observation_id"],
            "from_observed_at": observations[i - 1]["observed_at"],
            "to_observed_at": observations[i]["observed_at"],
            "sections": changes,
        })
    return {
        "schema": "ipr-vndj-window-drift-report/1",
        "source_slug": SOURCE,
        "observation_count": len(observations),
        "transitions": transitions,
        "historical_completeness_proven": False,
        "forward_collection_reliability_proven": False,
        "publisher_deletion_inferred": False,
        "publication_date_verified": False,
        "description": "Visible listing membership only; never publisher deletion, historical completeness, or an article publication date.",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("snapshots", nargs="+", help="at least two metadata-only JSON observations, in time order")
    args = ap.parse_args(argv)
    if len(args.snapshots) < 2:
        ap.error("at least two snapshots required")
    snapshots = []
    for item in args.snapshots:
        path = Path(item)
        if path.stat().st_size > 200_000:
            raise ObservationRefused("snapshot exceeds metadata-only size cap")
        snapshots.append(json.loads(path.read_text(encoding="utf-8")))
    print(json.dumps(compare_observations(snapshots), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
