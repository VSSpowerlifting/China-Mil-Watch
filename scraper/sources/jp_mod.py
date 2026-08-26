"""
Japan Ministry of Defense / Joint Staff — shadow source adapter.

What access actually looks like (qualified 2026-08-26)
-----------------------------------------------------
`www.mod.go.jp` sits behind Cloudflare, and the edge does **not** treat every
document the same way. Measured, one honest request per endpoint:

    /robots.txt                     200   text/plain   (disallows only /a/ and /sp/j/)
    /j/rss/news.xml                 200   application/xml
    /j/rss/update.xml               200   application/xml   (304 on If-None-Match)
    /j/press/news/2026/08/25a.pdf   200   application/pdf
    /j/press/news/2026/08/26b.html  403   Cf-Mitigated: challenge
    /en/press-release/              403   Cf-Mitigated: challenge
    /js/press/index-en.html         403   Cf-Mitigated: challenge

So: **XML and PDF are served; HTML is challenged.** Robots permits every path
this adapter touches — the challenge is an edge policy, not a robots directive.

That shapes the whole design. Discovery runs on RSS, which works. Bodies come
from PDF, which works. HTML items are discovered, recorded, and then *not
fetched* — they are marked `access_challenged` and carry no body.

What this adapter will not do
-----------------------------
It does not solve the challenge. No browser user agent, no cookie replay, no
headless browser, no proxy, no retry storm against a 403. A challenge is a
host telling this client it is not welcome on that path, and the honest
response is to record the refusal where a reader can see it.

`access_challenged` exists in the status vocabulary for exactly this. Recording
it as `fetch_failure` would file a policy decision as an outage, and a reader
comparing Japan's coverage against China's would draw a false conclusion about
which ministry publishes more.

Deduplication
-------------
By canonical URL, and by content hash for bodies. **Never by title.** Japanese
ministry releases reuse titles heavily and legitimately — 「日米合同委員会合意
について」 recurs whenever the Joint Committee agrees anything. Title-level
deduplication would silently collapse a year of distinct agreements into one
record. Recurring titles are preserved.
"""

from __future__ import annotations

import hashlib
import re
import time

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, CollectionWindow, DiscoveryResult,
    ExtractedDocument, ExtractionResult, SourceAdapter, SourceHealthResult,
)
from processing import pdf_text

HOST = "https://www.mod.go.jp"
ROBOTS = HOST + "/robots.txt"

#: Both official machine-readable discovery routes. `news.xml` is the press
#: stream; `update.xml` is the wider site-update stream and is a superset for
#: some sections. Both are polled; references are merged and de-duplicated by
#: canonical URL, so overlap costs nothing.
FEEDS = (HOST + "/j/rss/news.xml", HOST + "/j/rss/update.xml")

#: Honest identification. A ministry that wants to refuse this collector must be
#: able to recognise it in a log and say so in robots.txt.
USER_AGENT = ("ChinaMilWatch-ShadowCollector/0.1 "
              "(+https://chinamilwatch.org; research archive; contact via site)")

REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 2.0          # seconds between requests; one worker only
MAX_RETRIES = 1                 # one retry, transport errors only — never a 403
MAX_BODY_BYTES = pdf_text.MAX_BYTES

#: Paths robots.txt disallows for `User-agent: *` as measured 2026-08-26. Kept
#: as a fallback only; `assert_robots_allows` parses the live file when given it.
KNOWN_DISALLOW = ("/a/", "/sp/j/")

