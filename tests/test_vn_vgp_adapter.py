"""
Viet Nam Government News (English) `defense` tag shadow adapter: listing,
dates, identity, body boundaries, refusals, robots and transport.

Everything runs offline from the 2026-10-06 UTC captures in
tests/fixtures/vn_vgp/ and from variants built in memory from those same bytes.
A socket guard fails any real connection. Variants are labelled as derived and
are never written back: the fixtures stay exactly the bytes the probe received.

What this proves is limited to the adapter's own logic. The captures show that
en.baochinhphu.vn answered this identity on one day; they do not show reliable
access over time, access from GitHub Actions, or permission to reuse text.
"""

from __future__ import annotations

import ast
import hashlib
import json
import socket
import sys
import unicodedata
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import (                          # noqa: E402
    CandidateReference, CaptureResult, CollectionWindow, SourceAdapter)
from core.manifests import load_all_desks                       # noqa: E402
from scraper.sources import vn_vgp as vgp                       # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "vn_vgp"
MANIFEST = json.loads((REPO_ROOT / "shadow" / "vietnam" / "manifest.json")
                      .read_text(encoding="utf-8"))
SOURCE = MANIFEST["sources"][0]
PROBE = json.loads((FIX / "requests.json").read_text(encoding="utf-8"))
ROWS = {row["fixture"]: row for row in PROBE["requests"] if row["fixture"]}


def fixture(name):
    return (FIX / name).read_bytes()


ROBOTS_BIN = fixture("robots.bin")
LISTING_BIN = fixture("listing.bin")
LISTING_TEXT = LISTING_BIN.decode("utf-8")
MOD_CHALLENGE = fixture("mod-gov-vn-robots-challenge.bin")
#: item id -> (url, exact bytes) for every article page the probe kept.
PAGES = {name.rsplit("-", 1)[1][:-4]: (ROWS[name]["url"], fixture(name))
         for name in ROWS if name.startswith(("article-", "untagged-"))}
URL = {k: v[0] for k, v in PAGES.items()}
BIN = {k: v[1] for k, v in PAGES.items()}
SUMMARY = "111260804150254797"          # the untagged national security strategy summary
MAY = ("111260523144123151", "111260521151722925")
#: 2026-05-21..24 holds exactly the two May fixtures; the oldest listed item is
#: 2023-11-16, so the one captured page proves coverage of this window.
TARGET, LOOKBACK = date(2026, 5, 24), 3
HTML = {"Content-Type": "text/html; charset=utf-8"}
TEXT_PLAIN = {"Content-Type": "text/plain"}
CONTENT_OPEN = '<div class="detail-content afcbc-body clearfix" data-role="content">'
#: Derived, not captured: the generic Cloudflare form, for the phrase checks.
CF_CHALLENGE = (b'<!DOCTYPE html><html><head><title>Just a moment...</title></head><body>'
                b'<form id="challenge-form" method="POST"></form></body></html>')


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

class FakeRaw:
    def __init__(self, body, fail=None):
        self.body, self.fail, self.decode_flags = body, fail, []

    def stream(self, amt, decode_content=True):
        self.decode_flags.append(decode_content)
        for i in range(0, len(self.body), amt):
            yield self.body[i:i + amt]
        if self.fail is not None:
            raise self.fail


class FakeResponse:
    def __init__(self, body=b"", status=200, headers=None, fail=None):
        self.status_code = status
        self.headers = dict(HTML)
        self.headers.update(headers or {})
        self.raw = FakeRaw(body, fail)
        self.closed = 0

    def close(self):
        self.closed += 1


class Clock:
    """Monotonic time that only moves when the adapter sleeps or a request takes time."""

    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds

    def __call__(self):
        return self.t


class FakeSession:
    """Serves routes, answers 404 for anything else, and records every call."""

    def __init__(self, route_map, clock, duration=0.0):
        self.routes = dict(route_map)
        self.calls = []
        self.cookie_seen = []
        self.cookies = requests.cookies.RequestsCookieJar()
        self.clock, self.duration = clock, duration

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs, self.clock.t))
        self.cookie_seen.append(len(self.cookies))
        self.clock.t += self.duration
        route = self.routes.get(url, FakeResponse(b"not found", 404))
        if isinstance(route, BaseException):
            raise route
        self.cookies.set("muid_mly", "derived")     # as requests' jar would learn one
        return route


class FakeSource:
    slug = SOURCE["slug"]
    enabled = True
    base_url = SOURCE["base_url"]


def routes(over=None):
    base = {vgp.ROBOTS: FakeResponse(ROBOTS_BIN, headers=TEXT_PLAIN),
            vgp.LISTING: FakeResponse(LISTING_BIN)}
    base.update({URL[k]: FakeResponse(BIN[k]) for k in URL})
    base.update(over or {})
    return base


class Rig:
    def __init__(self, route_map=None, source=FakeSource, max_requests=None, duration=0.0):
        self.clock = Clock()
        self.session = FakeSession(routes() if route_map is None else route_map,
                                   self.clock, duration)
        self.adapter = vgp.VNVgpAdapter(source(), session=self.session,
                                        sleeper=self.clock.sleep, clock=self.clock,
                                        max_requests=max_requests)

    @property
    def urls(self):
        return [url for url, _, _ in self.session.calls]

    def discover(self, target=TARGET, lookback=LOOKBACK):
        return self.adapter.discover(CollectionWindow(target, lookback))


def robots_rig(policy, status=200, ctype="text/plain", extra=None):
    body = policy.encode("utf-8") if isinstance(policy, str) else policy
    headers = {"Content-Type": ctype}
    headers.update(extra or {})
    return Rig(routes({vgp.ROBOTS: FakeResponse(body, status, headers)}))


def edited(text, *pairs):
    """Exact, counted string surgery on a captured page. Derived, never written back."""
    for old, new in pairs:
        if text.count(old) != 1:
            raise AssertionError("anchor occurs %d times: %r" % (text.count(old), old))
        text = text.replace(old, new)
    return text


def page(item_id, *pairs):
    return edited(BIN[item_id].decode("utf-8"), *pairs)


def with_body(item_id, inner):
    """The page with its content block's inner HTML replaced. Derived."""
    text = BIN[item_id].decode("utf-8")
    start = text.index(CONTENT_OPEN) + len(CONTENT_OPEN)
    end = text.index("</div>", text.index("<!--", text.rindex("./.</p>")))
    return text[:start] + inner + text[end:]


