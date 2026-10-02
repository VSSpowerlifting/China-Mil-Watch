"""
Philippines NSC official-statements shadow adapter: extraction, refusal,
robots compliance and pagination.

Everything runs offline from the four 2026-10-01 captures in
tests/fixtures/ph_nsc/ and from variants built from those same bytes. A socket
guard fails any real connection, and no test touches a database or writes
outside a temporary location. Variants are built here, in memory, and are never
written back: the fixtures stay exactly the packet's bytes.

What this proves is limited to the adapter's own logic. The captures show the
site answered a generic urllib client; they do not show that this module's
`requests` transport works against nsc.gov.ph, that access is reliable over
time, or that the text may be reused. Those gates are listed in
shadow/ph_nsc/README.md and nothing here closes them.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import re
import socket
import sys
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import (                          # noqa: E402
    CandidateReference, CaptureResult, CollectionWindow, SourceAdapter)
from core.manifests import load_all_desks                       # noqa: E402
from scraper.sources import ph_nsc as nsc                       # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "ph_nsc"
SHADOW = REPO_ROOT / "shadow" / "ph_nsc"
MANIFEST = json.loads((SHADOW / "manifest.json").read_text(encoding="utf-8"))
SOURCE = MANIFEST["sources"][0]

#: The ten-row packet ledger is preserved whole; only the NSC rows apply here.
#: Digests of the JSON fixtures, which the ledger does not cover.
PINNED_JSON = {
    "requests.json": "6f521d78347ba71067e6e93a01aede5fdca8668222bf75a155c66db1c8202603",
    "nsc-discovery.json": "12dfb7446f006b870c6083f2a9d81c1404a2b143b4aabc481036ba665c3850e1",
    "nsc-article-1-extraction.json": "ef5281fd66802902b5af0c0cbfbbfd41945172aac0f571f6e9a3d88ebcd787f4",
    "nsc-article-2-extraction.json": "32e14192ed20fb2076f38283be2ee2947174ccabdfaec6b965d2d05f94d8a5b9",
}


def fixture(name):
    return (FIX / name).read_bytes()


def sha(data):
    return hashlib.sha256(data).hexdigest()


LEDGER = {row["capture"]: row for row in json.loads(fixture("requests.json"))
          if row["capture"].startswith("nsc-")}
ROBOTS_BIN = fixture("nsc-robots.bin")
LISTING_BIN = fixture("nsc-listing.bin")
ARTICLE_BIN = {1: fixture("nsc-article-1.bin"), 2: fixture("nsc-article-2.bin")}
PACKET = {n: json.loads(fixture("nsc-article-%d-extraction.json" % n)) for n in (1, 2)}
DISCOVERY = json.loads(fixture("nsc-discovery.json"))
ARTICLE_URL = {n: PACKET[n]["canonical"][0] for n in (1, 2)}

ROBOTS_URL, LISTING_URL = nsc.ROBOTS, nsc.LISTING
LISTED = nsc.parse_listing_page(LISTING_BIN.decode("utf-8"), LISTING_URL)
ITEM = {i.url: i for i in LISTED.items}
OLDEST = date.fromisoformat(LISTED.items[-1].published_date)
TARGET = date(2026, 7, 8)
#: Starts the day after the oldest listed item, so the one captured page proves
#: coverage; one day longer and it cannot.
COVERED = CollectionWindow(TARGET, (TARGET - OLDEST).days - 1)
UNCOVERED = CollectionWindow(TARGET, (TARGET - OLDEST).days)
#: A window the captured listing falls well short of, to get a multi-page walk.
MID = CollectionWindow(date(2026, 6, 15), 7)

TEXT_PLAIN = {"Content-Type": "text/plain"}
CHALLENGE = (b'<!DOCTYPE html><html lang="en-US"><head><title>Just a moment...</title></head>'
             b'<body><form id="challenge-form" method="POST"><noscript>Enable JavaScript and '
             b'cookies to continue</noscript></form></body></html>')
# Derived, not captured: the packet names only two marker strings from a page
# it never saved, so nothing here claims to reproduce that page.
GAMBLING = (b"<!DOCTYPE html><html><head><title>87CLUB2 Link Slot Gacor</title></head>"
            b"<body><h1>alanodt2 daftar</h1></body></html>")
MAINTENANCE = (b"<!DOCTYPE html><html><head><title>Site under maintenance</title></head>"
               b"<body><p>Back soon.</p></body></html>")


def setUpModule():
    def refuse(*_args, **_kwargs):
        raise AssertionError("network access attempted in an offline test")
    global _GUARDS
    _GUARDS = [mock.patch.object(socket.socket, "connect", refuse),
               mock.patch("socket.getaddrinfo", refuse),
               mock.patch("socket.create_connection", refuse)]
    for guard in _GUARDS:
        guard.start()


def tearDownModule():
    for guard in _GUARDS:
        guard.stop()


# -- doubles and builders -----------------------------------------------------

class FakeResponse:
    def __init__(self, body=b"", status=200, headers=None):
        self.status_code = status
        self._body = body
        self.headers = {"Content-Type": "text/html; charset=UTF-8"}
        self.headers.update(headers or {})
        self.streamed = False

    def iter_content(self, chunk_size=1):
        self.streamed = True
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def close(self):
        pass


class FakeSession:
    """Serves routes, answers 404 for anything else, and records every call."""

    def __init__(self, route_map):
        self.routes = dict(route_map)
        self.calls = []
        self.cookie_seen = []
        self.cookies = requests.cookies.RequestsCookieJar()

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        self.cookie_seen.append(len(self.cookies))
        route = self.routes.get(url, FakeResponse(b"not found", 404))
        if isinstance(route, BaseException):
            raise route
        self.cookies.set("slimstat_tracking_code", "test")     # as requests' jar learns it
        return route


class FakeSource:
    slug = SOURCE["slug"]
    enabled = False
    base_url = SOURCE["base_url"]
    language_tag = "en"


class EnabledSource(FakeSource):
    """A test double only. The manifest's `enabled` stays false."""
    enabled = True


def routes(over=None):
    base = {ROBOTS_URL: FakeResponse(ROBOTS_BIN, headers=TEXT_PLAIN),
            LISTING_URL: FakeResponse(LISTING_BIN)}
    base.update({ARTICLE_URL[n]: FakeResponse(ARTICLE_BIN[n]) for n in (1, 2)})
    base.update(over or {})
    return base


class Rig:
    def __init__(self, route_map=None, source=FakeSource):
        self.session = FakeSession(routes() if route_map is None else route_map)
        self.sleeps = []
        self.adapter = nsc.PHNscAdapter(source(), session=self.session,
                                        sleeper=self.sleeps.append)

    @property
    def urls(self):
        return [url for url, _ in self.session.calls]

    def discover(self, window):
        return self.adapter.discover(window)


def robots_rig(policy, status=200, ctype="text/plain", extra=None):
    body = policy.encode("utf-8") if isinstance(policy, str) else policy
    headers = {"Content-Type": ctype}
    headers.update(extra or {})
    return Rig(routes({ROBOTS_URL: FakeResponse(body, status, headers)}))


def ref(url, hint=None):
    item = ITEM.get(url)
    return CandidateReference(url=url, source_slug=SOURCE["slug"], discovered_via=LISTING_URL,
                              hint_published_date=hint or (item.published_date if item else None))


def capture(text, url=ARTICLE_URL[1], hint=None):
    return CaptureResult(ref(url, hint), st.OK, url, final_url=url, http_status=200,
                         content_type="text/html; charset=UTF-8", payload_bytes=len(text),
                         payload_sha256="x", retrieved_at="2026-10-01T00:00:00+00:00", body=text)


def page_url(n):
    return "%spage/%d/" % (LISTING_URL, n)


NEXT = '<a class="wp-block-query-pagination-next" href="%s">Next Page</a>'


def listing_page(keep, links="", head=""):
    """The real listing reduced to the items at `keep` (in that order), plus extra markup."""
    soup = BeautifulSoup(LISTING_BIN.decode("utf-8"), "html.parser")
    ul = soup.select_one("main ul.wp-block-post-template")
    chosen = [str(li) for li in (ul.find_all("li", recursive=False)[i] for i in keep)]
    ul.clear()
    for node in list(BeautifulSoup("".join(chosen), "html.parser").contents):
        ul.append(node)
    for where, html in ((soup.find("main"), links), (soup.head, head)):
        for node in list(BeautifulSoup(html, "html.parser").contents):
            where.append(node)
    return str(soup).encode("utf-8")


SHELL = ('<!DOCTYPE html><html><head><title>Official Statements &#8211; National Security '
         'Council</title></head><body class="archive category category-official-statements '
         'wp-theme-twentytwentyfour"><main><ul class="wp-block-post-template">%s</ul>%s</main>'
         '</body></html>')


def synthetic_item(iid, day):
    return ('<li class="wp-block-post post-%d category-official-statements">'
            '<h2 class="wp-block-post-title"><a href="https://nsc.gov.ph/%s/synthetic-%d/">S%d</a>'
            '</h2><div class="wp-block-post-date"><time datetime="%sT09:00:00+08:00">d</time>'
            '</div></li>' % (iid, day.strftime("%Y/%m/%d"), iid, iid, day.isoformat()))


