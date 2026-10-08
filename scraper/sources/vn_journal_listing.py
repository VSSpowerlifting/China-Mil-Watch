"""Offline-only English National Defence Journal category-list discovery contract.

The English site has four observed category pages, each with article links.
Their numeric IDs are stable. Links may repeat within and across pages.
This module parses supplied HTML only; it never fetches, stores or publishes
article prose, asserts an exhaustive date feed, follows pagination, or
activates a shadow/production collector.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from scraper.sources import vn_defence_journal as journal

CATEGORY_URLS = {
    "news": "https://tapchiqptd.vn/en/news-54.html",
    "theory-and-practice": "https://tapchiqptd.vn/en/theory-and-practice-56.html",
    "events-and-comments": "https://tapchiqptd.vn/en/events-and-comments-57.html",
    "research-and-discussion": "https://tapchiqptd.vn/en/research-and-discussion-58.html",
}
DATE_STAMP = re.compile(
    r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December) \d{1,2}, \d{4}, \d{1,2}:\d{2} \(GMT\+7\)"
)
SHORT_DATE = re.compile(r"(?<!\d)\d{1,2}/\d{1,2}/\d{4}(?!\d)")
MAX_CANDIDATES = 150
MAX_BYTES = 256_000


class ListingRefused(ValueError):
    pass


@dataclass(frozen=True)
class ListingCandidate:
    source_identity: str
    canonical_url: str
    category_from_permalink: str
    category_page: str
    date_hint: Optional[str]
    # This is not permission to archive prose or an authoritative article date.
    article_date_verified: bool = False


@dataclass(frozen=True)
class ListingObservation:
    category_page: str
    candidates: tuple[ListingCandidate, ...]
    duplicate_links: int
    dated_hint_count: int
    completeness_proven: bool = False
    pagination_verified: bool = False


def validate_listing_url(url):
    if url not in CATEGORY_URLS.values():
        raise ListingRefused("unexpected journal category URL")
    return next(category for category, known in CATEGORY_URLS.items() if known == url)


def _candidate_url(href, listing_url):
    url = urljoin(listing_url, href.strip())
    try:
        canonical = journal.canonical_article_url(url)
        ident = journal.article_identity(url)
    except (ValueError, TypeError):
        return None
    if canonical != url:
        return None
    section = urlsplit(url).path.split("/")[2]
    return ident, canonical, section


def _local_date_hint(anchor, canonical_url):
    """Only a date co-located with ONE unique article inside a small block.

    The global site clock and sidebars must never supply an article date.
    If attribution is uncertain, retain null rather than guessing.
    """
    parent = anchor
    for _ in range(3):
        parent = parent.parent
        if not isinstance(parent, Tag) or parent.name in ("html", "body", "form"):
            break
        if parent.name not in ("div", "p", "li", "td", "article"):
            continue
        # The publisher places a live site clock in #subTopMenu-time.
        # Some outer layout wrappers also contain only one article link;
        # their clock must NEVER become that article's publication hint.
        # A genuinely local date inside the smaller article row remains
        # admissible; only this contaminated ancestor is skipped.
        if parent.select_one("#subTopMenu-time") is not None:
            continue
        text = parent.get_text(" ", strip=True)
        if len(text) > 650:
            continue
        links = set()
        for link in parent.select("a[href]"):
            candidate = _candidate_url(link.get("href", ""), canonical_url)
            if candidate:
                links.add(candidate[1])
        if links != {canonical_url}:
            continue
        found = DATE_STAMP.findall(text)
        if len(found) == 1:
            try:
                return journal.stated_date(found[0])
            except ValueError as exc:
                raise ListingRefused("inconsistent printed listing date") from exc
        if len(found) == 0:
            short = SHORT_DATE.findall(text)
            if len(short) == 1:
                from datetime import datetime
                try:
                    return datetime.strptime(short[0], "%m/%d/%Y").date().isoformat()
                except ValueError as exc:
                    raise ListingRefused("invalid printed listing date") from exc
    return None


def parse_category_html(html, listing_url):
    category = validate_listing_url(listing_url)
    if len(html.encode("utf-8")) > MAX_BYTES:
        raise ListingRefused("HTML exceeds research byte budget")
    soup = BeautifulSoup(html, "html.parser")
    if not soup.html or not soup.body:
        raise ListingRefused("missing complete journal HTML")
    found = {}
    repeats = 0
    for a in soup.select("a[href]"):
        triple = _candidate_url(a.get("href", ""), listing_url)
        if triple is None:
            continue
        ident, canonical, sector = triple
        date_hint = _local_date_hint(a, canonical)
        if ident in found:
            previous = found[ident]
            if canonical != previous.canonical_url:
                raise ListingRefused("numeric ID points to different canonical URLs")
            if date_hint and previous.date_hint and date_hint != previous.date_hint:
                raise ListingRefused("conflicting listing date hints")
            if date_hint and not previous.date_hint:
                found[ident] = ListingCandidate(ident, canonical, sector, category, date_hint)
            repeats += 1
            continue
        found[ident] = ListingCandidate(ident, canonical, sector, category, date_hint)
        if len(found) > MAX_CANDIDATES:
            raise ListingRefused("too many article links on bounded category page")
    if not found:
        raise ListingRefused("no canonical journal article links on category page")
    candidates = tuple(found[x] for x in sorted(found, key=lambda k: int(k.split(":")[1]), reverse=True))
    return ListingObservation(category, candidates, repeats,
                              sum(item.date_hint is not None for item in candidates))


def merge_category_observations(observations):
    """Union listing identities while never promising historical completeness."""
    pages = {}
    merged = {}
    for o in observations:
        if o.category_page in pages:
            raise ListingRefused("duplicate category listing observation")
        pages[o.category_page] = o
        for rec in o.candidates:
            before = merged.get(rec.source_identity)
            if before and before.canonical_url != rec.canonical_url:
                raise ListingRefused("category sources disagree about one article ID")
            # A date hint seen only in a sidebar is not enough to approve any
            # publication date; retain a hint at most, never verified=True.
            if before is None or (before.date_hint is None and rec.date_hint):
                merged[rec.source_identity] = rec
            elif before.date_hint and rec.date_hint and before.date_hint != rec.date_hint:
                raise ListingRefused("different category listings give inconsistent dates")
    return {
        "unique_observed_article_count": len(merged),
        "observed_category_count": len(pages),
        "all_four_categories_observed": set(pages) == set(CATEGORY_URLS),
        "dated_hint_count": sum(r.date_hint is not None for r in merged.values()),
        "full_date_bounded_completeness_proven": False,
        "pagination_proven": False,
        "source_body_retention_authorized": False,
        "source_article_ids": sorted(merged),
    }
