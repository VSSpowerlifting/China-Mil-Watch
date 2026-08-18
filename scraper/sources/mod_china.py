"""
Scraper for Ministry of National Defense (国防部网) — www.mod.gov.cn

MOD China is the official press office of the Ministry of National Defense.
It publishes spokesperson press releases, military diplomacy readouts,
theater command and service branch news, and senior leadership activities.

URL structure (verified May 2026):
  Listing page:  http://www.mod.gov.cn/gfbw/{section_path}/index.html
  Article page:  http://www.mod.gov.cn/gfbw/{section_path}/{numeric_id}.html

Date filtering: each listing link carries its publication stamp in its own
element, <small class="time hidden-xs">, reading "YYYY-MM-DD HH:MM".  That
element is read directly; only if it is absent does the scraper fall back to
requiring the same stamp form at the very end of the flattened link text.
Neither path will accept a date found inside the headline.  A link is kept when
its stamp falls within the seven calendar dates ending on target_date; see
_LOOKBACK_DATES, _stamp_node and _parse_listing_date.

Article structure (verified May 2026):
  Title:  <h1> (first on page)
  Date:   regex YYYY-MM-DD in full page text (present in article-info area)
  Body:   <p class="ueditor-text-p_display"> — same CMS as 81.cn
"""

import re
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper

_BASE = "http://www.mod.gov.cn"

# Discovery window: the seven calendar dates ending on target_date, i.e.
# [target_date - 6 days, target_date] inclusive.
#
# Why a window at all: discovery used to keep a listing link only when the run
# date appeared verbatim in the link text, so an item was collectable on
# exactly one day and never again. MOD routinely posts an item a day or three
# after the date it stamps on it; every such item was invisible on the day it
# was stamped (not yet published) and ignored forever after (no longer today).
# Confirmed losses: hj/16474422 stamped 2026-07-14 but issued with 07-17's ID
# block, and hj/16475877 stamped 2026-07-25 but interleaved with 07-26's IDs.
#
# Seven dates covers ordinary backdating with margin. It is NOT an outage
# remedy: the 2026-07-17 → 07-24 pipeline gap is eight days wide and cost ten
# MOD articles that this window would still miss. Recovering a gap that long
# requires an explicit bounded backfill, not a wider daily window — widening
# the daily window to cover arbitrary outages would refetch the whole listing
# every day to insure against something that should be handled once, on
# purpose, when it happens.
_LOOKBACK_DATES = 7

# Sections with highest analytical value.
# Format: path → display label
_SECTIONS: dict[str, str] = {
    "gfbw/xwfyr/yzxwfb":   "例行新闻发布 (Regular Press Releases)",
    "gfbw/xwfyr/fyrthhdjzw": "发言人谈话 (Spokesperson Q&A)",
    "gfbw/wzll/yw_214068":  "要闻 (Armed Forces Top News)",
    "gfbw/wzll/hj":         "海军 (Navy)",
    "gfbw/wzll/kj":         "空军 (Air Force)",
    "gfbw/wzll/lj":         "陆军 (Army)",
}


class MODChinaScraper(BaseScraper):
    """Scrapes articles from the Ministry of National Defense website."""

    def __init__(self, target_date: Optional[date] = None) -> None:
        super().__init__("mod_china", target_date=target_date)

    # ── Listing pages ─────────────────────────────────────────────────────────

    def get_article_urls(self) -> list[str]:
        window_start = self.target_date - timedelta(days=_LOOKBACK_DATES - 1)
        seen: set[str] = set()

        for section_path, label in _SECTIONS.items():
            listing_url = f"{_BASE}/{section_path}/index.html"
            html = self.fetch(listing_url)
            if not html:
                self.logger.warning("Could not fetch section: %s", label)
                continue

            soup = self.parse(html)
            count = 0
            for a in soup.find_all("a", href=True):
                href: str = a["href"]
                full_url = urljoin(listing_url, href)

                if not _is_article_url(full_url) or full_url in seen:
                    continue

                published = _anchor_publication_date(a)
                if published is None:
                    # No parseable date, or a date that does not exist
                    # (e.g. 2026-13-45). Never guessed at: an item we cannot
                    # date is an item we cannot window.
                    continue
                if published > self.target_date:
                    # Future-stamped. Excluded rather than clamped — a date
                    # ahead of the run is bad data, not fresh news.
                    continue
                if published < window_start:
                    continue

                seen.add(full_url)
                count += 1

            self.logger.debug(
                "Section %s: %d articles in %s..%s",
                label, count, window_start.isoformat(),
                self.target_date.isoformat(),
            )

        self.logger.info(
            "%s: discovery window %s..%s (%d calendar dates) → %d unique URLs",
            self.source_slug, window_start.isoformat(),
            self.target_date.isoformat(), _LOOKBACK_DATES, len(seen),
        )
        return list(seen)

    # ── Article parsing ───────────────────────────────────────────────────────

    def parse_article(self, url: str, html: str) -> Optional[dict]:
        soup = self.parse(html)

        title = self._extract_title(soup)
        if not title:
            self.logger.debug("No title found, skipping: %s", url)
            return None

        text = self._extract_text(soup)
        pub_date = self._extract_date(html)

        return {
            "url":            url,
            "source_slug":    self.source_slug,
            "title_original": title,
            "text_original":  text,
            "published_date": pub_date,
        }

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text:
                return text
        h2 = soup.find("h2")
        if h2:
            text = h2.get_text(strip=True)
            if text:
                return text
        return None

    def _extract_text(self, soup: BeautifulSoup) -> str:
        # MOD uses the same CMS as 81.cn: ueditor-text-p_display paragraphs
        paras = soup.find_all("p", class_=lambda c: c and "ueditor" in c)
        if paras:
            return "\n".join(
                p.get_text(strip=True) for p in paras
                if "ueditor-text-tushuo" not in (p.get("class") or [])
                   and len(p.get_text(strip=True)) > 10
            )

        # Fallback: substantive <p> tags anywhere
        paragraphs = [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 30
               and "版权" not in p.get_text()
               and "责任编辑" not in p.get_text()
        ]
        return "\n".join(paragraphs)

    def _extract_date(self, html: str) -> str:
        # Date appears in the article-info area as YYYY-MM-DD
        match = re.search(r"(\d{4}-\d{2}-\d{2})", html)
        if match:
            return match.group(1)
        return self.target_date.isoformat()