def synthetic_page(items, links=""):
    return (SHELL % ("".join(synthetic_item(i, d) for i, d in items), links)).encode("utf-8")


def article_text(n=1, *edits):
    soup = BeautifulSoup(ARTICLE_BIN[n].decode("utf-8"), "html.parser")
    for edit in edits:
        edit(soup)
    return str(soup)


def drop(selector):
    def edit(soup):
        nodes = soup.select(selector)
        assert nodes, "variant would be a no-op: %s" % selector
        for node in nodes:
            node.decompose()
    return edit


def twice(selector):
    def edit(soup):
        node = soup.select_one(selector)
        node.insert_after(BeautifulSoup(str(node), "html.parser").find(node.name))
    return edit


def set_attr(selector, name, value):
    def edit(soup):
        soup.select_one(selector)[name] = value
    return edit


def body_classes(fn):
    def edit(soup):
        soup.body["class"] = fn(list(soup.body["class"]))
    return edit


def swap(text, old, new):
    assert old in text, "variant would be a no-op: %r" % old
    return text.replace(old, new)


HEADER_DATE = "main div.wp-block-post-date"
TITLE = "main h1.wp-block-post-title"
BODY = "div.entry-content"
BYLINE = "main div.wp-block-post-author-name a"
P1 = ARTICLE_BIN[1].decode("utf-8")


# -- 1. the fixtures are the packet's bytes -------------------------------------

class TestFixturesArePreserved(unittest.TestCase):

    def test_captures_match_the_packets_own_ledger(self):
        self.assertEqual(sorted(LEDGER), ["nsc-article-1.bin", "nsc-article-2.bin",
                                          "nsc-listing.bin", "nsc-robots.bin"])
        for name, row in LEDGER.items():
            with self.subTest(name):
                data = fixture(name)
                self.assertEqual(sha(data), row["sha256"])
                self.assertEqual(len(data), row["bytes"])
                self.assertEqual(row["status"], 200)
                self.assertFalse(row["challenge_detected"])
                self.assertFalse(row["truncated"])

    def test_json_fixtures_are_pinned(self):
        for name, digest in PINNED_JSON.items():
            with self.subTest(name):
                self.assertEqual(sha(fixture(name)), digest)

    def test_carriage_returns_survive_because_the_fixtures_are_binary(self):
        # Some Git configurations rewrite line endings on checkout. The HTML
        # captures contain carriage returns, so without this attribute the
        # pinned hashes above would silently change on those machines.
        self.assertIn(b"\r", LISTING_BIN)
        self.assertEqual((FIX / ".gitattributes").read_text().strip(), "* binary")

    def test_the_adapter_speaks_in_the_captures_identity(self):
        for row in LEDGER.values():
            self.assertEqual(row["user_agent"], nsc.USER_AGENT)
        self.assertEqual(nsc.REQUEST_HEADERS["User-Agent"], nsc.USER_AGENT)

    def test_the_socket_guard_is_live(self):
        with self.assertRaises(AssertionError):
            socket.create_connection(("nsc.gov.ph", 443), timeout=1)


# -- 2. extraction from the real captures -----------------------------------------

class TestListingFromTheRealCapture(unittest.TestCase):

    def test_items_match_the_packets_discovery_links_in_order(self):
        links = [u for u in DISCOVERY["links"] if nsc.canonical_url(u)]
        self.assertEqual([i.url for i in LISTED.items], links)
        self.assertEqual(len({i.post_id for i in LISTED.items}), len(LISTED.items))

    def test_dates_descend_and_keep_the_pages_own_offset(self):
        dates = [i.published_date for i in LISTED.items]
        self.assertEqual(dates, sorted(dates, reverse=True))
        for item in LISTED.items:
            self.assertTrue(item.published_at_original.endswith("+08:00"))
            self.assertTrue(item.published_at_utc.endswith("+00:00"))

    def test_the_capture_shows_no_pagination_at_all(self):
        self.assertEqual((LISTED.next_urls, LISTED.numbered, LISTED.unsupported),
                         (set(), set(), []))

    def test_recurring_titles_are_distinct_items(self):
        counts = Counter(i.title for i in LISTED.items)
        title, times = counts.most_common(1)[0]
        self.assertGreater(times, 1)
        same = [i for i in LISTED.items if i.title == title]
        self.assertEqual(len({i.post_id for i in same}), times)
        self.assertEqual(len({i.url for i in same}), times)
        self.assertTrue(any(re.search(r"-\d+/$", i.url) for i in same))


class TestArticlesFromTheRealCaptures(unittest.TestCase):

    def test_each_article_reproduces_the_packets_diagnostics(self):
        for n in (1, 2):
            with self.subTest(n):
                text = ARTICLE_BIN[n].decode("utf-8")
                art = nsc.parse_article(text, ARTICLE_URL[n])
                listed = ITEM[ARTICLE_URL[n]]
                self.assertEqual(art.post_id, listed.post_id)
                self.assertEqual(art.title, listed.title)
                self.assertEqual(art.published,
                                 (listed.published_date, listed.published_at_utc,
                                  listed.published_at_original))
                self.assertEqual((art.site_byline, art.site_byline_url),
                                 ("National Security Council", "https://nsc.gov.ph/author/nsc_admin/"))
                self.assertEqual(len(art.text), PACKET[n]["body_chars"])
                self.assertTrue(art.text.startswith(PACKET[n]["body_start"]))
                self.assertTrue(art.text.endswith(PACKET[n]["body_end"]))
                self.assertFalse(nsc.looks_challenged({}, text))

    def test_the_latest_post_sidebar_is_excluded(self):
        for n in (1, 2):
            with self.subTest(n):
                soup = BeautifulSoup(ARTICLE_BIN[n].decode("utf-8"), "html.parser")
                sidebar = [_squash(a.get_text()) for a in
                           soup.select("ul.wp-block-latest-posts__list a")]
                self.assertTrue(sidebar)
                lines = nsc.parse_article(ARTICLE_BIN[n].decode("utf-8"), ARTICLE_URL[n]).text.splitlines()
                for entry in sidebar:
                    self.assertNotIn(entry, lines)

    def test_a_latest_posts_widget_inside_the_body_is_still_excluded(self):
        # In the captures the widget follows entry-content. If a template change
        # moved it inside, its titles and dates must still not enter the text.
        widget = ('<ul class="wp-block-latest-posts__list"><li><a href="https://nsc.gov.ph/2026/08/21/z/">'
                  'Widget Title Zed</a><time datetime="2026-08-21T16:39:36+08:00">Aug 21</time></li></ul>')

        def inside(soup):
            soup.select_one(BODY).append(BeautifulSoup(widget, "html.parser").ul)

        text = article_text(1, inside)
        self.assertIn("Widget Title Zed", text)
        art = nsc.parse_article(text, ARTICLE_URL[1])
        self.assertNotIn("Widget Title Zed", art.text)
        self.assertEqual(art.text, nsc.parse_article(P1, ARTICLE_URL[1]).text)

    def test_replayed_through_fetch_and_extract_the_hashes_equal_the_ledger(self):
        rig = Rig()
        self.assertEqual(rig.discover(COVERED).status, st.OK)
        for n in (1, 2):
            with self.subTest(n):
                cap = rig.adapter.fetch(ref(ARTICLE_URL[n]))
                row = LEDGER["nsc-article-%d.bin" % n]
                self.assertEqual(cap.status, st.OK)
                self.assertEqual((cap.requested_url, cap.final_url, cap.http_status),
                                 (ARTICLE_URL[n], ARTICLE_URL[n], 200))
                self.assertEqual((cap.payload_sha256, cap.payload_bytes), (row["sha256"], row["bytes"]))
                result = rig.adapter.extract(cap)
                self.assertEqual(result.status, st.OK)
                doc, = result.documents
                listed = ITEM[ARTICLE_URL[n]]
                self.assertEqual((doc.url, doc.source_slug, doc.language_tag),
                                 (ARTICLE_URL[n], SOURCE["slug"], "en"))
                self.assertEqual(doc.title_original, listed.title)
                self.assertEqual(doc.published_date, listed.published_date)
                self.assertTrue(doc.has_usable_text)
                self.assertEqual(doc.extra["source_identity"], "nsc:%s" % listed.post_id)
                self.assertEqual(doc.extra["published_at_utc"], listed.published_at_utc)
                self.assertEqual(doc.extra["published_at_original"], listed.published_at_original)
                self.assertEqual(doc.extra["site_byline"], "National Security Council")
                self.assertEqual(doc.extra["content_sha256"], sha(doc.text_original.encode("utf-8")))
                self.assertEqual(doc.extra["capture_sha256"], row["sha256"])

    def test_a_recurring_title_keeps_a_distinct_identity(self):
        # Article 2's real bytes, re-labelled as the listing's "-2" item that
        # shares its title. Derived: the packet captured only two statements.
        target = next(i for i in LISTED.items if i.url.endswith("-west-philippine-sea-2/"))
        text = article_text(2)
        text = swap(text, ARTICLE_URL[2], target.url)
        text = swap(text, "2269", target.post_id)
        text = swap(text, "2026-06-17T12:13:13+08:00", target.published_at_original)
        rig = Rig()
        rig.discover(MID)
        first = rig.adapter.extract(capture(ARTICLE_BIN[2].decode("utf-8"), ARTICLE_URL[2]))
        second = rig.adapter.extract(capture(text, target.url))
        a, b = first.documents[0], second.documents[0]
        self.assertEqual(a.title_original, b.title_original)
        self.assertNotEqual(a.extra["source_identity"], b.extra["source_identity"])
        self.assertEqual(b.extra["source_identity"], "nsc:%s" % target.post_id)


