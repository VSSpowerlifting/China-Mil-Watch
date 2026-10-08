"""
Philippines National Security Council — official-statements shadow adapter.

Conforms to `core.collection.contract.SourceAdapter`. It is NOT registered in
any production desk manifest: `shadow/ph_nsc/manifest.json` lives outside
`desks/` so `load_all_desks()` cannot find it. The source is enabled only for
its isolated shadow runner and workflow. Nothing here can reach
`pla_watch.db` or `output/`. It was built and tested offline against four
captures from 2026-10-01. On 2026-10-02 an authorized bounded live rehearsal
used this module's `requests` transport successfully against robots.txt, the
Official Statements listing and two statement pages. Nothing was written to
the database, output tree or production state.

WHAT THIS SOURCE IS
-------------------
The `Official Statements` category of nsc.gov.ph (WordPress, block theme
Twenty Twenty-Four). The category hosts statements issued by several offices —
the National Security Adviser, the National Task Force for the West Philippine
Sea — and the site byline on every one is "National Security Council". That
names the publisher that hosts the page, not the office that issued the
statement, so it is stored as `site_byline` and no issuer is ever derived from
a title or a body.

WHAT THE CAPTURES ESTABLISH, AND WHAT THEY DO NOT
-------------------------------------------------
Four generic urllib requests on 2026-10-01 established bounded
accessibility under the identity in `USER_AGENT`. An authorized 2026-10-02
live rehearsal then established compatibility with this module's `requests`
transport from the owner's Mac environment: robots.txt and the listing returned
HTTP 200, discovery succeeded, and two statement pages fetched and extracted
successfully. This does NOT establish multi-day reliability, GitHub Actions
egress, proxy equivalence, or permission to reuse the text.

The live category still exposed six items, newest 2026-07-08 and oldest
2026-06-03, with no pagination. Its sitemap exposed only the homepage. The
two-page author archive exposed the same six Official Statements and page 3
returned 404. Prospective windows beginning after 2026-06-03 can therefore be
proven from the category page; historical completeness before that date remains
unestablished. The gaps are enforced rather than assumed (see "pagination").

RULES THAT MATTER TO THIS FILE
------------------------------
  * identity is the WordPress post id, `nsc:<id>`. Recurring statements share
    a title and differ only by a `-2` / `-3` slug suffix; neither title nor
    slug is ever an identity or a dedupe key
  * the listing id, the article's `postid-` class, its shortlink and its
    canonical link must agree, or the document is refused
  * the publication date is the one the page declares, kept in its own offset
    with the UTC instant beside it; a timestamp without an offset is refused
  * the body is `div.entry-content` and nothing else. The "Latest Post"
    widget that follows it carries other documents' dates and titles
  * robots.txt is re-read every run and checked before every request
  * a page is accepted only if it positively looks like an NSC WordPress page
    with every expected element present exactly once. A challenge, a parked or
    spam page, a maintenance page or a changed template is refused whatever it
    is, and never becomes a document
  * pagination: only links the listing itself publishes are followed (a page
    URL is never guessed). Discovery walks newest-first until the oldest item
    listed is older than the window start; if it runs out of published pages
    first, window coverage is unprovable and the run fails with zero
    references. Any repeated item, loop, skipped page, off-host link, wrong
    order or page-cap breach fails the whole run — never a partial listing

Deliberately absent: relevance filtering, translation, classification and any
editorial judgement. Absent for later, with the reason recorded in
`shadow/ph_nsc/README.md`: retries, `Crawl-delay`, percent-decoding of robots
paths.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString
from bs4.builder import ParserRejectedMarkup

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, CollectionWindow, DiscoveryResult,
    ExtractedDocument, ExtractionResult, SourceAdapter, SourceHealthResult,
)

HOSTNAME = "nsc.gov.ph"
HOST = "https://" + HOSTNAME
ROBOTS = HOST + "/robots.txt"
LISTING = HOST + "/category/official-statements/"
CATEGORY_CLASS = "category-official-statements"

#: The identity under which the 2026-10-01 captures were taken, character for
#: character (the `user_agent` field of tests/fixtures/ph_nsc/requests.json).
#: It is NOT the identity stated in the AFP correspondence, `ChinaMilWatch/1.0`.
#: The successful rehearsal used this unchanged string. Ben approved retaining
#: the full identity for periodic NSC shadow collection on 2026-10-02.
USER_AGENT = ("ChinaMilWatch-ShadowCollector/0.1 "
              "(+https://chinamilwatch.org; research archive; contact via site)")

#: The only request headers this adapter sets. `Accept-Encoding: identity` is
#: what urllib sent for the captures, so the stored bytes are the bytes that
#: crossed the wire and the replay stays comparable. `requests` adds its own
#: `Accept` and `Connection` defaults, which the captures did not have; that
#: difference is an open gate, not something these tests can measure.
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}

#: The names a publisher may use in robots.txt to address this collector. A
#: group naming either is read in preference to the `*` group.
ROBOTS_TOKENS = ("chinamilwatch-shadowcollector", "chinamilwatch")

REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 2.0          # seconds between requests; one worker only
MAX_BODY_BYTES = 2_000_000
MAX_ROBOTS_BYTES = 512 * 1024
MAX_LISTING_PAGES = 20
MIN_BODY_CHARS = 100            # drift tripwire, not an editorial threshold

#: `/YYYY/MM/DD/slug/`. Observed slugs are lowercase alphanumerics and hyphens;
#: anything else is refused and surfaces as a failure, not a guess.
PERMALINK_RE = re.compile(r"^/(\d{4})/(\d{2})/(\d{2})/([a-z0-9]+(?:-[a-z0-9]+)*)/$")
PAGE_PATH_RE = re.compile(r"^/category/official-statements/page/(\d+)/$")
#: Pagination forms the walker cannot follow. Reported, and named in the
#: failure when they are all that stands between the run and window coverage.
PAGING_QUERY_RE = re.compile(r"(?:^|&)(?:paged|page|query-page|query-\d+-page)=", re.I)

#: Named in the evaluation packet's README about ONE web-tool retrieval of the
#: category URL that returned gambling content. That page was never captured,
#: so this list has not been checked against a real sample and is not a spam
#: detector. The positive structure checks are the defence; this is a tripwire,
#: and it reads only the page's frame (see `_shell`), never the statement text.
OBSERVED_SPAM_MARKERS = ("alanodt2", "87club2")

#: Cloudflare's interstitial, not its passive script: `/cdn-cgi/challenge-platform/`
#: alone also appears on ordinary pages that merely run its JS detections, so
#: it is deliberately NOT a marker.
_CHALLENGE_RE = re.compile(
    r"<title>\s*(?:just a moment|attention required)|cf-browser-verification|"
    r"_cf_chl_opt|id=[\"']challenge-form[\"']|"
    r"enable javascript and cookies to continue|"
    r"checking your browser before accessing", re.I)

#: The NSC theme's own body class, which comes from the theme and not from a
#: statement. An interstitial replaces the page, so it never carries this; a
#: statement titled "Just a moment" or quoting a challenge phrase does.
_THEME_BODY_RE = re.compile(
    r"<body\b[^>]*\bclass=[\"'][^\"']*\bwp-theme-twentytwentyfour\b", re.I)

_BLOCK_TAGS = frozenset((
    "p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
    "blockquote", "br", "hr", "pre", "table", "tr", "figure", "figcaption",
    "section", "article"))
_SKIP_TAGS = frozenset(("script", "style", "noscript"))


class PageRejected(ValueError):
    """A page that is not what an NSC page must be. Never becomes a document."""


class _Refusal(Exception):
    """A collection stage that must stop, with the status that names why."""

    def __init__(self, status: str, detail: str, endpoint: Optional[str] = None):
        super().__init__(detail)
        self.status, self.detail, self.endpoint = status, detail, endpoint


@dataclass(frozen=True)
class _Raw:
    status: int
    headers: Dict[str, str]     # lower-cased names
    body: bytes
    oversized: bool


@dataclass(frozen=True)
class ListingItem:
    post_id: str
    url: str
    title: str
    published_date: str         # in the publisher's own offset
    published_at_utc: str
    published_at_original: str


@dataclass(frozen=True)
class ListingPage:
    items: List[ListingItem]
    next_urls: Set[str]         # explicit "next" links this page publishes
    numbered: Set[int]          # page numbers it links to
    unsupported: List[str]      # pagination-looking query strings we cannot follow


@dataclass(frozen=True)
class Article:
    post_id: str
    title: str
    published: Tuple[str, str, str]
    site_byline: str
    site_byline_url: str
    text: str


# ── pure helpers, unit-testable without a network ────────────────────────────

def canonical_url(url: str) -> Optional[str]:
    """
    `url` unchanged when it is an https permalink on nsc.gov.ph, else None.

    Nothing is rewritten: an http link, another host (the packet's listing also
    links `evas.nsc.gov.ph`), a query string, a fragment or a path that is not
    `/YYYY/MM/DD/slug/` is refused rather than relocated.
    """
    if not url:
        return None
    try:
        parts = urlparse(url)
    except ValueError:                  # e.g. an unterminated IPv6 literal in a malformed link
        return None
    if (parts.scheme, parts.netloc) != ("https", HOSTNAME):
        return None
    if parts.query or parts.fragment or not PERMALINK_RE.match(parts.path):
        return None
    return url


def parse_published(raw: str) -> Optional[Tuple[str, str, str]]:
    """
    `(published_date, published_at_utc, published_at_original)`.

    The date is the one in the offset the page declared (`+08:00`), not the UTC
    date; the UTC instant is preserved beside it. A timestamp with no offset is
    refused: guessing a zone would be inventing a fact about when it appeared.
    """
    raw = (raw or "").strip()
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return (dt.date().isoformat(),
                dt.astimezone(timezone.utc).isoformat(timespec="seconds"), raw)
    except (ValueError, OverflowError):     # OverflowError: 0001-01-01T00:00+08:00 has no UTC instant
        return None


def parse_robots(text: str) -> List[Tuple[List[str], List[Tuple[bool, str]]]]:
    """
    `[(agents, [(allow, pattern), ...]), ...]`, one entry per group.

    Consecutive `User-agent` lines share a group; one after a rule line starts
    a new group. An empty `Allow:` / `Disallow:` value is no rule at all, so
    the captured policy (`User-agent: *`, `Disallow:`) restricts nothing.
    """
    groups, agents, rules, in_rules = [], [], [], False
    for line in (text or "").lstrip("\ufeff").splitlines():
        field, sep, value = line.split("#", 1)[0].partition(":")
        if not sep:
            continue
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif field in ("allow", "disallow") and agents:
            in_rules = True
            if value:
                rules.append((field == "allow", value))
    if agents:
        groups.append((agents, rules))
    return groups


def robots_rules(groups) -> List[Tuple[bool, str]]:
    """
    The rules that govern this collector: every group naming one of
    `ROBOTS_TOKENS`, combined; only when none does, every `*` group, combined.
    The first matching group alone would silently drop the rest.
    """
    named = [g for g in groups if any(a in ROBOTS_TOKENS for a in g[0])]
    chosen = named or [g for g in groups if "*" in g[0]]
    return [rule for _, rules in chosen for rule in rules]


def robots_allows(rules, target: str) -> bool:
    """
    RFC 9309 matching on `path[?query]`: the longest matching pattern wins,
    Allow wins a tie, `*` is a wildcard and a trailing `$` anchors the end. No
    matching rule means allowed.
    # ponytail: patterns are compared as written, no percent-decoding; add if a
    # live robots.txt ever carries encoded paths.
    """
    best = (-1, True)
    for allow, pattern in rules:
        anchored = pattern.endswith("$")
        body = re.escape(pattern[:-1] if anchored else pattern).replace(r"\*", ".*")
        if re.match(body + ("$" if anchored else ""), target):
            best = max(best, (len(pattern), allow))
    return best[1]


def looks_challenged(headers: Dict[str, str], text: str) -> bool:
    """
    An edge challenge, recognised on any status including HTTP 200. The header
    and active challenge form/script are authoritative even on a themed page.
    Plain phrases are read only on an unthemed page, so quoted statement text
    cannot trip them; other malformed themed pages fail their structural checks.
    """
    if headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    try:
        soup = BeautifulSoup(text, "html.parser")
    except ParserRejectedMarkup:
        # The parser rejected the response itself; this alone does not prove
        # a challenge. Fetch/extract and robots validation still reject malformed
        # source content through their existing typed failure paths.
        return not _THEME_BODY_RE.search(text) and bool(_CHALLENGE_RE.search(text))
    # Keep selector and script defects visible: they are not source markup
    # refusals and must not be misreported as innocuous HTML.
    if soup.select("form#challenge-form, #cf-browser-verification"):
        return True
    if any(re.search(r"\b(?:window\.)?_cf_chl_opt\s*=", script.get_text(), re.I)
           for script in soup.find_all("script")):
        return True
    return not _THEME_BODY_RE.search(text) and bool(_CHALLENGE_RE.search(text))


def _one(nodes, what: str):
    if len(nodes) != 1:
        raise PageRejected("expected exactly one %s, found %d" % (what, len(nodes)))
    return nodes[0]


def _squash(text: str) -> str:
    return " ".join(text.split())


def _shell(soup, text: str, kind: str) -> Set[str]:
    """
    The positive fingerprint of an NSC WordPress page; returns its body classes.
    Anything that does not match is refused, whatever it happens to be.
    """
    # The tripwire reads the frame around the statements, not the statements:
    # a statement may name or quote anything, and that is not tampering.
    frame = str(soup)
    for region in soup.select("ul.wp-block-post-template" if kind == "listing"
                              else "div.entry-content"):
        frame = frame.replace(str(region), "", 1)
    frame = frame.lower()
    for marker in OBSERVED_SPAM_MARKERS:
        if marker in frame:
            raise PageRejected("known spam marker %r in the page" % marker)
    if text.rstrip()[-7:].lower() != "</html>":
        raise PageRejected("document does not end with </html>: possible truncation")
    title = soup.title.get_text(strip=True) if soup.title else ""
    if not title.endswith("National Security Council"):
        raise PageRejected("page <title> is not an NSC title: %r" % title[:80])
    tokens = set((soup.body.get("class") if soup.body else None) or [])
    need = {"wp-theme-twentytwentyfour"} | (
        {"archive", "category", CATEGORY_CLASS} if kind == "listing"
        else {"single", "single-post"})
    if not need <= tokens:
        raise PageRejected("body classes lack %s" % sorted(need - tokens))
    return tokens


def _listing_item(li) -> ListingItem:
    classes = li.get("class") or []
    ids = [c[5:] for c in classes if re.fullmatch(r"post-\d+", c)]
    if len(ids) != 1 or CATEGORY_CLASS not in classes:
        raise PageRejected("item lacks a single post-<id> class or the category class")
    link = _one(li.select("h2.wp-block-post-title a[href]"), "item title link")
    stamp = _one(li.select("div.wp-block-post-date time[datetime]"), "item date")
    url = canonical_url(link["href"].strip())
    title = _squash(link.get_text())
    published = parse_published(stamp["datetime"])
    if not (url and title and published):
        raise PageRejected("item %s has an unusable link, title or date" % ids[0])
    if "-".join(PERMALINK_RE.match(urlparse(url).path).groups()[:3]) != published[0]:
        raise PageRejected("item %s: permalink date disagrees with its date" % ids[0])
    return ListingItem(ids[0], url, title, *published)


def _page_number(url: str) -> Optional[int]:
    parts = urlparse(url)
    match = PAGE_PATH_RE.match(parts.path)
    if (parts.scheme == "https" and parts.netloc == HOSTNAME
            and not parts.query and not parts.fragment and match):
        return int(match.group(1))
    return None


def parse_listing_page(text: str, page_url: str) -> ListingPage:
    """
    One category page, strictly. Any deviation raises `PageRejected` for the
    whole page: a listing that silently skips one item is an incomplete listing.
    """
    soup = BeautifulSoup(text, "html.parser")
    _shell(soup, text, "listing")
    main = _one(soup.find_all("main"), "main")
    ul = _one(main.select("ul.wp-block-post-template"), "ul.wp-block-post-template")
    children = ul.find_all("li", recursive=False)
    if any("wp-block-post" not in (li.get("class") or []) for li in children):
        raise PageRejected("the post list holds an item that is not a post")
    items = [_listing_item(li) for li in children]
    if not items:
        raise PageRejected("the listing carries no items (a shape change, not a quiet day)")
    if (len({i.post_id for i in items}) != len(items)
            or len({i.url for i in items}) != len(items)):
        raise PageRejected("an item appears twice on one page")

    next_urls = {urljoin(page_url, a["href"].strip()) for a in soup.select(
        "link[rel~=next][href], main a[rel~=next][href], "
        "main a.wp-block-query-pagination-next[href], main a.next[href]")}
    hrefs = [urljoin(page_url, a["href"].strip()) for a in main.select("a[href]")]
    numbered = {n for n in map(_page_number, hrefs) if n is not None}
    unsupported = sorted({
        urlparse(h).query for h in hrefs
        if urlparse(h).netloc == HOSTNAME and PAGING_QUERY_RE.search(urlparse(h).query)})
    return ListingPage(items, next_urls, numbered, unsupported)


def _body_lines(node) -> List[str]:
    """
    Block-aware text: a block element or `<br>` ends a line, inline markup does
    not, so a sentence split by a link or `<strong>` stays one line. The only
    exclusions are scripts and the latest-posts widget.
    """
    lines, buf = [], []

    def flush():
        line = _squash("".join(buf))
        if line:
            lines.append(line)
        buf.clear()

    def walk(parent):
        for child in parent.children:
            if type(child) is NavigableString:          # not comments, doctypes
                buf.append(str(child))
            elif getattr(child, "name", None) is None:
                continue
            elif child.name in _SKIP_TAGS or any(
                    c.startswith("wp-block-latest-posts") for c in (child.get("class") or [])):
                continue
            elif child.name in _BLOCK_TAGS:
                flush()
                walk(child)
                flush()
            else:
                walk(child)

    walk(node)
    flush()
    return lines


def parse_article(text: str, url: str) -> Article:
    """
    One statement page. Every element is required exactly once inside `<main>`,
    and none has a fallback: a missing date is a refusal, never the sidebar's
    first `<time>`, and a missing title is never the `<title>` tag.
    """
    soup = BeautifulSoup(text, "html.parser")
    tokens = _shell(soup, text, "article")
    ids = [t[7:] for t in tokens if re.fullmatch(r"postid-\d+", t)]
    if len(ids) != 1:
        raise PageRejected("body carries no single postid-<id> class")
    post_id = ids[0]

    canonical = _one(soup.select("link[rel~=canonical][href]"), "canonical link")
    if canonical["href"].strip() != url:
        raise PageRejected("canonical link %r is not the requested URL" % canonical["href"])
    short = soup.select("link[rel~=shortlink][href]")
    if len(short) > 1 or (short and short[0]["href"].strip() != "%s/?p=%s" % (HOST, post_id)):
        raise PageRejected("shortlink does not name post %s" % post_id)

    main = _one(soup.find_all("main"), "main")
    title = _squash(_one(main.select("h1.wp-block-post-title"), "post title").get_text())
    stamp = _one(main.select("div.wp-block-post-date time[datetime]"), "post date")
    byline = _one(main.select("div.wp-block-post-author-name a[href]"), "byline")
    content = _one(main.select("div.entry-content"), "entry-content")

    published = parse_published(stamp["datetime"])
    byline_name, byline_url = _squash(byline.get_text()), byline["href"].strip()
    if not title:
        raise PageRejected("post title is empty")
    if not published:
        raise PageRejected("post date %r carries no usable offset" % stamp["datetime"])
    if not byline_name or urlparse(byline_url).netloc != HOSTNAME:
        raise PageRejected("byline is empty or links off-host")
    if "-".join(PERMALINK_RE.match(urlparse(url).path).groups()[:3]) != published[0]:
        raise PageRejected("permalink date disagrees with the post date")
    body = "\n".join(_body_lines(content))
    if len(body) < MIN_BODY_CHARS:
        raise PageRejected("entry-content holds %d characters: not a complete statement"
                           % len(body))
    return Article(post_id, title, published, byline_name, byline_url, body)


def _transport_status(exc: Exception, default: str) -> str:
    return st.TIMEOUT if isinstance(exc, requests.exceptions.Timeout) else default


# ── the adapter ──────────────────────────────────────────────────────────────

class PHNscAdapter(SourceAdapter):
    """Discovery, retrieval and extraction. No storage, no analysis."""

    implemented = True

    def __init__(self, source, session=None, sleeper=time.sleep) -> None:
        super().__init__(source)
        self._session = session or requests.Session()
        self._sleep = sleeper
        self._last_request: Optional[float] = None
        self._rules: Optional[List[Tuple[bool, str]]] = None
        self._listing_ids: Dict[str, str] = {}
        #: Populated by `discover()`; the shadow runner writes it to the ledger.
        self.robots_status: Optional[str] = None
        self.listing_report: Dict[str, object] = {}

    # -- transport ------------------------------------------------------------

    def _get(self, url: str, limit: int) -> _Raw:
        """
        One polite request: honest User-Agent, no redirects followed, bounded
        read, 2 s apart. Never retried within a run, so a refusal or an outage
        is recorded once rather than answered by hammering.
        # ponytail: single attempt; add transport-only retries if a live
        # rehearsal shows connection resets.
        """
        if self._last_request is not None:
            wait = REQUEST_INTERVAL - (time.monotonic() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT, stream=True,
                                     allow_redirects=False,
                                     headers=dict(REQUEST_HEADERS))
        finally:
            # A failed attempt counts too: a reset or TLS error must not let the
            # next request go out at once, least of all when the host is struggling.
            self._last_request = time.monotonic()
        # The site sets a tracking cookie on listing and statement responses.
        # The captures were stateless, so no cookie is ever sent back.
        self._session.cookies.clear()
        try:
            headers = {k.lower(): v for k, v in (resp.headers or {}).items()}
            declared = headers.get("content-length", "")
            oversized = declared.isdigit() and int(declared) > limit
            chunks, size = [], 0
            if not oversized:
                for chunk in resp.iter_content(chunk_size=65536):
                    size += len(chunk)
                    if size > limit:
                        oversized = True
                        break
                    chunks.append(chunk)
            return _Raw(resp.status_code, headers,
                        b"" if oversized else b"".join(chunks), oversized)
        finally:
            resp.close()
            # Spacing runs from the END of an attempt: a body that stalled, was
            # reset or trickled in must not let the next request follow at once.
            self._last_request = time.monotonic()

    def _gate(self, raw: _Raw) -> str:
        """Status-independent refusals. Returns the body decoded for scanning."""
        if 300 <= raw.status < 400:
            raise _Refusal(st.DISALLOWED_REDIRECT, "HTTP %d redirect to %s was not followed"
                           % (raw.status, raw.headers.get("location", "?")))
        if raw.oversized:
            raise _Refusal(st.OVERSIZED_RESPONSE, "response exceeds the byte limit")
        probe = raw.body.decode("utf-8", "replace")
        if looks_challenged(raw.headers, probe):
            raise _Refusal(st.ACCESS_CHALLENGED,
                           "an access challenge was served instead of the document")
        return probe

    def _screen(self, raw: _Raw, generic: str) -> str:
        """A usable HTML body as text, or a refusal that names the reason."""
        self._gate(raw)
        if raw.status in (401, 403):
            raise _Refusal(st.AUTH_FAILURE, "HTTP %d" % raw.status)
        if raw.status != 200:
            raise _Refusal(generic, "HTTP %d" % raw.status)
        ctype = raw.headers.get("content-type", "")
        charset = re.search(r"charset=([^;\s]+)", ctype, re.I)
        if (not ctype.lower().startswith("text/html")
                or (charset and charset.group(1).strip("\"'").lower() not in ("utf-8", "utf8"))):
            raise _Refusal(st.UNEXPECTED_CONTENT_TYPE, "content-type %r, expected UTF-8 HTML" % ctype)
        try:
            return raw.body.decode("utf-8")
        except UnicodeDecodeError:
            raise _Refusal(st.UNEXPECTED_CONTENT_TYPE, "body is not valid UTF-8")

    # -- policy ---------------------------------------------------------------

    def _load_robots(self, generic: str) -> None:
        """
        Read robots.txt for this run, or refuse. 404 states no restriction; 403
        means the host will not tell this client its rules, which is no
        permission basis; a 200 that is not a plain-text rules file (an HTML
        page, a challenge) is never read as allow-all.
        # ponytail: Crawl-delay is not parsed; the fixed 2 s spacing applies.
        """
        self._rules = None
        try:
            raw = self._get(ROBOTS, MAX_ROBOTS_BYTES)
        except Exception as exc:
            raise _Refusal(_transport_status(exc, generic),
                           "robots.txt unreachable: %s" % type(exc).__name__, ROBOTS)
        try:
            self._gate(raw)
        except _Refusal as refusal:
            refusal.endpoint = ROBOTS
            raise
        if raw.status in (404, 410):
            self._rules, self.robots_status = [], "absent"
            return
        if raw.status in (401, 403):
            raise _Refusal(st.AUTH_FAILURE, "robots.txt returned HTTP %d; no basis to "
                           "conclude collection is permitted" % raw.status, ROBOTS)
        if raw.status != 200:
            raise _Refusal(generic, "robots.txt returned HTTP %d" % raw.status, ROBOTS)
        try:
            text = raw.body.decode("utf-8")
        except UnicodeDecodeError:
            text = "<"
        if (not raw.headers.get("content-type", "").lower().startswith("text/plain")
                or text.lstrip("\ufeff").lstrip().startswith("<")):
            raise _Refusal(st.UNEXPECTED_CONTENT_TYPE,
                           "robots.txt is not a plain-text rules file", ROBOTS)
        self._rules, self.robots_status = robots_rules(parse_robots(text)), "read"

    def _permits(self, url: str) -> bool:
        parts = urlparse(url)
        return robots_allows(self._rules or [],
                             parts.path + ("?" + parts.query if parts.query else ""))

    # -- discovery ------------------------------------------------------------

    def _read_listing(self, url: str) -> ListingPage:
        if not self._permits(url):
            raise _Refusal(st.AUTH_FAILURE,
                           "robots.txt disallows %s for this collector" % url, url)
        try:
            raw = self._get(url, MAX_BODY_BYTES)
        except Exception as exc:
            raise _Refusal(_transport_status(exc, st.LISTING_FAILURE),
                           "listing unreachable: %s" % type(exc).__name__, url)
        try:
            return parse_listing_page(self._screen(raw, st.LISTING_FAILURE), url)
        except _Refusal as refusal:
            refusal.endpoint = url
            raise
        except PageRejected as exc:
            raise _Refusal(st.LISTING_FAILURE, "%s: %s" % (url, exc), url)
        except Exception as exc:
            # Malformed markup is the site's failure mode, not a programming
            # error: a status, never a raise (the shadow runners do not catch).
            raise _Refusal(st.LISTING_FAILURE, "%s: unparseable listing (%s)"
                           % (url, type(exc).__name__), url)

    def _walk_listing(self, start: date) -> List[ListingItem]:
        items: List[ListingItem] = []
        seen_markup = False
        url, number = LISTING, 1
        while True:
            page = self._read_listing(url)
            if ({i.post_id for i in page.items} & {i.post_id for i in items}
                    or {i.url for i in page.items} & {i.url for i in items}):
                raise _Refusal(st.LISTING_FAILURE,
                               "page %d repeats an item already listed" % number, url)
            items.extend(page.items)
            stamps = [i.published_at_utc for i in items]
            if stamps != sorted(stamps, reverse=True):
                raise _Refusal(st.LISTING_FAILURE, "the listing is not newest-first, so what "
                               "it omits cannot be reasoned about", url)
            seen_markup = seen_markup or bool(page.next_urls or page.numbered or page.unsupported)
            oldest = date.fromisoformat(items[-1].published_date)
            if oldest < start:
                break                                   # the window is covered
            want = "%spage/%d/" % (LISTING, number + 1)
            if len(page.next_urls) > 1 or (page.next_urls and page.next_urls != {want}):
                raise _Refusal(st.LISTING_FAILURE, "next link(s) %s do not lead to page %d"
                               % (sorted(page.next_urls), number + 1), url)
            if not page.next_urls and number + 1 not in page.numbered:
                hint = ""
                if page.numbered and max(page.numbered) > number:
                    hint = "; page numbers advertise up to page %d but no link to page %d " \
                           "is published" % (max(page.numbered), number + 1)
                elif page.unsupported:
                    hint = "; unsupported pagination links: %s" % page.unsupported
                raise _Refusal(st.LISTING_FAILURE,
                               "window coverage unprovable: the oldest item listed (%s) is not "
                               "older than the window start (%s) and no further page is "
                               "published%s" % (items[-1].published_date, start, hint), url)
            if number >= MAX_LISTING_PAGES:
                raise _Refusal(st.LISTING_FAILURE, "more than %d pages; refusing to walk on"
                               % MAX_LISTING_PAGES, url)
            url, number = want, number + 1
        self.listing_report = {
            "pages_walked": number, "items_listed": len(items),
            "newest": items[0].published_date, "oldest": items[-1].published_date,
            "window_start": start.isoformat(), "pagination_markup_seen": seen_markup,
            "unsupported_pagination": page.unsupported,
        }
        return items

    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        self._listing_ids, self.listing_report, self.robots_status = {}, {}, None
        start = window.target_date - timedelta(days=window.lookback_days)
        try:
            self._load_robots(st.LISTING_FAILURE)
            items = self._walk_listing(start)
        except _Refusal as refusal:
            return DiscoveryResult(
                self.slug, refusal.status, error_detail=refusal.detail,
                failed_endpoints=[refusal.endpoint] if refusal.endpoint else [])
        self._listing_ids = {i.url: i.post_id for i in items}
        chosen = [i for i in items
                  if start <= date.fromisoformat(i.published_date) <= window.target_date]
        refs = [CandidateReference(url=i.url, source_slug=self.slug, discovered_via=LISTING,
                                   hint_published_date=i.published_date) for i in chosen]
        if not refs:
            return DiscoveryResult(self.slug, st.OK_NO_PUBLICATIONS)
        return DiscoveryResult(self.slug, st.OK, references=refs)

    # -- retrieval ------------------------------------------------------------

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        url = reference.url
        if canonical_url(url) is None:
            # Defence in depth: nothing off-host or off-pattern is requested,
            # not even robots.txt, for a reference this adapter did not discover.
            return CaptureResult(reference, st.FETCH_FAILURE, url,
                                 error_detail="refusing to request a non-permalink URL: %s" % url)
        try:
            if self._rules is None:
                self._load_robots(st.FETCH_FAILURE)
            if not self._permits(url):
                raise _Refusal(st.AUTH_FAILURE, "robots.txt disallows %s for this collector" % url)
            try:
                raw = self._get(url, MAX_BODY_BYTES)
            except Exception as exc:
                raise _Refusal(_transport_status(exc, st.FETCH_FAILURE), type(exc).__name__)
            text = self._screen(raw, st.FETCH_FAILURE)
        except _Refusal as refusal:
            return CaptureResult(reference, refusal.status, url, error_detail=refusal.detail)
        return CaptureResult(
            reference, st.OK, url, final_url=url, http_status=raw.status,
            content_type=raw.headers.get("content-type"),
            payload_bytes=len(raw.body),
            payload_sha256=hashlib.sha256(raw.body).hexdigest(),
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            body=text)

    # -- extraction -----------------------------------------------------------

    def extract(self, capture: CaptureResult) -> ExtractionResult:
        """One document or a refusal. Never a partial record."""
        def refuse(detail: str) -> ExtractionResult:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE, error_detail=detail)

        ref = capture.reference
        url = canonical_url(ref.url)
        if not capture.ok or not capture.body:
            return refuse("no body to extract")
        if not url:
            return refuse("not a permalink URL: %s" % ref.url)
        if capture.final_url and capture.final_url != url:
            return refuse("capture was served from %s, not %s" % (capture.final_url, url))
        try:
            art = parse_article(capture.body, url)
        except PageRejected as exc:
            return refuse("%s: %s" % (url, exc))
        except Exception as exc:                # as in `_read_listing`: a status, not a raise
            return refuse("%s: unparseable page (%s)" % (url, type(exc).__name__))
        if ref.hint_published_date and ref.hint_published_date != art.published[0]:
            return refuse("%s: the listing dated this item %s but the page says %s"
                          % (url, ref.hint_published_date, art.published[0]))
        listed = self._listing_ids.get(url)
        if listed is not None and listed != art.post_id:
            return refuse("%s: the listing named post %s but the page is post %s"
                          % (url, listed, art.post_id))
        doc = ExtractedDocument(
            url=url, source_slug=self.slug, title_original=art.title,
            text_original=art.text, published_date=art.published[0], language_tag="en",
            extra={
                "source_identity": "nsc:%s" % art.post_id,
                "published_at_utc": art.published[1],
                "published_at_original": art.published[2],
                "site_byline": art.site_byline,
                "site_byline_url": art.site_byline_url,
                "publication_kind": "official statement",
                "content_sha256": hashlib.sha256(art.text.encode("utf-8")).hexdigest(),
                "capture_sha256": capture.payload_sha256,
                "retrieved_at": capture.retrieved_at,
            })
        return ExtractionResult(self.slug, st.OK, documents=[doc])

    def healthcheck(self) -> SourceHealthResult:
        return SourceHealthResult(
            self.slug, st.OK if self.source.enabled is True else st.SKIPPED_DISABLED,
            "isolated shadow configuration; no production desk")