def item_block(item_id):
    """The raw markup of one listing item that is not the last in the stream."""
    start = LISTING_TEXT.index('<div class="box-stream-item" data-id="%s">' % item_id)
    end = LISTING_TEXT.index('<div class="box-stream-item"', start + 1)
    return start, end


def ref(item_id, hint="from-listing"):
    listed = {i.item_id: i for i in vgp.parse_listing_page(LISTING_TEXT)}.get(item_id)
    if hint == "from-listing":
        hint = listed.listed_date if listed else None
    return CandidateReference(url=URL[item_id], source_slug=SOURCE["slug"],
                              discovered_via=vgp.LISTING, hint_published_date=hint)


def capture(text, item_id=MAY[0], hint="from-listing", final_url=None):
    url = URL[item_id]
    body = text if isinstance(text, str) else text.decode("utf-8")
    return CaptureResult(ref(item_id, hint), st.OK, url, final_url=final_url or url,
                         http_status=200, content_type=HTML["Content-Type"],
                         payload_bytes=len(body.encode("utf-8")),
                         payload_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                         retrieved_at="2026-10-06T01:50:00+00:00", body=body)


def extract(text, item_id=MAY[0], hint="from-listing", adapter=None):
    return (adapter or Rig().adapter).extract(capture(text, item_id, hint))


# -- the captures themselves ---------------------------------------------------

class TestFixtureIntegrity(unittest.TestCase):
    def test_every_fixture_is_the_byte_exact_probe_capture(self):
        for name, row in ROWS.items():
            with self.subTest(name=name):
                data = fixture(name)
                self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
                self.assertEqual(len(data), row["bytes"])
                self.assertTrue(row["exact_wire_bytes"])
                self.assertFalse(row["truncated"])
        self.assertEqual((FIX / ".gitattributes").read_text(), "* binary\n")
        # CRLF is part of the published bytes and must survive storage untouched.
        self.assertIn(b"\r\n", BIN[MAY[0]])

    def test_probe_stayed_inside_its_written_cap_and_spacing(self):
        rows = PROBE["requests"]
        self.assertEqual([r["seq"] for r in rows], list(range(1, len(rows) + 1)))
        self.assertEqual(PROBE["used"]["total"], len(rows))
        self.assertLessEqual(len(rows), PROBE["written_cap"]["session_total"])
        for phase in ("survey", "deep"):
            used = sum(1 for r in rows if r["phase"] == phase)
            self.assertEqual(PROBE["used"]["per_phase"][phase], used)
            self.assertLessEqual(used, PROBE["written_cap"][phase])
        self.assertEqual(PROBE["user_agent"], vgp.USER_AGENT)
        self.assertEqual(PROBE["request_headers"], vgp.REQUEST_HEADERS)
        for before, after in zip(rows, rows[1:]):
            gap = (datetime.fromisoformat(after["requested_at_utc"])
                   - datetime.fromisoformat(before["completed_at_utc"])).total_seconds()
            self.assertGreaterEqual(gap, vgp.REQUEST_INTERVAL, after["seq"])

    def test_the_listing_was_identical_on_refetch(self):
        listing_rows = [r for r in PROBE["requests"] if r["url"] == vgp.LISTING]
        self.assertEqual(len(listing_rows), 2)
        self.assertEqual({r["sha256"] for r in listing_rows}, {hashlib.sha256(LISTING_BIN).hexdigest()})

    def test_the_two_refused_surfaces_are_recorded_as_measured(self):
        mod = [r for r in PROBE["requests"] if r["url"] == "https://mod.gov.vn/robots.txt"]
        self.assertEqual(len(mod), 2)
        self.assertEqual({r["sha256"] for r in mod}, {hashlib.sha256(MOD_CHALLENGE).hexdigest()})
        self.assertTrue(vgp.looks_challenged({}, MOD_CHALLENGE.decode("utf-8")))
        qdnd = [r for r in PROBE["requests"]
                if r["url"].startswith("https://en.qdnd.vn/") and not r["url"].endswith("robots.txt")]
        self.assertEqual(len(qdnd), 3)
        for row in qdnd:
            self.assertEqual((row["status"], row["location"]), (302, row["url"]))
            self.assertIn("muid_mly=<redacted>", row["set_cookie"])


# -- pure helpers -----------------------------------------------------------------

class TestDates(unittest.TestCase):
    def test_listing_time_reads_both_forms_with_fixed_orders(self):
        self.assertEqual(vgp.parse_listing_time("05/08/2026 20:35", "8/5/2026 8:35:00 PM"),
                         datetime(2026, 8, 5, 20, 35))
        self.assertEqual(vgp.parse_listing_time("12/01/2026 00:05", "1/12/2026 12:05:00 AM"),
                         datetime(2026, 1, 12, 0, 5))
        self.assertEqual(vgp.parse_listing_time("12/01/2026 12:05", "1/12/2026 12:05:00 PM"),
                         datetime(2026, 1, 12, 12, 5))

    def test_a_day_first_month_first_disagreement_is_refused_not_guessed(self):
        for text, title in (("05/08/2026 20:35", "5/8/2026 8:35:00 PM"),   # May 8 vs 5 Aug
                            ("05/08/2026 20:35", "8/5/2026 8:35:30 PM"),   # seconds
                            ("05/08/2026 20:35", "8/5/2026 8:35:00 AM"),   # meridiem
                            ("2026-08-05 20:35", "8/5/2026 8:35:00 PM"),   # unseen form
                            ("05/08/2026 20:35", "")):
            with self.subTest(text=text, title=title), self.assertRaises(ValueError):
                vgp.parse_listing_time(text, title)

    def test_iso_stamp_keeps_its_declared_offset_and_date(self):
        stamp = vgp.parse_iso_stamp("2026-05-24T03:30:00+07:00")
        self.assertEqual((stamp.date, stamp.utc, stamp.offset_minutes),
                         ("2026-05-24", "2026-05-23T20:30:00+00:00", 420))
        bare = vgp.parse_iso_stamp("2026-05-24T15:38:00")
        self.assertEqual((bare.date, bare.utc, bare.offset_minutes), ("2026-05-24", None, None))
        for junk in ("", "24/05/2026", "May 24, 2026", "2026-02-30T00:00:00+07:00"):
            self.assertIsNone(vgp.parse_iso_stamp(junk))

    def test_visible_header_stamp(self):
        self.assertEqual(vgp.parse_visible_stamp("September 09, 2026 9:33 AM GMT+7"),
                         ("2026-09-09T09:33", 420))
        self.assertEqual(vgp.parse_visible_stamp("May 24, 2026 12:05 AM GMT+5:30"),
                         ("2026-05-24T00:05", 330))
        for junk in ("Sept 09, 2026 9:33 AM GMT+7", "September 31, 2026 9:33 AM GMT+7",
                     "September 09, 2026 13:33 PM GMT+7", "09/09/2026 09:33"):
            self.assertIsNone(vgp.parse_visible_stamp(junk))


