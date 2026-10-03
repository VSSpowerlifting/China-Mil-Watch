"""
Singapore MINDEF official releases adapter.

Conforms to `core.collection.contract.SourceAdapter`. Registered in
`desks/singapore/manifest.json`, which `load_all_desks()` discovers, so this
adapter is reachable from `pla_watch.db` and `output/` through the ordinary
scheduled pipeline (`pipeline.py`, invoked by `.github/workflows/daily_update.yml`)
the same way every other source is. It is also still run, unchanged, by the
separate shadow evaluation workflow (`scripts/shadow_collect.py`,
`.github/workflows/singapore_shadow.yml`), which writes to isolated shadow
state and never touches production.

Scope, inclusions, exclusions and rules are in
`shadow/singapore_mindef/README.md`. The rules that matter to this file:

  * identity is the canonical URL, never a title or a listing position
  * the publication date comes from the ministry's own slug, never `lastmod`
  * a missing title, date, body or identity is a refusal, not a partial record;
    the one exception is a release whose article is only an image, which the
    scheduled collection keeps as a text-unavailable record (see
    `article_evidence` and `_extract`)
  * robots policy is re-read every run and a disallow is a hard failure
  * an empty day is a success, and is never conflated with a listing failure
  * two records, `15aug26-speech` and `16sep26-speech`, are held out of
    everything this adapter discovers (see `HELD_RELEASE_SLUGS` below) — the
    governed exclusion decided in DECISION_LOG.md, 2026-09-21, for unrepaired
    CJK extraction damage, enforced here so a live run can never reintroduce
    them even though MINDEF's own sitemap still lists both

Deliberately absent: translation, classification, significance scoring and any
editorial judgement.
"""

from __future__ import annotations

import codecs
import hashlib
import logging
import re
import time
import urllib.robotparser
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, CollectionWindow, DiscoveryResult,
    ExtractedDocument, ExtractionResult, SourceAdapter, SourceHealthResult,
    SourceRunResult,
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

HOST = "https://www.mindef.gov.sg"
SITEMAP = HOST + "/sitemap.xml"
ROBOTS = HOST + "/robots.txt"
RELEASE_RE = re.compile(
    r"^https://www\.mindef\.gov\.sg/news-and-events/latest-releases/[^/]+/$")

#: Governed holds. Both records were promoted from the shadow corpus with
#: unrepaired CJK-passage extraction damage the correction overlay could not
#: fix, and DECISION_LOG.md (2026-09-21) held both out of the 57-record
#: production promotion rather than publish damaged text. That promotion was
#: a one-time batch write; it did not, and could not, stop a live collection
#: run from rediscovering these same URLs through MINDEF's own sitemap, which
#: still lists them. This set is the enforcement that closes that gap: any
#: scheduled `discover()` call excludes them before a window or cap is ever
#: applied, so neither can reach `fetch()`, `extract()`, or `pla_watch.db`.
HELD_RELEASE_SLUGS = frozenset({"15aug26-speech", "16sep26-speech"})

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


def release_slug(url: str) -> Optional[str]:
    """The path token that identifies a release, e.g. '15aug26-speech'."""
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    return tail or None


def publication_kind(url: str) -> str:
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    token = re.sub(r"^\d{1,2}[a-z]{3}\d{2}[-_]", "", tail)
    token = re.sub(r"\d+$", "", token)
    return KINDS.get(token, "other")


#: How many leading bytes may declare an encoding. The HTML standard's own
#: prescan limit; a declaration further in is not one a browser would honour.
META_PRESCAN_BYTES = 1024

#: Used only when nothing declares an encoding at all. Never a guess at the
#: bytes — a documented default, and `decode_response` always says it used it.
UNDECLARED_DEFAULT = "utf-8"

_META_CHARSET_RE = re.compile(
    rb"""<meta[^>]+charset\s*=\s*["']?\s*([A-Za-z0-9_:.-]+)""", re.I)
_CT_CHARSET_RE = re.compile(r"""charset\s*=\s*["']?\s*([A-Za-z0-9_:.-]+)""", re.I)

#: Byte-order marks, which outrank every declaration.
_BOMS = ((b"\xef\xbb\xbf", "utf-8-sig"),
         (b"\xff\xfe", "utf-16"),
         (b"\xfe\xff", "utf-16"))