def _squash(text):
    return " ".join(text.split())


# -- 3. nothing is guessed: exactly-one elements, no fallbacks -----------------------

class TestAnArticleThatIsNotCompleteIsRefused(unittest.TestCase):

    def variants(self):
        """(label, page, what the refusal must say): every one is a real page with one fault."""
        yield "no header date", article_text(1, drop(HEADER_DATE)), "post date"
        yield "no title", article_text(1, drop(TITLE)), "post title"
        yield "no entry-content", article_text(1, drop(BODY)), "entry-content"
        yield "no byline", article_text(1, drop(BYLINE)), "byline"
        yield "two titles", article_text(1, twice(TITLE)), "post title, found 2"
        yield "two header dates", article_text(1, twice(HEADER_DATE)), "post date, found 2"
        yield "two entry-content blocks", article_text(1, twice(BODY)), "entry-content, found 2"
        yield "empty body", article_text(1, lambda s: s.select_one(BODY).clear()), "0 characters"
        yield "tiny body", article_text(1, lambda s: (s.select_one(BODY).clear(),
                                                      s.select_one(BODY).append("Hi"))), "2 characters"
        yield "date without offset", article_text(
            1, set_attr(HEADER_DATE + " time", "datetime", "2026-07-08T17:14:00")), "no usable offset"
        yield "unparseable date", article_text(
            1, set_attr(HEADER_DATE + " time", "datetime", "yesterday")), "no usable offset"
        yield "permalink date disagrees", article_text(
            1, set_attr(HEADER_DATE + " time", "datetime", "2026-07-09T17:14:00+08:00")), \
            "permalink date disagrees"
        yield "no postid class", article_text(
            1, body_classes(lambda c: [x for x in c if not x.startswith("postid-")])), "postid"
        yield "two postid classes", article_text(1, body_classes(lambda c: c + ["postid-1"])), "postid"
        yield "shortlink names another post", swap(P1, "?p=3108", "?p=3109"), "shortlink"
        yield "canonical is another URL", swap(
            P1, '<link rel="canonical" href="%s"' % ARTICLE_URL[1],
            '<link rel="canonical" href="%s"' % ARTICLE_URL[2]), "canonical link"
        yield "theme changed", article_text(
            1, body_classes(lambda c: [x for x in c if x != "wp-theme-twentytwentyfour"])), "body classes lack"
        yield "not a single post", article_text(
            1, body_classes(lambda c: [x for x in c if x != "single-post"])), "body classes lack"
        yield "title tag is not NSC", re.sub(r"<title>.*?</title>", "<title>Hello</title>", P1,
                                            flags=re.S), "not an NSC title"
        yield "byline off-host", article_text(1, set_attr(BYLINE, "href", "https://example.org/a/")), "byline"
        yield "truncated mid-document", P1[: len(P1) // 2], "truncation"
        yield "spam injected into a valid page", swap(P1, "</body>", "<div hidden>87club2</div></body>"), \
            "spam marker"

    def test_each_is_refused_for_its_own_reason_by_the_parser_and_by_extract(self):
        adapter = Rig().adapter
        for label, text, why in self.variants():
            with self.subTest(label):
                with self.assertRaisesRegex(nsc.PageRejected, why):
                    nsc.parse_article(text, ARTICLE_URL[1])
                result = adapter.extract(capture(text))
                self.assertEqual(result.status, st.EXTRACTION_FAILURE)
                self.assertIn(why, result.error_detail)
                self.assertEqual(result.documents, [])

    def test_the_sidebar_date_is_never_borrowed(self):
        # The trap must be armed: with the header date gone, the sidebar still
        # holds <time> elements an implementation with a fallback would use.
        text = article_text(1, drop(HEADER_DATE))
        self.assertTrue(BeautifulSoup(text, "html.parser").select("time[datetime]"))
        with self.assertRaisesRegex(nsc.PageRejected, "post date"):
            nsc.parse_article(text, ARTICLE_URL[1])

    def test_the_title_tag_is_never_borrowed(self):
        with self.assertRaisesRegex(nsc.PageRejected, "post title"):
            nsc.parse_article(article_text(1, drop(TITLE)), ARTICLE_URL[1])

    def test_extract_cross_checks_the_listing_the_url_and_the_date(self):
        rig = Rig()
        rig.discover(COVERED)
        renumbered = swap(swap(P1, "postid-3108", "postid-4242"), "?p=3108", "?p=4242")
        self.assertEqual(rig.adapter.extract(capture(renumbered)).status, st.EXTRACTION_FAILURE)
        # Another statement's page served at this URL: its canonical differs.
        other = ARTICLE_BIN[2].decode("utf-8")
        self.assertEqual(rig.adapter.extract(capture(other)).status, st.EXTRACTION_FAILURE)
        # The listing dated this item differently from the page.
        self.assertEqual(rig.adapter.extract(capture(P1, hint="2026-07-09")).status,
                         st.EXTRACTION_FAILURE)
        # A capture served from somewhere other than its URL.
        moved = capture(P1)
        moved.final_url = ARTICLE_URL[2]
        self.assertEqual(rig.adapter.extract(moved).status, st.EXTRACTION_FAILURE)
        # And the unmodified page is still accepted.
        self.assertEqual(rig.adapter.extract(capture(P1)).status, st.OK)

    def test_no_body_and_failed_captures_are_refused(self):
        adapter = Rig().adapter
        self.assertEqual(adapter.extract(capture("")).status, st.EXTRACTION_FAILURE)
        failed = capture(P1)
        failed.status = st.FETCH_FAILURE
        self.assertEqual(adapter.extract(failed).status, st.EXTRACTION_FAILURE)


# -- 4. challenge and anomalous pages --------------------------------------------

CHALLENGES = (
    ("HTTP 200 challenge page", lambda: FakeResponse(CHALLENGE)),
    ("HTTP 403 challenge page", lambda: FakeResponse(CHALLENGE, 403)),
    ("HTTP 503 challenge page", lambda: FakeResponse(CHALLENGE, 503)),
    ("cf-mitigated header on a normal body", lambda: FakeResponse(LISTING_BIN, 200,
                                                                  {"cf-mitigated": "challenge"})),
)


class TestChallengedPagesAreRecordedNotCollected(unittest.TestCase):

    def test_a_challenged_robots_file_stops_the_run_before_any_content_request(self):
        for label, make in CHALLENGES:
            with self.subTest(label):
                rig = Rig(routes({ROBOTS_URL: make()}))
                result = rig.discover(COVERED)
                self.assertEqual(result.status, st.ACCESS_CHALLENGED)
                self.assertIn("challenge", result.error_detail)
                self.assertEqual(result.references, [])
                self.assertEqual(rig.urls, [ROBOTS_URL])

    def test_a_challenged_listing_yields_no_references(self):
        for label, make in CHALLENGES:
            with self.subTest(label):
                rig = Rig(routes({LISTING_URL: make()}))
                result = rig.discover(COVERED)
                self.assertEqual(result.status, st.ACCESS_CHALLENGED)
                self.assertEqual(result.references, [])
                self.assertEqual(result.failed_endpoints, [LISTING_URL])
                self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_a_challenged_article_is_not_retained_or_retried(self):
        for label, make in CHALLENGES:
            with self.subTest(label):
                rig = Rig(routes({ARTICLE_URL[1]: make()}))
                cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
                self.assertEqual(cap.status, st.ACCESS_CHALLENGED)
                self.assertIn("challenge", cap.error_detail)
                self.assertFalse(cap.body)
                self.assertIsNone(cap.payload_sha256)
                self.assertEqual(rig.urls.count(ARTICLE_URL[1]), 1)

    def test_the_passive_cloudflare_script_alone_is_not_a_challenge(self):
        script = '<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script></body>'
        text = swap(P1, "</body>", script)
        self.assertFalse(nsc.looks_challenged({}, text))
        self.assertEqual(Rig().adapter.extract(capture(text)).status, st.OK)

    def test_the_header_alone_is_recognised_case_insensitively(self):
        self.assertTrue(nsc.looks_challenged({"cf-mitigated": "Challenge"}, "<html></html>"))
        self.assertFalse(nsc.looks_challenged({"cf-mitigated": "other"}, "<html></html>"))


class TestAnomalousPagesAreRefusedWhateverTheyAre(unittest.TestCase):
    """HTTP 200, text/html, plausible bytes: the page itself must be recognised."""

    BAD = (("known spam marker", GAMBLING, "spam marker"),
           ("generic maintenance page, no marker", MAINTENANCE, "not an NSC title"),
           ("empty document", b"", "truncation"),
           ("an article where the listing should be", ARTICLE_BIN[1], "body classes lack"),
           ("spam injected into a valid listing",
            swap(LISTING_BIN.decode("utf-8"), "</body>", "<div hidden>alanodt2</div></body>").encode(),
            "spam marker"),
           ("listing truncated mid-document", LISTING_BIN[: len(LISTING_BIN) // 2], "truncation"))

    def test_the_listing_is_refused_for_its_own_reason(self):
        for label, body, why in self.BAD:
            with self.subTest(label):
                rig = Rig(routes({LISTING_URL: FakeResponse(body)}))
                result = rig.discover(COVERED)
                self.assertEqual(result.status, st.LISTING_FAILURE)
                self.assertIn(why, result.error_detail)
                self.assertEqual(result.references, [])

    def test_a_statement_page_is_fetched_but_never_becomes_a_document(self):
        pages = (("known spam marker", GAMBLING, "spam marker"),
                 ("generic maintenance page", MAINTENANCE, "not an NSC title"),
                 ("the listing where a statement should be", LISTING_BIN, "body classes lack"),
                 ("empty", b"", "no body"))
        adapter = Rig().adapter
        for label, body, why in pages:
            with self.subTest(label):
                rig = Rig(routes({ARTICLE_URL[1]: FakeResponse(body)}))
                cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
                result = adapter.extract(cap)
                self.assertEqual(result.status, st.EXTRACTION_FAILURE)
                self.assertIn(why, result.error_detail)
                self.assertEqual(result.documents, [])

    def test_a_listing_with_no_items_is_a_shape_change_not_a_quiet_day(self):
        rig = Rig(routes({LISTING_URL: FakeResponse(synthetic_page([]))}))
        result = rig.discover(COVERED)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertIn("no items", result.error_detail)

    def test_a_listing_item_that_cannot_be_read_fails_the_whole_page(self):
        broken = synthetic_page([(1, date(2026, 7, 1))]).replace(b"datetime=", b"data-x=")
        result = Rig(routes({LISTING_URL: FakeResponse(broken)})).discover(COVERED)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertIn("item date", result.error_detail)


# -- 5. robots compliance ----------------------------------------------------------

LISTING_PATH = "/category/official-statements/"


def allowed(policy, path=LISTING_PATH):
    return nsc.robots_allows(nsc.robots_rules(nsc.parse_robots(policy)), path)


class TestRobotsMatching(unittest.TestCase):

    def test_the_captured_policy_restricts_nothing(self):
        text = ROBOTS_BIN.decode("utf-8")
        self.assertEqual(nsc.robots_rules(nsc.parse_robots(text)), [])
        self.assertTrue(allowed(text))
        self.assertTrue(allowed(text, urlparse_path(ARTICLE_URL[1])))

    def test_disallow_and_path_prefixes(self):
        self.assertFalse(allowed("User-agent: *\nDisallow: /\n"))
        self.assertFalse(allowed("User-agent: *\nDisallow: /category/\n"))
        self.assertTrue(allowed("User-agent: *\nDisallow: /category/\n", "/2026/07/08/x/"))
        self.assertTrue(allowed("Disallow: /\n"))          # no user-agent line: no group

    def test_a_group_naming_this_collector_beats_the_wildcard_group(self):
        deny = "User-agent: ChinaMilWatch-ShadowCollector\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
        self.assertFalse(allowed(deny))
        self.assertFalse(allowed(deny.replace("ChinaMilWatch-ShadowCollector", "chinamilwatch")))
        self.assertTrue(allowed("User-agent: ChinaMilWatch\nDisallow:\n\nUser-agent: *\nDisallow: /\n"))

    def test_other_agents_and_lookalikes_do_not_apply(self):
        self.assertTrue(allowed("User-agent: SomeoneElse\nDisallow: /\n\nUser-agent: *\nDisallow:\n"))
        self.assertTrue(allowed("User-agent: ChinaMilWatchX\nDisallow: /\n"))

    def test_groups_are_combined_not_first_wins(self):
        self.assertFalse(allowed("User-agent: *\nDisallow: /a/\n\nUser-agent: *\nDisallow: /category/\n"))
        self.assertFalse(allowed("User-agent: chinamilwatch\nDisallow: /a/\n\n"
                                 "User-agent: chinamilwatch-shadowcollector\nDisallow: /category/\n"))
        self.assertFalse(allowed("User-agent: Foo\nUser-agent: ChinaMilWatch\nDisallow: /\n"))

    def test_a_user_agent_line_after_rules_starts_a_new_group(self):
        self.assertTrue(allowed("User-agent: *\nDisallow:\nUser-agent: Foo\nDisallow: /\n"))

    def test_longest_match_wins_and_allow_wins_a_tie(self):
        self.assertTrue(allowed("User-agent: *\nDisallow: /category/\nAllow: /category/official-statements/\n"))
        self.assertTrue(allowed("User-agent: *\nDisallow: /category/official-statements/\n"
                                "Allow: /category/official-statements/\n"))
        self.assertFalse(allowed("User-agent: *\nAllow: /category/\n"
                                 "Disallow: /category/official-statements/\n"))

    def test_wildcards_end_anchors_and_queries(self):
        page2 = "/category/official-statements/page/2/"
        self.assertFalse(allowed("User-agent: *\nDisallow: /category/*/page/\n", page2))
        self.assertTrue(allowed("User-agent: *\nDisallow: /category/*/page/\n"))
        anchored = "User-agent: *\nDisallow: /category/official-statements/$\n"
        self.assertFalse(allowed(anchored))
        self.assertTrue(allowed(anchored, page2))
        self.assertFalse(allowed("User-agent: *\nDisallow: /*?paged=\n", LISTING_PATH + "?paged=2"))

    def test_comments_bom_crlf_and_field_case_are_tolerated(self):
        self.assertFalse(allowed("\ufeffUSER-AGENT: *\r\nDISALLOW: /category/ # private\r\n"))

    def test_an_empty_value_is_no_rule(self):
        self.assertTrue(allowed("User-agent: *\nDisallow:\nAllow:\n"))


def urlparse_path(url):
    return re.sub(r"^https://[^/]+", "", url)


class TestRobotsIsEnforcedByTheAdapter(unittest.TestCase):

    def test_robots_is_requested_first_and_read_again_every_run(self):
        rig = Rig()
        rig.discover(COVERED)
        self.assertEqual(rig.urls[0], ROBOTS_URL)
        rig.discover(COVERED)
        self.assertEqual(rig.urls.count(ROBOTS_URL), 2)
        rig.session.routes[ROBOTS_URL] = FakeResponse(b"User-agent: *\nDisallow: /\n", headers=TEXT_PLAIN)
        again = rig.discover(COVERED)
        self.assertEqual((again.status, again.references), (st.AUTH_FAILURE, []))

    def test_a_disallowed_listing_is_never_requested(self):
        for policy in ("User-agent: *\nDisallow: /\n", "User-agent: *\nDisallow: /category/\n",
                       "User-agent: ChinaMilWatch-ShadowCollector\nDisallow: /\n"
                       "\nUser-agent: *\nDisallow:\n"):
            with self.subTest(policy):
                rig = robots_rig(policy)
                result = rig.discover(COVERED)
                self.assertEqual(result.status, st.AUTH_FAILURE)
                self.assertEqual(result.references, [])
                self.assertEqual(rig.urls, [ROBOTS_URL])
                self.assertIn("robots.txt disallows", result.error_detail)

    def test_a_disallowed_statement_is_never_requested(self):
        rig = robots_rig("User-agent: *\nDisallow: /2026/\n")
        self.assertEqual(rig.discover(COVERED).status, st.OK)         # the listing is allowed
        cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
        self.assertEqual(cap.status, st.AUTH_FAILURE)
        self.assertNotIn(ARTICLE_URL[1], rig.urls)

    def test_a_statement_fetched_cold_reads_robots_first(self):
        rig = Rig()
        self.assertEqual(rig.adapter.fetch(ref(ARTICLE_URL[1])).status, st.OK)
        self.assertEqual(rig.urls, [ROBOTS_URL, ARTICLE_URL[1]])

    def test_every_robots_failure_stops_the_run_with_no_content_request(self):
        html_soft_404 = (b"<!DOCTYPE html><html><head><title>Page not found &#8211; National "
                         b"Security Council</title></head><body></body></html>")
        cases = (
            ("403 means no permission basis", lambda: FakeResponse(b"", 403, TEXT_PLAIN),
             st.AUTH_FAILURE, "HTTP 403"),
            ("401", lambda: FakeResponse(b"", 401, TEXT_PLAIN), st.AUTH_FAILURE, "HTTP 401"),
            ("500", lambda: FakeResponse(b"", 500, TEXT_PLAIN), st.LISTING_FAILURE, "HTTP 500"),
            ("503", lambda: FakeResponse(b"", 503, TEXT_PLAIN), st.LISTING_FAILURE, "HTTP 503"),
            ("redirect is not followed", lambda: FakeResponse(b"", 302, {"Location": "/x"}),
             st.DISALLOWED_REDIRECT, "redirect"),
            ("an HTML 200 is not allow-all", lambda: FakeResponse(html_soft_404, 200),
             st.UNEXPECTED_CONTENT_TYPE, "plain-text rules file"),
            ("text/plain claiming HTML inside", lambda: FakeResponse(html_soft_404, 200, TEXT_PLAIN),
             st.UNEXPECTED_CONTENT_TYPE, "plain-text rules file"),
            ("invalid UTF-8", lambda: FakeResponse(b"\xff\xfe\x00", 200, TEXT_PLAIN),
             st.UNEXPECTED_CONTENT_TYPE, "plain-text rules file"),
            ("transport error", lambda: requests.exceptions.ConnectionError("reset"),
             st.LISTING_FAILURE, "ConnectionError"),
            ("timeout", lambda: requests.exceptions.Timeout("slow"), st.TIMEOUT, "Timeout"),
        )
        for label, make, expected, why in cases:
            with self.subTest(label):
                rig = Rig(routes({ROBOTS_URL: make()}))
                result = rig.discover(COVERED)
                self.assertEqual(result.status, expected)
                self.assertIn(why, result.error_detail)
                self.assertEqual(result.references, [])
                self.assertEqual(result.failed_endpoints, [ROBOTS_URL])
                self.assertEqual(rig.urls, [ROBOTS_URL])

    def test_an_oversized_robots_file_is_refused(self):
        with mock.patch.object(nsc, "MAX_ROBOTS_BYTES", len(ROBOTS_BIN) - 1):
            rig = Rig()
            result = rig.discover(COVERED)
        self.assertEqual(result.status, st.OVERSIZED_RESPONSE)
        self.assertEqual(result.failed_endpoints, [ROBOTS_URL])
        self.assertEqual(rig.urls, [ROBOTS_URL])

    def test_a_missing_robots_file_states_no_restriction(self):
        for code in (404, 410):
            with self.subTest(code):
                rig = Rig(routes({ROBOTS_URL: FakeResponse(b"<html>not found</html>", code)}))
                self.assertEqual(rig.discover(COVERED).status, st.OK)
                self.assertEqual(rig.adapter.robots_status, "absent")

    def test_the_captured_policy_is_recorded_as_read(self):
        rig = Rig()
        rig.discover(COVERED)
        self.assertEqual(rig.adapter.robots_status, "read")


# -- 6. pagination --------------------------------------------------------------------

class TestTheCapturedSinglePageListing(unittest.TestCase):

    def test_coverage_is_proven_and_only_the_window_is_returned(self):
        rig = Rig()
        result = rig.discover(COVERED)
        expected = [i for i in LISTED.items if date.fromisoformat(i.published_date) > OLDEST]
        self.assertEqual(result.status, st.OK)
        self.assertEqual([r.url for r in result.references], [i.url for i in expected])
        self.assertEqual([r.hint_published_date for r in result.references],
                         [i.published_date for i in expected])
        self.assertTrue(all(r.discovered_via == LISTING_URL and r.source_slug == SOURCE["slug"]
                            for r in result.references))
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])             # no page guessed
        report = rig.adapter.listing_report
        self.assertEqual((report["pages_walked"], report["items_listed"],
                          report["pagination_markup_seen"]), (1, len(LISTED.items), False))

    def test_a_window_the_listing_cannot_prove_fails_whole_and_guesses_nothing(self):
        rig = Rig()
        result = rig.discover(UNCOVERED)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertEqual(result.references, [])
        self.assertIn("window coverage unprovable", result.error_detail)
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_a_recent_window_is_a_healthy_empty_result(self):
        result = Rig().discover(CollectionWindow(date(2026, 10, 1), 7))
        self.assertEqual((result.status, result.references), (st.OK_NO_PUBLICATIONS, []))
        self.assertTrue(st.is_success(result.status))

    def test_the_target_date_bounds_the_window_from_above(self):
        result = Rig().discover(CollectionWindow(date(2026, 6, 10), 3))
        self.assertEqual([r.hint_published_date for r in result.references], ["2026-06-09"])


class TestAMultiPageWalk(unittest.TestCase):

    def pages(self, page2=None, links=None):
        """Page one of the real listing (first three items), page two (the rest) or `page2`."""
        first = listing_page([0, 1, 2], NEXT % page_url(2) if links is None else links)
        second = listing_page([3, 4, 5]) if page2 is None else page2
        if isinstance(second, bytes):
            second = FakeResponse(second)
        return routes({LISTING_URL: FakeResponse(first), page_url(2): second})

    def test_a_valid_two_page_walk_returns_the_window_newest_first(self):
        rig = Rig(self.pages())
        result = rig.discover(MID)
        self.assertEqual(result.status, st.OK)
        self.assertEqual([r.hint_published_date for r in result.references],
                         ["2026-06-12", "2026-06-12", "2026-06-09"])
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL, page_url(2)])
        report = rig.adapter.listing_report
        self.assertEqual((report["pages_walked"], report["items_listed"],
                          report["pagination_markup_seen"]), (2, len(LISTED.items), True))

    def test_a_numbered_link_the_page_publishes_may_be_followed(self):
        links = '<a class="page-numbers" href="%s">2</a>' % page_url(2)
        self.assertEqual(Rig(self.pages(links=links)).discover(MID).status, st.OK)

    def test_noncanonical_numbered_links_do_not_authorize_a_page_request(self):
        for label, target in (
            ("plain http", page_url(2).replace("https://", "http://", 1)),
            ("fragment", page_url(2) + "#page-2"),
        ):
            with self.subTest(label):
                links = '<a class="page-numbers" href="%s">2</a>' % target
                rig = Rig(self.pages(links=links))
                result = rig.discover(MID)
                self.assertEqual(
                    (result.status, result.references),
                    (st.LISTING_FAILURE, []),
                )
                self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])
                self.assertIn("window coverage unprovable", result.error_detail)

    def test_a_rel_next_link_in_the_head_is_followed(self):
        rig = Rig(routes({LISTING_URL: FakeResponse(listing_page([0, 1, 2], head='<link rel="next" href="%s" />'
                                                                  % page_url(2))),
                          page_url(2): FakeResponse(listing_page([3, 4, 5]))}))
        self.assertEqual(rig.discover(MID).status, st.OK)

    def test_a_next_link_is_not_followed_once_the_window_is_covered(self):
        rig = Rig(routes({LISTING_URL: FakeResponse(listing_page(range(6), NEXT % page_url(2)))}))
        self.assertEqual(rig.discover(COVERED).status, st.OK)
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_an_incomplete_walk_returns_no_references_at_all(self):
        # Page one alone holds three in-window items. None may be returned.
        failures = (
            ("page 2 is 404", FakeResponse(b"nope", 404), st.LISTING_FAILURE, "HTTP 404"),
            ("page 2 is 503", FakeResponse(b"", 503), st.LISTING_FAILURE, "HTTP 503"),
            ("page 2 is 403", FakeResponse(b"", 403), st.AUTH_FAILURE, "HTTP 403"),
            ("page 2 is challenged", FakeResponse(CHALLENGE), st.ACCESS_CHALLENGED, "challenge"),
            ("page 2 is a spam page", FakeResponse(GAMBLING), st.LISTING_FAILURE, "spam marker"),
            ("page 2 is empty", FakeResponse(synthetic_page([])), st.LISTING_FAILURE, "no items"),
            ("page 2 redirects", FakeResponse(b"", 302, {"Location": LISTING_URL}),
             st.DISALLOWED_REDIRECT, "redirect"),
            ("page 2 times out", requests.exceptions.Timeout("slow"), st.TIMEOUT, "Timeout"),
            ("page 2 resets", requests.exceptions.ConnectionError("reset"), st.LISTING_FAILURE,
             "ConnectionError"),
        )
        for label, response, expected, why in failures:
            with self.subTest(label):
                rig = Rig(self.pages(page2=response))
                result = rig.discover(MID)
                self.assertEqual(result.status, expected)
                self.assertIn(why, result.error_detail)
                self.assertEqual(result.references, [])
                self.assertEqual(result.failed_endpoints, [page_url(2)])
                self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL, page_url(2)])

    def test_a_repeated_page_fails_the_run(self):
        repeat = listing_page([0, 1, 2], NEXT % page_url(2))
        result = Rig(self.pages(page2=repeat)).discover(MID)
        self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
        self.assertIn("repeats an item", result.error_detail)

    def test_a_single_overlapping_item_fails_the_run(self):
        result = Rig(self.pages(page2=listing_page([2, 3, 4, 5]))).discover(MID)
        self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
        self.assertIn("repeats an item", result.error_detail)

    def test_a_duplicate_within_a_page_fails_the_page(self):
        twin = listing_page([0, 0]).decode("utf-8")
        head, _, tail = twin.rpartition("wp-block-post post-3108")
        for label, page in (("same item twice", twin),
                            ("same URL under another id", head + "wp-block-post post-9999" + tail)):
            with self.subTest(label):
                result = Rig(routes({LISTING_URL: FakeResponse(page.encode("utf-8"))})).discover(COVERED)
                self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
                self.assertIn("appears twice", result.error_detail)

    def test_a_loop_fails_the_run(self):
        for label, links in (("page 2 links to itself", NEXT % page_url(2)),
                             ("page 2 links back to page 1", NEXT % LISTING_URL)):
            with self.subTest(label):
                page2 = listing_page([3, 4], links)
                rig = Rig(self.pages(page2=page2))
                result = rig.discover(MID)
                self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
                self.assertIn("do not lead to page 3", result.error_detail)
                self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL, page_url(2)])

    def test_a_skipped_or_foreign_next_link_is_not_followed(self):
        for label, target in (("skips page 2", page_url(3)),
                              ("another host", "https://example.org/category/official-statements/page/2/"),
                              ("a sibling subdomain", "https://evas.nsc.gov.ph/category/official-statements/page/2/"),
                              ("plain http", "http://nsc.gov.ph/category/official-statements/page/2/"),
                              ("a query form", LISTING_URL + "?paged=2")):
            with self.subTest(label):
                rig = Rig(self.pages(links=NEXT % target))
                result = rig.discover(MID)
                self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
                self.assertIn("do not lead to page 2", result.error_detail)
                self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_two_different_next_links_are_ambiguous(self):
        links = (NEXT % page_url(2)) + (NEXT % page_url(3))
        rig = Rig(self.pages(links=links))
        result = rig.discover(MID)
        self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
        self.assertIn("do not lead to page 2", result.error_detail)
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_numbers_that_advertise_more_without_a_link_to_the_next_page_fail(self):
        links = '<a class="page-numbers" href="%s">3</a>' % page_url(3)
        rig = Rig(self.pages(links=links))
        result = rig.discover(MID)
        self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
        self.assertIn("advertise up to page 3", result.error_detail)
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_a_pagination_form_the_walker_cannot_follow_is_named_in_the_failure(self):
        links = '<a href="%s?paged=2">2</a>' % LISTING_URL
        rig = Rig(self.pages(links=links))
        result = rig.discover(MID)
        self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
        self.assertIn("unsupported pagination links", result.error_detail)
        self.assertIn("paged=2", result.error_detail)
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_a_listing_that_is_not_newest_first_cannot_be_reasoned_about(self):
        swapped = Rig(routes({LISTING_URL: FakeResponse(listing_page([1, 0, 2, 3, 4, 5]))}))
        self.assertIn("newest-first", swapped.discover(COVERED).error_detail)
        newer = synthetic_page([(2, date(2026, 6, 20))])
        first = synthetic_page([(1, date(2026, 6, 12))], NEXT % page_url(2))
        rig = Rig(routes({LISTING_URL: FakeResponse(first), page_url(2): FakeResponse(newer)}))
        result = rig.discover(MID)
        self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
        self.assertIn("newest-first", result.error_detail)

    def test_a_chain_that_never_reaches_the_window_stops_at_the_page_cap(self):
        cap = nsc.MAX_LISTING_PAGES
        chain = {LISTING_URL: FakeResponse(synthetic_page([(1, TARGET - timedelta(days=1))],
                                                          NEXT % page_url(2)))}
        for n in range(2, cap + 3):
            chain[page_url(n)] = FakeResponse(synthetic_page(
                [(9000 + n, TARGET - timedelta(days=n))], NEXT % page_url(n + 1)))
        rig = Rig(routes(chain))
        result = rig.discover(CollectionWindow(TARGET, 400))
        self.assertEqual((result.status, result.references), (st.LISTING_FAILURE, []))
        self.assertIn("more than %d pages" % cap, result.error_detail)
        self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL] + [page_url(n) for n in range(2, cap + 1)])