class TestIdentityAndText(unittest.TestCase):
    def test_article_ids_have_no_fixed_width_and_no_rewriting(self):
        self.assertEqual(vgp.article_id(URL[MAY[0]]), MAY[0])
        self.assertEqual(vgp.article_id(
            "https://en.baochinhphu.vn/viet-nam-invites-japan-to-attend-3rd-international-"
            "defense-expo-11126060215325338.htm"), "11126060215325338")
        self.assertEqual(vgp.article_id("https://en.baochinhphu.vn/some-story-11112345.htm"),
                         "11112345")
        for url in (URL[MAY[0]].replace("https", "http"),
                    URL[MAY[0]].replace("en.baochinhphu.vn", "baochinhphu.vn"),
                    URL[MAY[0]] + "?utm=x", URL[MAY[0]] + "#top",
                    vgp.LISTING, "https://en.baochinhphu.vn/politics.htm",
                    "https://en.baochinhphu.vn/timelinetags/defense/2.htm",
                    "https://en.baochinhphu.vn/Viet-Nam-111260523144123151.htm", "", None):
            self.assertIsNone(vgp.article_id(url), url)

    def test_squash_collapses_only_html_whitespace(self):
        self.assertEqual(vgp.squash(" a\r\n\t b\f "), "a b")
        self.assertEqual(vgp.squash("a b­c d"), "a b­c d")

    def test_content_hash_is_the_written_rule(self):
        blocks = [("p", "One./.")]
        expected = hashlib.sha256(json.dumps(
            {"blocks": [["p", "One./."]], "lead": "VGP - L", "rule": vgp.CONTENT_HASH_RULE,
             "title": "T"}, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            .encode("utf-8")).hexdigest()
        self.assertEqual(vgp.content_sha256("T", "VGP - L", blocks), expected)
        self.assertNotEqual(vgp.content_sha256("T", "VGP - L", [("h4", "One./.")]), expected)
        self.assertNotEqual(vgp.content_sha256("T ", "VGP - L", blocks), expected)


class TestRobotsParsing(unittest.TestCase):
    def test_the_captured_robots_file_allows_everything_after_its_bom(self):
        self.assertTrue(ROBOTS_BIN.startswith(b"\xef\xbb\xbf"))
        groups = vgp.parse_robots(ROBOTS_BIN.decode("utf-8"))
        self.assertEqual(groups, [{"agents": ["*"], "rules": [(True, "/")], "crawl_delay": None}])
        self.assertTrue(vgp.robots_allows(vgp.robots_rules(groups), vgp.TAG_PATH))

    def test_named_group_governs_and_longest_match_wins(self):
        groups = vgp.parse_robots(
            "User-agent: *\nDisallow: /\n\nUser-agent: ChinaMilWatch\n"
            "Disallow: /*.htm$\nAllow: /defense.html\nCrawl-delay: 4\n")
        rules = vgp.robots_rules(groups)
        self.assertTrue(vgp.robots_allows(rules, "/defense.html"))
        self.assertFalse(vgp.robots_allows(rules, "/a-story-111.htm"))
        self.assertTrue(vgp.robots_allows(rules, "/a-story-111.htm?x"))   # `$` anchors
        self.assertEqual(vgp.robots_crawl_delay(groups), 4.0)
        self.assertEqual(vgp.robots_crawl_delay(vgp.parse_robots(
            "User-agent: *\nCrawl-delay: soon\n")), float("inf"))


# -- discovery -------------------------------------------------------------------

class TestListing(unittest.TestCase):
    def test_the_captured_tag_page(self):
        items = vgp.parse_listing_page(LISTING_TEXT)
        self.assertEqual(len(items), 24)
        self.assertEqual((items[0].listed_date, items[-1].listed_date), ("2026-09-09", "2023-11-16"))
        self.assertEqual({i.category for i in items}, {"Politics"})
        self.assertEqual(len({i.title for i in items}), 24)
        widths = {len(i.item_id) for i in items}
        self.assertEqual(widths, {17, 18})

    def test_sidebar_widgets_never_become_references(self):
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        soup = BeautifulSoup(LISTING_TEXT, "html.parser")
        linked = {vgp.article_id(urljoin(vgp.HOST + "/", a["href"].strip()))
                  for a in soup.select("a[href]")} - {None}
        stream = {i.item_id for i in vgp.parse_listing_page(LISTING_TEXT)}
        widgets = linked - stream
        self.assertEqual(len(widgets), 5)
        # A window holding the widgets' own date (2026-10-05) selects nothing,
        # and the widest provable window selects only stream items.
        rig = Rig()
        self.assertEqual(rig.discover(date(2026, 10, 5), 0).status, st.OK_NO_PUBLICATIONS)
        wide = Rig().discover(date(2026, 10, 5), (date(2026, 10, 5) - date(2023, 11, 17)).days)
        chosen = {vgp.article_id(r.url) for r in wide.references}
        self.assertEqual(len(chosen), 23)
        self.assertFalse(chosen & widgets)

    def test_window_selection_uses_publisher_local_dates_and_proves_coverage(self):
        rig = Rig()
        result = rig.discover()
        self.assertEqual(result.status, st.OK)
        self.assertEqual([(vgp.article_id(r.url), r.hint_published_date) for r in result.references],
                         [(MAY[0], "2026-05-24"), (MAY[1], "2026-05-21")])
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING])
        report = rig.adapter.listing_report
        self.assertEqual((report["coverage"], report["items_listed"], report["selected"],
                          report["listed_after_window"], report["pages_read"]),
                         ("proven", 24, 2, 8, 1))
        self.assertEqual(len(report["listed"]), 24)
        self.assertEqual(report["listed"][0], ["111260909103625767", "2026-09-09T09:33"])
        self.assertEqual(report["listed"][-1][0], "111231116101259413")
        self.assertEqual(rig.adapter.robots_status, "read")
        self.assertEqual([e["role"] for e in rig.adapter.evidence], ["robots", "listing"])
        self.assertEqual(rig.adapter.evidence[1]["payload"], LISTING_BIN)

    def test_a_same_day_pair_is_two_references(self):
        result = Rig().discover(date(2026, 8, 5), 0)
        self.assertEqual([vgp.article_id(r.url) for r in result.references],
                         ["111260805182734508", "111260805144909723"])

    def test_current_quiet_window_is_success_without_publications(self):
        rig = Rig()
        result = rig.discover(date(2026, 10, 5), 6)
        self.assertEqual((result.status, result.references), (st.OK_NO_PUBLICATIONS, []))
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING])
        self.assertEqual(rig.adapter.listing_report["coverage"], "proven")

    def test_a_window_reaching_the_oldest_item_is_unprovable(self):
        for target, lookback in ((date(2023, 11, 22), 6), (date(2023, 11, 16), 0)):
            rig = Rig()
            result = rig.discover(target, lookback)
            self.assertEqual(result.status, st.LISTING_FAILURE)
            self.assertIn("coverage unprovable", result.error_detail)
            self.assertEqual(result.references, [])
            self.assertEqual(rig.adapter.listing_report["coverage"], "unprovable")
        # One day later the oldest item is outside the window and it is proven.
        self.assertEqual(Rig().discover(date(2023, 11, 23), 6).status, st.OK_NO_PUBLICATIONS)

    def test_script_pagination_is_never_requested(self):
        self.assertIn("timeline.url = '/timelinetags/{0}/{1}.htm'", LISTING_TEXT.replace(
            "timeline.url='", "timeline.url = '"))
        rig = Rig()
        rig.discover(date(2026, 10, 5), (date(2026, 10, 5) - date(2023, 11, 17)).days)
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING])

    def listing_refused(self, body, needle):
        rig = Rig(routes({vgp.LISTING: FakeResponse(body.encode("utf-8")
                                                    if isinstance(body, str) else body)}))
        result = rig.discover()
        self.assertEqual(result.status, st.LISTING_FAILURE, needle)
        self.assertIn(needle, result.error_detail)
        self.assertEqual(result.failed_endpoints, [vgp.LISTING])
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING])
        # The refused page is kept byte for byte as evidence of what was served.
        self.assertEqual([e["role"] for e in rig.adapter.evidence], ["robots", "listing"])
        self.assertEqual(rig.adapter.evidence[1]["payload"], rig.session.routes[vgp.LISTING].raw.body)
        return result

    def test_listing_shape_changes_are_refusals(self):
        a0, a1 = item_block("111260909103625767")
        b0, b1 = item_block("111260805182734508")
        first, second = LISTING_TEXT[a0:a1], LISTING_TEXT[b0:b1]
        stream_open = LISTING_TEXT.index('<div class="box-stream timeline_list"')
        stream_body = LISTING_TEXT.index(">", stream_open) + 1
        last_close = LISTING_TEXT.index("</div>", LISTING_TEXT.index(
            '<div class="box-stream-item" data-id="111231116101259413">'))
        cases = [
            (LISTING_TEXT[:a0] + second + first + LISTING_TEXT[b1:], "not newest-first"),
            (LISTING_TEXT[:a0] + first + first + LISTING_TEXT[a1:], "appears twice"),
            (edited(LISTING_TEXT, ('title="8/5/2026 8:35:00 PM">05/08/2026 20:35',
                                   'title="5/8/2026 8:35:00 PM">05/08/2026 20:35')), "disagree"),
            (edited(LISTING_TEXT, ('href="https://en.baochinhphu.vn/defense.html"',
                                   'href="https://en.baochinhphu.vn/politics.htm"')), "canonical"),
            (edited(LISTING_TEXT, ('id="hdCatUrl" value="defense"', 'id="hdCatUrl" value="navy"')),
             "declares tag"),
            (LISTING_TEXT[:LISTING_TEXT.rindex("</html>")], "truncation"),
            (edited(LISTING_TEXT, ('content="&#xA9; Viet Nam Government Portal"',
                                   'content="Viet Nam Government Portal"')), "frame"),
            (LISTING_TEXT[:a0] + '<div class="promo"><a href="/x-111260909103625767.htm">x</a></div>'
             + LISTING_TEXT[a0:], "unrecognised element"),
            (LISTING_TEXT[:stream_body] + LISTING_TEXT[last_close:].split("</div>", 1)[0]
             + LISTING_TEXT[last_close:], "no items"),
            (edited(LISTING_TEXT, ('data-id="111260909103625767" class="box-stream-link-title"',
                                   'data-id="111260909103625768" class="box-stream-link-title"')),
             "disagree"),
        ]
        for body, needle in cases:
            with self.subTest(needle=needle):
                self.listing_refused(body, needle)

    def test_repeated_titles_are_two_publications_never_one(self):
        derived = edited(
            LISTING_TEXT,
            ('title="Deputy Minister of National Defense hosts Commander of U.S. Indo- Pacific '
             'Command">Deputy Minister of National Defense hosts Commander of U.S. Indo- Pacific '
             'Command</a>',
             'title="Prime Minister receives Malaysian Minister of Defense">Prime Minister '
             'receives Malaysian Minister of Defense</a>'))
        rig = Rig(routes({vgp.LISTING: FakeResponse(derived.encode("utf-8"))}))
        result = rig.discover(date(2026, 8, 5), 0)
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len({r.url for r in result.references}), 2)


