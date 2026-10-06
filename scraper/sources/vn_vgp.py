"""
Viet Nam Government News, English edition — `defense` tag shadow adapter.

Conforms to `core.collection.contract.SourceAdapter`. It is NOT registered in
any production desk manifest: `shadow/vietnam/manifest.json` lives outside
`desks/` so `load_all_desks()` cannot find it. The source is enabled only for
its isolated shadow runner and workflow. Nothing here can reach
`pla_watch.db` or `output/`. It was built and tested offline against captures
taken 2026-10-06 UTC by a capped probe that used the same identity, headers and
spacing as this module (docs/VIETNAM_DESK_FEASIBILITY_2026-10-05.md).

WHAT THIS SOURCE IS
-------------------
The page https://en.baochinhphu.vn/defense.html, which labels itself
"Tags: defense", on the English edition of the Government's online newspaper
(Viet Nam Government News, Department of Government Information and
Communications), and the article pages it links. It is a newsroom: its
reports are Tier B institutional public-affairs reporting. An article that
names a resolution or quotes a minister is still a newsroom report about it;
no issuing office is derived from a title or a body, and the byline is the
page's byline, not an author, a translator or an issuer.

A tag is not a category. Articles carry it when an editor applies it. On
2026-10-06 UTC the strategy summary of 2026-08-04 carried no tags at all and a
2026-09-23 Navy-related item on the Politics page did not carry this one. So
this adapter collects every item the tag lists and claims nothing about the
items it does not; it never widens the scope with keywords or other pages.

RULES THAT MATTER TO THIS FILE
------------------------------
  * identity is the trailing digit run of the article path, `vgp-en:<id>`. The
    listing item's `data-id`, the URL it links and the article's canonical
    link must all name the same id, or the item is refused. The digit run has
    no fixed width (17- and 18-digit ids are both listed; the site's homepage
    links 8-digit legacy ids). The id is never parsed for a date: 2026-05-24's
    maritime-consultation article has an id that reads like 2026-05-23
  * titles are never an identity or a dedupe key; the 2025-12-25 Azerbaijan
    article's slug and its edited title differ, and both are kept as published
  * discovery reads ONE published page, the tag page. Its 24 items reached back
    to 2023-11-16 on 2026-10-06 UTC. Older items load by script from
    `/timelinetags/...`, a URL the page never publishes as a link, so it is
    never requested. Window coverage is proven only when the oldest listed item
    is older than the window start; otherwise the run fails with no references
  * items are read from the single `div.timeline > div.box-stream` stream and
    nothing else. The same page links five other articles from sidebar widgets;
    they never become references
  * the listing shows each item's local time twice, day-first as text
    (`05/08/2026 20:35`) and month-first in a title attribute
    (`8/5/2026 8:35:00 PM`). Both are parsed with fixed orders and must agree;
    for any day up to the 12th a single guessed order would silently move the
    date. Neither carries an offset, so the listing time selects the window
    and is never stored as a publication time
  * the publication time is the article's own `article:published_time`,
    kept in the offset it declares with the UTC instant beside it. A stamp with
    no offset keeps its date and gets no UTC instant; no offset is assumed.
    JSON-LD `datePublished` and the visible header are cross-checks recorded as
    anomalies, never substitutes. The modification time is kept separately.
    Dates in the related-stories box (`data-date`) and the CMS comment at the
    end of the body are never read
  * the body is the single `div.detail-content[data-role=content]`: paragraphs,
    headings, list items, quotations, table rows and figure captions, in page
    order, each labelled with its element. The related-stories box, comments,
    scripts, images and the tag list are excluded. The lead (`VGP - ...`) is
    the first line of the text and is also stored on its own. The `./.` end
    marker and every character are kept as published: only the ASCII
    whitespace HTML itself collapses is collapsed, never NBSP or a soft hyphen,
    and no Unicode normalization is applied
  * a body is accepted on structure, never on length. A body with no text but
    with images or embedded media is kept as `media_only`; a body with neither
    is refused
  * a page is accepted only if it positively looks like a Government News
    page. A challenge, a cookie gate or a changed template is refused and never
    stored as a document

Deliberately absent: relevance filtering, translation, classification, any
editorial judgement, retries and redirects.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, CollectionWindow, DiscoveryResult,
    ExtractedDocument, ExtractionResult, SourceHealthResult,
)
# The identity, the transport limits, robots parsing and the request loop were
# written here and moved to the module every Vietnam shadow adapter shares.
# Two things changed in the move: a Crawl-delay that is not a finite,
# non-negative number now reads as infinite (refused, never guessed low), and
# a delay read from robots.txt reaches the shared host gate with that request.
# REQUEST_HEADERS, REQUEST_TIMEOUT, USER_AGENT and robots_allows are not used
# below; they are re-exported so nothing that reads them here changes.
from scraper.sources.vn_shadow_http import (
    CHALLENGE_RE as _CHALLENGE_RE, MAX_BODY_BYTES, MAX_CRAWL_DELAY, MAX_ROBOTS_BYTES,
    REQUEST_HEADERS, REQUEST_INTERVAL, REQUEST_TIMEOUT, USER_AGENT, Refusal as _Refusal,
    ShadowHttpAdapter, parse_robots, robots_allows, robots_crawl_delay,
    robots_rules, squash,
)

HOSTNAME = "en.baochinhphu.vn"
HOST = "https://" + HOSTNAME
ROBOTS = HOST + "/robots.txt"
TAG_PATH = "/defense.html"
LISTING = HOST + TAG_PATH
#: The listing's own `#hdCatUrl` value: the page's statement of which tag it is.
TAG_ZONE = "defense"
IDENTITY_PREFIX = "vgp-en:"

#: Frame markers every Government News page carried in the 2026-10-06 UTC captures
#: (listing, articles, the Politics page). An interstitial carries neither.
SITE_COPYRIGHT = "© Viet Nam Government Portal"
SITE_NAME = "en.baochinhphu.vn"

#: `/<slug>-<id>.htm`. The slug is lowercase ASCII words; the id is the final
#: all-digit segment, of whatever width.
ARTICLE_PATH_RE = re.compile(r"^/(?:[a-z0-9]+-)+?(\d+)\.htm$")

#: How `content_sha256` is computed, named so a stored hash can say which rule
#: produced it. Over the title, the lead and the labelled body blocks — never
#: dates, bylines or page chrome — so a title or text edit is a new version and
#: a re-served page with only its sidebars or modification time changed is not.
CONTENT_HASH_RULE = "vgp-en-content-v1"

_MONTHS = ("january", "february", "march", "april", "may", "june", "july",
           "august", "september", "october", "november", "december")
_VISIBLE_STAMP = re.compile(
    r"^([A-Za-z]+) (\d{1,2}), (\d{4}) (\d{1,2}):(\d{2}) (AM|PM) GMT([+-])(\d{1,2})(?::?(\d{2}))?$")
_LIST_TEXT = re.compile(r"^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2})$")
_LIST_TITLE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4}) (\d{1,2}):(\d{2}):(\d{2}) (AM|PM)$")

_BLOCK_TAGS = frozenset((
    "p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "br", "hr", "pre", "section", "article", "dl", "dt", "dd"))
_SKIP_TAGS = frozenset(("script", "style", "noscript", "template"))
#: Inside one table cell or caption, these separate words: a nested table's
#: cells must not run together into one word.
_CELL_BREAKS = _BLOCK_TAGS | frozenset(("table", "thead", "tbody", "tfoot", "tr", "td", "th",
                                        "caption", "figure", "figcaption"))
#: Elements whose name labels the lines they hold. Inside a sticky one (a
#: quotation, a list item) nested paragraphs keep the outer label.
_LABELS = frozenset(("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote",
                     "pre", "dt", "dd"))
_STICKY = frozenset(("blockquote", "li", "pre", "dt", "dd"))
_MEDIA_TAGS = frozenset(("img", "picture", "video", "audio", "iframe", "object",
                         "embed", "svg"))
#: `type` values on body blocks that the captures showed and this file handles.
#: Any other typed block is still read for text, and is reported as an anomaly.
_KNOWN_BLOCK_TYPES = frozenset(("Photo", "RelatedNewsBox"))


class PageRejected(ValueError):
    """A page that is not what a Government News page must be."""


@dataclass(frozen=True)
class ListingItem:
    item_id: str
    url: str
    title: str
    listed_local: str           # YYYY-MM-DDTHH:MM, the publisher's wall clock, no offset
    listed_date: str
    category: Optional[str]


@dataclass(frozen=True)
class Stamp:
    original: str
    date: str
    utc: Optional[str]          # None when the stamp declares no offset
    local: str                  # YYYY-MM-DDTHH:MM as written
    offset_minutes: Optional[int]


@dataclass
class Article:
    item_id: str
    canonical_url: str
    title: str
    lead: str
    blocks: List[Tuple[str, str]]
    body_status: str
    media_count: int
    related_boxes_excluded: int
    published: Stamp
    modified: Optional[Stamp]
    visible_published: Optional[str]
    byline: Optional[str]
    byline_jsonld: Optional[str]
    publisher_jsonld: Optional[str]
    category: Optional[str]
    tags: List[Tuple[str, str]]
    anomalies: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(([self.lead] if self.lead else []) + [t for _, t in self.blocks])


# ── pure helpers, unit-testable without a network ────────────────────────────

def article_id(url: str) -> Optional[str]:
    """The id of an https article URL on this host, else None. Nothing is rewritten."""
    if not url:
        return None
    try:
        parts = urlparse(url)
    except ValueError:
        return None
    if (parts.scheme, parts.netloc) != ("https", HOSTNAME):
        return None
    if parts.query or parts.fragment or parts.params:
        return None
    match = ARTICLE_PATH_RE.match(parts.path)
    return match.group(1) if match else None


def content_sha256(title: str, lead: str, blocks) -> str:
    """See CONTENT_HASH_RULE. UTF-8 JSON, sorted keys, no whitespace separators."""
    payload = json.dumps({"rule": CONTENT_HASH_RULE, "title": title, "lead": lead,
                          "blocks": [[k, t] for k, t in blocks]},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _hour24(hour: int, meridiem: str) -> int:
    if not 1 <= hour <= 12:
        raise ValueError("12-hour clock hour out of range")
    return (hour % 12) + (12 if meridiem == "PM" else 0)


def parse_listing_time(text: str, title_attr: str) -> datetime:
    """
    The naive local time a listing item shows, read from both of its forms.
    Raises ValueError unless the day-first text and the month-first title agree.
    """
    a = _LIST_TEXT.match(squash(text))
    b = _LIST_TITLE.match(squash(title_attr))
    if not a or not b:
        raise ValueError("listing time %r / %r is not in the observed forms" % (text, title_attr))
    day, month, year, hour, minute = map(int, a.groups())
    from_text = datetime(year, month, day, hour, minute)
    m2, d2, y2, h2, mi2, sec2 = map(int, b.groups()[:6])
    from_title = datetime(y2, m2, d2, _hour24(h2, b.group(7)), mi2, sec2)
    if from_title.replace(second=0) != from_text or sec2:
        raise ValueError("listing time forms disagree: %r reads %s, %r reads %s"
                         % (text, from_text, title_attr, from_title))
    return from_text


def parse_iso_stamp(raw: str) -> Optional[Stamp]:
    """
    An ISO 8601 stamp as the page wrote it. With an offset: the date in that
    offset and the UTC instant. Without: the written date and no instant.
    """
    raw = (raw or "").strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    local = dt.strftime("%Y-%m-%dT%H:%M")
    if dt.tzinfo is None:
        return Stamp(raw, dt.date().isoformat(), None, local, None)
    try:
        utc = dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except OverflowError:
        return None
    offset = int(dt.utcoffset().total_seconds() // 60)
    return Stamp(raw, dt.date().isoformat(), utc, local, offset)


def parse_visible_stamp(text: str) -> Optional[Tuple[str, int]]:
    """`September 09, 2026 9:33 AM GMT+7` -> ("2026-09-09T09:33", 420), else None."""
    m = _VISIBLE_STAMP.match(squash(text))
    if not m or m.group(1).lower() not in _MONTHS:
        return None
    try:
        dt = datetime(int(m.group(3)), _MONTHS.index(m.group(1).lower()) + 1,
                      int(m.group(2)), _hour24(int(m.group(4)), m.group(6)), int(m.group(5)))
    except ValueError:
        return None
    offset = int(m.group(8)) * 60 + int(m.group(9) or 0)
    return dt.strftime("%Y-%m-%dT%H:%M"), offset if m.group(7) == "+" else -offset


def _framed(soup) -> bool:
    copyright_ = [m.get("content") for m in soup.select("meta[name=copyright]")]
    site = [m.get("content") for m in soup.select('meta[property="og:site_name"]')]
    return copyright_ == [SITE_COPYRIGHT] and site == [SITE_NAME]


def looks_challenged(headers: Dict[str, str], text: str) -> bool:
    """
    An edge challenge, recognised on any status. A Government News page is
    never one: phrases are read only on a page without the site frame, so an
    article quoting a challenge phrase cannot trip them. The cookie-and-reload
    interstitial is the form measured at mod.gov.vn on 2026-10-06 UTC.
    """
    if headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    soup = BeautifulSoup(text, "html.parser")
    if soup.select("form#challenge-form, #cf-browser-verification"):
        return True
    if _framed(soup):
        return False
    if _CHALLENGE_RE.search(text):
        return True
    scripts = " ".join(s.get_text() for s in soup.find_all("script"))
    return (len(text) < 8192 and "document.cookie" in scripts
            and re.search(r"location\.(?:reload|replace|href)", scripts) is not None)


def _one(nodes, what: str):
    if len(nodes) != 1:
        raise PageRejected("expected exactly one %s, found %d" % (what, len(nodes)))
    return nodes[0]


def _at_most_one(nodes, what: str):
    if len(nodes) > 1:
        raise PageRejected("expected at most one %s, found %d" % (what, len(nodes)))
    return nodes[0] if nodes else None


#: The site's cache can append its own stamp after the document. Measured in
#: the 2026-10-06 rehearsal: the tag page came back as the earlier bytes plus
#: `<!--u: 10/6/2026 9:59:55 AM-->`. Whitespace and complete comments after
#: </html> are tolerated; anything else, a comment cut short included, is
#: still a possible truncation.
_DOCUMENT_END_RE = re.compile(r"</html>(?:[ \t\n\r\f]|<!--(?:(?!-->).)*-->)*\Z",
                              re.IGNORECASE | re.DOTALL)


def _frame(soup, text: str) -> None:
    if not _DOCUMENT_END_RE.search(text):
        raise PageRejected("document does not end with </html>: possible truncation")
    if not _framed(soup):
        raise PageRejected("page lacks the Government News frame (copyright and site name)")


def parse_listing_page(text: str) -> List[ListingItem]:
    """
    The tag page, strictly. Any deviation raises PageRejected for the whole
    page: a listing that silently skips one item is an incomplete listing.
    """
    soup = BeautifulSoup(text, "html.parser")
    _frame(soup, text)
    canonical = [l.get("href", "").strip() for l in soup.select("link[rel~=canonical]")]
    if canonical != [LISTING]:
        raise PageRejected("listing canonical is %r, not %s" % (canonical, LISTING))
    zone = _one(soup.select("input#hdCatUrl"), "#hdCatUrl").get("value")
    if zone != TAG_ZONE:
        raise PageRejected("the page declares tag %r, not %r" % (zone, TAG_ZONE))
    stream = _one(soup.select("div.timeline > div.box-stream.timeline_list"), "tag stream")
    items: List[ListingItem] = []
    for child in stream.children:
        if getattr(child, "name", None) is None:
            if type(child) is NavigableString and squash(str(child)):
                raise PageRejected("stray text in the tag stream")
            continue
        if "box-stream-item" not in (child.get("class") or []):
            if any(article_id(urljoin(HOST, a.get("href", ""))) for a in child.select("a[href]")):
                raise PageRejected("an unrecognised element in the stream links an article")
            continue
        items.append(_listing_item(child))
    if not items:
        raise PageRejected("the tag stream carries no items (a shape change, not a quiet day)")
    if len({i.item_id for i in items}) != len(items) or len({i.url for i in items}) != len(items):
        raise PageRejected("an item appears twice in the tag stream")
    return items


def _listing_item(node) -> ListingItem:
    item_id = node.get("data-id", "")
    link = _one(node.select("h2 > a.box-stream-link-title[href]"), "item title link")
    url = urljoin(HOST + "/", link["href"].strip())
    url_id = article_id(url)
    if not item_id.isdigit() or url_id != item_id or link.get("data-id") != item_id:
        raise PageRejected("item %r: data-id, link data-id and URL id %r disagree"
                           % (item_id, url_id))
    title = squash(link.get_text())
    if not title:
        raise PageRejected("item %s has an empty title" % item_id)
    stamp = _one(node.select("span.box-stream-time"), "item time")
    try:
        listed = parse_listing_time(stamp.get_text(), stamp.get("title", ""))
    except ValueError as exc:
        raise PageRejected("item %s: %s" % (item_id, exc))
    category = _at_most_one(node.select("a.box-stream-category"), "item category")
    return ListingItem(item_id, url, title, listed.strftime("%Y-%m-%dT%H:%M"),
                       listed.date().isoformat(),
                       squash(category.get_text()) if category else None)


def _jsonld_article(soup) -> Optional[dict]:
    found = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.get_text())
        except ValueError:
            continue                    # another block's syntax is not this page's article
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict) and node.get("@type") == "NewsArticle":
                found.append(node)
    return _at_most_one(found, "JSON-LD NewsArticle")


def _jsonld_name(node) -> Optional[str]:
    if isinstance(node, dict) and isinstance(node.get("name"), str):
        return squash(html_lib.unescape(node["name"])) or None
    return None


def _body(content) -> Tuple[List[Tuple[str, str]], int, int, List[str]]:
    """
    `(blocks, media_count, related_boxes_excluded, unrecognised_types)`.

    A block element or `<br>` ends a line and inline markup does not, so a
    sentence split by a link or `<strong>` stays one line. Each line is
    labelled with the block element that holds it.
    """
    blocks: List[Tuple[str, str]] = []
    buf: List[str] = []
    counts = {"media": 0, "related": 0}
    unknown: List[str] = []
    kinds = ["p"]

    def flush():
        line = squash("".join(buf))
        if line:
            blocks.append((kinds[-1], line))
        buf.clear()

    def cell_text(cell) -> str:
        parts: List[str] = []

        def collect(node):
            for child in node.children:
                name = getattr(child, "name", None)
                if type(child) is NavigableString:
                    parts.append(str(child))
                elif name is not None and name not in _SKIP_TAGS:
                    if name in _CELL_BREAKS:
                        parts.append(" ")
                    collect(child)
        collect(cell)
        return squash("".join(parts))

    def walk(parent):
        for child in parent.children:
            if type(child) is NavigableString:          # never comments or doctypes
                buf.append(str(child))
                continue
            name = getattr(child, "name", None)
            if name is None or name in _SKIP_TAGS:
                continue
            block_type = child.get("type")
            if block_type == "RelatedNewsBox":
                counts["related"] += 1
                continue
            if block_type and block_type not in _KNOWN_BLOCK_TYPES:
                unknown.append(block_type)
            if name in _MEDIA_TAGS:
                counts["media"] += 1
                continue
            if name == "figure":
                flush()
                counts["media"] += len(child.find_all(sorted(_MEDIA_TAGS))) or 1
                for caption in child.find_all("figcaption"):
                    text = cell_text(caption)
                    if text:
                        blocks.append(("figcaption", text))
                continue
            if name == "table":
                flush()
                for row in child.find_all("tr"):
                    if row.find_parent("table") is not child:
                        continue                # a nested table's rows belong to its cell
                    cells = [cell_text(c) for c in row.find_all(["td", "th"], recursive=False)]
                    if any(cells):
                        blocks.append(("tr", " | ".join(cells)))
                continue
            if name in _BLOCK_TAGS:
                flush()
                outer = kinds[-1]
                kinds.append(outer if outer in _STICKY or name not in _LABELS else name)
                walk(child)
                flush()
                kinds.pop()
            else:
                walk(child)

    walk(content)
    flush()
    return blocks, counts["media"], counts["related"], unknown


def parse_article(text: str, url: str) -> Article:
    """
    One article page. Every structural element is required exactly once and
    none has a fallback: a missing publication stamp is a refusal, never the
    visible header or a related story's date, and a missing title is never the
    `<title>` tag.
    """
    soup = BeautifulSoup(text, "html.parser")
    _frame(soup, text)
    item_id = article_id(url)
    if item_id is None:
        raise PageRejected("not an article URL: %s" % url)
    anomalies: List[str] = []

    canonical = _one(soup.select("link[rel~=canonical][href]"), "canonical link")["href"].strip()
    if article_id(canonical) != item_id:
        raise PageRejected("canonical %s names a different publication than %s" % (canonical, url))
    if canonical != url:
        anomalies.append("canonical_url_differs: requested %s, canonical %s" % (url, canonical))
    og = [m.get("content", "").strip() for m in soup.select('meta[property="og:url"]')]
    if og != [canonical]:
        anomalies.append("og_url_differs: %r" % (og,))

    main = _one(soup.select("div.detail-mcontent"), "div.detail-mcontent")
    title = squash(_one(main.select("h1.detail-title[data-role=title]"), "title").get_text())
    if not title:
        raise PageRejected("title is empty")
    lead_node = _at_most_one(main.select("h2.detail-sapo[data-role=sapo]"), "lead")
    lead = squash(lead_node.get_text()) if lead_node else ""
    content = _one(main.select("div.detail-content[data-role=content]"), "content block")

    published = parse_iso_stamp(_one(
        soup.select('meta[property="article:published_time"][content]'),
        "article:published_time")["content"])
    if published is None:
        raise PageRejected("article:published_time is not a readable ISO 8601 stamp")
    modified_meta = _at_most_one(
        soup.select('meta[property="article:modified_time"][content]'), "article:modified_time")
    modified = parse_iso_stamp(modified_meta["content"]) if modified_meta else None
    if modified_meta and modified is None:
        anomalies.append("modified_time_unreadable: %r" % modified_meta["content"])

    ld = _jsonld_article(soup)
    if ld is None:
        anomalies.append("jsonld_article_absent")
    else:
        for key, stamp, label in (("datePublished", published, "published"),
                                  ("dateModified", modified, "modified")):
            other = parse_iso_stamp(str(ld.get(key) or ""))
            if stamp is not None and (other is None or (other.utc, other.local)
                                      != (stamp.utc, stamp.local)):
                anomalies.append("jsonld_%s_differs: meta %s, JSON-LD %r"
                                 % (label, stamp.original, ld.get(key)))
    visible_node = _at_most_one(main.select("[data-role=publishdate]"), "visible date")
    visible = squash(visible_node.get_text()) if visible_node else None
    if visible is None:
        anomalies.append("visible_date_absent")
    else:
        parsed = parse_visible_stamp(visible)
        if parsed is None:
            anomalies.append("visible_date_unreadable: %r" % visible)
        elif parsed != (published.local, published.offset_minutes):
            anomalies.append("visible_date_differs: meta %s, header %r"
                             % (published.original, visible))

    byline_node = _at_most_one(main.select(".detail-author-top-name"), "byline")
    byline = squash(byline_node.get_text()) if byline_node else None
    byline_ld = _jsonld_name(ld.get("author")) if ld else None
    if byline and byline_ld and byline != byline_ld:
        anomalies.append("byline_differs: header %r, JSON-LD %r" % (byline, byline_ld))
    category = _at_most_one(main.select(".detail-breadcrumb a[data-role=cate-name]"), "category")
    tags = [(a.get("href", "").strip(), squash(a.get_text()))
            for a in soup.select("ul.detail-tag-list[data-role=tags] a[href]")]

    blocks, media, related, unknown = _body(content)
    for block_type in sorted(set(unknown)):
        anomalies.append("unrecognised_block_type: %s" % block_type)
    if any(kind != "figcaption" for kind, _ in blocks):
        body_status = "text"
    elif media:
        body_status = "media_only"
        anomalies.append("media_only_body")
    else:
        raise PageRejected("the content block holds no text and no media")

    return Article(
        item_id=item_id, canonical_url=canonical, title=title, lead=lead, blocks=blocks,
        body_status=body_status, media_count=media, related_boxes_excluded=related,
        published=published, modified=modified, visible_published=visible,
        byline=byline or byline_ld, byline_jsonld=byline_ld,
        publisher_jsonld=_jsonld_name(ld.get("publisher")) if ld else None,
        category=squash(category.get_text()) if category else None,
        tags=tags, anomalies=anomalies)


# ── the adapter ──────────────────────────────────────────────────────────────

class VNVgpAdapter(ShadowHttpAdapter):
    """Discovery, retrieval and extraction. No storage, no analysis."""

    implemented = True
    robots_url = ROBOTS

    def __init__(self, source, session=None, sleeper=time.sleep, clock=time.monotonic,
                 max_requests: Optional[int] = None, gate=None, wall=time.time) -> None:
        super().__init__(source, session=session, sleeper=sleeper, clock=clock,
                         max_requests=max_requests, gate=gate, wall=wall)
        self._listing: Dict[str, ListingItem] = {}
        self.listing_report: Dict[str, object] = {}

    def _challenged(self, headers: Dict[str, str], text: str) -> bool:
        return looks_challenged(headers, text)

    # -- policy ---------------------------------------------------------------

    def _robots_problem(self, raw) -> Optional[str]:
        """
        This adapter's acceptance rule, unchanged since the pilot: a 200 that
        is not a plain-text rules file (an HTML page, a challenge) is never
        read as allow-all. The header decides here, as it always has.
        """
        try:
            text = raw.body.decode("utf-8")
        except UnicodeDecodeError:
            text = "<"
        if (not raw.headers.get("content-type", "").lower().startswith("text/plain")
                or text.lstrip("\ufeff").lstrip().startswith("<")):
            return "robots.txt is not a plain-text rules file"
        return None

    # -- discovery ------------------------------------------------------------

    def _read_listing(self) -> List[ListingItem]:
        if not self._permits(LISTING):
            raise _Refusal(st.AUTH_FAILURE,
                           "robots.txt disallows %s for this collector" % LISTING, LISTING)
        raw = self._get(LISTING, MAX_BODY_BYTES, st.LISTING_FAILURE)
        text = self._screen(raw, st.LISTING_FAILURE)
        # Kept before parsing, so a page refused for its shape is evidence too.
        self._keep("listing", raw)
        try:
            items = parse_listing_page(text)
        except PageRejected as exc:
            raise _Refusal(st.LISTING_FAILURE, "%s: %s" % (LISTING, exc), LISTING, raw.status)
        except Exception as exc:
            raise _Refusal(st.LISTING_FAILURE, "%s: unparseable listing (%s)"
                           % (LISTING, type(exc).__name__), LISTING, raw.status)
        stamps = [i.listed_local for i in items]
        if stamps != sorted(stamps, reverse=True):
            raise _Refusal(st.LISTING_FAILURE, "the tag stream is not newest-first, so "
                           "what it omits cannot be reasoned about", LISTING, raw.status)
        return items

    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        self._listing, self.listing_report, self.robots_status = {}, {}, None
        start = window.target_date - timedelta(days=window.lookback_days)
        end = window.target_date
        try:
            self._load_robots(st.LISTING_FAILURE)
            items = self._read_listing()
            oldest = date.fromisoformat(items[-1].listed_date)
            self.listing_report = {
                "listing_url": LISTING, "pages_read": 1, "items_listed": len(items),
                "newest_listed": items[0].listed_date, "oldest_listed": items[-1].listed_date,
                "window_start": start.isoformat(), "window_end": end.isoformat(),
                "pagination": "script-built only (/timelinetags/); never requested",
                "coverage": "proven" if oldest < start else "unprovable",
                # Every item the page listed, so a later review can see an
                # item that appears in a window after that window was read.
                "listed": [[i.item_id, i.listed_local] for i in items],
            }
            if not oldest < start:
                raise _Refusal(st.LISTING_FAILURE,
                               "window coverage unprovable: the oldest item the tag page lists "
                               "(%s) is not older than the window start (%s), and the page "
                               "publishes no further listing page as a link"
                               % (items[-1].listed_date, start), LISTING)
        except _Refusal as refusal:
            return DiscoveryResult(
                self.slug, refusal.status, error_detail=refusal.detail,
                failed_endpoints=[refusal.endpoint] if refusal.endpoint else [])
        chosen = [i for i in items
                  if start <= date.fromisoformat(i.listed_date) <= end]
        self._listing = {i.url: i for i in chosen}
        self.listing_report.update(
            selected=len(chosen),
            listed_after_window=sum(1 for i in items if date.fromisoformat(i.listed_date) > end))
        refs = [CandidateReference(url=i.url, source_slug=self.slug, discovered_via=LISTING,
                                   hint_published_date=i.listed_date) for i in chosen]
        if not refs:
            return DiscoveryResult(self.slug, st.OK_NO_PUBLICATIONS)
        return DiscoveryResult(self.slug, st.OK, references=refs)

    # -- retrieval ------------------------------------------------------------

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        url = reference.url
        if article_id(url) is None:
            # Nothing off-host or off-pattern is requested, not even robots.txt.
            return CaptureResult(reference, st.FETCH_FAILURE, url,
                                 error_detail="refusing to request a non-article URL: %s" % url)
        try:
            if self._rules is None:
                self._load_robots(st.FETCH_FAILURE)
            if not self._permits(url):
                raise _Refusal(st.AUTH_FAILURE, "robots.txt disallows %s for this collector" % url)
            raw = self._get(url, MAX_BODY_BYTES, st.FETCH_FAILURE)
            text = self._screen(raw, st.FETCH_FAILURE)
        except _Refusal as refusal:
            return CaptureResult(reference, refusal.status, url, http_status=refusal.http_status,
                                 error_detail=refusal.detail)
        return CaptureResult(
            reference, st.OK, url, final_url=url, http_status=raw.status,
            content_type=raw.headers.get("content-type"),
            payload_bytes=len(raw.body),
            payload_sha256=hashlib.sha256(raw.body).hexdigest(),
            retrieved_at=raw.retrieved_at, body=text)

    # -- extraction -----------------------------------------------------------

    def extract(self, capture: CaptureResult) -> ExtractionResult:
        """One document or a refusal. Never a partial record."""
        def refuse(detail: str) -> ExtractionResult:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE, error_detail=detail)

        ref = capture.reference
        url = ref.url
        if not capture.ok or not capture.body:
            return refuse("no body to extract")
        if article_id(url) is None:
            return refuse("not an article URL: %s" % url)
        if capture.final_url and capture.final_url != url:
            return refuse("capture was served from %s, not %s" % (capture.final_url, url))
        try:
            art = parse_article(capture.body, url)
        except PageRejected as exc:
            return refuse("%s: %s" % (url, exc))
        except Exception as exc:                # malformed markup is a status, not a raise
            return refuse("%s: unparseable page (%s)" % (url, type(exc).__name__))
        anomalies = list(art.anomalies)
        listed = self._listing.get(url)
        if listed is not None and listed.item_id != art.item_id:
            return refuse("%s: the listing named item %s but the page is item %s"
                          % (url, listed.item_id, art.item_id))
        if ref.hint_published_date and ref.hint_published_date != art.published.date:
            anomalies.append("listing_date_differs: listing %s, page %s"
                             % (ref.hint_published_date, art.published.date))
        if listed is not None and listed.title != art.title:
            anomalies.append("listing_title_differs: listing %r, page %r"
                             % (listed.title, art.title))
        if TAG_PATH not in [href for href, _ in art.tags]:
            anomalies.append("listed_but_not_tagged: the page's tag list lacks %s" % TAG_PATH)
        doc = ExtractedDocument(
            url=url, source_slug=self.slug, title_original=art.title,
            text_original=art.text, published_date=art.published.date, language_tag="en",
            extra={
                "source_identity": IDENTITY_PREFIX + art.item_id,
                "item_id": art.item_id,
                "canonical_url": art.canonical_url,
                "published_at_original": art.published.original,
                "published_at_utc": art.published.utc,
                "modified_at_original": art.modified.original if art.modified else None,
                "modified_at_utc": art.modified.utc if art.modified else None,
                "visible_published": art.visible_published,
                "byline": art.byline,
                "byline_jsonld": art.byline_jsonld,
                "publisher_jsonld": art.publisher_jsonld,
                "category": art.category,
                "tags": [list(t) for t in art.tags],
                "lead_original": art.lead,
                "blocks": [list(b) for b in art.blocks],
                "body_status": art.body_status,
                "media_count": art.media_count,
                "related_boxes_excluded": art.related_boxes_excluded,
                "publication_kind": "newsroom report",
                "listing_title": listed.title if listed else None,
                "listing_local_time": listed.listed_local if listed else None,
                "listing_category": listed.category if listed else None,
                "content_hash_rule": CONTENT_HASH_RULE,
                "content_sha256": content_sha256(art.title, art.lead, art.blocks),
                "capture_sha256": capture.payload_sha256,
                "retrieved_at": capture.retrieved_at,
                "anomalies": anomalies,
            })
        return ExtractionResult(self.slug, st.OK, documents=[doc])

    def healthcheck(self) -> SourceHealthResult:
        return SourceHealthResult(
            self.slug, st.OK if self.source.enabled is True else st.SKIPPED_DISABLED,
            "isolated shadow configuration; no production desk")
