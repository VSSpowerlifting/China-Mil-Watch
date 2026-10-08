"""Fail-closed, network-free parser pilot for Kemhan's separate Siaran Pers family.

This is NOT a registered SourceAdapter. There is intentionally no manifest,
schedule, shadow-state branch, production import, fetch, or archive write.
Real native bytes/robots checks and original-language fidelity reviews must
precede any operational adapter. Synthetic tests prove contracts only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from scraper.sources.id_kemhan import (
    HOST, article_url, one, stated_date,
)

LISTING = "https://" + HOST + "/category/siaran-pers"
NEXT = re.compile(r"^https://www\.kemhan\.go\.id/category/siaran-pers/page/([1-9][0-9]*)$")
BODY_TAGS = {"p", "div", "ul", "ol", "table", "blockquote"}


@dataclass(frozen=True)
class PressCandidate:
    url: str
    published_date: str
    title: str


@dataclass(frozen=True)
class PressPage:
    records: tuple
    next_url: str | None  # Python 3.9 runtime accepts annotations due to future annotations


@dataclass(frozen=True)
class PressBody:
    url: str
    published_date: str
    title: str
    original_text: str
    language: str = "id"
    publication_kind: str = "official_press_release"


def listing_url(value, number):
    if number < 1 or type(number) is not int:
        raise ValueError("invalid Siaran Pers page number")
    expect = LISTING if number == 1 else LISTING + "/page/" + str(number)
    if value != expect:
        raise ValueError("listing address outside explicit Siaran Pers page")
    return expect


def parse_press_listing(html, *, url=LISTING, number=1):
    """Pure HTML extraction. Assumes the current Kemhan category template;
    real Siaran Pers raw-byte fixture still required before activation.
    """
    listing_url(url, number)
    soup = BeautifulSoup(html, "html.parser")
    heading = one(soup.select("h1"), "ministry masthead")
    if heading.get_text(" ", strip=True) != "KEMENTERIAN PERTAHANAN REPUBLIK INDONESIA":
        raise ValueError("unexpected issuer page")
    rows = soup.select(".listing-news")
    if not rows:
        raise ValueError("Siaran Pers listing rows absent; never infer source silence")
    found = []
    for row in rows:
        anchor = one(row.select("h4 a[href]"), "press announcement")
        link, date_in_path = article_url(anchor["href"])
        date_in_listing = stated_date(one(row.select("small"), "press listing date").get_text(" ", strip=True))
        if date_in_listing != date_in_path:
            raise ValueError("Siaran Pers listing publication date mismatch")
        if not row.select('a[href="' + LISTING + '"]'):
            raise ValueError("record is not labeled Siaran Pers")
        title = anchor.get_text(" ", strip=True)
        if not title:
            raise ValueError("empty Siaran Pers headline")
        found.append(PressCandidate(link, date_in_listing, title))
    if len({p.url for p in found}) != len(found):
        raise ValueError("duplicate Siaran Pers listing URL")
    dates = [p.published_date for p in found]
    if dates != sorted(dates, reverse=True):
        raise ValueError("out-of-order Siaran Pers listing")
    active = one(soup.select("a.active"), "current page marker")
    if active.get_text(strip=True) != str(number):
        raise ValueError("Siaraan Pers page index mismatch")
    pagination = active.parent.parent
    next_url = LISTING + "/page/" + str(number + 1)
    linked = [a["href"] for a in pagination.select("a[href]")]
    advertised_later = [int(m[1]) for u in linked if (m := NEXT.fullmatch(u))
                        and int(m[1]) > number]
    if advertised_later and next_url not in linked:
        raise ValueError("Siaraan Pers next page missing")
    return PressPage(tuple(found), next_url if next_url in linked else None)


def parse_press_article(html, *, url, listed_title, listed_date):
    """Read bounded article container only, without pretending to verify a PDF.

    Nested elements can occur in historical press statements. A single selected
    top-level text block is flattened once to avoid doubling its child prose.
    Structural anomalies fail, rather than substitute navigation/footer text.
    """
    url, date_in_path = article_url(url)
    if date_in_path != listed_date:
        raise ValueError("listed and URL dates disagree")
    soup = BeautifulSoup(html, "html.parser")
    canonical = one(soup.select('link[rel="canonical"]'), "press canonical").get("href")
    if canonical != url:
        raise ValueError("press canonical/source mismatch")
    body = one(soup.select(".def-page.article"), "press article container")
    title = one(body.select("h2"), "press heading").get_text(" ", strip=True)
    if title != listed_title or not title:
        raise ValueError("press article title disagrees with listing")
    published = stated_date(one(body.select("small"), "press original date").get_text(" ", strip=True))
    if published != listed_date:
        raise ValueError("press article publication date mismatch")
    for node in body.select("script, style, noscript, iframe, form"):
        node.decompose()
    segments = [x.get_text(" ", strip=True)
                for x in body.find_all(recursive=False)
                if x.name in BODY_TAGS]
    content = "\n\n".join(p for p in segments if p)
    if not content or len(content) < 40:
        raise ValueError("missing/short unverified Siaran Pers body")
    return PressBody(url, published, title, content)