# -- robots and transport ----------------------------------------------------------

class TestRobotsCompliance(unittest.TestCase):
    def test_disallow_for_this_collector_stops_before_the_listing(self):
        for policy in ("User-agent: *\nDisallow: /\n",
                       "User-agent: chinamilwatch-shadowcollector\nDisallow: /defense.html\n",
                       "User-agent: *\nAllow: /\n\nUser-agent: ChinaMilWatch\nDisallow: /\n"):
            with self.subTest(policy=policy):
                rig = robots_rig(policy)
                result = rig.discover()
                self.assertEqual(result.status, st.AUTH_FAILURE)
                self.assertEqual(rig.urls, [vgp.ROBOTS])
                self.assertEqual(rig.adapter.robots_status, "read")

    def test_a_named_allow_overrides_a_star_disallow(self):
        rig = robots_rig("User-agent: *\nDisallow: /\n\nUser-agent: chinamilwatch\nAllow: /\n")
        self.assertEqual(rig.discover().status, st.OK)

    def test_robots_disallowing_articles_refuses_the_fetch_without_requesting(self):
        rig = robots_rig("User-agent: *\nAllow: /defense.html\nDisallow: /\n")
        refs = rig.discover().references
        self.assertEqual(len(refs), 2)
        result = rig.adapter.fetch(refs[0])
        self.assertEqual(result.status, st.AUTH_FAILURE)
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING])

    def test_a_published_crawl_delay_is_honoured_and_an_excessive_one_refused(self):
        rig = robots_rig("User-agent: *\nCrawl-delay: 7\nAllow: /\n")
        refs = rig.discover().references
        rig.adapter.fetch(refs[0])
        # robots.txt is read first; every later request waits the published delay.
        self.assertEqual(rig.clock.sleeps, [7.0, 7.0])
        for delay in ("500", "soon"):
            rig = robots_rig("User-agent: *\nCrawl-delay: %s\n" % delay)
            result = rig.discover()
            self.assertEqual(result.status, st.LISTING_FAILURE)
            self.assertIn("Crawl-delay", result.error_detail)
            self.assertEqual(rig.urls, [vgp.ROBOTS])

    def test_robots_states(self):
        cases = [
            (dict(policy=b"", status=404), st.OK, "absent"),
            (dict(policy=b"", status=403), st.AUTH_FAILURE, None),
            (dict(policy=b"oops", status=500), st.LISTING_FAILURE, None),
            (dict(policy="<html><body>Allow</body></html>", ctype="text/html"),
             st.UNEXPECTED_CONTENT_TYPE, None),
            (dict(policy="<html>User-agent: *</html>"), st.UNEXPECTED_CONTENT_TYPE, None),
            (dict(policy=MOD_CHALLENGE, ctype="text/html; charset=utf-8,gbk"),
             st.ACCESS_CHALLENGED, None),
            (dict(policy=b"", status=301, extra={"Location": "https://www.example.org/robots.txt"}),
             st.DISALLOWED_REDIRECT, None),
        ]
        for kw, status, robots_status in cases:
            with self.subTest(kw=kw):
                rig = robots_rig(**kw)
                self.assertEqual(rig.discover().status, status)
                self.assertEqual(rig.adapter.robots_status, robots_status)
                if status != st.OK:
                    self.assertEqual(rig.urls, [vgp.ROBOTS])


