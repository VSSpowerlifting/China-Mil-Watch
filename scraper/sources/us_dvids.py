"""
US Indo-Pacific — DVIDS shadow adapter.

Conforms to `core.collection.contract.SourceAdapter`. It is NOT registered in
any production desk manifest: `shadow/us_indopacom/manifest.json` lives outside
`desks/` precisely so `load_all_desks()` cannot find it, and the source is
`enabled: false`. Nothing here can reach `pla_watch.db` or `output/`.

WHAT THIS SOURCE IS
-------------------
**DVIDS USINDOPACOM-tagged reference stream.**

  * a **Tier B DoD media-service feed** -- the publisher is Defense Media
    Activity, a DoD field activity, not U.S. Pacific Command
  * **unit tagging does not imply command authorship or comprehensive
    Indo-Pacific relevance**; the tag is applied by the submitting unit
  * it is **not a complete USINDOPACOM command-release wire**
  * it is **not presently a peer of the China Desk**
  * **the public US Indo-Pacific Reference Desk remains `access_blocked`**
  * **shadow collection evaluates whether this source can support that desk
    later** -- it does not presuppose that it can

No record may be called Indo-Pacific-relevant merely because DVIDS tagged it
to the unit. Measured 2026-09-17: 428 items, 171 of them `/news/`, and 15 of
those 171 titles carry any Indo-Pacific keyword at all. The complete eligible
`/news/` stream is collected and **no relevance filter is applied**: filtering
at collection would predetermine the usefulness question this shadow phase
exists to measure.

WHY DVIDS AND NOT pacom.mil
---------------------------
`www.pacom.mil` and `www.defense.gov` return **HTTP 403 for `robots.txt`
itself**. That finding is recorded in `desks/registry.json` and in
`docs/DESK_RELIABILITY_REVIEW_2026-09-16.md`, and this adapter does not
reinterpret, soften or route around it. A host that will not serve its own
rules has not granted permission, and an RSS endpoint that happens to answer
does not supply the permission the rules file withheld. DVIDS is a different
host with a different, readable policy — it is an alternative official route,
not a workaround for the blocked one. The `us-indopacific` desk therefore stays
`access_blocked` until this collector has actually run and been reviewed.

RULES THAT MATTER TO THIS FILE
------------------------------
  * identity is the feed's own `guid` (`news:574946`), and it must agree with
    the numeric id in the item's link, or the item is refused
  * the canonical URL is the item's `link`, host-checked and normalized; a
    link on any other host is refused rather than followed
  * the publication date is the publisher's own `pubDate`, kept in the offset
    the publisher declared, with the UTC instant preserved alongside it
  * only `/news/` items are accepted; image, video and audio items are counted
    and rejected, never coerced into text records
  * robots policy is re-read every run and a disallow is a hard failure
  * `/search/` and `/tags/` are Disallow in DVIDS robots and are never used;
    discovery is the feed alone, and no identifier is ever enumerated
  * an empty feed window is a success, never a listing failure

Deliberately absent: translation, classification, significance scoring and any
editorial judgement. The shadow phase proves retrieval, identity, preservation
and reliability first.
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, CollectionWindow, DiscoveryResult,
    ExtractedDocument, ExtractionResult, SourceAdapter, SourceHealthResult,
)

HOST = "https://www.dvidshub.net"
FEED = HOST + "/rss/unit/USINDOPACOM"
ROBOTS = HOST + "/robots.txt"

#: The only hosts this adapter will retrieve from. A feed link pointing
#: anywhere else is a refusal, not a redirect to follow. Mirrors the host
#: governance established for `xinhua_mil`.
PERMITTED_HOSTS = ("www.dvidshub.net", "dvidshub.net")

#: Honest identification. A publisher that wants to refuse this collector must
#: be able to recognise it and say so in robots.txt.
USER_AGENT = ("ChinaMilWatch-ShadowCollector/0.1 "
              "(+https://chinamilwatch.org; research archive; contact via site)")

REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 2.0          # seconds between requests; one worker only
MAX_RETRIES = 2                 # transport errors only; never a 4xx
MAX_BODY_BYTES = 4_000_000
MAX_FEED_BYTES = 12_000_000
MIN_BODY_CHARS = 200

#: `/news/<id>/<slug>`. The id is the same integer the guid carries.
NEWS_PATH_RE = re.compile(r"^/news/(\d+)/[^/]+$")
GUID_RE = re.compile(r"^news:(\d+)$")

#: First path segment -> what DVIDS calls the asset. Only `news` is text.
MEDIA_SEGMENTS = ("image", "video", "audio", "publication", "graphic")

#: The body container, verified stable across sampled articles. Its children
#: are `p` and `strong` only: no related-article rail, no boilerplate.
BODY_SELECTOR = "div.news-body"

# ── Rejection taxonomy ────────────────────────────────────────────────────────
# Every discarded item is counted under exactly one of these. A collector that
# reports only what it kept cannot be audited.

R_NOT_NEWS_MEDIA = "not_news_media"        # image/video/audio/publication item
R_FOREIGN_HOST = "foreign_host"            # link outside PERMITTED_HOSTS
R_UNPARSEABLE_URL = "unparseable_url"      # not /news/<id>/<slug>
R_MISSING_GUID = "missing_guid"
R_IDENTITY_MISMATCH = "identity_mismatch"  # guid id != link id
R_MISSING_LINK = "missing_link"
R_MISSING_TITLE = "missing_title"
R_MISSING_PUBDATE = "missing_pubdate"
R_UNPARSEABLE_PUBDATE = "unparseable_pubdate"
R_OUTSIDE_WINDOW = "outside_window"
R_DUPLICATE_IN_FEED = "duplicate_in_feed"

REJECTION_REASONS = (
    R_NOT_NEWS_MEDIA, R_FOREIGN_HOST, R_UNPARSEABLE_URL, R_MISSING_GUID,
    R_IDENTITY_MISMATCH, R_MISSING_LINK, R_MISSING_TITLE, R_MISSING_PUBDATE,
    R_UNPARSEABLE_PUBDATE, R_OUTSIDE_WINDOW, R_DUPLICATE_IN_FEED,
)


class RobotsDisallowed(RuntimeError):
    """The published policy no longer permits the feed or an article path."""


class FeedUnparseable(RuntimeError):
    """The feed body is not XML we can read at all."""


# ── pure helpers, unit-testable without a network ────────────────────────────

def canonical_url(url: str) -> Optional[str]:
    """
    The article URL as published, or None when it is not a DVIDS news document.

    Query strings and fragments are dropped: DVIDS appends tracking parameters
    in some contexts and they are never part of a document's identity. A host
    outside `PERMITTED_HOSTS` returns None rather than being rewritten — this
    adapter refuses foreign hosts, it does not relocate them.
    """
    if not url:
        return None
    parts = urlparse(url.strip())
    if parts.scheme not in ("http", "https"):
        return None
    if parts.netloc.lower() not in PERMITTED_HOSTS:
        return None
    path = parts.path.rstrip("/")
    if not NEWS_PATH_RE.match(path):
        return None
    return urlunparse(("https", "www.dvidshub.net", path, "", "", ""))


def url_media_segment(url: str) -> Optional[str]:
    """The first path segment (`news`, `image`, `video`, …) for classification."""
    if not url:
        return None
    parts = urlparse(url.strip())
    if parts.netloc.lower() not in PERMITTED_HOSTS:
        return None
    segs = [s for s in parts.path.split("/") if s]
    return segs[0].lower() if segs else None


def url_identity(url: str) -> Optional[str]:
    """The numeric document id carried in a canonical news URL."""
    canon = canonical_url(url)
    if not canon:
        return None
    m = NEWS_PATH_RE.match(urlparse(canon).path)
    return m.group(1) if m else None


def guid_identity(guid: str) -> Optional[str]:
    """
    The numeric document id carried by the feed's own `guid`.

    DVIDS emits `news:574946`. The guid is the source's stable identifier and
    is preferred over anything derived from the slug, which can be re-worded.
    """
    if not guid:
        return None
    m = GUID_RE.match(guid.strip())
    return m.group(1) if m else None


def parse_pubdate(raw: str) -> Optional[Tuple[str, str, str]]:
    """
    `(published_date, published_at_utc, published_at_original)`.

    DVIDS emits RFC-2822 with a real offset, e.g.
    `Wed, 16 Sep 2026 22:13:04 -0400`. That item is published on the **16th**
    in the publisher's own reckoning and on the **17th** in UTC. Recording the
    UTC date as the publication date would silently re-date a fifth of an
    evening-heavy feed, so the date kept is the one in the offset the publisher
    declared, and the UTC instant is preserved beside it rather than instead of
    it. A timestamp with no offset is refused: guessing a zone is inventing a
    fact about when something was published.
    """
    if not raw or not raw.strip():
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError, IndexError):
        return None
    if dt is None or dt.tzinfo is None:
        return None
    return (dt.date().isoformat(),
            dt.astimezone(timezone.utc).isoformat(timespec="seconds"),
            raw.strip())


class FeedItem:
    """One accepted `/news/` item, with everything identity needs."""

    __slots__ = ("identity", "url", "title", "published_date",
                 "published_at_utc", "published_at_original", "author")

    def __init__(self, identity, url, title, published_date,
                 published_at_utc, published_at_original, author):
        self.identity = identity
        self.url = url
        self.title = title
        self.published_date = published_date
        self.published_at_utc = published_at_utc
        self.published_at_original = published_at_original
        self.author = author

    def __repr__(self):                                   # pragma: no cover
        return "FeedItem(%s, %s)" % (self.identity, self.published_date)


def parse_feed(xml_text) -> Tuple[List[FeedItem], Dict[str, int]]:
    """
    `(items, rejections)` for one feed body.

    Raises `FeedUnparseable` only when the document is not XML at all. A single
    malformed *item* is counted and skipped: one bad entry must not discard a
    feed of several hundred good ones, and the count is what makes the loss
    visible instead of silent.
    """
    if isinstance(xml_text, bytes):
        payload = xml_text
    else:
        payload = (xml_text or "").encode("utf-8", "replace")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise FeedUnparseable(str(exc))

    rejections = {r: 0 for r in REJECTION_REASONS}
    items: List[FeedItem] = []
    seen: Dict[str, str] = {}

    for node in root.findall(".//item"):
        link = (node.findtext("link") or "").strip()
        guid = (node.findtext("guid") or "").strip()
        title = (node.findtext("title") or "").strip()
        pubdate = (node.findtext("pubDate") or "").strip()
        author = (node.findtext("author") or "").strip() or None

        if not link:
            rejections[R_MISSING_LINK] += 1
            continue

        segment = url_media_segment(link)
        if segment is None:
            rejections[R_FOREIGN_HOST] += 1
            continue
        if segment in MEDIA_SEGMENTS:
            # A photo or a video is not a document with a body. Counted, never
            # stored as a text record with an empty body.
            rejections[R_NOT_NEWS_MEDIA] += 1
            continue

        canon = canonical_url(link)
        if not canon:
            rejections[R_UNPARSEABLE_URL] += 1
            continue

        link_id = url_identity(canon)
        gid = guid_identity(guid)
        if gid is None:
            rejections[R_MISSING_GUID] += 1
            continue
        if gid != link_id:
            # The feed disagrees with itself about which document this is.
            # Picking one would be choosing which fact to ignore.
            rejections[R_IDENTITY_MISMATCH] += 1
            continue
        if not title:
            rejections[R_MISSING_TITLE] += 1
            continue
        if not pubdate:
            rejections[R_MISSING_PUBDATE] += 1
            continue
        parsed = parse_pubdate(pubdate)
        if parsed is None:
            rejections[R_UNPARSEABLE_PUBDATE] += 1
            continue
        if gid in seen:
            rejections[R_DUPLICATE_IN_FEED] += 1
            continue
        seen[gid] = canon

        published_date, published_utc, published_raw = parsed
        items.append(FeedItem(gid, canon, title, published_date,
                              published_utc, published_raw, author))

    return items, rejections


def select_window(items: List[FeedItem], window: CollectionWindow,
                  cap: int, rejections: Optional[Dict[str, int]] = None):
    """
    Deterministic bounded selection.

    Sorted by publication date descending then identity ascending, so the same
    feed and the same window always yield the same list in the same order
    regardless of the feed's ordering. Identity, not title, breaks ties: two
    documents may legitimately share a title. The cap bounds a first run; it is
    not a statement about what the desk covers.
    """
    start = window.target_date - timedelta(days=window.lookback_days)
    chosen = []
    for it in items:
        d = datetime.fromisoformat(it.published_date).date()
        if start <= d <= window.target_date:
            chosen.append(it)
        elif rejections is not None:
            rejections[R_OUTSIDE_WINDOW] += 1
    chosen.sort(key=lambda i: (i.published_date, int(i.identity)), reverse=True)
    return chosen[:cap]


def document_title(html: str) -> Optional[str]:
    """og:title first — DVIDS truncates the visible `h1` on long headlines."""
    soup = BeautifulSoup(html or "", "html.parser")
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and (meta.get("content") or "").strip():
        return meta["content"].strip()
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(" ", strip=True)
        if text:
            return text
    return None


#: DVIDS renders a metadata table carrying `Location:` and links each item to
#: the submitting unit at `/unit/<code>`. Both are the publisher's own
#: structured fields, which is why they are read instead of a dateline regex:
#: only one of three sampled bodies carried a parseable dateline at all.
_LOCATION_RE = re.compile(r"Location:\s*(.+?)(?:\s+Web Views|\s+Downloads|$)")
_UNIT_HREF_RE = re.compile(r"^/unit/([A-Za-z0-9._-]+)/?$")


def document_location(html: str) -> Optional[str]:
    """
    The publisher's own `Location:` field, e.g. `FORT SMITH, ARKANSAS, US`.

    Recorded for the checkpoint report, never to decide whether a record is
    kept. Geography is evidence about what this stream carries; it is not a
    filter, and treating it as one would decide the question the shadow phase
    exists to measure.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    text = " ".join(tbl.get_text(" ", strip=True)
                    for tbl in soup.find_all("table"))
    match = _LOCATION_RE.search(text)
    return match.group(1).strip() if match else None