# -- 7. transport discipline -------------------------------------------------------------

class TestEveryRequestIsPolite(unittest.TestCase):

    def run_everything(self):
        rig = Rig(source=EnabledSource)
        with mock.patch.object(nsc.time, "monotonic", return_value=500.0):
            rig.adapter.collect(COVERED)
        return rig

    def test_headers_redirects_streaming_and_timeout_are_fixed(self):
        rig = self.run_everything()
        self.assertGreater(len(rig.session.calls), 3)
        for url, kwargs in rig.session.calls:
            with self.subTest(url):
                self.assertEqual(set(kwargs), {"headers", "allow_redirects", "stream", "timeout"})
                self.assertEqual(kwargs["headers"], {"User-Agent": nsc.USER_AGENT,
                                                     "Accept-Encoding": "identity"})
                self.assertIs(kwargs["allow_redirects"], False)
                self.assertIs(kwargs["stream"], True)
                self.assertEqual(kwargs["timeout"], nsc.REQUEST_TIMEOUT)

    def test_requests_are_spaced_by_the_fixed_interval(self):
        rig = self.run_everything()
        self.assertEqual(rig.sleeps, [nsc.REQUEST_INTERVAL] * (len(rig.session.calls) - 1))

    def test_a_failed_attempt_still_counts_for_spacing(self):
        clock, sleeps = [0.0], []

        def sleeper(seconds):                    # time passes while the adapter waits
            sleeps.append(seconds)
            clock[0] += seconds

        session = FakeSession(routes({
            ARTICLE_URL[1]: requests.exceptions.ConnectionError("reset by peer")}))
        adapter = nsc.PHNscAdapter(FakeSource(), session=session, sleeper=sleeper)
        with mock.patch.object(nsc.time, "monotonic", side_effect=lambda: clock[0]):
            failed = adapter.fetch(ref(ARTICLE_URL[1]))
            after = adapter.fetch(ref(ARTICLE_URL[2]))
        self.assertEqual(failed.status, st.FETCH_FAILURE)
        self.assertEqual(after.status, st.OK)
        self.assertEqual([url for url, _ in session.calls],
                         [ROBOTS_URL, ARTICLE_URL[1], ARTICLE_URL[2]])
        # robots, then the article that failed, then the next: each one waits out
        # the interval, including the one that follows the failure
        self.assertEqual(sleeps, [nsc.REQUEST_INTERVAL] * 2)

    def test_no_cookie_is_ever_sent_back(self):
        rig = self.run_everything()
        self.assertEqual(set(rig.session.cookie_seen), {0})

    def test_nothing_is_retried(self):
        rig = self.run_everything()
        self.assertEqual(len(rig.urls), len(set(rig.urls)))
        failing = Rig(routes({ARTICLE_URL[1]: FakeResponse(b"", 429)}))
        failing.adapter.fetch(ref(ARTICLE_URL[1]))
        self.assertEqual(failing.urls.count(ARTICLE_URL[1]), 1)