class TestTransport(unittest.TestCase):
    def test_every_request_is_polite_honest_and_bounded(self):
        rig = Rig()
        refs = rig.discover().references
        for r in refs:
            self.assertEqual(rig.adapter.fetch(r).status, st.OK)
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING, URL[MAY[0]], URL[MAY[1]]])
        for _, kwargs, _ in rig.session.calls:
            self.assertEqual(kwargs, {"timeout": vgp.REQUEST_TIMEOUT, "stream": True,
                                      "allow_redirects": False, "headers": vgp.REQUEST_HEADERS})
        self.assertEqual(rig.session.cookie_seen, [0, 0, 0, 0])
        starts = [t for _, _, t in rig.session.calls]
        self.assertTrue(all(b - a >= vgp.REQUEST_INTERVAL for a, b in zip(starts, starts[1:])))
        self.assertEqual(rig.clock.sleeps, [2.0, 2.0, 2.0])
        for response in rig.session.routes.values():
            self.assertTrue(all(flag is False for flag in response.raw.decode_flags))
        self.assertEqual([r["status"] for r in rig.adapter.request_log], [200] * 4)

    def test_spacing_runs_from_the_end_of_the_previous_request(self):
        rig = Rig(duration=5.0)
        rig.discover()
        self.assertEqual(rig.clock.sleeps, [2.0])
        starts = [t for _, _, t in rig.session.calls]
        self.assertEqual(starts[1] - starts[0], 7.0)

    def test_redirects_and_cookie_gates_are_refusals_never_followed(self):
        gate = FakeResponse(b"", 302, {"Location": vgp.LISTING,
                                       "Set-Cookie": "muid_mly=derived; Path=/"})
        rig = Rig(routes({vgp.LISTING: gate}))
        result = rig.discover()
        self.assertEqual(result.status, st.ACCESS_CHALLENGED)
        self.assertIn("cookie gate", result.error_detail)
        moved = FakeResponse(b"", 301, {"Location": "/defense-tag.html"})
        rig = Rig(routes({vgp.LISTING: moved}))
        self.assertEqual(rig.discover().status, st.DISALLOWED_REDIRECT)
        self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING])

    def test_compressed_oversized_and_undecodable_bodies_are_refused(self):
        cases = [
            (FakeResponse(LISTING_BIN, headers={"Content-Encoding": "gzip"}),
             st.UNEXPECTED_CONTENT_TYPE),
            (FakeResponse(LISTING_BIN, headers={"Content-Length": str(vgp.MAX_BODY_BYTES + 1)}),
             st.OVERSIZED_RESPONSE),
            (FakeResponse(b"x" * (vgp.MAX_BODY_BYTES + 1)), st.OVERSIZED_RESPONSE),
            (FakeResponse(LISTING_BIN, headers={"Content-Type": "application/json"}),
             st.UNEXPECTED_CONTENT_TYPE),
            (FakeResponse(LISTING_BIN, headers={"Content-Type": "text/html; charset=windows-1258"}),
             st.UNEXPECTED_CONTENT_TYPE),
            (FakeResponse(LISTING_BIN.replace(b"Politics", b"Politi\xe7s", 1)),
             st.UNEXPECTED_CONTENT_TYPE),
            (FakeResponse(LISTING_BIN, status=500), st.LISTING_FAILURE),
            (FakeResponse(LISTING_BIN, status=403), st.AUTH_FAILURE),
            (FakeResponse(CF_CHALLENGE, status=403), st.ACCESS_CHALLENGED),
            (FakeResponse(LISTING_BIN, fail=requests.exceptions.ReadTimeout()), st.TIMEOUT),
            (requests.exceptions.ConnectTimeout(), st.TIMEOUT),
            (requests.exceptions.ConnectionError(), st.LISTING_FAILURE),
        ]
        for response, status in cases:
            with self.subTest(status=status, response=response):
                rig = Rig(routes({vgp.LISTING: response}))
                result = rig.discover()
                self.assertEqual(result.status, status)
                self.assertEqual(result.references, [])
                self.assertEqual(rig.urls, [vgp.ROBOTS, vgp.LISTING])

    def test_article_failures_are_statuses_with_no_retry(self):
        cases = [
            (FakeResponse(b"gone", 404), st.FETCH_FAILURE, 404),
            (FakeResponse(b"no", 403), st.AUTH_FAILURE, 403),
            (FakeResponse(MOD_CHALLENGE), st.ACCESS_CHALLENGED, 200),
            (FakeResponse(b"", 302, {"Location": "https://en.baochinhphu.vn/"}),
             st.DISALLOWED_REDIRECT, 302),
            (requests.exceptions.ReadTimeout(), st.TIMEOUT, None),
            (requests.exceptions.ConnectionError(), st.FETCH_FAILURE, None),
        ]
        for response, status, http_status in cases:
            with self.subTest(status=status):
                rig = Rig(routes({URL[MAY[0]]: response}))
                refs = rig.discover().references
                result = rig.adapter.fetch(refs[0])
                self.assertEqual((result.status, result.http_status), (status, http_status))
                self.assertIsNone(result.body)
                self.assertEqual(rig.urls.count(URL[MAY[0]]), 1)

    def test_off_pattern_urls_are_never_requested(self):
        rig = Rig()
        for url in (vgp.LISTING, "https://example.org/a-111.htm", URL[MAY[0]] + "?x=1",
                    "https://en.baochinhphu.vn/timelinetags/defense/2.htm"):
            reference = CandidateReference(url=url, source_slug=SOURCE["slug"],
                                           discovered_via=vgp.LISTING)
            self.assertEqual(rig.adapter.fetch(reference).status, st.FETCH_FAILURE)
        self.assertEqual(rig.urls, [])

    def test_fetch_reads_robots_first_when_discovery_did_not(self):
        rig = Rig()
        result = rig.adapter.fetch(ref(MAY[0]))
        self.assertEqual(result.status, st.OK)
        self.assertEqual(rig.urls, [vgp.ROBOTS, URL[MAY[0]]])
        self.assertEqual(result.payload_sha256, hashlib.sha256(BIN[MAY[0]]).hexdigest())
        self.assertEqual(result.body.encode("utf-8"), BIN[MAY[0]])
        self.assertEqual((result.requested_url, result.final_url), (URL[MAY[0]], URL[MAY[0]]))

    def test_the_request_cap_is_a_hard_ceiling(self):
        rig = Rig(max_requests=3)
        refs = rig.discover().references
        self.assertEqual(rig.adapter.fetch(refs[0]).status, st.OK)
        refused = rig.adapter.fetch(refs[1])
        self.assertEqual(refused.status, st.FETCH_FAILURE)
        self.assertIn("request cap of 3", refused.error_detail)
        self.assertEqual(len(rig.urls), 3)
        rig = Rig(max_requests=1)
        result = rig.discover()
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertIn("request cap", result.error_detail)
        self.assertEqual(rig.urls, [vgp.ROBOTS])


