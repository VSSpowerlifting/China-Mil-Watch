"""
Scraper for Global Times — Military section (环球时报·军事)
https://www.globaltimes.cn/china/military/

Global Times is a CCP-affiliated tabloid published under People's Daily.
Its military coverage is English-language, often more sensational than
official PLA Daily output but useful for tracking official narrative aimed
at international audiences and for triangulating PLA signaling.

URL structure (verified May 2026):
  Listing page:  https://www.globaltimes.cn/china/military/
  Article page:  https://www.globaltimes.cn/page/YYYYMM/{numeric_id}.shtml

Date filtering: The listing page includes <div class="source_time"> elements
with text in the format "By Author  |  YYYY/M/D H:MM:SS".  The year/month
portion of the article URL also encodes the publication month.

Article structure (verified May 2026):
  Title:  <div class="article_title"> text content
  Date:   <div class="source_time"> — regex parses "YYYY/M/D" portion
  Body:   <div class="article_content"> → <p> tags (first occurrence only;
          subsequent div.article_content elements are related-article embeds)
"""

import re
from datetime import date
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper

_BASE = "https://www.globaltimes.cn"
_LISTING_URL = f"{_BASE}/china/military/"

# Article URL: /page/YYYYMM/ID.shtml
_ARTICLE_URL_RE = re.compile(
    r"https?://www\.globaltimes\.cn/page/(\d{4})(\d{2})/\d+\.shtml$"
)