def declared_encoding(raw: bytes, content_type: Optional[str] = None):
    """`(encoding, source)` for a byte stream, by declaration only.

    The order is the HTML standard's: a `charset` on the HTTP `Content-Type`
    wins, then a byte-order mark, then a `<meta charset>` within the first
    1024 bytes, then a documented default. `source` is one of `http-header`,
    `bom`, `meta` or `undeclared`, and the caller is expected to surface it —
    "we fell back" must be visible, not inferred.

    Nothing here inspects the payload to guess. `requests` would answer
    ISO-8859-1 for any `text/*` without a charset, per RFC 2616, which is how
    mindef.gov.sg — `Content-Type: text/html`, no charset, `<meta charset=
    utf-8>` — had every apostrophe and dash in the corpus mis-decoded.
    """
    if content_type:
        m = _CT_CHARSET_RE.search(content_type)
        if m:
            return m.group(1).strip().lower(), "http-header"
    for bom, enc in _BOMS:
        if raw.startswith(bom):
            return enc, "bom"
    m = _META_CHARSET_RE.search(raw[:META_PRESCAN_BYTES])
    if m:
        return m.group(1).decode("ascii", "ignore").strip().lower(), "meta"
    return UNDECLARED_DEFAULT, "undeclared"


class DecodedResponse:
    """Decoded text plus how the encoding was chosen, so a run can report it."""

    __slots__ = ("text", "encoding", "source", "replacements")

    def __init__(self, text, encoding, source, replacements):
        self.text = text
        self.encoding = encoding
        self.source = source
        #: U+FFFD introduced by a lossy fallback. Zero on a clean decode.
        self.replacements = replacements

    @property
    def lossy(self) -> bool:
        return self.replacements > 0


def decode_response(raw: bytes, content_type: Optional[str] = None) -> DecodedResponse:
    """Decode by declaration, strictly, and say so when that is not possible.

    A declared encoding that the bytes contradict is not quietly swapped for a
    better guess. The strict decode is attempted first; only if it raises does
    this fall back to replacement characters, and the count comes back with the
    text so a caller can refuse or log rather than store damage silently.
    """
    encoding, source = declared_encoding(raw, content_type)
    try:
        return DecodedResponse(raw.decode(encoding), encoding, source, 0)
    except (UnicodeDecodeError, LookupError):
        text = raw.decode(encoding, "replace") if _known(encoding) \
            else raw.decode(UNDECLARED_DEFAULT, "replace")
        return DecodedResponse(text, encoding, source, text.count("\ufffd"))


def _known(encoding: str) -> bool:
    """Whether Python has this codec.

    `codecs.lookup`, not a trial decode: decoding an empty bytes object takes a
    fast path that never consults the codec registry, so `b"".decode(junk)`
    happily returns `""` and would report an unknown encoding as known.
    """
    try:
        codecs.lookup(encoding)
        return True
    except LookupError:
        return False


def response_text(resp) -> str:
    """The decoded body of a `requests` response, by declaration.

    Deliberately not `resp.text`: that applies RFC 2616's ISO-8859-1 default to
    any `text/*` served without a charset, which is exactly this ministry.
    """
    decoded = decode_response(resp.content or b"",
                              (resp.headers or {}).get("Content-Type"))
    if decoded.lossy:
        logging.getLogger(__name__).warning(
            "%s: %d byte(s) undecodable as %s (declared via %s); replaced",
            getattr(resp, "url", "?"), decoded.replacements,
            decoded.encoding, decoded.source)
    return decoded.text


def visible_text(markup: str) -> str:
    """Reader-visible text of an HTML fragment.

    Entity decoding is `html.unescape`, not a hand-written table. The table
    this replaced knew six entities and missed `&#x27;` — the hexadecimal
    spelling of the apostrophe the ministry's CMS actually emits — which left
    84 literal `&#x27;` sequences in 29 of the 59 Singapore shadow records.
    It also decoded in table order rather than in one pass, so it rewrote
    `&amp;` to `&` and then read the `&#39;` it had just manufactured: a page
    that escaped an entity for display ("&amp;#39;") came out as an apostrophe
    instead of the literal text `&#39;`. `unescape` scans once, left to right,
    and does neither.

    Order matters and is deliberate: tags are stripped *before* entities are
    decoded, so markup a page escaped for display stays text and can never be
    promoted into real markup.
    """
    markup = re.sub(r"(?is)<(script|style|nav|header|footer|form)[^>]*>.*?</\1>",
                    " ", markup)
    text = re.sub(r"(?s)<[^>]+>", " ", markup)
    text = unescape(text)
    # `\s` covers the U+00A0 that `&nbsp;` decodes to, so the collapse below
    # still flattens non-breaking spaces the way the old table did.
    return re.sub(r"\s+", " ", text).strip()


