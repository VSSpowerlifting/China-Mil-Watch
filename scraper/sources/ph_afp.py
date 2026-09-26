"""
Philippines — Armed Forces of the Philippines (AFP) shadow adapter.

Conforms to `core.collection.contract.SourceAdapter`. It is NOT registered in
any production desk manifest: `shadow/ph_afp/manifest.json` lives outside
`desks/` precisely so `load_all_desks()` cannot find it, and the source is
`enabled: false`. Nothing here can reach `pla_watch.db` or `output/`.

WHAT THIS SOURCE IS
-------------------
**The article stream of www.afp.mil.ph, the official website of the Armed
Forces of the Philippines**, published by its Public Affairs Office.

  * a **Tier A** first-party source: the institution speaking for itself
  * **not the Department of National Defense** (`dnd.gov.ph`, behind a
    Cloudflare challenge), **not the Philippine Coast Guard**
    (`coastguard.gov.ph`, likewise) and not the Philippine News Agency
  * **not comprehensive Philippine defense coverage**: it is what the AFP
    chose to publish on its own site, at the pace it publishes it

HOW IT IS RETRIEVED
-------------------
`www.afp.mil.ph` is a single-page application: its HTML is an empty shell, its
`sitemap.xml` returns that shell, and the article text is served as JSON by the
site's own backend, `api.afp.mil.ph`, which the app calls from every visitor's
browser. This adapter reads that same public JSON. It does not render or drive
the SPA, and it does not fetch the shell per article.

  * discovery: `GET /articles/?page_size=100` and the `next` links it returns
  * retrieval: `GET /articles/<slug>/`, one request per article
  * preservation: the exact response bytes of the detail request, hashed

The canonical URL of a record is `https://www.afp.mil.ph/news/<slug>`, the
route the SPA's own router serves for an article (`news/:slug`). It is
reconstructed from the slug, not fetched, and it is the URL a reader can open.
The URL actually requested is the API detail URL, recorded on every capture.

ROBOTS POSITION
---------------
Read on every run, from BOTH hosts:

  * `www.afp.mil.ph/robots.txt` is `User-agent: * / Allow: /`.
  * `api.afp.mil.ph` publishes no `robots.txt` (HTTP 404). Under RFC 9309 an
    unavailable rules file means no rules were published; it does not mean
    permission was withheld. That is the opposite of `pacom.mil`, which
    answers 403 for its own rules file and is therefore treated as no
    permission (see `us_dvids.py`). A 401/403 on either host is a hard
    failure here too, and a challenge page is `ACCESS_CHALLENGED`, never
    retried and never solved.
  * `api.afp.mil.ph` answers with `X-Robots-Tag: noindex, nofollow`. That is
    a search-indexing directive, not an access rule, and this adapter does not
    treat it as a refusal — but it is recorded on every run, because it is a
    signal that the API was not built as a crawl surface, and it is an open
    point for the owner (shadow/ph_afp/README.md).

RULES THAT MATTER TO THIS FILE
------------------------------
  * identity is the API's integer `id`, `afp:<id>`, cross-checked against the
    slug. A slug can be edited and the detail endpoint is keyed by slug only,
    so a detail whose id or slug disagrees with the listing is refused
  * a listing or a redirect that leaves the permitted hosts is refused, never
    followed
  * the publication date is the publisher's own `published_at`, kept in the
    offset it was stated in, with the UTC instant preserved alongside it. A
    timestamp with no offset is refused: an offset is not guessed
  * the whole listing is walked every run (about eleven requests). The window
    only selects what is fetched afterwards. Nothing is assumed about sort
    order, because stopping early on the first out-of-window date is exactly
    how a backdated item is lost
  * an item whose text is not in the payload (the AFP publishes some
    statements as an image alone) is a metadata-only record: title, date and
    URL are kept, the text is empty, and nothing is inferred or transcribed
  * an article that changes after capture is a revision, detected by
    fingerprint and recorded by the runner; it is never a new record and never
    a silent overwrite
  * an empty listing window is a success, never a listing failure

Deliberately absent: translation, classification, relevance filtering,
significance scoring and any editorial judgement. The shadow phase proves
retrieval, identity, preservation and reliability first.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from bs4.element import Comment

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, CollectionWindow, DiscoveryResult,
    ExtractedDocument, ExtractionResult, SourceAdapter, SourceHealthResult,
)

WWW = "https://www.afp.mil.ph"
API = "https://api.afp.mil.ph"
ROBOTS_WWW = WWW + "/robots.txt"
ROBOTS_API = API + "/robots.txt"
LIST_URL = API + "/articles/"

#: The only hosts this adapter will retrieve from, and the only hosts a
#: canonical URL may carry. Anything else is a refusal, not a redirect.
PERMITTED_API_HOSTS = ("api.afp.mil.ph",)
PERMITTED_SITE_HOSTS = ("www.afp.mil.ph", "afp.mil.ph")

#: Honest identification, identical to the other shadow collectors. A
#: publisher that wants to refuse this collector must be able to recognise it.
USER_AGENT = ("ChinaMilWatch-ShadowCollector/0.1 "
              "(+https://chinamilwatch.org; research archive; contact via site)")

REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 2.0          # seconds between requests; one worker only
MAX_RETRIES = 2                 # transport errors only; never a 4xx
MAX_LIST_BYTES = 3_000_000
MAX_DETAIL_BYTES = 2_000_000
PAGE_SIZE = 100
#: 1,076 items at 100 per page is 11 pages. A listing that needs more than
#: this has changed shape, and stopping is safer than walking it.
MAX_PAGES = 40

#: Categories that carry press items. `uncategorised` is included because it
#: holds real statements (`AFP Statement on the Appointment of Secretary
#: Galvez`) beside misfiled site pages; it is collected in full and screened
#: downstream, not here. Any other category is counted and rejected so a NEW
#: category is visible instead of being silently ingested or silently dropped.
ACCEPTED_CATEGORIES = ("news-blog", "uncategorised")

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SITE_ARTICLE_PATH_RE = re.compile(r"^/news/([a-z0-9]+(?:-[a-z0-9]+)*)$")
DATETIME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

#: The fields a detail payload must carry. An ABSENT key is template drift; an
#: empty value is a fact about the article. The two are never conflated.
REQUIRED_DETAIL_KEYS = ("id", "slug", "title", "published_at", "status",
                        "category_slug", "intro_html", "body_html")

BLOCK_TAGS = ("p", "div", "li", "ul", "ol", "table", "tr", "td", "th",
              "blockquote", "h1", "h2", "h3", "h4", "h5", "h6")

PUBLICATION_KIND = "official website article"

# ── Rejection taxonomy ────────────────────────────────────────────────────────
# Every discarded item is counted under exactly one of these. A collector that
# reports only what it kept cannot be audited.

R_NON_PRESS_CATEGORY = "non_press_category"
R_MISSING_ID = "missing_id"
R_INVALID_SLUG = "invalid_slug"
R_MISSING_TITLE = "missing_title"
R_MISSING_PUBDATE = "missing_pubdate"
R_UNPARSEABLE_PUBDATE = "unparseable_pubdate"    # includes "no UTC offset"
R_DUPLICATE_IN_LIST = "duplicate_in_list"
R_OUTSIDE_WINDOW = "outside_window"
R_BEYOND_CAP = "beyond_cap"
R_IDENTITY_MISMATCH = "identity_mismatch"        # detail id/slug != listing
R_NOT_PUBLISHED = "not_published"

REJECTION_REASONS = (
    R_NON_PRESS_CATEGORY, R_MISSING_ID, R_INVALID_SLUG, R_MISSING_TITLE,
    R_MISSING_PUBDATE, R_UNPARSEABLE_PUBDATE, R_DUPLICATE_IN_LIST,
    R_OUTSIDE_WINDOW, R_BEYOND_CAP, R_IDENTITY_MISMATCH, R_NOT_PUBLISHED,
)


class RobotsDisallowed(RuntimeError):
    """The published policy no longer permits the listing or an article path."""


class ListingUnparseable(RuntimeError):
    """A listing response that is not the shape this adapter understands."""


# ── URLs ──────────────────────────────────────────────────────────────────────

def canonical_url(slug: str) -> Optional[str]:
    """The reader-facing URL for a slug, or None if the slug is not a slug."""
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        return None
    return "%s/news/%s" % (WWW, slug)


def slug_from_canonical(url: str) -> Optional[str]:
    """The slug of a canonical article URL, or None for anything else."""
    try:
        parts = urlparse(url or "")
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    if parts.netloc.lower() not in PERMITTED_SITE_HOSTS:
        return None
    if parts.query or parts.params or parts.fragment:
        return None
    m = SITE_ARTICLE_PATH_RE.match(parts.path)
    return m.group(1) if m else None


def detail_url(slug: str) -> Optional[str]:
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        return None
    return "%s/articles/%s/" % (API, slug)


def is_permitted_api_url(url: str) -> bool:
    """True only for an https/http URL on the API host, under `/articles/`."""
    try:
        parts = urlparse(url or "")
    except ValueError:
        return False
    return (parts.scheme in ("http", "https")
            and parts.netloc.lower() in PERMITTED_API_HOSTS
            and parts.path.startswith("/articles/"))


def source_identity(article_id) -> Optional[str]:
    """`afp:<id>` for a positive integer id (or its decimal string)."""
    if isinstance(article_id, bool):
        return None
    if isinstance(article_id, int):
        n = article_id
    elif isinstance(article_id, str) and article_id.isdigit():
        n = int(article_id)
    else:
        return None
    return "afp:%d" % n if n > 0 else None


# ── Dates ─────────────────────────────────────────────────────────────────────

def parse_published_at(raw) -> Optional[Tuple[str, str, str]]:
    """
    `(local_date, original, utc_instant)` or None.

    `local_date` is the calendar date IN THE OFFSET THE PUBLISHER STATED, which
    is the date a reader of the AFP site sees. The original string is kept
    verbatim, and the UTC instant is derived from it. A timestamp with no
    offset is refused rather than assumed to be Manila time.
    """
    if not isinstance(raw, str):
        return None
    m = DATETIME_RE.match(raw.strip())
    if not m:
        return None
    day, clock, frac, zone = m.groups()
    micro = ((frac or ".0")[1:] + "000000")[:6]
    try:
        naive = datetime.strptime("%s %s.%s" % (day, clock, micro),
                                  "%Y-%m-%d %H:%M:%S.%f")
        if zone == "Z":
            offset = timezone.utc
        else:
            sign = 1 if zone[0] == "+" else -1
            hh, mm = int(zone[1:3]), int(zone[4:6])
            if hh > 23 or mm > 59:
                return None
            offset = timezone(sign * timedelta(hours=hh, minutes=mm))
        aware = naive.replace(tzinfo=offset)
    except ValueError:
        return None
    utc = aware.astimezone(timezone.utc).isoformat(timespec="seconds")
    return aware.date().isoformat(), raw.strip(), utc


# ── Text ──────────────────────────────────────────────────────────────────────

def html_to_text(html: Optional[str]) -> str:
    """
    Readable text from a fragment of the publisher's HTML.

    Structural only: block elements become paragraph breaks, `<br>` a line
    break, whitespace inside a paragraph is collapsed, and entities are
    decoded. No word is added, removed or reordered.
    """
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    for node in soup.find_all(string=True):
        if isinstance(node, Comment):
            node.extract()
        else:
            node.replace_with(re.sub(r"\s+", " ", str(node)))
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before("\n\n")
        tag.insert_after("\n\n")
    raw = soup.get_text("")
    paragraphs = []
    for chunk in re.split(r"\n[ \t]*\n", raw):
        lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in chunk.split("\n")]
        lines = [ln for ln in lines if ln]
        if lines:
            paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


#: A paragraph shorter than this is never used to decide that two fields
#: overlap: a short line can repeat by coincidence.
MIN_OVERLAP_CHARS = 20


def _contained(paragraph: str, other: str) -> bool:
    p = _squash(paragraph)
    return len(p) >= MIN_OVERLAP_CHARS and p in _squash(other)


def assemble_text(intro_html: Optional[str], body_html: Optional[str]
                  ) -> Tuple[str, str]:
    """
    `(text, composition)`.

    Two publishing eras coexist in this API. Items authored in the current CMS
    carry an `intro_html` that is the opening of `body_html` (measured: the
    intro is a prefix of the body). Items migrated from the previous Joomla
    site keep Joomla's split: the intro is the introduction and the body is the
    remainder, so neither contains the other. Storing the body alone would
    drop the opening paragraphs of every migrated item.

      * intro contained in body     -> body           ("body")
      * both present, not contained -> intro + body   ("intro+body")
      * body only                   -> body           ("body")
      * intro only                  -> intro          ("intro")
      * neither                     -> ""             ("none")

    In the "intro+body" case the two fields can still overlap. A current-CMS
    intro carries the dateline ("CAMP AGUINALDO, Quezon City -- ") that the
    body omits, so the body's first paragraph sits INSIDE the intro without the
    intro sitting inside the body. Leading body paragraphs already contained in
    the intro, and trailing intro paragraphs already contained in the body, are
    therefore not repeated. Measured on 2026-09-26, that applies to 5 of the
    814 items composed this way. No word is added, removed or reordered.
    """
    intro = html_to_text(intro_html)
    body = html_to_text(body_html)
    if intro and body:
        if _squash(intro) in _squash(body):
            return body, "body"
        intro_paras = intro.split("\n\n")
        body_paras = body.split("\n\n")
        while body_paras and _contained(body_paras[0], intro):
            body_paras.pop(0)
        # Checked against the body AS TRIMMED, so a paragraph shared by both
        # fields is kept once and never removed from both sides.
        while intro_paras and _contained(intro_paras[-1],
                                         "\n\n".join(body_paras)):
            intro_paras.pop()
        return "\n\n".join(intro_paras + body_paras), "intro+body"
    if body:
        return body, "body"
    if intro:
        return intro, "intro"
    return "", "none"


def revision_fingerprint(data: dict) -> str:
    """
    A hash over the fields a reader would call "the article".

    Deliberately NOT over the whole payload: `hits` (a view counter) is in
    every response and changes on every read, so a whole-payload hash would
    report a revision on every fetch. The slug IS included: the identity is the
    integer id, so an edited slug leaves the id unchanged, and without the slug
    here the run would call the article a duplicate and lose its new URL.
    """
    material = {k: data.get(k) for k in
                ("slug", "title", "published_at", "category_slug",
                 "intro_html", "body_html")}
    blob = json.dumps(material, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ── Listing ───────────────────────────────────────────────────────────────────

@dataclass
class ListItem:
    article_id: int
    identity: str
    slug: str
    url: str
    title: str
    category_slug: str
    published_date: str
    published_at_original: str
    published_at_utc: str


def parse_list_page(text: str) -> Tuple[List[dict], Optional[str], Optional[int]]:
    """`(raw_items, next_url, reported_count)`; raises ListingUnparseable."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ListingUnparseable("listing is not JSON: %s" % type(exc).__name__)
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ListingUnparseable(
            "listing has no `results` array — shape changed")
    nxt = data.get("next")
    if nxt is not None and not isinstance(nxt, str):
        raise ListingUnparseable("listing `next` is not a string or null")
    count = data.get("count")
    return data["results"], nxt, count if isinstance(count, int) else None