# ── Helpers ───────────────────────────────────────────────────────────────────

# The publication stamp MOD appends to a listing link.
#
# Verified against every listing document held locally — 10 archived cache dates
# plus the six sections fetched 2026-08-17, 71 documents, 2,850 article anchors:
#
#   * 1,980 anchors carry the stamp in its own element,
#     <small class="time hidden-xs">, and every one of those 1,980 reads
#     exactly "YYYY-MM-DD HH:MM". No date-only stamp occurs anywhere in the
#     archive.
#   * 0 anchors have any non-whitespace content after the stamp.
#   * The remaining 870 anchors carry no stamp element and no terminal stamp in
#     their text either; they are navigation and feature links, and they were
#     already being dropped.
#
# So the regex requires a time and anchors to end-of-string, allowing trailing
# whitespace only. A bare "YYYY-MM-DD" is deliberately NOT accepted, because the
# archive does not show MOD emitting one and accepting it is what let a date
# inside a headline pass as metadata.
#
# Stated ambiguity: if MOD ever starts emitting a date-only stamp, both paths
# below reject it and those items stop being discovered. That failure is loud
# rather than silent — discovery drops to zero for the affected sections and the
# 21-day liveness gate fires — which is the direction to fail in. Widening the
# pattern should follow evidence of the new form, not anticipate it.
_LISTING_STAMP_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})\s+\d{1,2}:\d{2}(?::\d{2})?\s*\Z"
)


def _stamp_node(anchor):
    """
    The element carrying the publication stamp, or None.

    MOD marks it up as <small class="time hidden-xs">, so the stamp does not
    have to be recovered from the flattened headline at all.
    """
    return anchor.find("small", class_=lambda c: c and "time" in c)


def _parse_listing_date(link_text: str) -> Optional[date]:
    """
    Parse a terminal publication stamp out of listing text.

    The stamp must be the LAST thing in the string, in the form MOD actually
    emits — "YYYY-MM-DD HH:MM", optionally with seconds — followed by nothing
    but whitespace. Returns None otherwise.

    Why the anchor matters. When a listing link is flattened, the headline and
    the stamp become one string with no separator, so any rule that hunts for a
    date *somewhere* in that string can be answered by the headline instead of
    the metadata. Searching for the first date was the original defect:
    "回顾2020-01-01演习2026-08-14 15:00" read as 2020-01-01. Searching for the
    last date candidate fixed that case but not the class of case —
    "回顾2026-08-14演习" and "回顾2026-08-14演习纪要" carry no publication stamp
    at all, yet both still returned 2026-08-14, because a date in the prose was
    the last candidate present. Requiring the stamp to terminate the string, in
    the observed form, is what distinguishes metadata from prose.

    A malformed terminal stamp returns None and is never repaired from an
    earlier candidate: falling back would mean dating an article by a number
    that happens to appear in its headline.
    """
    if not link_text:
        return None
    m = _LISTING_STAMP_RE.search(link_text)
    if m is None:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _anchor_publication_date(anchor) -> Optional[date]:
    """
    The publication date for one listing anchor.

    Prefers the stamp element, which is metadata by construction and cannot be
    confused with the headline. Falls back to a terminal stamp in the flattened
    text only when no such element is present, so a markup change that drops the
    element degrades to the stricter text rule rather than to guessing.
    """
    node = _stamp_node(anchor)
    if node is not None:
        return _parse_listing_date(node.get_text())
    return _parse_listing_date(anchor.get_text())

def _is_article_url(url: str) -> bool:
    """
    True if the URL looks like a mod.gov.cn article page.
    Pattern: http://www.mod.gov.cn/gfbw/{path}/{numeric_id}.html
    """
    return bool(
        re.match(r"https?://www\.mod\.gov\.cn/gfbw/[^/]+(?:/[^/]+)*/\d+\.html$", url)
    )