class TestResponsesAreScreened(unittest.TestCase):

    def fetch_with(self, response, url=ARTICLE_URL[1]):
        rig = Rig(routes({url: response}))
        return rig, rig.adapter.fetch(ref(url))

    def test_redirects_are_recorded_not_followed(self):
        for code in (301, 302, 303, 307, 308):
            with self.subTest(code):
                target = "https://evas.nsc.gov.ph/x"
                rig, cap = self.fetch_with(FakeResponse(b"", code, {"Location": target}))
                self.assertEqual(cap.status, st.DISALLOWED_REDIRECT)
                self.assertIn("HTTP %d redirect" % code, cap.error_detail)
                self.assertNotIn(target, rig.urls)
                listing = Rig(routes({LISTING_URL: FakeResponse(b"", code, {"Location": target})}))
                self.assertEqual(listing.discover(COVERED).status, st.DISALLOWED_REDIRECT)

    def test_status_codes_map_to_named_outcomes(self):
        for code, expected in ((404, st.FETCH_FAILURE), (410, st.FETCH_FAILURE), (429, st.FETCH_FAILURE),
                               (500, st.FETCH_FAILURE), (503, st.FETCH_FAILURE),
                               (401, st.AUTH_FAILURE), (403, st.AUTH_FAILURE)):
            with self.subTest(code):
                _, cap = self.fetch_with(FakeResponse(b"x", code))
                self.assertEqual(cap.status, expected)
                self.assertIn("HTTP %d" % code, cap.error_detail)
                self.assertFalse(cap.body)
        for exc, expected in ((requests.exceptions.Timeout("slow"), st.TIMEOUT),
                              (requests.exceptions.ConnectionError("reset"), st.FETCH_FAILURE)):
            with self.subTest(type(exc).__name__):
                cap = self.fetch_with(exc)[1]
                self.assertEqual(cap.status, expected)
                self.assertEqual(cap.error_detail, type(exc).__name__)

    def test_listing_status_codes(self):
        for code, expected in ((404, st.LISTING_FAILURE), (500, st.LISTING_FAILURE),
                               (503, st.LISTING_FAILURE), (403, st.AUTH_FAILURE)):
            with self.subTest(code):
                result = Rig(routes({LISTING_URL: FakeResponse(b"x", code)})).discover(COVERED)
                self.assertEqual((result.status, result.references), (expected, []))
                self.assertIn("HTTP %d" % code, result.error_detail)
        for exc, expected in ((requests.exceptions.Timeout("slow"), st.TIMEOUT),
                              (requests.exceptions.ConnectionError("reset"), st.LISTING_FAILURE)):
            with self.subTest(type(exc).__name__):
                self.assertEqual(Rig(routes({LISTING_URL: exc})).discover(COVERED).status, expected)

    def test_only_utf8_html_is_accepted(self):
        for label, headers, body in (
                ("pdf", {"Content-Type": "application/pdf"}, ARTICLE_BIN[1]),
                ("json", {"Content-Type": "application/json"}, b"{}"),
                ("plain text", {"Content-Type": "text/plain"}, ARTICLE_BIN[1]),
                ("no content type", {"Content-Type": ""}, ARTICLE_BIN[1]),
                ("latin-1 declared", {"Content-Type": "text/html; charset=ISO-8859-1"}, ARTICLE_BIN[1]),
                ("invalid UTF-8", {}, b"\xff\xfe" + ARTICLE_BIN[1])):
            with self.subTest(label):
                _, cap = self.fetch_with(FakeResponse(body, 200, headers))
                self.assertEqual(cap.status, st.UNEXPECTED_CONTENT_TYPE)
                self.assertRegex(cap.error_detail, "content-type|UTF-8")
                self.assertFalse(cap.body)
        for ctype in ("text/html", "text/html; charset=utf-8", 'TEXT/HTML; charset="UTF-8"'):
            with self.subTest(ctype):
                self.assertEqual(self.fetch_with(FakeResponse(ARTICLE_BIN[1], 200,
                                                              {"Content-Type": ctype}))[1].status, st.OK)

    def test_an_oversized_body_is_refused_and_not_kept(self):
        limit = len(ARTICLE_BIN[1]) - 1
        with mock.patch.object(nsc, "MAX_BODY_BYTES", limit):
            _, streamed = self.fetch_with(FakeResponse(ARTICLE_BIN[1]))
            declared = FakeResponse(b"tiny", 200, {"Content-Length": str(limit + 1)})
            _, by_header = self.fetch_with(declared)
        for cap in (streamed, by_header):
            self.assertEqual(cap.status, st.OVERSIZED_RESPONSE)
            self.assertIn("exceeds", cap.error_detail)
            self.assertFalse(cap.body)
            self.assertIsNone(cap.payload_sha256)
        self.assertFalse(declared.streamed)          # refused from the header, unread

    def test_a_url_that_is_not_a_permalink_is_never_requested(self):
        for bad in ("http://nsc.gov.ph/2026/07/08/x/", "https://evas.nsc.gov.ph/2026/07/08/x/",
                    "https://www.nsc.gov.ph/2026/07/08/x/", "https://nsc.gov.ph.evil.example/2026/07/08/x/",
                    "https://nsc.gov.ph@evil.example/2026/07/08/x/", "https://nsc.gov.ph:8443/2026/07/08/x/",
                    "https://nsc.gov.ph/2026/07/08/x/?p=1", "https://nsc.gov.ph/2026/07/08/x/#top",
                    "https://nsc.gov.ph/2026/07/08/x", "https://nsc.gov.ph/wp-admin/",
                    "https://nsc.gov.ph/author/nsc_admin/", LISTING_URL, "", "javascript:alert(1)"):
            with self.subTest(bad):
                rig = Rig()
                cap = rig.adapter.fetch(CandidateReference(bad, SOURCE["slug"]))
                self.assertEqual(cap.status, st.FETCH_FAILURE)
                self.assertIn("non-permalink", cap.error_detail)
                self.assertEqual(rig.urls, [])


