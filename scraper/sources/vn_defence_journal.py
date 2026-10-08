"""National Defence Journal (Vietnam) English source identity — offline only.

The main and mobile sites are alternate layouts of ONE publication. This
module never makes network requests, captures source prose, or approves reuse.
A collector may only be activated after robots, layout and rights checks.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urlsplit, urljoin

from bs4 import BeautifulSoup

SOURCE_SLUG = "vn_national_defence_journal_en"
PUBLISHER = "National Defence Journal (Tạp chí Quốc phòng toàn dân)"
DESKTOP = "https://tapchiqptd.vn/en/default.html"
MOBILE = "https://m.tapchiqptd.vn/en"
HOME_URLS = frozenset((DESKTOP, MOBILE))
HOSTS = frozenset(("tapchiqptd.vn", "m.tapchiqptd.vn"))
CATEGORIES = frozenset(("news", "theory-and-practice",
                        "events-and-comments", "research-and-discussion"))
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
DESKTOP_ARTICLE = re.compile(
    rf"^/en/({ '|'.join(sorted(CATEGORIES)) })/({SLUG})/([0-9]{{4,9}})\.html$".replace(" ", ""))
MOBILE_ARTICLE = re.compile(
    rf"^/en/({ '|'.join(sorted(CATEGORIES)) })/({SLUG})-([0-9]{{4,9}})\.html$".replace(" ", ""))
DESKTOP_STAMP = re.compile(
    r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December) ([0-9]{1,2}), ([0-9]{4}), ([0-9]{2}):([0-9]{2}) \(GMT\+7\)$")
MOBILE_STAMP = re.compile(
    r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{4}) "
    r"([0-9]{1,2}):([0-9]{2}):([0-9]{2}) (AM|PM)$")


def _article_parts(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc not in HOSTS
            or parts.query or parts.fragment or parts.username or parts.password
            or parts.port is not None):
        raise ValueError("not a journal English article URL")
    pattern = DESKTOP_ARTICLE if parts.netloc == "tapchiqptd.vn" else MOBILE_ARTICLE
    match = pattern.fullmatch(parts.path)
    if match is None:
        raise ValueError("unknown journal article URL form")
    category, slug, number = match.groups()
    return category, slug, number


def canonical_article_url(url):
    """Normalize matching mobile/desktop article IDs to the desktop permalink.

    This deliberately rejects unknown redirects, languages, query strings
    and unrelated paths. No title- or text-based duplicate suppression.
    """
    category, slug, number = _article_parts(url)
    return f"https://tapchiqptd.vn/en/{category}/{slug}/{number}.html"


def article_identity(url):
    """Sitewide numeric article ID, stable across main/mobile layouts."""
    return "vndj-en:" + _article_parts(url)[2]


def discovery_links(html, listing_url):
    """Offline research candidate links only; no date/window/completeness claim.

    Homepage repeats headlines across Highlights, sections and Most Read.
    Dedupe by stable numeric article ID, retain the first canonical URL.
    Only anchor text and navigable URL are used; no article body extraction.
    """
    if listing_url not in HOME_URLS:
        raise ValueError("unapproved journal listing URL")
    soup = BeautifulSoup(html, "html.parser")
    by_id = {}
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        try:
            absolute = urljoin(listing_url, href)
            canonical = canonical_article_url(absolute)
            identity = article_identity(absolute)
        except ValueError:
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        if identity in by_id and by_id[identity]["url"] != canonical:
            raise ValueError("same journal article ID resolves to inconsistent permalinks")
        by_id.setdefault(identity, {"identity": identity, "url": canonical,
                                     "source_url": absolute, "title_hint": title})
    if not by_id:
        raise ValueError("journal listing contains no identifiable articles")
    if len(by_id) > 150:
        raise ValueError("journal listing exceeds bounded offline candidate limit")
    return list(by_id.values())


def stated_date(text):
    """A date explicitly printed by one of the two observed site layouts.

    Day precision only: neither format authorizes an invented UTC timestamp.
    """
    stamp = " ".join((text or "").split())
    desktop = DESKTOP_STAMP.fullmatch(stamp)
    if desktop:
        weekday, month, day, year, hour, minute = desktop.groups()
        parsed = datetime.strptime(
            f"{month} {day} {year} {hour}:{minute}", "%B %d %Y %H:%M")
        if parsed.strftime("%A") != weekday:
            raise ValueError("journal printed weekday disagrees with date")
        return parsed.date().isoformat()
    mobile = MOBILE_STAMP.fullmatch(stamp)
    if mobile:
        parsed = datetime.strptime(stamp, "%m/%d/%Y %I:%M:%S %p")
        return parsed.date().isoformat()
    raise ValueError("unrecognized journal publication stamp")