#: URL family -> what that family actually is, measured across both feeds on
#: 2026-08-26. These are **labels, not filters**. Nothing is dropped for failing
#: to match: an unrecognised family is stored as "ministry page (unclassified)"
#: so a new section shows up as itself rather than vanishing.
#:
#: `update.xml` is a whole-site stream, so it carries budget tables, profile
#: pages and even a children's page alongside press releases. Storing all of
#: them under one word like "release" would fabricate a document type; storing
#: only the ones that look like releases would be silent sampling. Both are
#: refused: everything is kept, and each record says which family it came from.
_PRESS_KIND = (
    (re.compile(r"^/js/"), "joint staff publication"),
    (re.compile(r"^/en/"), "ministry page (english)"),
    (re.compile(r"^/j/press/news/"), "press release"),
    (re.compile(r"^/j/press/"), "press material"),
    (re.compile(r"^/j/approach/"), "defense exchange or policy item"),
    (re.compile(r"^/j/budget/"), "budget document"),
    (re.compile(r"^/j/profile/"), "ministry profile page"),
    (re.compile(r"^/j/policy/"), "policy document"),
    (re.compile(r"^/j/presiding/"), "presiding-office page"),
    (re.compile(r"^/j/kids/"), "public education page"),
)


class RobotsDisallowed(RuntimeError):
    """The live robots.txt forbids a path this adapter was about to request."""


def canonical_url(url: str) -> Optional[str]:
    """
    Absolute, https, no query, no fragment, host-normalised.

    RSS items carry site-relative links (`/j/press/news/2026/08/26b.html`), so
    this is also what turns a feed entry into an identity.
    """
    if not url:
        return None
    absolute = urljoin(HOST + "/", url.strip())
    parts = urlsplit(absolute)
    if parts.scheme not in ("http", "https"):
        return None
    host = parts.netloc.lower()
    if host != "www.mod.go.jp":
        return None
    return urlunsplit(("https", host, parts.path, "", ""))


def is_pdf(url: str) -> bool:
    return urlsplit(url).path.lower().endswith(".pdf")


def publication_kind(url: str) -> str:
    path = urlsplit(url).path
    for pattern, kind in _PRESS_KIND:
        if pattern.search(path):
            return kind
    return "ministry page (unclassified)"


def language_tag(url: str) -> str:
    """`/en/` is the English estate; everything else publishes in Japanese."""
    return "en" if urlsplit(url).path.startswith("/en/") else "ja"


def parse_robots(robots_text: str) -> List[str]:
    """
    Disallow rules that apply to `User-agent: *`.

    Deliberately simple, and deliberately conservative in the one way that
    matters: an unparseable robots file yields no permission, not blanket
    permission. The caller decides what to do with an empty result.
    """
    disallow: List[str] = []
    applies = False
    for raw in robots_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            applies = (value == "*")
        elif field == "disallow" and applies and value:
            disallow.append(value)
    return disallow


def parse_feed(xml_text: str, feed_url: str,
               titles: Optional[dict] = None,
               source_slug: str = "jp_mod_news_ja") -> List[CandidateReference]:
    """
    RSS 2.0 items -> candidate references.

    A malformed feed raises; it is a listing failure, not an empty day. The
    difference matters: silence and breakage look identical downstream unless
    one of them is made to shout.
    """
    root = ET.fromstring(xml_text)
    refs: List[CandidateReference] = []
    for item in root.findall(".//item"):
        link = canonical_url((item.findtext("link") or "").strip())
        if not link:
            continue
        if titles is not None:
            title = (item.findtext("title") or "").strip()
            # First feed to carry a title wins; `update.xml` sometimes repeats an
            # item with a terser label than `news.xml` gave it.
            if title and link not in titles:
                titles[link] = title
        refs.append(CandidateReference(
            url=link,
            source_slug=source_slug,
            discovered_via=feed_url,
            hint_published_date=_rfc822_date(item.findtext("pubDate")),
        ))
    return refs