class TestPureHelpers(unittest.TestCase):

    def test_canonical_url_accepts_only_nsc_permalinks_unchanged(self):
        for url in ARTICLE_URL.values():
            self.assertEqual(nsc.canonical_url(url), url)
        self.assertIsNone(nsc.canonical_url(None))
        self.assertIsNone(nsc.canonical_url("https://nsc.gov.ph/2026/07/08/Upper-Case/"))
        self.assertIsNone(nsc.canonical_url("https://nsc.gov.ph/2026/7/8/x/"))
        self.assertIsNone(nsc.canonical_url("https://nsc.gov.ph/2026/07/08/x/y/"))

    def test_publication_dates_keep_their_own_offset(self):
        self.assertEqual(nsc.parse_published("2026-07-08T17:14:00+08:00"),
                         ("2026-07-08", "2026-07-08T09:14:00+00:00", "2026-07-08T17:14:00+08:00"))
        # Late evening UTC is already the next day in Manila: the stated date wins.
        self.assertEqual(nsc.parse_published("2026-07-09T02:00:00+08:00")[:2],
                         ("2026-07-09", "2026-07-08T18:00:00+00:00"))
        self.assertEqual(nsc.parse_published("2026-07-08T09:14:00Z")[:2],
                         ("2026-07-08", "2026-07-08T09:14:00+00:00"))
        for bad in ("2026-07-08T17:14:00", "2026-07-08", "yesterday", "", None):
            self.assertIsNone(nsc.parse_published(bad))


