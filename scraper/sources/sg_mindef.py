"""
Singapore MINDEF official releases — shadow adapter.

Conforms to `core.collection.contract.SourceAdapter`. It is NOT registered in
any production desk manifest: `shadow/singapore_mindef/manifest.json` lives
outside `desks/` precisely so `load_all_desks()` cannot find it, and the source
is `enabled: false`. Nothing here can reach `pla_watch.db` or `output/`.

Scope, inclusions, exclusions and rules are in
`shadow/singapore_mindef/README.md`. The rules that matter to this file:

  * identity is the canonical URL, never a title or a listing position
  * the publication date comes from the ministry's own slug, never `lastmod`
  * a missing title, date, body or identity is a refusal, not a partial record
  * robots policy is re-read every run and a disallow is a hard failure
  * an empty day is a success, and is never conflated with a listing failure

Deliberately absent: translation, classification, significance scoring and any
editorial judgement. The shadow phase proves retrieval, identity, preservation
and reliability first.
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.robotparser
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlparse, urlunparse

import requests

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, CollectionWindow, DiscoveryResult,
    ExtractedDocument, ExtractionResult, SourceAdapter, SourceHealthResult,
)

HOST = "https://www.mindef.gov.sg"
SITEMAP = HOST + "/sitemap.xml"
ROBOTS = HOST + "/robots.txt"
RELEASE_RE = re.compile(
    r"^https://www\.mindef\.gov\.sg/news-and-events/latest-releases/[^/]+/$")

#: Honest identification. A ministry that wants to refuse this collector must be
#: able to recognise it and say so in robots.txt.
USER_AGENT = ("ChinaMilWatch-ShadowCollector/0.1 "
              "(+https://chinamilwatch.org; research archive; contact via site)")

REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 1.5          # seconds between requests; one worker only
MAX_RETRIES = 2
MAX_BODY_BYTES = 4_000_000
MIN_BODY_CHARS = 200

#: Slug token -> publication family. Verified against the sampled set; an
#: unrecognised token is recorded as "other" rather than guessed at.
KINDS = {"nr": "news release", "speech": "speech", "fs": "fact sheet",
         "mq": "ministerial question", "pq": "parliamentary question"}

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


class RobotsDisallowed(RuntimeError):
    """The published policy no longer permits the release path."""


# ── pure helpers, unit-testable without a network ────────────────────────────

def canonical_url(url: str) -> Optional[str]:
    """
    The URL as published, or None when it is not a release document.

    Query strings and fragments are dropped: they are never part of a release's
    identity here, and keeping them would let one document enter twice.
    """
    if not url:
        return None
    parts = urlparse(url.strip())
    if parts.scheme != "https" or parts.netloc != "www.mindef.gov.sg":
        return None
    clean = urlunparse(("https", "www.mindef.gov.sg", parts.path, "", "", ""))
    if not clean.endswith("/"):
        clean += "/"
    return clean if RELEASE_RE.match(clean) else None


def slug_published_date(url: str) -> Optional[str]:
    """ISO date from the ministry's own slug, e.g. `/15aug26-speech/`."""
    m = re.search(r"/latest-releases/(\d{1,2})([a-z]{3})(\d{2})[-_]", url)
    if not m:
        return None
    mon = _MONTHS.get(m.group(2))
    if not mon:
        return None
    try:
        return date(2000 + int(m.group(3)), mon, int(m.group(1))).isoformat()
    except ValueError:
        return None


def publication_kind(url: str) -> str:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    token = re.sub(r"^\d{1,2}[a-z]{3}\d{2}[-_]", "", tail)
    token = re.sub(r"\d+$", "", token)
    return KINDS.get(token, "other")


def visible_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|nav|header|footer|form)[^>]*>.*?</\1>",
                  " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"),
                    ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(ent, ch)
    return re.sub(r"\s+", " ", text).strip()


def document_title(html: str) -> Optional[str]:
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if m and m.group(1).strip():
        return m.group(1).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        t = visible_text(m.group(1))
        if t:
            return t
    return None


def document_body(html: str) -> str:
    trimmed = re.sub(r"(?is)^.*?<h1[^>]*>.*?</h1>", " ", html, count=1)
    return visible_text(trimmed) or visible_text(html)


def parse_sitemap(xml: str):
    """(canonical_url, lastmod) for release documents. Order is the file's."""
    out = []
    for loc, lastmod in re.findall(
            r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]*)</lastmod>", xml):
        c = canonical_url(loc)
        if c:
            out.append((c, lastmod.strip()))
    return out


def select_window(entries, window: CollectionWindow, cap: int):
    """
    Deterministic bounded selection.

    Sorted by publication date descending then URL, so the same corpus and the
    same window always yield the same list in the same order regardless of the
    sitemap's ordering. The cap bounds a first run; it is not a filter on what
    the desk covers.
    """
    start = window.target_date - timedelta(days=window.lookback_days)
    chosen = []
    for url, lastmod in entries:
        published = slug_published_date(url)
        if not published:
            continue
        d = date.fromisoformat(published)
        if start <= d <= window.target_date:
            chosen.append((published, url, lastmod))
    chosen.sort(key=lambda r: (r[0], r[1]), reverse=True)
    return chosen[:cap]