def classify_list_item(raw, rejections: Dict[str, int]) -> Optional[ListItem]:
    """One listing entry -> ListItem, or None with the reason counted."""
    if not isinstance(raw, dict):
        rejections[R_MISSING_ID] += 1
        return None
    ident = source_identity(raw.get("id"))
    if ident is None:
        rejections[R_MISSING_ID] += 1
        return None
    slug = raw.get("slug")
    url = canonical_url(slug)
    if url is None:
        rejections[R_INVALID_SLUG] += 1
        return None
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        rejections[R_MISSING_TITLE] += 1
        return None
    stated = raw.get("published_at")
    if not stated:
        rejections[R_MISSING_PUBDATE] += 1
        return None
    parsed = parse_published_at(stated)
    if parsed is None:
        rejections[R_UNPARSEABLE_PUBDATE] += 1
        return None
    if raw.get("category_slug") not in ACCEPTED_CATEGORIES:
        rejections[R_NON_PRESS_CATEGORY] += 1
        return None
    local_date, original, utc = parsed
    return ListItem(
        article_id=int(ident.split(":", 1)[1]), identity=ident, slug=slug,
        url=url, title=title.strip(), category_slug=raw["category_slug"],
        published_date=local_date, published_at_original=original,
        published_at_utc=utc)