def document_units(html: str):
    """
    The submitting unit codes the page links to, e.g. `['188WG']`.

    `/unit/` is permitted by DVIDS robots; these are read from links already
    present on the retrieved page and are never followed. Like location, this
    is reporting material, not a gate.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    found = set()
    for anchor in soup.find_all("a", href=True):
        match = _UNIT_HREF_RE.match(anchor["href"].strip())
        if match:
            found.add(match.group(1))
    return sorted(found)


def document_body(html: str) -> Tuple[str, bool]:
    """
    `(text, container_present)`.

    The second value is the distinction the China desk had to learn the hard
    way: an empty string because the container was missing is **template
    drift**, and an empty string because the container held no prose is a
    **media-only entry**. Returning one value for both would make a parser bug
    indistinguishable from a legitimately body-less item, which is exactly the
    confusion that let Global Times store empty bodies for live documents.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    node = soup.select_one(BODY_SELECTOR)
    if node is None:
        return "", False
    for junk in node.select("script, style, iframe, figure, .relatedimage"):
        junk.decompose()
    lines = [ln.strip() for ln in node.get_text("\n").splitlines()]
    return "\n".join(ln for ln in lines if ln), True


class USDvidsAdapter(SourceAdapter):
    """Discovery, retrieval and extraction. No storage, no analysis."""

    implemented = True

    def __init__(self, source, session=None, cap: int = 40,
                 sleeper=time.sleep) -> None:
        super().__init__(source)
        self._session = session or requests.Session()
        self._cap = cap
        self._sleep = sleeper
        self._last_request = 0.0
        #: Populated by `discover()`; the runner reads it for the ledger.
        self.rejections: Dict[str, int] = {r: 0 for r in REJECTION_REASONS}

    # -- policy ---------------------------------------------------------------

    def assert_robots_allows(self, robots_text: str, url: str) -> None:
        rp = urllib.robotparser.RobotFileParser()
        rp.parse((robots_text or "").splitlines())
        if not rp.can_fetch(USER_AGENT, url):
            raise RobotsDisallowed(
                "robots.txt disallows %s for this collector" % url)

    # -- transport ------------------------------------------------------------

    def _get(self, url: str):
        """
        One polite request. Retries cover transport failures only: a 403 or a
        404 is an answer, and asking again is how a collector turns a refusal
        into a hammering.
        """
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
        self.rejections = {r: 0 for r in REJECTION_REASONS}
        try:
            robots = self._get(ROBOTS)
            if robots.status_code == 403:
                # The pacom.mil finding, exactly: a host that refuses its own
                # rules file has not granted permission.
                return DiscoveryResult(
                    self.slug, st.AUTH_FAILURE,
                    error_detail="robots.txt returned HTTP 403; no basis to "
                                 "conclude collection is permitted")
            if robots.status_code != 200:
                return DiscoveryResult(
                    self.slug, st.LISTING_FAILURE,
                    error_detail="robots.txt returned HTTP %d"
                                 % robots.status_code)
            self.assert_robots_allows(robots.text, FEED)
        except RobotsDisallowed as exc:
            return DiscoveryResult(self.slug, st.AUTH_FAILURE,
                                   error_detail=str(exc))
        except Exception as exc:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="robots.txt unreachable: %s" % type(exc).__name__)

        try:
            resp = self._get(FEED)
        except Exception as exc:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="feed unreachable: %s" % type(exc).__name__)
        if resp.status_code == 403:
            return DiscoveryResult(self.slug, st.AUTH_FAILURE,
                                   error_detail="feed returned HTTP 403")
        if resp.status_code != 200:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="feed returned HTTP %d" % resp.status_code)

        payload = resp.content or b""
        if len(payload) > MAX_FEED_BYTES:
            return DiscoveryResult(
                self.slug, st.OVERSIZED_RESPONSE,
                error_detail="feed exceeds %d bytes" % MAX_FEED_BYTES)

        try:
            items, rejections = parse_feed(payload)
        except FeedUnparseable as exc:
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="feed did not parse as XML: %s" % exc)
        self.rejections = rejections

        if not items and not any(rejections.values()):
            # A 200 that contains no <item> at all is a shape change, not a
            # quiet day: this feed carries hundreds of items continuously.
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="feed parsed to zero items of any kind")

        selected = select_window(items, window, self._cap, rejections)
        refs = [CandidateReference(url=i.url, source_slug=self.slug,
                                   discovered_via=FEED,
                                   hint_published_date=i.published_date)
                for i in selected]
        # Keyed by IDENTITY, not by URL. DVIDS can re-word a slug without
        # the document changing, and a lookup that a re-wording breaks would
        # make the stable identifier decorative.
        self._by_identity = {i.identity: i for i in selected}
        if not refs:
            return DiscoveryResult(self.slug, st.OK_NO_PUBLICATIONS)
        return DiscoveryResult(self.slug, st.OK, references=refs)

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        if canonical_url(reference.url) is None:
            # Defence in depth: nothing off-host is retrieved even if a caller
            # hands this adapter a reference it did not discover.
            return CaptureResult(
                reference, st.DISALLOWED_REDIRECT, reference.url,
                error_detail="refusing to retrieve a non-permitted URL: %s"
                             % reference.url)
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
        final = getattr(resp, "url", reference.url) or reference.url
        if canonical_url(final) is None:
            return CaptureResult(
                reference, st.DISALLOWED_REDIRECT, reference.url,
                final_url=final, http_status=resp.status_code,
                error_detail="redirected off the permitted host: %s" % final)
        body = resp.text or ""
        payload = body.encode("utf-8", "ignore")
        if len(payload) > MAX_BODY_BYTES:
            return CaptureResult(reference, st.OVERSIZED_RESPONSE,
                                 reference.url, http_status=200,
                                 payload_bytes=len(payload),
                                 error_detail="body exceeds %d bytes"
                                              % MAX_BODY_BYTES)
        return CaptureResult(
            reference, st.OK, reference.url, final_url=final, http_status=200,
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
                error_detail="not a canonical news URL: %s"
                             % capture.reference.url)
        item = getattr(self, "_by_identity", {}).get(url_identity(url))
        title = document_title(capture.body) or (item.title if item else None)
        if not title:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE,
                                    error_detail="no title: %s" % url)
        if item is None:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="no feed record for %s; publication date and "
                             "identity come from the feed, never from the "
                             "article page" % url)
        body, container = document_body(capture.body)
        if not container:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="body container %s absent — template drift, not "
                             "an empty document: %s" % (BODY_SELECTOR, url))
        if len(body.strip()) < MIN_BODY_CHARS:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="body container present but carried %d chars; "
                             "a news item with no prose is rejected, not "
                             "stored empty: %s" % (len(body.strip()), url))
        doc = ExtractedDocument(
            url=url, source_slug=self.slug, title_original=title,
            text_original=body, published_date=item.published_date,
            language_tag="en",
            extra={
                "source_identity": item.identity,
                "published_at_utc": item.published_at_utc,
                "published_at_original": item.published_at_original,
                "byline": item.author,
                "location": document_location(capture.body),
                "units": ",".join(document_units(capture.body)) or None,
                "publication_kind": "public affairs release",
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