def document_title(markup: str) -> Optional[str]:
    """The release's own title.

    The `og:title` branch decodes entities too. An attribute value is escaped
    by definition, so what the meta tag carries is never what a reader sees —
    this branch used to return it raw, which is why four stored titles kept
    `&#x27;`, `&quot;` and `&amp;` verbatim. The `<h1>` branch already decoded,
    via `visible_text`; the two branches now agree.
    """
    m = re.search(r'<meta property="og:title" content="([^"]+)"', markup)
    if m and m.group(1).strip():
        decoded = unescape(m.group(1)).strip()
        if decoded:
            return decoded
    m = re.search(r"<h1[^>]*>(.*?)</h1>", markup, re.S)
    if m:
        t = visible_text(m.group(1))
        if t:
            return t
    return None


def document_body(html: str) -> str:
    trimmed = re.sub(r"(?is)^.*?<h1[^>]*>.*?</h1>", " ", html, count=1)
    return visible_text(trimmed) or visible_text(html)


#: The ministry's own furniture at the foot of an article: a bold "More
#: Resources" label above links to related releases. It is page structure, not
#: the release's text, so it never counts as prose.
RESOURCES_LABEL = "more resources"


class ArticleEvidence:
    """What the article container of a release page holds.

    `prose_chars` counts the release's own words: the lede and every block in
    the container except the resources label and paragraphs that are only
    links. `images` counts `<img>` elements with a source. Alt text and file
    names are attributes, not text, and are never read.
    """

    __slots__ = ("prose_chars", "images")

    def __init__(self, prose_chars: int, images: int) -> None:
        self.prose_chars = prose_chars
        self.images = images

    @property
    def is_image_only(self) -> bool:
        return self.images > 0 and self.prose_chars == 0

    @property
    def has_prose(self) -> bool:
        return self.prose_chars > 0


def _has_class(tag, *names) -> bool:
    classes = tag.get("class") or []
    return all(n in classes for n in names)


