"""
Scraper for Xinhua Military (新华军事) — https://www.news.cn/milpro/

Xinhua is the state news agency. Its military desk is a distinct institution
from the armed forces newspaper and the defense ministry, which is why this
source exists: the China Desk's corpus is heavily concentrated in `pla_daily`,
and concentration is a coverage fact every public surface has to show honestly.

What changed, and why this file is no longer a stub
---------------------------------------------------
The previous stub recorded that the military section "renders article listings
entirely via JavaScript API calls to xhpfmapi.zhongguowangshi.com", and that
the static HTML held only 2020-era articles. That was measured against
`www.xinhuanet.com/mil/`.

Re-measured 2026-09-16 against the agency's current domain and path:

    https://www.news.cn/robots.txt   200  text/plain   "User-Agent: * / Allow: /"
    https://www.news.cn/milpro/      200  text/html; charset=utf-8, 59,193 bytes
                                     198 hrefs, 186 article-shaped, 106 distinct
    an article page                  200  text/html; charset=utf-8, full prose

The listing is **server-rendered**. No JavaScript is executed, no API is
reverse-engineered, no headless browser is used, and robots permits every path
touched here. The stub's diagnosis was true of the path it named and is stale
for this one.

URL structure
-------------
    Listing:  https://www.news.cn/milpro/
    Article:  https://www.news.cn/milpro/YYYYMMDD/<32 hex>/c.html

The publication date is in the path and the identity is the 32-character hex
segment, so a canonical URL is a pure function of the discovered link. That is
a better identity than either existing HTML source in this desk offers.

Article structure (verified 2026-09-16 against four captured pages)
-------------------------------------------------------------------
    Title:  <h1>, with <span class="title"> carrying the same string
    Date:   <meta name="publishdate" content="YYYY-MM-DD">, corroborated by
            the date in the URL path
    Body:   <div id="detail"> → <p> tags

Dates are parsed defensively. The meta tag is preferred, the URL path is the
fallback, and the two are compared: when they disagree the URL wins, because it
is the address the agency itself published the document at, and the
disagreement is logged rather than averaged away.

What this adapter will not do
-----------------------------
It does not manufacture prose. A page whose `#detail` holds no paragraph text —
a photo set, a video shell, a redirect stub — yields an empty body and says so.
An empty body is a fact about the document; filling it from the headline, the
meta description or an image caption would be inventing text for a state news
agency, which is exactly the failure mode this project refuses.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scraper.base import BaseScraper

_BASE = "https://www.news.cn"
_LISTING_URL = f"{_BASE}/milpro/"

#: Article path: /milpro/YYYYMMDD/<32 hex>/c.html
_ARTICLE_PATH_RE = re.compile(r"^/milpro/(\d{8})/([0-9a-f]{32})/c\.html$")

#: Discovery window: the three calendar dates ending on target_date. Xinhua
#: stamps the path in China Standard Time while this pipeline runs on a UTC
#: date, so a strict same-day filter drops the tail of the agency's publishing
#: day on every run. Three days also lets one missed run recover without a
#: backfill. Re-seeing an item costs nothing: identity is the canonical URL.
_LOOKBACK_DATES = 3

#: Body paragraphs shorter than this are page furniture — share prompts,
#: breadcrumb fragments, the "责任编辑" line. Chinese prose carries far more
#: meaning per character than English, so this sits well below the English
#: thresholds used elsewhere in the package.
_MIN_PARAGRAPH_CHARS = 12


def canonical_url(href: str, base: str = _LISTING_URL) -> Optional[str]:
    """
    Absolute https news.cn URL with no query and no fragment, or None.

    Returns None for anything that is not an article of this section, so the
    caller never has to decide what a link is: a link either canonicalises or
    it is not one of ours.
    """
    if not href:
        return None
    absolute = urljoin(base, href.strip())
    parts = urlsplit(absolute)
    host = parts.netloc.lower()
    if host not in ("www.news.cn", "news.cn"):
        return None
    if not _ARTICLE_PATH_RE.match(parts.path):
        return None
    return "https://www.news.cn" + parts.path


def article_identity(url: str) -> Optional[str]:
    """The 32-character hex segment that names this document, or None."""
    match = _ARTICLE_PATH_RE.match(urlsplit(url).path)
    return match.group(2) if match else None


def url_date(url: str) -> Optional[date]:
    """The publication date encoded in the path, or None if unparseable."""
    match = _ARTICLE_PATH_RE.match(urlsplit(url).path)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


class XinhuaMilScraper(BaseScraper):
    """Scrapes the Xinhua military desk from its server-rendered listing."""

    def __init__(self, target_date: Optional[date] = None) -> None:
        super().__init__("xinhua_mil", target_date=target_date)

    # ── Listing page ─────────────────────────────────────────────────────────

    def get_article_urls(self) -> list[str]:
        html = self.fetch(_LISTING_URL)
        if not html:
            self.logger.warning("Could not fetch the Xinhua military listing")
            return []

        window_start = self.target_date - timedelta(days=_LOOKBACK_DATES - 1)
        soup = self.parse(html)

        seen: list[str] = []
        known: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            url = canonical_url(anchor["href"])
            if url is None or url in known:
                continue
            published = url_date(url)
            if published is None:
                continue
            if not (window_start <= published <= self.target_date):
                continue
            known.add(url)
            seen.append(url)

        self.logger.info(
            "xinhua_mil: %s, %d-day window, %d article(s)",
            self.target_date.isoformat(), _LOOKBACK_DATES, len(seen),
        )
        return seen

    # ── Article parsing ──────────────────────────────────────────────────────

    def parse_article(self, url: str, html: str) -> Optional[dict]:
        soup = self.parse(html)

        title = self._extract_title(soup)
        if not title:
            self.logger.debug("No title found, skipping: %s", url)
            return None

        return {
            "url":            canonical_url(url) or url,
            "source_slug":    self.source_slug,
            "title_original": title,
            "text_original":  self._extract_text(soup),
            "published_date": self._extract_date(soup, url),
        }

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        for finder in (lambda: soup.find("h1"),
                       lambda: soup.find("span", class_="title")):
            node = finder()
            if node:
                text = node.get_text(strip=True)
                if text:
                    return text
        if soup.title:
            # "标题\n-新华网" — the agency appends its own name.
            text = soup.title.get_text(strip=True)
            text = re.split(r"\s*-\s*新华网\s*$", text)[0].strip()
            if text:
                return text
        return None

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        The article's prose, or an empty string.

        An empty string is a real answer. A photo set, a video shell or a
        redirect stub genuinely has no prose, and this returns nothing rather
        than promoting the headline or an image caption into a body.
        """
        detail = soup.find(id="detail")
        if detail is None:
            return ""
        paragraphs = [
            p.get_text(strip=True)
            for p in detail.find_all("p")
            if len(p.get_text(strip=True)) >= _MIN_PARAGRAPH_CHARS
        ]
        return "\n".join(paragraphs)

    def _extract_date(self, soup: BeautifulSoup, url: str) -> str:
        """
        The publication date, preferring the URL the agency published at.

        Both sources are read so they can be compared. They agree on every page
        measured; when they do not, the path wins and the disagreement is
        logged, because a silent tie-break is how a date defect survives.
        """
        from_url = url_date(url)
        from_meta = None
        meta = soup.find("meta", attrs={"name": "publishdate"})
        if meta and meta.get("content"):
            raw = meta["content"].strip()[:10]
            try:
                from_meta = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                self.logger.debug("Unparseable publishdate %r on %s", raw, url)

        if from_url and from_meta and from_url != from_meta:
            self.logger.warning(
                "xinhua_mil date disagreement on %s: path=%s meta=%s "
                "— using the path", url, from_url, from_meta,
            )
        chosen = from_url or from_meta or self.target_date
        return chosen.isoformat()