# -- 8. contract and isolation ---------------------------------------------------------------

class TestContract(unittest.TestCase):

    def test_it_is_a_source_adapter_and_the_manifest_path_resolves_to_it(self):
        module, _, name = SOURCE["adapter"].partition(":")
        cls = getattr(importlib.import_module(module), name)
        self.assertIs(cls, nsc.PHNscAdapter)
        self.assertTrue(issubclass(cls, SourceAdapter))

    def test_healthcheck_is_offline_and_reports_disabled(self):
        rig = Rig()
        health = rig.adapter.healthcheck()
        self.assertEqual(health.status, st.SKIPPED_DISABLED)
        self.assertEqual(rig.session.calls, [])

    def test_a_disabled_source_collects_nothing(self):
        rig = Rig()
        result, documents = rig.adapter.collect(COVERED)
        self.assertEqual((result.status, documents), (st.SKIPPED_DISABLED, []))
        self.assertEqual(rig.session.calls, [])

    def test_collection_through_an_enabled_test_double_survives_per_item_failures(self):
        rig = Rig(source=EnabledSource)
        result, documents = rig.adapter.collect(COVERED)       # three of five have no fixture
        self.assertEqual(result.status, st.OK)
        self.assertEqual(sorted(d.extra["source_identity"] for d in documents),
                         sorted("nsc:%s" % ITEM[ARTICLE_URL[n]].post_id for n in (1, 2)))

    def test_the_manifest_patterns_match_real_permalinks_and_nothing_else(self):
        pattern = re.compile(SOURCE["article_url_patterns"][0])
        for url in ARTICLE_URL.values():
            self.assertTrue(pattern.match(url))
        for url in (LISTING_URL, "https://evas.nsc.gov.ph/2026/07/08/x/", "http://nsc.gov.ph/2026/07/08/x/"):
            self.assertFalse(pattern.match(url))