# -- extraction ----------------------------------------------------------------

class TestExtraction(unittest.TestCase):
    def test_every_captured_article_extracts_cleanly(self):
        for item_id, url in URL.items():
            with self.subTest(item=item_id):
                hint = "from-listing" if item_id != SUMMARY else None
                result = extract(BIN[item_id], item_id, hint)
                self.assertEqual(result.status, st.OK)
                doc = result.documents[0]
                x = doc.extra
                self.assertEqual(x["source_identity"], "vgp-en:" + item_id)
                self.assertEqual((doc.url, x["canonical_url"]), (url, url))
                self.assertTrue(doc.text_original.startswith(x["lead_original"]))
                self.assertTrue(x["lead_original"].startswith("VGP "))
                self.assertTrue(doc.text_original.endswith("./."))
                self.assertTrue(x["published_at_original"].endswith("+07:00"))
                self.assertTrue(x["published_at_utc"].endswith("+00:00"))
                self.assertEqual(x["publisher_jsonld"], "en.baochinhphu.vn")
                self.assertEqual(x["byline"], x["byline_jsonld"])
                self.assertEqual(x["body_status"], "text")
                self.assertEqual(x["related_boxes_excluded"], 1)
                self.assertEqual(x["publication_kind"], "newsroom report")
                self.assertEqual(doc.language_tag, "en")
                expected = [] if item_id != SUMMARY else [
                    "listed_but_not_tagged: the page's tag list lacks /defense.html"]
                self.assertEqual(x["anomalies"], expected)

    def test_text_is_exactly_as_published(self):
        doc = extract(BIN[MAY[1]], MAY[1]).documents[0]
        self.assertIn(" ", doc.text_original)                # NBSP kept, not a space
        summary = extract(BIN[SUMMARY], SUMMARY, None).documents[0]
        self.assertTrue(summary.title_original.startswith("­"))   # soft hyphen kept
        self.assertTrue(summary.extra["lead_original"].startswith("VGP – "))
        chile = extract(BIN["111241112103823427"], "111241112103823427").documents[0]
        self.assertEqual(chile.title_original, "Viet Nam opens defense attaché office in Chile")
        for doc in (doc, summary, chile):
            raw = BIN[vgp.article_id(doc.url)].decode("utf-8")
            for _, line in doc.extra["blocks"]:
                if "&" not in line and "<" not in line:
                    self.assertIn(line.split(" ")[0], raw)

    def test_no_unicode_normalization_is_applied(self):
        # Derived: Vietnamese written decomposed (NFD) and precomposed (NFC).
        nfd = unicodedata.normalize("NFD", "Đại tướng Phan Văn Giang")
        nfc = unicodedata.normalize("NFC", "Bộ Quốc phòng")
        self.assertNotEqual(nfd, unicodedata.normalize("NFC", nfd))
        text = with_body(MAY[0], "<p>%s met %s./.</p>" % (nfd, nfc))
        doc = extract(text).documents[0]
        self.assertEqual(doc.extra["blocks"], [["p", "%s met %s./." % (nfd, nfc)]])

    def test_body_excludes_related_stories_comments_tags_and_image_text(self):
        doc = extract(BIN[MAY[0]]).documents[0]
        text = doc.text_original
        for excluded in ("Viet Nam, Russia boost defense cooperation",    # related box
                         "22/05/2026", "Giờ Đông Dương", "Sun May 24 2026",   # widget + CMS dates
                         "Ảnh 1", "Nhập chú thích ảnh",                       # alt text, placeholder
                         "Thuy Dung", "Politics", "Phan Van Giang\nRussia"):  # byline, chrome, tags
            self.assertNotIn(excluded, text)
        self.assertEqual(doc.extra["blocks"][0][0], "figcaption")
        self.assertTrue(doc.extra["blocks"][0][1].endswith("- Photo: VNA"))
        self.assertEqual(doc.extra["media_count"], 1)
        self.assertEqual(doc.extra["byline"], "Thuy Dung")
        self.assertEqual(doc.extra["category"], "Politics")
        self.assertIn(["/defense.html", "defense"], doc.extra["tags"])

    def test_block_labels_tables_quotes_and_unknown_types(self):
        inner = ('<p>VGP lead line./.</p><h3>Heading</h3><blockquote><p>Quoted</p></blockquote>'
                 '<ul><li>One <strong>bold</strong> item</li></ul>'
                 '<table><tr><th>Unit</th><td>Ha Noi<table><tr><td>inner</td></tr></table></td></tr>'
                 '<tr><td></td><td></td></tr></table>'
                 '<div type="VideoStream"><p>Video caption</p></div>'
                 '<p>Line<br/>break</p>')
        doc = extract(with_body(MAY[0], inner)).documents[0]
        self.assertEqual(doc.extra["blocks"], [
            ["p", "VGP lead line./."], ["h3", "Heading"], ["blockquote", "Quoted"],
            ["li", "One bold item"], ["tr", "Unit | Ha Noi inner"], ["p", "Video caption"],
            ["p", "Line"], ["p", "break"]])
        self.assertIn("unrecognised_block_type: VideoStream", doc.extra["anomalies"])

    def test_short_prose_is_accepted_on_structure_not_length(self):
        doc = extract(with_body(MAY[0], "<p>Talks held./.</p>")).documents[0]
        self.assertEqual((doc.extra["body_status"], doc.extra["blocks"]),
                         ("text", [["p", "Talks held./."]]))

    def test_an_image_only_body_is_kept_as_media_only_and_an_empty_one_refused(self):
        figure = ('<figure type="Photo"><div><img src="https://bcp.cdnchinhphu.vn/x.jpg"/></div>'
                  '<figcaption><p>Delegates pose - Photo: VGP</p></figcaption></figure>')
        doc = extract(with_body(MAY[0], figure)).documents[0]
        self.assertEqual(doc.extra["body_status"], "media_only")
        self.assertIn("media_only_body", doc.extra["anomalies"])
        self.assertEqual(doc.extra["blocks"], [["figcaption", "Delegates pose - Photo: VGP"]])
        for inner in ("", "<p><br/></p><!-- Sun May 24 2026 -->",
                      '<div type="RelatedNewsBox"><a href="/x-1.htm">Related</a></div>'):
            result = extract(with_body(MAY[0], inner))
            self.assertEqual(result.status, st.EXTRACTION_FAILURE)
            self.assertIn("no text and no media", result.error_detail)

    def test_publication_date_has_one_source_and_no_fallback(self):
        # The page writes `+` as `&#x2B;`; the attribute value is the decoded stamp.
        published = ('<meta property="article:published_time" '
                     'content="2026-05-24T15:38:00&#x2B;07:00" />')
        result = extract(page(MAY[0], (published, "")))
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertIn("article:published_time", result.error_detail)
        bare = extract(page(MAY[0], (published, published.replace("&#x2B;07:00", "")))).documents[0]
        self.assertEqual((bare.published_date, bare.extra["published_at_utc"]), ("2026-05-24", None))
        late = extract(page(MAY[0], (published, published.replace("15:38", "03:30")))).documents[0]
        self.assertEqual((late.published_date, late.extra["published_at_utc"]),
                         ("2026-05-24", "2026-05-23T20:30:00+00:00"))
        self.assertIn("visible_date_differs", " ".join(late.extra["anomalies"]))
        self.assertIn("jsonld_published_differs", " ".join(late.extra["anomalies"]))

    def test_cross_checks_are_recorded_not_substituted(self):
        doc = extract(page(MAY[0],
                           ('"datePublished": "2026-05-24T15:38:00+07:00"',
                            '"datePublished": "2026-05-23T15:38:00+07:00"'),
                           ("May 24, 2026 3:38 PM GMT+7", "May 25, 2026 3:38 PM GMT+7"),
                           ('"name": "Thuy Dung"', '"name": "Another Name"'))).documents[0]
        self.assertEqual(doc.published_date, "2026-05-24")
        found = " ".join(doc.extra["anomalies"])
        for name in ("jsonld_published_differs", "visible_date_differs", "byline_differs"):
            self.assertIn(name, found)
        self.assertEqual(doc.extra["byline"], "Thuy Dung")
        self.assertEqual(doc.extra["byline_jsonld"], "Another Name")
        hint = extract(BIN[MAY[0]], hint="2026-05-23").documents[0]
        self.assertIn("listing_date_differs: listing 2026-05-23, page 2026-05-24",
                      hint.extra["anomalies"])

    def test_modification_time_is_separate_and_not_a_content_change(self):
        original = extract(BIN[MAY[0]]).documents[0].extra
        touched = extract(page(MAY[0],
                               ('content="2026-05-24T15:41:00&#x2B;07:00"',
                                'content="2026-06-01T09:00:00&#x2B;07:00"'),
                               ('"dateModified": "2026-05-24T15:41:00+07:00"',
                                '"dateModified": "2026-06-01T09:00:00+07:00"'),
                               ('data-date="22/05/2026 09:06"', 'data-date="01/06/2026 09:06"'))
                          ).documents[0].extra
        self.assertEqual(touched["modified_at_original"], "2026-06-01T09:00:00+07:00")
        self.assertEqual(original["modified_at_original"], "2026-05-24T15:41:00+07:00")
        self.assertEqual(touched["published_at_original"], original["published_at_original"])
        self.assertEqual(touched["content_sha256"], original["content_sha256"])

    def test_title_lead_and_body_edits_are_new_content(self):
        base = extract(BIN[MAY[0]]).documents[0].extra["content_sha256"]
        for pair in (("second consultation session on maritime issues</h1>",
                      "second consultation session on maritime affairs</h1>"),
                     ("on May 22. \r\n                    </h2>",
                      "on May 23. \r\n                    </h2>"),
                     ("Both sides pledged", "The two sides pledged")):
            with self.subTest(pair=pair):
                doc = extract(page(MAY[0], pair)).documents[0]
                self.assertNotEqual(doc.extra["content_sha256"], base)

    def test_canonical_identity_conflicts(self):
        url = URL[MAY[0]]
        other = url.replace("111260523144123151", "111260522110959498")
        moved = url.replace("viet-nam-russia-hold", "vietnam-russia-hold")
        conflict = extract(page(MAY[0], ('<link rel="canonical" href="%s"' % url,
                                         '<link rel="canonical" href="%s"' % other)))
        self.assertEqual(conflict.status, st.EXTRACTION_FAILURE)
        self.assertIn("names a different publication", conflict.error_detail)
        slug = extract(page(MAY[0], ('<link rel="canonical" href="%s"' % url,
                                     '<link rel="canonical" href="%s"' % moved))).documents[0]
        self.assertEqual(slug.extra["canonical_url"], moved)
        self.assertEqual(slug.extra["source_identity"], "vgp-en:" + MAY[0])
        self.assertIn("canonical_url_differs", " ".join(slug.extra["anomalies"]))
        self.assertIn("og_url_differs", " ".join(slug.extra["anomalies"]))
        twice = page(MAY[0], ('<link rel="canonical" href="%s"' % url,
                              '<link rel="canonical" href="%s" /><link rel="canonical" href="%s"'
                              % (url, url)))
        self.assertIn("canonical link", extract(twice).error_detail)
        served = Rig().adapter.extract(capture(BIN[MAY[0]].decode("utf-8"), final_url=moved))
        self.assertIn("was served from", served.error_detail)

    def test_listing_title_is_metadata_not_identity(self):
        rig = Rig(routes({vgp.LISTING: FakeResponse(edited(
            LISTING_TEXT, ('title="Viet Nam, Russia hold second consultation session on maritime '
                           'issues">Viet Nam, Russia hold second consultation session on maritime '
                           'issues</a>',
                           'title="Viet Nam, Russia hold maritime consultation">Viet Nam, Russia '
                           'hold maritime consultation</a>')).encode("utf-8"))}))
        refs = rig.discover().references
        doc = rig.adapter.extract(rig.adapter.fetch(refs[0])).documents[0]
        self.assertEqual(doc.title_original,
                         "Viet Nam, Russia hold second consultation session on maritime issues")
        self.assertEqual(doc.extra["listing_title"], "Viet Nam, Russia hold maritime consultation")
        self.assertIn("listing_title_differs", " ".join(doc.extra["anomalies"]))

    def test_template_challenge_and_truncation_refusals(self):
        cases = [
            (BIN[MAY[0]].decode("utf-8")[:-200], "truncation"),
            (page(MAY[0], ('<meta property="og:site_name" content="en.baochinhphu.vn" />',
                           '<meta property="og:site_name" content="baochinhphu.vn" />')),
             "frame"),
            (page(MAY[0], ('<h1 class="detail-title" data-role="title">',
                           '<h1 class="detail-heading">')), "title"),
            (page(MAY[0], ('data-role="content"', 'data-role="body"')), "content block"),
            (CF_CHALLENGE.decode("utf-8"), "frame"),
        ]
        for text, needle in cases:
            with self.subTest(needle=needle):
                result = extract(text)
                self.assertEqual((result.status, result.documents), (st.EXTRACTION_FAILURE, []))
                self.assertIn(needle, result.error_detail)

    def test_a_framed_article_quoting_challenge_words_is_not_a_challenge(self):
        text = with_body(MAY[0], "<p>Checking your browser before accessing the portal: "
                                 "Just a moment, said the official./.</p>")
        self.assertFalse(vgp.looks_challenged({}, text))
        self.assertTrue(vgp.looks_challenged({"cf-mitigated": "challenge"}, text))
        self.assertEqual(extract(text).status, st.OK)
        self.assertFalse(vgp.looks_challenged({}, BIN[MAY[0]].decode("utf-8")))
        self.assertFalse(vgp.looks_challenged({}, LISTING_TEXT))

    def test_the_untagged_strategy_summary_is_never_discovered(self):
        self.assertNotIn(SUMMARY, {i.item_id for i in vgp.parse_listing_page(LISTING_TEXT)})
        doc = extract(BIN[SUMMARY], SUMMARY, None).documents[0]
        self.assertEqual((doc.extra["category"], doc.extra["tags"]), ("Policies", []))
        self.assertEqual(len(doc.extra["blocks"]), 60)
        self.assertEqual(doc.extra["modified_at_original"], "2026-08-06T16:32:00+07:00")
        self.assertEqual(doc.published_date, "2026-08-04")