class GlobalTimesMilScraper(BaseScraper):
    """Scrapes military articles from the Global Times."""

    def __init__(self, target_date: Optional[date] = None) -> None:
        super().__init__("global_times_mil", target_date=target_date)

    # ── Listing page ──────────────────────────────────────────────────────────

    def get_article_urls(self) -> list[str]:
        html = self.fetch(_LISTING_URL)
        if not html:
            self.logger.warning("Could not fetch Global Times military listing")
            return []

        soup = self.parse(html)
        today_str = self.target_date.strftime("%Y-%m-%d")
        target_ym = self.target_date.strftime("%Y%m")     # e.g. "202605"
        target_year = str(self.target_date.year)          # e.g. "2026"
        target_month = str(self.target_date.month)        # e.g. "5" (no zero-pad)
        target_day = str(self.target_date.day)            # e.g. "7"

        seen: set[str] = set()

        # Each article entry is a pair: <a href> (link) + <div class="source_time">
        # (date).  Walk all links and validate against the date shown in source_time.
        for a in soup.find_all("a", href=True):
            href = urljoin(_LISTING_URL, a["href"])
            m = _ARTICLE_URL_RE.match(href)
            if not m:
                continue
            # Quickly reject articles from a different month/year
            if m.group(1) + m.group(2) != target_ym:
                continue

            # Find the nearest sibling or parent <div class="source_time">
            date_text = _nearest_source_time(a)
            if date_text is None:
                # No date found; accept if the URL year/month matches today
                pass
            else:
                # Parse "By Author  |  2026/5/7 18:37:07"
                date_match = re.search(
                    r"(\d{4})/(\d{1,2})/(\d{1,2})", date_text
                )
                if date_match:
                    y, mo, d = date_match.groups()
                    article_date = f"{y}-{int(mo):02d}-{int(d):02d}"
                    if article_date != today_str:
                        continue

            if href not in seen:
                seen.add(href)

        self.logger.debug("Global Times military: %d today's articles", len(seen))
        return list(seen)

    # ── Article parsing ───────────────────────────────────────────────────────

    def parse_article(self, url: str, html: str) -> Optional[dict]:
        soup = self.parse(html)

        title = self._extract_title(soup)
        if not title:
            self.logger.debug("No title found, skipping: %s", url)
            return None

        text = self._extract_text(soup)
        pub_date = self._extract_date(soup, url)

        return {
            "url":             url,
            "source_slug":     self.source_slug,
            "title_original":  title,
            "text_original":   text,
            "published_date":  pub_date,
            "content_verdict": self._content_verdict(soup, text),
        }

    @staticmethod
    def _content_verdict(soup: BeautifulSoup, text: str):
        """
        A deterministic statement about the document, or None.

        `media_only` only when the body container was found (so the template is
        still understood), it carries media, and it carries no prose. A missing
        container is template drift and returns None — which is exactly the
        case that produced records 3432, 3946 and 3948, and the reason an empty
        body is never a permanent verdict on its own.
        """
        if text.strip():
            return None
        content_div = soup.find("div", class_="article_content")
        if content_div is None:
            return None                      # template drift — say nothing
        if content_div.find(["img", "video", "iframe"]) is not None:
            return "media_only"
        return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        div = soup.find("div", class_="article_title")
        if div:
            text = div.get_text(strip=True)
            if text:
                return text
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(strip=True)
            if text:
                return text
        return None

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        The article's prose, or an empty string.

        Three routes, tried in order, because the site serves two templates and
        the older one still has to keep working.

        1. **Paragraph markup.** `div.article_content` with real `<p>` bodies.
           This is the original route and is unchanged, so every page that
           extracted correctly before still takes exactly this path.
        2. **Flow markup.** `div.article_content > div.article_right` carrying
           the body as bare text nodes separated by `<br><br>`, with the only
           `<p>` being `class="picture"` image captions. Measured 2026-09-16:
           this is why records 3432, 3946 and 3948 were stored with empty
           bodies while their pages served 359, 3,969 and 2,113 characters of
           prose. Route 1 looked for `<p>` inside `article_content`, found only
           captions, correctly refused to treat a caption as a body, and
           returned nothing — so an extraction defect was recorded as source
           silence. C5 in docs/DESK_STRENGTH_CRITERIA.md names that inversion.
        3. **Bare paragraphs** anywhere on the page. The original fallback,
           unchanged.

        An empty string remains a real answer. A page that is genuinely a photo
        set or a video shell has no prose, and this returns nothing rather than
        promoting a caption or a headline into a body.
        """
        # Route 1 — paragraph markup, byte-for-byte the original behaviour.
        content_div = soup.find("div", class_="article_content")
        if content_div:
            paras = [
                p.get_text(strip=True)
                for p in content_div.find_all("p")
                if len(p.get_text(strip=True)) > 30
                   and p.get("class") != ["picture"]
            ]
            if paras:
                return "\n".join(paras)

        # Route 2 — flow markup.
        if content_div:
            flow = _flow_text(content_div)
            if flow:
                return flow

        # Route 3 — bare paragraphs, excluding related-article embeds.
        paragraphs = [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if not p.get("class")
               and len(p.get_text(strip=True)) > 40
               and not _inside_embed(p)
        ]
        return "\n".join(paragraphs)

    def _extract_date(self, soup: BeautifulSoup, url: str) -> str:
        # Primary: <div class="source_time"> — "By X  |  2026/5/7 18:37:07"
        for div in soup.find_all("div", class_=lambda c: c and "source_time" in c):
            text = div.get_text(strip=True)
            m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", text)
            if m:
                y, mo, d = m.groups()
                return f"{y}-{int(mo):02d}-{int(d):02d}"

        # Fallback: year/month from URL, day unknown → use target date
        m = _ARTICLE_URL_RE.match(url)
        if m:
            year, month = m.group(1), m.group(2)
            if year == str(self.target_date.year) and int(month) == self.target_date.month:
                return self.target_date.isoformat()

        return self.target_date.isoformat()



#: Containers that hold other articles' text on an article page: the related
#: and recommended rails. The module docstring has always noted that repeated
#: `div.article_content` elements are related-article embeds; route 3 did not
#: act on it, and on a flow-markup page where route 1 finds nothing it swept
#: thirty teaser paragraphs into the body. Measured 2026-09-16 on the PLA Navy
#: missile-test page: 2,726 characters of other articles' first lines stored as
#: this article's body, against a real body of 797. That is worse than an empty
#: body — an empty body is a gap, and this was other reporting attributed to
#: the wrong document.
_EMBED_CLASSES = ("related_content", "related_article", "related_section",
                  "recommend", "latest_news")


def _inside_embed(tag) -> bool:
    """True when this node sits inside a related/recommended rail."""
    for parent in tag.parents:
        classes = parent.get("class") if hasattr(parent, "get") else None
        if classes and any(c in _EMBED_CLASSES for c in classes):
            return True
    return False


#: Body text shorter than this is page furniture rather than a paragraph.
#: Matches the threshold route 1 already applies to `<p>` bodies.
_MIN_FLOW_PARAGRAPH_CHARS = 30


def _flow_text(content_div) -> str:
    """
    Recover paragraphs from a body written as bare text nodes and `<br>`.

    The container is copied before it is stripped, because these helpers run
    against a soup the caller may still read — `_extract_date` walks the same
    tree — and mutating shared state to compute a return value is how a second
    defect gets introduced while fixing the first.

    Image captions (`p.picture`), the images themselves and their `<center>`
    wrappers are removed rather than flattened. A caption describes a
    photograph; it is not a sentence the paper published as its report, and
    letting one stand in for a body is the same invention this adapter refuses
    everywhere else.
    """
    import copy

    node = copy.copy(content_div)
    for junk in node.find_all(["script", "style", "img", "center", "iframe"]):
        junk.decompose()
    for caption in node.find_all("p", class_="picture"):
        caption.decompose()

    for br in node.find_all("br"):
        br.replace_with("\n")

    text = node.get_text()
    paragraphs = [
        line.strip()
        for line in text.split("\n")
        if len(line.strip()) >= _MIN_FLOW_PARAGRAPH_CHARS
    ]
    return "\n".join(paragraphs)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nearest_source_time(tag) -> Optional[str]:
    """
    Walk up the DOM tree from <a> looking for a sibling or ancestor
    <div class="source_time"> that carries the article's publication date.
    Checks parent, grandparent, and great-grandparent elements.
    """
    node = tag
    for _ in range(4):
        node = node.parent
        if node is None:
            return None
        # Look at siblings of the current node
        for sibling in node.find_all("div", class_=lambda c: c and "source_time" in c):
            text = sibling.get_text(strip=True)
            if re.search(r"\d{4}/\d{1,2}/\d{1,2}", text):
                return text
    return None