def select_window(items: List[ListItem], window: CollectionWindow, cap: int,
                  rejections: Dict[str, int]) -> List[ListItem]:
    """
    Items whose stated local date lies in the window, newest first, at most
    `cap` of them (0 or less means no cap). Each exclusion is counted.
    """
    lo = window.target_date - timedelta(days=window.lookback_days)
    hi = window.target_date
    inside = []
    for it in items:
        d = date.fromisoformat(it.published_date)
        if lo <= d <= hi:
            inside.append(it)
        else:
            rejections[R_OUTSIDE_WINDOW] += 1
    inside.sort(key=lambda i: (i.published_at_utc, i.article_id), reverse=True)
    if cap and cap > 0 and len(inside) > cap:
        rejections[R_BEYOND_CAP] += len(inside) - cap
        inside = inside[:cap]
    return inside


def looks_challenged(resp) -> bool:
    """An edge challenge page, or a header that says one was issued."""
    headers = getattr(resp, "headers", None) or {}
    if str(headers.get("cf-mitigated", "")).lower() == "challenge":
        return True
    head = (getattr(resp, "text", "") or "")[:4000].lower()
    return "just a moment" in head or "challenge-platform" in head


# ── The adapter ───────────────────────────────────────────────────────────────

class PHAfpAdapter(SourceAdapter):
    """Discovery, retrieval and extraction. No storage, no analysis."""

    implemented = True

    def __init__(self, source, session=None, cap: int = 100,
                 page_size: int = PAGE_SIZE, max_pages: int = MAX_PAGES,
                 sleeper=time.sleep) -> None:
        super().__init__(source)
        self._session = session or requests.Session()
        self._cap = cap
        self._page_size = page_size
        self._max_pages = max_pages
        self._sleep = sleeper
        self._last_request = 0.0
        self._by_slug: Dict[str, ListItem] = {}
        #: Populated by `discover()` and `extract()`; the runner reads both.
        self.rejections: Dict[str, int] = {r: 0 for r in REJECTION_REASONS}
        self.observed: Dict[str, object] = {}
        self.failed_fetches: List[str] = []

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
                    headers={"User-Agent": USER_AGENT,
                             "Accept": "application/json, text/plain;q=0.5"})
                self._last_request = time.monotonic()
                return resp
            except Exception as exc:            # transport only
                last = exc
                self._last_request = time.monotonic()
                if attempt < MAX_RETRIES:
                    self._sleep(max(REQUEST_INTERVAL, 2 ** attempt))
        raise last

    @staticmethod
    def _transport_status(exc: Exception) -> str:
        return st.TIMEOUT if "timeout" in type(exc).__name__.lower() \
            else st.LISTING_FAILURE

    def _note_api_headers(self, resp) -> None:
        """Record the API's `X-Robots-Tag` the first time it is seen."""
        if "api_x_robots_tag" in self.observed:
            return
        tag = (getattr(resp, "headers", None) or {}).get("X-Robots-Tag")
        if tag:
            self.observed["api_x_robots_tag"] = tag

    # -- policy ---------------------------------------------------------------

    def _read_policy(self, url: str, label: str):
        """
        `(rules_text_or_None, failure)`; `failure` is a DiscoveryResult when the
        run must stop. 200 supplies rules; 404/410 supplies none (RFC 9309: an
        unavailable file is not a refusal); 401/403 and a challenge are hard
        failures; anything else means the policy could not be read.
        """
        try:
            resp = self._get(url)
        except Exception as exc:
            return None, DiscoveryResult(
                self.slug, self._transport_status(exc),
                error_detail="%s robots.txt unreachable: %s"
                             % (label, type(exc).__name__))
        code = resp.status_code
        self.observed["%s_robots_status" % label] = code
        if label == "api":
            self._note_api_headers(resp)
        if code == 200:
            return resp.text or "", None
        if code in (404, 410):
            return None, None
        if code in (401, 403):
            if looks_challenged(resp):
                return None, DiscoveryResult(
                    self.slug, st.ACCESS_CHALLENGED,
                    error_detail="%s robots.txt answered with an access "
                                 "challenge; not retried, not solved" % label)
            return None, DiscoveryResult(
                self.slug, st.AUTH_FAILURE,
                error_detail="%s robots.txt returned HTTP %d; no basis to "
                             "conclude collection is permitted" % (label, code))
        return None, DiscoveryResult(
            self.slug, st.LISTING_FAILURE,
            error_detail="%s robots.txt returned HTTP %d" % (label, code))

    def assert_robots_allow(self, rules: Optional[str], url: str) -> None:
        if rules is None:
            return
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(rules.splitlines())
        if not rp.can_fetch(USER_AGENT, url):
            raise RobotsDisallowed(
                "robots.txt disallows %s for this collector" % url)

    def _check_policy(self) -> Optional[DiscoveryResult]:
        www_rules, failure = self._read_policy(ROBOTS_WWW, "www")
        if failure:
            return failure
        api_rules, failure = self._read_policy(ROBOTS_API, "api")
        if failure:
            return failure
        try:
            self.assert_robots_allow(www_rules, WWW + "/news/")
            self.assert_robots_allow(api_rules, LIST_URL)
            self.assert_robots_allow(api_rules, API + "/articles/x/")
        except RobotsDisallowed as exc:
            return DiscoveryResult(self.slug, st.AUTH_FAILURE,
                                   error_detail=str(exc))
        return None

    # -- discovery ------------------------------------------------------------

    def _list_failure(self, status: str, detail: str) -> DiscoveryResult:
        return DiscoveryResult(self.slug, status, error_detail=detail)

    def discover(self, window: CollectionWindow) -> DiscoveryResult:
        self.rejections = {r: 0 for r in REJECTION_REASONS}
        self.observed = {}
        self.failed_fetches = []
        self._by_slug = {}

        failure = self._check_policy()
        if failure:
            return failure

        raw_items: List[dict] = []
        reported_count: Optional[int] = None
        url = "%s?page_size=%d&page=1" % (LIST_URL, self._page_size)
        seen_urls = set()
        pages = 0
        truncated = False
        end_by_invalid_page = False

        while url:
            if url in seen_urls or pages >= self._max_pages:
                truncated = True
                break
            seen_urls.add(url)
            try:
                resp = self._get(url)
            except Exception as exc:
                self.failed_fetches.append(url)
                return self._list_failure(
                    self._transport_status(exc),
                    "listing page %d unreachable: %s"
                    % (pages + 1, type(exc).__name__))
            code = resp.status_code
            self._note_api_headers(resp)
            if code == 404 and pages > 0:
                # DRF answers `{"detail": "Invalid page."}` past the end. That
                # is the end of the list, not a failure.
                end_by_invalid_page = True
                break
            if code in (401, 403):
                self.failed_fetches.append(url)
                if looks_challenged(resp):
                    return self._list_failure(
                        st.ACCESS_CHALLENGED,
                        "listing answered with an access challenge; not "
                        "retried, not solved")
                return self._list_failure(
                    st.AUTH_FAILURE, "listing returned HTTP %d" % code)
            if code != 200:
                self.failed_fetches.append(url)
                return self._list_failure(
                    st.LISTING_FAILURE,
                    "listing page %d returned HTTP %d" % (pages + 1, code))
            if looks_challenged(resp):
                self.failed_fetches.append(url)
                return self._list_failure(
                    st.ACCESS_CHALLENGED,
                    "listing answered with an access challenge; not "
                    "retried, not solved")
            ctype = (getattr(resp, "headers", None) or {}).get(
                "Content-Type", "")
            if "json" not in ctype.lower():
                self.failed_fetches.append(url)
                return self._list_failure(
                    st.UNEXPECTED_CONTENT_TYPE,
                    "listing returned %r, not JSON" % ctype)
            body = resp.content or b""
            if len(body) > MAX_LIST_BYTES:
                return self._list_failure(
                    st.OVERSIZED_RESPONSE,
                    "listing page exceeds %d bytes" % MAX_LIST_BYTES)
            try:
                page_items, nxt, count = parse_list_page(
                    body.decode("utf-8"))
            except (ListingUnparseable, UnicodeDecodeError) as exc:
                self.failed_fetches.append(url)
                return self._list_failure(st.LISTING_FAILURE, str(exc))
            pages += 1
            raw_items.extend(page_items)
            if count is not None:
                reported_count = count
            if nxt and not is_permitted_api_url(nxt):
                # A `next` that points elsewhere is a refusal, not a link.
                return self._list_failure(
                    st.DISALLOWED_REDIRECT,
                    "listing `next` leaves the permitted host: %s" % nxt)
            url = nxt

        self.observed.update(
            list_pages=pages, listed_items=len(raw_items),
            api_reported_count=reported_count,
            listing_end="invalid_page" if end_by_invalid_page
            else "truncated" if truncated else "next_null")

        if truncated:
            return self._list_failure(
                st.LISTING_FAILURE,
                "listing did not terminate within %d pages or looped; the "
                "window cannot be reported as covered" % self._max_pages)
        if not raw_items:
            # ~1,000 items are listed continuously; an empty array is a shape
            # change or an outage, not a quiet day.
            return self._list_failure(
                st.LISTING_FAILURE, "listing parsed to zero items")
        self.observed["count_mismatch"] = (
            reported_count is not None and reported_count != len(raw_items))

        seen_ids, seen_slugs = set(), set()
        valid: List[ListItem] = []
        for raw in raw_items:
            item = classify_list_item(raw, self.rejections)
            if item is None:
                continue
            if item.identity in seen_ids or item.slug in seen_slugs:
                self.rejections[R_DUPLICATE_IN_LIST] += 1
                continue
            seen_ids.add(item.identity)
            seen_slugs.add(item.slug)
            valid.append(item)

        dates = sorted(i.published_date for i in valid)
        self.observed["listed_date_min"] = dates[0] if dates else None
        self.observed["listed_date_max"] = dates[-1] if dates else None
        twins: Dict[Tuple[str, str], int] = {}
        for i in valid:
            key = (i.title, i.published_date)
            twins[key] = twins.get(key, 0) + 1
        self.observed["same_title_same_date_groups"] = sum(
            1 for n in twins.values() if n > 1)

        selected = select_window(valid, window, self._cap, self.rejections)
        self._by_slug = {i.slug: i for i in selected}
        refs = [CandidateReference(url=i.url, source_slug=self.slug,
                                   discovered_via=LIST_URL,
                                   hint_published_date=i.published_date)
                for i in selected]
        if not refs:
            return DiscoveryResult(self.slug, st.OK_NO_PUBLICATIONS)
        return DiscoveryResult(self.slug, st.OK, references=refs)

    # -- retrieval ------------------------------------------------------------

    def fetch(self, reference: CandidateReference) -> CaptureResult:
        slug = slug_from_canonical(reference.url)
        target = detail_url(slug) if slug else None
        if target is None or not is_permitted_api_url(target):
            # Defence in depth: nothing off-host is retrieved even if a caller
            # hands this adapter a reference it did not discover.
            return CaptureResult(
                reference, st.DISALLOWED_REDIRECT, reference.url,
                error_detail="refusing to retrieve a non-permitted URL: %s"
                             % reference.url)
        try:
            resp = self._get(target)
        except Exception as exc:
            self.failed_fetches.append(target)
            return CaptureResult(
                reference,
                st.TIMEOUT if "timeout" in type(exc).__name__.lower()
                else st.FETCH_FAILURE, target,
                error_detail="%s" % type(exc).__name__)
        code = resp.status_code
        if code in (401, 403):
            self.failed_fetches.append(target)
            return CaptureResult(
                reference,
                st.ACCESS_CHALLENGED if looks_challenged(resp)
                else st.AUTH_FAILURE, target, http_status=code,
                error_detail="item returned HTTP %d" % code)
        if code != 200:
            self.failed_fetches.append(target)
            return CaptureResult(
                reference, st.FETCH_FAILURE, target, http_status=code,
                error_detail="HTTP %d" % code)
        final = getattr(resp, "url", None) or target
        if not is_permitted_api_url(final):
            return CaptureResult(
                reference, st.DISALLOWED_REDIRECT, target, final_url=final,
                http_status=code,
                error_detail="redirected off the permitted host: %s" % final)
        ctype = (getattr(resp, "headers", None) or {}).get("Content-Type", "")
        if "json" not in ctype.lower():
            self.failed_fetches.append(target)
            return CaptureResult(
                reference, st.UNEXPECTED_CONTENT_TYPE, target, final_url=final,
                http_status=code, content_type=ctype,
                error_detail="detail returned %r, not JSON" % ctype)
        payload = resp.content or b""
        if len(payload) > MAX_DETAIL_BYTES:
            return CaptureResult(
                reference, st.OVERSIZED_RESPONSE, target, final_url=final,
                http_status=code, payload_bytes=len(payload),
                error_detail="detail exceeds %d bytes" % MAX_DETAIL_BYTES)
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            self.failed_fetches.append(target)
            return CaptureResult(
                reference, st.FETCH_FAILURE, target, final_url=final,
                http_status=code,
                error_detail="detail is not valid UTF-8; nothing is stored "
                             "that could not be preserved exactly")
        return CaptureResult(
            reference, st.OK, target, final_url=final, http_status=code,
            content_type=ctype, payload_bytes=len(payload),
            payload_sha256=hashlib.sha256(payload).hexdigest(),
            retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            body=text)

    # -- extraction -----------------------------------------------------------

    def _refuse(self, reason: str, detail: str) -> ExtractionResult:
        self.rejections[reason] += 1
        return ExtractionResult(self.slug, st.EXTRACTION_FAILURE,
                                error_detail=detail)

    def extract(self, capture: CaptureResult) -> ExtractionResult:
        """One document or a refusal. Never a partial record."""
        if not capture.ok or not capture.body:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE,
                                    error_detail="no body to extract")
        slug = slug_from_canonical(capture.reference.url)
        if slug is None:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="not a canonical article URL: %s"
                             % capture.reference.url)
        try:
            data = json.loads(capture.body)
        except ValueError:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="detail is not JSON: %s" % slug)
        if not isinstance(data, dict):
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="detail is not a JSON object: %s" % slug)
        missing = [k for k in REQUIRED_DETAIL_KEYS if k not in data]
        if missing:
            return ExtractionResult(
                self.slug, st.EXTRACTION_FAILURE,
                error_detail="detail lacks %s — template drift, not an empty "
                             "article: %s" % (", ".join(missing), slug))

        ident = source_identity(data["id"])
        listed = self._by_slug.get(slug)
        if ident is None or data["slug"] != slug or (
                listed is not None and listed.identity != ident):
            return self._refuse(
                R_IDENTITY_MISMATCH,
                "detail id/slug (%r, %r) does not match the listing (%s, %s)"
                % (data.get("id"), data.get("slug"),
                   listed.identity if listed else "unlisted", slug))
        if data["status"] != "published":
            return self._refuse(R_NOT_PUBLISHED,
                                "detail status %r: %s" % (data["status"], slug))
        if data["category_slug"] not in ACCEPTED_CATEGORIES:
            return self._refuse(
                R_NON_PRESS_CATEGORY,
                "category %r is not a press category: %s"
                % (data["category_slug"], slug))
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            return self._refuse(R_MISSING_TITLE, "no title: %s" % slug)
        parsed = parse_published_at(data["published_at"])
        if parsed is None:
            return self._refuse(
                R_UNPARSEABLE_PUBDATE,
                "published_at %r has no usable date and offset: %s"
                % (data["published_at"], slug))
        local_date, original, utc = parsed
        if listed is not None and listed.published_at_original != original:
            self.observed["list_detail_date_disagreements"] = int(
                self.observed.get("list_detail_date_disagreements", 0)) + 1

        text, composition = assemble_text(data["intro_html"], data["body_html"])
        byline = data.get("author_name")
        doc = ExtractedDocument(
            url=capture.reference.url, source_slug=self.slug,
            title_original=title.strip(), text_original=text,
            published_date=local_date, language_tag="en",
            extra={
                "source_identity": ident,
                "published_at_utc": utc,
                "published_at_original": original,
                "byline": byline if isinstance(byline, str) and byline
                and byline != "None" else None,
                "category_slug": data["category_slug"],
                "api_created_at": data.get("created_at"),
                "api_updated_at": data.get("updated_at"),
                "featured_image_path": data.get("featured_image") or None,
                "publication_kind": PUBLICATION_KIND,
                "text_composition": composition,
                "text_status": "text" if text.strip() else "no_text",
                "content_sha256": hashlib.sha256(
                    text.encode("utf-8")).hexdigest(),
                "source_fingerprint": revision_fingerprint(data),
                "capture_sha256": capture.payload_sha256,
                "retrieved_at": capture.retrieved_at,
                "requested_url": capture.requested_url,
                "final_url": capture.final_url,
            })
        return ExtractionResult(self.slug, st.OK, documents=[doc])

    def healthcheck(self) -> SourceHealthResult:
        return SourceHealthResult(
            self.slug, st.SKIPPED_DISABLED,
            "shadow evaluation; not enabled in any production desk")