def _rfc822_date(value: Optional[str]) -> Optional[str]:
    """
    `Wed, 26 Aug 2026 18:06` -> `2026-08-26`.

    The feed omits seconds and zone on some items, so several shapes are tried
    and an unparseable date returns None rather than a guess.
    """
    if not value:
        return None
    value = value.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S",
                "%a, %d %b %Y %H:%M", "%a, %d %b %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def select_window(refs, window: CollectionWindow, cap: int):
    """
    Keep references published inside the window, newest first, up to `cap`.

    An item with no parseable date is kept: dropping it would be a silent
    sampling decision, and the run counters would then describe a corpus the
    collector chose rather than the one the ministry published.
    """
    start = window.target_date.toordinal() - max(0, window.lookback_days)
    kept = []
    for ref in refs:
        if ref.hint_published_date:
            try:
                d = datetime.strptime(ref.hint_published_date, "%Y-%m-%d").date()
            except ValueError:
                kept.append(ref)
                continue
            if start <= d.toordinal() <= window.target_date.toordinal():
                kept.append(ref)
        else:
            kept.append(ref)
    kept.sort(key=lambda r: (r.hint_published_date or ""), reverse=True)
    return kept[:cap]


class JPModAdapter(SourceAdapter):
    """
    Japan MOD / Joint Staff shadow adapter.

    One worker, one run a day, `REQUEST_INTERVAL` between requests, conditional
    requests when the caller supplies validators. It never opens the production
    database and never writes anywhere; it returns values and the shadow runner
    decides what to persist.
    """

    def __init__(self, source, session=None, cap: int = 40,
                 validators=None, sleep=time.sleep):
        self.source = source
        self.slug = getattr(source, "slug", "jp_mod_news_ja")
        #: Each declared feed is its own source, because the two are objectively
        #: different things: news.xml is the press stream, update.xml reports any
        #: page on the site. Merging them into one "releases" source is what made
        #: the first manifest describe a budget table as an official release.
        self.feeds = tuple(getattr(source, "discovery_endpoints", None) or FEEDS)
        # A real session by default. Leaving this None meant every live run
        # raised AttributeError inside the transport try/except and reported
        # `listing_failure` — a broken collector that looked like a dead
        # ministry. Caught by the first live dry run, not by the unit tests,
        # because every test injects its own stub session.
        self._session = session if session is not None else requests.Session()
        self._cap = cap
        #: {url: {"etag": ..., "last_modified": ...}} carried across runs so a
        #: document already stored is revalidated rather than re-downloaded.
        self._validators = validators or {}
        self._sleep = sleep
        self._robots_disallow: Optional[List[str]] = None
        #: {canonical url: title as the feed published it}. Titles live here
        #: rather than on CandidateReference because the contract has no title
        #: field, and inventing one for a shadow source would change a shared
        #: dataclass for every desk.
        self._titles: dict = {}
        self.challenged: List[str] = []
        self.failed_fetches: List[str] = []

    # ---------------------------------------------------------------- robots

    def assert_robots_allows(self, robots_text: str, url: str) -> None:
        rules = parse_robots(robots_text) if robots_text else list(KNOWN_DISALLOW)
        path = urlsplit(url).path or "/"
        for rule in rules:
            if path.startswith(rule):
                raise RobotsDisallowed(
                    "robots.txt disallows %s (rule %r)" % (path, rule))

    # ----------------------------------------------------------------- fetch

    def _get(self, url: str, conditional: bool = True):
        """
        One request, honest identity, bounded retries on *transport* errors only.

        A 403 is never retried. It is the host's answer, and asking again is
        both rude and useless.
        """
        headers = {"User-Agent": USER_AGENT, "Accept": "*/*",
                   "Accept-Language": "en,ja"}
        if conditional:
            v = self._validators.get(url) or {}
            if v.get("etag"):
                headers["If-None-Match"] = v["etag"]
            if v.get("last_modified"):
                headers["If-Modified-Since"] = v["last_modified"]

        attempt = 0
        while True:
            response = self._session.get(
                url, headers=headers, timeout=REQUEST_TIMEOUT)
            code = getattr(response, "status_code", None)
            if code == 403 or _is_challenge(response):
                return response                     # never retried
            if code is not None and code < 500:
                return response
            attempt += 1
            if attempt > MAX_RETRIES:
                return response
            self._sleep(REQUEST_INTERVAL)

    # ------------------------------------------------------------- discovery

    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        refs, failed = [], []
        seen = set()
        for feed in self.feeds:
            try:
                response = self._get(feed)
                if getattr(response, "status_code", None) == 304:
                    continue                        # unchanged since last run
                if getattr(response, "status_code", None) != 200:
                    failed.append(feed)
                    continue
                for ref in parse_feed(response.text, feed, self._titles,
                                      source_slug=self.slug):
                    if ref.url not in seen:
                        seen.add(ref.url)
                        refs.append(ref)
            except ET.ParseError as exc:
                failed.append("%s (malformed feed: %s)" % (feed, exc))
            except Exception as exc:                # transport
                failed.append("%s (%s)" % (feed, type(exc).__name__))
            self._sleep(REQUEST_INTERVAL)

        if failed and not refs:
            return DiscoveryResult(
                source_slug=self.slug, status=st.LISTING_FAILURE,
                failed_endpoints=failed,
                error_detail="no discovery route returned a usable feed")

        return DiscoveryResult(
            source_slug=self.slug,
            status=st.OK if refs else st.OK_NO_PUBLICATIONS,
            references=select_window(refs, window, self._cap),
            failed_endpoints=failed)

    # ----------------------------------------------------------------- fetch

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # HTML is challenged at the edge. Do not spend a request discovering
        # that again for every item on every run.
        if not is_pdf(reference.url):
            self.challenged.append(reference.url)
            return CaptureResult(
                reference=reference, status=st.ACCESS_CHALLENGED,
                requested_url=reference.url, retrieved_at=now,
                error_detail="HTML documents on this host are served behind a "
                             "bot-mitigation challenge; not fetched")

        try:
            response = self._get(reference.url)
        except Exception as exc:
            self.failed_fetches.append(reference.url)
            return CaptureResult(
                reference=reference, status=st.FETCH_FAILURE,
                requested_url=reference.url, retrieved_at=now,
                error_detail="%s: %s" % (type(exc).__name__, exc))

        code = getattr(response, "status_code", None)
        ctype = (getattr(response, "headers", {}) or {}).get("Content-Type", "")

        if _is_challenge(response) or code == 403:
            self.challenged.append(reference.url)
            return CaptureResult(
                reference=reference, status=st.ACCESS_CHALLENGED,
                requested_url=reference.url, http_status=code,
                content_type=ctype, retrieved_at=now,
                error_detail="edge challenge")
        if code == 304:
            return CaptureResult(
                reference=reference, status=st.OK_ALL_DUPLICATES,
                requested_url=reference.url, http_status=304,
                retrieved_at=now,
                error_detail="unchanged since the stored validator")
        if code != 200:
            self.failed_fetches.append(reference.url)
            return CaptureResult(
                reference=reference, status=st.FETCH_FAILURE,
                requested_url=reference.url, http_status=code,
                content_type=ctype, retrieved_at=now)

        payload = getattr(response, "content", b"") or b""
        if len(payload) > MAX_BODY_BYTES:
            return CaptureResult(
                reference=reference, status=st.OVERSIZED_RESPONSE,
                requested_url=reference.url, http_status=code,
                content_type=ctype, payload_bytes=len(payload),
                retrieved_at=now,
                error_detail="refused unread at %d bytes" % len(payload))
        if "pdf" not in ctype.lower() and not payload.startswith(pdf_text.MAGIC):
            return CaptureResult(
                reference=reference, status=st.UNEXPECTED_CONTENT_TYPE,
                requested_url=reference.url, http_status=code,
                content_type=ctype, payload_bytes=len(payload),
                retrieved_at=now)

        capture = CaptureResult(
            reference=reference, status=st.OK, requested_url=reference.url,
            final_url=getattr(response, "url", None) or reference.url,
            http_status=code, content_type=ctype,
            payload_bytes=len(payload), retrieved_at=now)
        # Bytes ride along for extract(); the contract's `body` is text-only and
        # neither is persisted.
        capture.raw = {"pdf_bytes": payload,
                       "etag": (getattr(response, "headers", {}) or {}).get("ETag"),
                       "last_modified": (getattr(response, "headers", {}) or {})
                                        .get("Last-Modified")}
        return capture

    # --------------------------------------------------------------- extract

    def extract(self, capture: CaptureResult) -> ExtractionResult:
        if capture.status != st.OK:
            return ExtractionResult(
                source_slug=self.slug, status=capture.status,
                error_detail=capture.error_detail)

        data = (capture.raw or {}).get("pdf_bytes") or b""
        result = pdf_text.extract_pdf_text(data)

        if result.status != pdf_text.OK:
            # no_text_layer / encrypted / malformed / too_large / too_many_pages
            # each arrive here by name. None of them becomes an empty-bodied
            # record, and none of them is OCR'd.
            return ExtractionResult(
                source_slug=self.slug, status=st.EXTRACTION_FAILURE,
                error_detail="pdf: %s" % result.status)

        url = capture.requested_url
        title = (self._titles.get(url) or "").strip()
        if not title:
            # A record with a body and no title is the half-record this project
            # has been burned by before (article id=2678). Refuse it by name
            # rather than storing a document titled "".
            return ExtractionResult(
                source_slug=self.slug, status=st.EXTRACTION_FAILURE,
                error_detail="no title for %s in either discovery feed" % url)

        return ExtractionResult(
            source_slug=self.slug, status=st.OK,
            documents=[ExtractedDocument(
                url=url,
                source_slug=self.slug,
                title_original=title,
                text_original=result.text,
                published_date=capture.reference.hint_published_date,
                language_tag=language_tag(url),
                extra={"publication_kind": publication_kind(url),
                       "pdf_status": result.status,
                       # Content identity is the extracted text, so a ministry
                       # re-issuing byte-different PDFs of the same notice is
                       # still recognisable as the same document.
                       "content_sha256": hashlib.sha256(
                           result.text.encode("utf-8")).hexdigest(),
                       "capture_sha256": hashlib.sha256(data).hexdigest(),
                       "retrieved_at": capture.retrieved_at,
                       "etag": (capture.raw or {}).get("etag"),
                       "last_modified": (capture.raw or {}).get("last_modified")},
            )])

    # ------------------------------------------------------------ healthcheck

    def healthcheck(self) -> SourceHealthResult:
        try:
            response = self._get(self.feeds[0], conditional=False)
        except Exception as exc:
            return SourceHealthResult(
                source_slug=self.slug, status=st.LISTING_FAILURE,
                detail="%s: %s" % (type(exc).__name__, exc))
        code = getattr(response, "status_code", None)
        if _is_challenge(response) or code == 403:
            return SourceHealthResult(
                source_slug=self.slug, status=st.ACCESS_CHALLENGED,
                detail="discovery feed is behind an edge challenge")
        if code != 200:
            return SourceHealthResult(
                source_slug=self.slug, status=st.LISTING_FAILURE,
                detail="feed returned HTTP %s" % code)
        return SourceHealthResult(source_slug=self.slug, status=st.OK)


def _is_challenge(response) -> bool:
    """
    Cloudflare marks a mitigated request with `Cf-Mitigated: challenge`, and the
    interstitial itself is recognisable. Both are checked: a header can change,
    and a body served with 200 would otherwise be stored as a document.
    """
    headers = getattr(response, "headers", {}) or {}
    if str(headers.get("Cf-Mitigated", "")).lower() == "challenge":
        return True
    ctype = str(headers.get("Content-Type", "")).lower()
    if "html" in ctype:
        head = (getattr(response, "text", "") or "")[:600]
        return "Just a moment" in head or "cf-browser-verification" in head
    return False