class TestProductionIsolation(unittest.TestCase):

    def test_the_manifest_is_a_disabled_shadow_manifest_outside_desks(self):
        self.assertIs(MANIFEST["_shadow"], True)
        self.assertIs(SOURCE["enabled"], False)
        self.assertEqual(MANIFEST["desk"]["public_status"], "shadow")
        self.assertIs(MANIFEST["desk"]["active"], False)
        self.assertFalse((REPO_ROOT / "desks" / "philippines").exists())
        self.assertEqual(list((REPO_ROOT / "desks").rglob("*ph_nsc*")), [])

    def test_production_discovery_cannot_see_this_source_or_a_philippines_desk(self):
        desks = load_all_desks()
        self.assertNotIn(MANIFEST["desk"]["desk_id"], desks)
        self.assertNotIn(SOURCE["slug"], {s.slug for d in desks.values() for s in d.sources})
        registry = (REPO_ROOT / "desks" / "registry.json").read_text(encoding="utf-8").lower()
        self.assertNotIn("philippines", registry)
        self.assertNotIn("ph_nsc", registry)

    def test_nothing_in_production_code_or_workflows_references_the_adapter(self):
        roots = [REPO_ROOT / name for name in (".github", "core", "desks", "scripts", "site",
                                               "processing", "adapters")]
        files = [p for root in roots if root.exists() for p in root.rglob("*")
                 if p.suffix in (".py", ".json", ".yml", ".yaml", ".toml") and p.is_file()
                 and p.stat().st_size < 2_000_000]
        files += list((REPO_ROOT / "scraper").glob("*.py")) + [REPO_ROOT / "pipeline.py",
                                                               REPO_ROOT / "scraper" / "sources" / "__init__.py"]
        for path in files:
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
                self.assertNotIn("ph_nsc", text, path)
                self.assertNotIn("PHNscAdapter", text, path)

    def test_the_adapter_imports_nothing_that_stores_or_reaches_production(self):
        tree = ast.parse((REPO_ROOT / "scraper" / "sources" / "ph_nsc.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        allowed = {"__future__", "hashlib", "re", "time", "dataclasses", "datetime", "typing",
                   "urllib.parse", "requests", "bs4"}
        extra = {m for m in imported if m not in allowed and not m.startswith("core.collection")}
        self.assertEqual(extra, set())


class TestReviewRegressions(unittest.TestCase):
    """F1-F3: faithful page variants, tested through the public contract."""

    def test_legitimate_challenge_phrases_are_collected_as_statement_text(self):
        phrases = ("Just a moment", "Attention required",
                   "Enable JavaScript and cookies to continue",
                   "Checking your browser before accessing", "_cf_chl_opt",
                   "cf-browser-verification", "alanodt2", "87club2")
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                def edit(soup):
                    soup.select_one(BODY).append(soup.new_tag("p"))
                    soup.select_one(BODY).find_all("p")[-1].string = phrase
                text = article_text(1, edit)
                rig = Rig(routes({ARTICLE_URL[1]: FakeResponse(text.encode())}))
                cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
                self.assertEqual(cap.status, st.OK)
                result = rig.adapter.extract(cap)
                self.assertEqual(result.status, st.OK, result.error_detail)
                self.assertIn(phrase, result.documents[0].text_original)

    def test_legitimate_challenge_titles_are_not_interstitials(self):
        for title in ("Just a moment of reflection", "Attention required for maritime safety"):
            with self.subTest(title=title):
                def edit(soup):
                    soup.title.string = title + " – National Security Council"
                    soup.select_one(TITLE).string = title
                text = article_text(1, edit)
                rig = Rig(routes({ARTICLE_URL[1]: FakeResponse(text.encode())}))
                cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
                self.assertEqual(cap.status, st.OK)
                result = rig.adapter.extract(cap)
                self.assertEqual(result.status, st.OK, result.error_detail)
                self.assertEqual(result.documents[0].title_original, title)

    def test_explicit_challenge_header_overrides_valid_statement_structure(self):
        rig = Rig(routes({ARTICLE_URL[1]: FakeResponse(
            ARTICLE_BIN[1], headers={"cf-mitigated": "challenge"})}))
        cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
        self.assertEqual(cap.status, st.ACCESS_CHALLENGED)
        self.assertIsNone(cap.body)
        self.assertEqual(rig.adapter.extract(cap).documents, [])

    def test_active_challenge_markup_stops_even_when_theme_classes_remain(self):
        for markup in ('<form id="challenge-form"></form>',
                       '<script>window._cf_chl_opt = {cType: "managed"};</script>'):
            with self.subTest(markup=markup):
                text = swap(P1, "</body>", markup + "</body>")
                rig = Rig(routes({ARTICLE_URL[1]: FakeResponse(text.encode())}))
                cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
                self.assertEqual(cap.status, st.ACCESS_CHALLENGED)
                self.assertIsNone(cap.body)

    def test_malformed_listing_links_return_failure_and_no_references(self):
        for selector in ("h2.wp-block-post-title a", "next-link"):
            with self.subTest(selector=selector):
                soup = BeautifulSoup(LISTING_BIN.decode(), "html.parser")
                if selector == "next-link":
                    link = soup.new_tag("a", href="https://[broken/", rel="next")
                    soup.find("main").append(link)
                else:
                    soup.select_one(selector)["href"] = "https://[broken/"
                rig = Rig(routes({LISTING_URL: FakeResponse(str(soup).encode())}))
                result = rig.discover(COVERED)
                self.assertEqual(result.status, st.LISTING_FAILURE)
                self.assertEqual(result.references, [])
                self.assertEqual(result.failed_endpoints, [LISTING_URL])
                self.assertEqual(rig.adapter._listing_ids, {})
                self.assertEqual(rig.adapter.listing_report, {})
                self.assertEqual(rig.urls, [ROBOTS_URL, LISTING_URL])

    def test_malformed_article_byline_returns_failure_without_documents(self):
        text = article_text(1, set_attr(BYLINE, "href", "https://[broken/"))
        rig = Rig(routes({ARTICLE_URL[1]: FakeResponse(text.encode())}))
        cap = rig.adapter.fetch(ref(ARTICLE_URL[1]))
        self.assertEqual(cap.status, st.OK)
        result = rig.adapter.extract(cap)
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(result.documents, [])
        self.assertIn("unparseable page", result.error_detail)

    def test_malformed_reference_is_never_requested(self):
        rig = Rig()
        cap = rig.adapter.fetch(ref("https://[broken/"))
        self.assertEqual(cap.status, st.FETCH_FAILURE)
        self.assertEqual(rig.urls, [])

    def test_repeated_url_with_changed_post_id_fails_required_pagination(self):
        second = BeautifulSoup(listing_page([2, 3, 4, 5]).decode(), "html.parser")
        item = second.select_one("ul.wp-block-post-template > li")
        item["class"] = ["post-99999" if c.startswith("post-") else c
                         for c in item["class"]]
        rig = Rig(TestAMultiPageWalk().pages(str(second).encode()))
        result = rig.discover(MID)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertEqual(result.references, [])
        self.assertEqual(rig.adapter._listing_ids, {})
        self.assertEqual(rig.adapter.listing_report, {})

    def test_unrepresentable_utc_date_is_refused_instead_of_raising(self):
        self.assertIsNone(nsc.parse_published("0001-01-01T00:00:00+08:00"))
        text = article_text(1, set_attr(
            HEADER_DATE + " time", "datetime", "0001-01-01T00:00:00+08:00"))
        result = Rig().adapter.extract(capture(text))
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(result.documents, [])

    def test_next_request_waits_after_slow_or_failed_body_read(self):
        for fails in (False, True):
            with self.subTest(fails=fails):
                clock, sleeps, starts = [0.0], [], []

                def sleeper(seconds):
                    sleeps.append(seconds)
                    clock[0] += seconds

                class SlowBody(FakeResponse):
                    closed = False

                    def iter_content(self, chunk_size=1):
                        yield self._body[:20]
                        clock[0] += 10.0
                        if fails:
                            raise requests.exceptions.ConnectionError("mid-body reset")
                        yield self._body[20:]

                    def close(self):
                        self.closed = True

                slow = SlowBody(ARTICLE_BIN[1])
                session = FakeSession(routes({ARTICLE_URL[1]: slow}))
                original_get = session.get

                def get(url, **kwargs):
                    starts.append(clock[0])
                    return original_get(url, **kwargs)

                session.get = get
                adapter = nsc.PHNscAdapter(FakeSource(), session=session, sleeper=sleeper)
                with mock.patch.object(nsc.time, "monotonic", side_effect=lambda: clock[0]):
                    first = adapter.fetch(ref(ARTICLE_URL[1]))
                    after = adapter.fetch(ref(ARTICLE_URL[2]))
                self.assertEqual(first.status, st.FETCH_FAILURE if fails else st.OK)
                self.assertEqual(after.status, st.OK)
                self.assertTrue(slow.closed)
                self.assertEqual(starts, [0.0, 2.0, 14.0])
                self.assertEqual(sleeps, [nsc.REQUEST_INTERVAL] * 2)
                self.assertEqual(len(session.cookies), 0)

    def test_hosting_byline_never_becomes_an_inferred_issuer_or_author(self):
        for n in (1, 2):
            with self.subTest(article=n):
                result = Rig().adapter.extract(capture(ARTICLE_BIN[n].decode(), ARTICLE_URL[n]))
                self.assertEqual(result.status, st.OK)
                doc, = result.documents
                self.assertEqual(doc.extra["site_byline"], "National Security Council")
                self.assertEqual(doc.extra["site_byline_url"],
                                 "https://nsc.gov.ph/author/nsc_admin/")
                self.assertIsNone(doc.raw)
                for key in doc.as_article_dict():
                    self.assertFalse("issuer" in key or "author" in key or key == "byline", key)


class TestTheGatesAreRecorded(unittest.TestCase):

    def test_the_readme_states_each_open_gate_and_the_packet_identity(self):
        readme = (SHADOW / "README.md").read_text(encoding="utf-8").lower()
        for gate in (
                "repository-client compatibility: measured successfully for the owner's mac environment",
                "reliable periodic access: unmeasured",
                "reuse permission: not reviewed",
                "discovery completeness: prospectively bounded",
                "category anomaly: unresolved but not reproduced on 2026-10-02",
                "collector identity: undecided for scheduled use",
                "live remeasurement with the repository client: completed successfully on 2026-10-02",
                "880e330b594709fe722d952abb2a6b7ce150b83dcd7cf5fbe8dbc4b06e237b54",
        ):
            self.assertIn(gate, readme)
        for row in LEDGER.values():
            self.assertIn(row["sha256"], readme)

    def test_the_manifest_scope_states_the_limit_of_the_evidence(self):
        scope = " ".join(SOURCE["declared_scope"]).lower()
        self.assertIn("bounded accessibility only", scope)
        self.assertIn("hosting is not issuing", scope)


if __name__ == "__main__":
    unittest.main()