class SGMindefAdapter(SourceAdapter):
    """Discovery, retrieval and extraction. No storage, no analysis."""

    implemented = True

    def __init__(self, source, session=None, cap: int = 40,
                 sleeper=time.sleep) -> None:
        super().__init__(source)
        self._session = session or requests.Session()
        self._cap = cap
        self._sleep = sleeper
        self._last_request = 0.0

    # -- policy ---------------------------------------------------------------

    def assert_robots_allows(self, robots_text: str, url: str) -> None:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(robots_text.splitlines())
        if not rp.can_fetch(USER_AGENT, url):
            raise RobotsDisallowed(
                "robots.txt disallows %s for this collector" % url)

    # -- transport ------------------------------------------------------------

    def _get(self, url: str):
        wait = REQUEST_INTERVAL - (time.monotonic() - self._last_request)
        if wait > 0:
            self._sleep(wait)
        last = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._session.get(
                    url, timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": USER_AGENT})
                self._last_request = time.monotonic()
                return resp
            except Exception as exc:            # transport only
                last = exc
                if attempt < MAX_RETRIES:
                    self._sleep(2 ** attempt)
        raise last

    # -- contract -------------------------------------------------------------

    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        try:
            robots = self._get(ROBOTS)
            if robots.status_code != 200:
                return DiscoveryResult(
                    self.slug, st.LISTING_FAILURE,
                    error_detail="robots.txt returned HTTP %d" % robots.status_code)
            self.assert_robots_allows(robots.text, SITEMAP)
        except RobotsDisallowed as exc:
            return DiscoveryResult(self.slug, st.AUTH_FAILURE,
                                   error_detail=str(exc))
        except Exception as exc:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="robots.txt unreachable: %s" % type(exc).__name__)

        try:
            resp = self._get(SITEMAP)
        except Exception as exc:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="sitemap unreachable: %s" % type(exc).__name__)
        if resp.status_code == 403:
            return DiscoveryResult(
                self.slug, st.AUTH_FAILURE,
                error_detail="sitemap returned HTTP 403")
        if resp.status_code != 200:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="sitemap returned HTTP %d" % resp.status_code)

        entries = parse_sitemap(resp.text)
        if not entries:
            # An empty parse of a 200 sitemap is a listing failure, not silence:
            # the ministry publishes thousands of URLs, so zero means the shape
            # changed under us.
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="sitemap parsed to zero release URLs")

        selected = select_window(entries, window, self._cap)
        refs = [CandidateReference(url=u, source_slug=self.slug,
                                   discovered_via=SITEMAP,
                                   hint_published_date=p)
                for p, u, _ in selected]
        if not refs:
            return DiscoveryResult(self.slug, st.OK_NO_PUBLICATIONS)
        return DiscoveryResult(self.slug, st.OK, references=refs)

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        try:
            resp = self._get(reference.url)
        except Exception as exc:
            return CaptureResult(reference, st.FETCH_FAILURE, reference.url,
                                 error_detail="%s" % type(exc).__name__)
        if resp.status_code == 403:
            return CaptureResult(reference, st.AUTH_FAILURE, reference.url,
                                 http_status=403,
                                 error_detail="item returned HTTP 403")
        if resp.status_code != 200:
            return CaptureResult(reference, st.FETCH_FAILURE, reference.url,
                                 http_status=resp.status_code,
                                 error_detail="HTTP %d" % resp.status_code)
        body = resp.text or ""
        payload = body.encode("utf-8", "ignore")
        if len(payload) > MAX_BODY_BYTES:
            return CaptureResult(reference, st.OVERSIZED_RESPONSE, reference.url,
                                 http_status=200, payload_bytes=len(payload),
                                 error_detail="body exceeds %d bytes" % MAX_BODY_BYTES)
        return CaptureResult(
            reference, st.OK, reference.url,
            final_url=getattr(resp, "url", reference.url),
            http_status=200,
            content_type=(resp.headers or {}).get("Content-Type"),
            payload_bytes=len(payload),
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            body=body)

    def extract(self, capture: CaptureResult) -> ExtractionResult:
        """One document or a refusal. Never a partial record."""
        if not capture.ok or not capture.body:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE,
                                    error_detail="no body to extract")
        url = canonical_url(capture.reference.url)
        if not url:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="not a canonical release URL: %s"
                             % capture.reference.url)
        title = document_title(capture.body)
        if not title:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE,
                                    error_detail="no title: %s" % url)
        published = slug_published_date(url)
        if not published:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="no publication date in the official slug: %s" % url)
        body = document_body(capture.body)
        if len(body) < MIN_BODY_CHARS:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="body too short to be a published record "
                             "(%d chars): %s" % (len(body), url))
        doc = ExtractedDocument(
            url=url, source_slug=self.slug, title_original=title,
            text_original=body, published_date=published, language_tag="en",
            extra={
                "publication_kind": publication_kind(url),
                "content_sha256": hashlib.sha256(
                    body.encode("utf-8")).hexdigest(),
                "capture_sha256": capture.payload_sha256,
                "retrieved_at": capture.retrieved_at,
            })
        return ExtractionResult(self.slug, st.OK, documents=[doc])

    def healthcheck(self) -> SourceHealthResult:
        return SourceHealthResult(
            self.slug, st.SKIPPED_DISABLED,
            "shadow evaluation; not enabled in any production desk")