# -- contract and isolation ------------------------------------------------------

class TestContractAndIsolation(unittest.TestCase):
    def test_adapter_contract_and_manifest_agree(self):
        self.assertTrue(issubclass(vgp.VNVgpAdapter, SourceAdapter))
        self.assertTrue(vgp.VNVgpAdapter.implemented)
        module, _, name = SOURCE["adapter"].partition(":")
        self.assertEqual((module, name), (vgp.__name__, "VNVgpAdapter"))
        self.assertEqual((SOURCE["slug"], SOURCE["authority_tier"], SOURCE["language_tags"]),
                         ("vn_vgp_defense_en", "B", ["en"]))
        self.assertEqual(SOURCE["discovery_endpoints"], [vgp.LISTING])
        desk = MANIFEST["desk"]
        self.assertEqual((desk["desk_id"], desk["jurisdiction_code"], desk["default_timezone"]),
                         ("vietnam", "VN", "Asia/Ho_Chi_Minh"))
        import re
        pattern = re.compile(SOURCE["article_url_patterns"][0])
        for url in URL.values():
            self.assertTrue(pattern.match(url))
            self.assertIsNotNone(vgp.article_id(url))

    def test_healthcheck_is_offline_and_truthful(self):
        rig = Rig()
        self.assertEqual(rig.adapter.healthcheck().status, st.OK)

        class Disabled(FakeSource):
            enabled = False
        self.assertEqual(Rig(source=Disabled).adapter.healthcheck().status, st.SKIPPED_DISABLED)
        self.assertEqual(rig.urls, [])

    def test_vietnam_is_invisible_to_production_discovery(self):
        self.assertFalse((REPO_ROOT / "desks" / "vietnam").exists())
        desks = load_all_desks()
        self.assertNotIn("vietnam", desks)
        self.assertNotIn(SOURCE["slug"], {s.slug for cfg in desks.values() for s in cfg.sources})

    def test_adapter_imports_nothing_from_production_storage(self):
        tree = ast.parse(Path(vgp.__file__).read_text(encoding="utf-8"))
        modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertFalse({m for m in modules if m and m.split(".")[0] in
                          ("storage", "pipeline", "config", "site", "analysis", "anthropic")})
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
                      and node.body and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant)}
        literals = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                    and isinstance(n.value, str) and id(n) not in docstrings]
        self.assertFalse(any("pla_watch.db" in s or "output/" in s for s in literals))


if __name__ == "__main__":
    unittest.main()