def article_evidence(markup: str) -> Optional[ArticleEvidence]:
    """Read the release container, or None when this is not the known layout.

    The container is the `overflow-x-auto break-words` `<div>` after the page's
    `<h1>`. Finding it is the whole basis on which a page may be called
    anything other than a failure: when it is missing (a new template, an error
    page, a stub) this returns None, and the caller treats the page as it always
    did. "We cannot read this" must never be filed as "there is nothing here".
    """
    soup = BeautifulSoup(markup, "html.parser")
    h1 = soup.find("h1")
    if h1 is None:
        return None
    container = h1.find_next(
        lambda t: t.name == "div"
        and _has_class(t, "overflow-x-auto", "break-words"))
    if container is None:
        return None
    # The lede sits between the heading and the container. Walk to the
    # container rather than search the page, so a later paragraph that happens
    # to share the class cannot be mistaken for it.
    lede = ""
    for node in h1.next_elements:
        if node is container:
            break
        if getattr(node, "name", None) == "p" and _has_class(node, "prose-title-lg"):
            lede = node.get_text(" ", strip=True)
            break
    prose = lede
    images = len([i for i in container.find_all("img") if i.get("src")])
    for block in container.find_all("p"):
        text = block.get_text(" ", strip=True)
        anchors = " ".join(a.get_text(" ", strip=True)
                           for a in block.find_all("a"))
        if text.casefold() == RESOURCES_LABEL or (text and text == anchors):
            block.decompose()
    prose = (prose + " " + container.get_text(" ", strip=True)).strip()
    return ArticleEvidence(len(prose), images)


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

    #: The scheduled production window: the target date and the six slug
    #: dates before it, seven in all -- MOD China's span, for MOD China's
    #: reason. With no window, production lost three releases in its first
    #: week that the shadow collector holds (compared 2026-09-28):
    #: `22sep26-nr` and `22sep26-speech`, when the 2026-09-22 run's Singapore
    #: collection crashed and the next run looked only at 2026-09-23; and
    #: `23sep26-mq`, which the sitemap first listed two days after its slug
    #: date (shadow run 36202893583, 2026-09-25). Across the 37 releases the
    #: shadow collector saw published after it started, that is the longest
    #: listing lag observed. Seven dates covers it and a short run of failed
    #: days. It is not an outage remedy: a longer gap is recovered once, on
    #: purpose, with `pipeline.py --date`. The shadow collector passes its
    #: own window and is unaffected.
    production_lookback_days = 6

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
            self.assert_robots_allows(response_text(robots), SITEMAP)
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

        entries = parse_sitemap(response_text(resp))
        if not entries:
            # An empty parse of a 200 sitemap is a listing failure, not silence:
            # the ministry publishes thousands of URLs, so zero means the shape
            # changed under us.
            return DiscoveryResult(
                self.slug, st.LISTING_FAILURE,
                error_detail="sitemap parsed to zero release URLs")

        # Governed holds are removed before window/cap selection, not after:
        # they must never occupy a cap slot or a window position that belongs
        # to a publishable record.
        entries = [(u, lastmod) for u, lastmod in entries
                   if release_slug(u) not in HELD_RELEASE_SLUGS]

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
        body = response_text(resp) or ""
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
        """One document or a refusal. Never a partial record.

        Everything past the body check is wrapped in one try/except, matching
        `adapters.legacy.LegacyScraperAdapter.extract()`'s established pattern
        for the same reason: `collect()` (`core.collection.contract`) accumulates
        documents from multiple references in one local list and only returns
        it at the end of its loop. An uncaught exception here would not just
        fail this one release -- it would abort that whole loop and discard
        every already-extracted document from earlier references in the same
        run, which is a real cost even though nothing is corrupted (a source
        crash still degrades cleanly to ADAPTER_ERROR with zero documents
        stored). The helpers below (`document_title`, `document_body`,
        `slug_published_date`, `canonical_url`) are all written to return
        `None`/short values rather than raise for the "missing field" cases
        already handled explicitly; this catches only a genuinely unexpected
        parser bug, the one case those explicit checks cannot anticipate.
        """
        return self._extract(capture, structural=False)

    def _extract(self, capture: CaptureResult, structural: bool
                 ) -> ExtractionResult:
        """`extract()`, optionally reading the page's structure when the body
        is under `MIN_BODY_CHARS`.

        `structural=False` is `extract()` exactly as it has always been, and is
        what the shadow collector runs: a short body is a refusal, so the
        shadow corpus and its ledgers do not change. `collect()` passes True.
        A body of `MIN_BODY_CHARS` or more never reaches the structural branch,
        so every record this adapter extracted before is extracted identically.
        """
        if not capture.ok or not capture.body:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE,
                                    error_detail="no body to extract")
        try:
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
                    error_detail="no publication date in the official slug: %s"
                                 % url)
            body = document_body(capture.body)
            verdict = None
            if len(body) < MIN_BODY_CHARS:
                evidence = article_evidence(capture.body) if structural else None
                if evidence is not None and evidence.is_image_only:
                    # The container is found, holds an image, and holds no
                    # words of the release. What `document_body` returned is
                    # the page's date line and links, which are not this
                    # release's text and must not be stored as if they were.
                    # The title, URL and date are the ministry's own. The image
                    # is not read: nothing is transcribed or inferred from it.
                    body, verdict = "", "media_only"
                elif evidence is not None and evidence.has_prose:
                    # The container is found and holds prose: a genuinely
                    # short release, not a page we failed to read. Kept as
                    # text, exactly as a long one is.
                    pass
                else:
                    detail = ("body too short to be a published record "
                              "(%d chars): %s" % (len(body), url))
                    if evidence is not None:
                        detail = ("article container holds neither prose nor "
                                  "an image (%d chars): %s" % (len(body), url))
                    return ExtractionResult(
                        self.slug, st.EXTRACTION_FAILURE, error_detail=detail)
            extra = {
                "publication_kind": publication_kind(url),
                "content_sha256": hashlib.sha256(
                    body.encode("utf-8")).hexdigest(),
                "capture_sha256": capture.payload_sha256,
                "retrieved_at": capture.retrieved_at,
            }
            if verdict:
                extra["content_verdict"] = verdict
            doc = ExtractedDocument(
                url=url, source_slug=self.slug, title_original=title,
                text_original=body, published_date=published, language_tag="en",
                extra=extra)
            return ExtractionResult(self.slug, st.OK, documents=[doc])
        except Exception as exc:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="parser raised: %s: %s"
                             % (type(exc).__name__, str(exc)[:160]))

    # healthcheck() is inherited from SourceAdapter: OK when `implemented`
    # and `source.enabled` both hold, SKIPPED_DISABLED when the desk manifest
    # disables the source, offline either way. The override this replaced
    # hardcoded "shadow evaluation; not enabled in any production desk",
    # which was true only while this adapter had no production manifest.

    def collect(
        self, window: CollectionWindow
    ) -> Tuple[SourceRunResult, List[ExtractedDocument]]:
        """
        All-or-nothing collection: this run's new documents are returned only
        when every discovered reference collected cleanly.

        The inherited generic `SourceAdapter.collect()`
        (`core.collection.contract`) degrades gracefully per record -- exactly
        right for China's five sources, where one bad PLA Daily page must not
        cost the other fifty, and left unchanged there for that reason. This
        adapter overrides it instead of using that default, because Singapore's
        own history argues for the opposite: the corpus already holds two
        records a silent extraction defect damaged badly enough to need a
        governed, human-reviewed exclusion (DECISION_LOG.md, 2026-09-21) -- a
        defect `extract()`'s own checks did not catch at the time it happened.
        A live scheduled run gets no such review before publishing. So for
        this adapter specifically, ANY trouble in a batch -- a fetch failure,
        an extraction failure, or (defensively, on top of `discover()`'s own
        filter) a held URL somehow present in the result -- withholds the
        WHOLE batch rather than keeping the records that happened to succeed.
        Nothing already published is touched. A withheld record is
        rediscovered and retried by every later scheduled run whose window
        still holds its slug date -- seven runs, under
        `production_lookback_days`. Before that window existed the next run
        looked only at its own date, so a withheld or crashed day was lost to
        production outright, which is what happened on 2026-09-22.
        """
        started = _now()
        result = SourceRunResult(
            source_slug=self.slug, status=st.OK,
            desk_id=getattr(self.source, "desk_id", None), started_at=started,
        )

        if not getattr(self.source, "enabled", True):
            result.status = st.SKIPPED_DISABLED
            result.completed_at = _now()
            return result, []

        discovery = self.discover(window)
        result.references_discovered = len(discovery.references)

        if not discovery.ok or not discovery.references:
            result.status = discovery.status
            result.error_detail = discovery.error_detail
            result.completed_at = _now()
            return result, []

        documents: List[ExtractedDocument] = []
        fetch_failures = 0
        extraction_failures = 0
        for ref in discovery.references:
            capture = self.fetch(ref)
            if not capture.ok:
                fetch_failures += 1
                continue
            result.fetched += 1
            extracted = self._extract(capture, structural=True)
            if extracted.status == st.OK and extracted.documents:
                documents.extend(extracted.documents)
            else:
                extraction_failures += 1

        result.extracted = len(documents)
        result.failed_fetches = fetch_failures
        result.completed_at = _now()

        # Defense in depth. discover() already filters HELD_RELEASE_SLUGS
        # before window/cap selection, so this should never fire -- checked
        # again here, against the actual documents about to be returned,
        # because this is the last point inside the adapter before pipeline.py
        # can reach pla_watch.db with them.
        held_leak = [d.url for d in documents
                     if release_slug(d.url) in HELD_RELEASE_SLUGS]

        if fetch_failures or extraction_failures or held_leak:
            notes = []
            if fetch_failures or extraction_failures:
                notes.append(
                    "%d of %d discovered reference(s) failed fetch or "
                    "extraction" % (fetch_failures + extraction_failures,
                                    result.references_discovered))
            if held_leak:
                notes.append("held record(s) present in results: %s"
                             % ", ".join(held_leak))
            result.status = st.EXTRACTION_FAILURE
            result.error_detail = ("; ".join(notes) +
                                   " -- whole batch withheld, nothing "
                                   "committed this run")
            result.text_unavailable = None
            return result, []

        # An image-only release (`_extract`) is such a document: its title,
        # URL and date are kept and its body is empty. It is counted here, not
        # treated as a failure, so it never withholds an otherwise sound batch.
        unusable = [d for d in documents if not d.has_usable_text]
        result.text_unavailable = len(unusable)
        if documents and unusable:
            result.error_detail = (
                "%d of %d parsed page(s) carried no usable text; their "
                "titles, URLs and dates were kept"
                % (len(unusable), len(documents)))
        return result, documents
