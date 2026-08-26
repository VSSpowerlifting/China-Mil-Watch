"""
Japan MOD shadow adapter — access reality, isolation, and honest counters.

The access picture this adapter was written against, measured 2026-08-26 with
one honest request per endpoint:

    XML feeds  -> 200, and 304 on If-None-Match
    PDF bodies -> 200
    HTML pages -> 403, Cf-Mitigated: challenge

Every test here exists because getting one of those wrong would put a false
number in front of a reader: a challenged path counted as an outage, an
untitled record stored as a document, a recurring ministry title collapsed into
one row, or a scanned PDF stored as an article that says nothing.

Nothing here touches the network. The feed fixture is the real
`https://www.mod.go.jp/j/rss/news.xml`, trimmed to six real items.
"""
import io
import sys
import time
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection import status as st                        # noqa: E402
from core.collection.contract import CollectionWindow           # noqa: E402
from processing import pdf_text                                 # noqa: E402
from scraper.sources import jp_mod                              # noqa: E402
from tests.test_pdf_text import build_pdf                       # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "jp_mod"
FEED = (FIXTURES / "news.xml").read_text(encoding="utf-8")

PDF_URL = "https://www.mod.go.jp/j/press/news/2026/08/25a.pdf"
HTML_URL = "https://www.mod.go.jp/j/press/news/2026/08/26b.html"

CHALLENGE_BODY = ('<!DOCTYPE html><html lang="en-US"><head>'
                  '<title>Just a moment...</title></head><body></body></html>')


class Response:
    def __init__(self, status_code=200, text="", content=b"", headers=None,
                 url=None):
        self.status_code = status_code
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.url = url


def challenge():
    return Response(403, text=CHALLENGE_BODY,
                    headers={"Cf-Mitigated": "challenge",
                             "Content-Type": "text/html; charset=UTF-8"})


class Session:
    """Records every request so tests can assert what was *not* sent."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, dict(headers or {})))
        route = self.routes.get(url)
        if route is None:
            return Response(404, headers={"Content-Type": "text/html"})
        return route(headers or {}) if callable(route) else route


def feed_ok(_headers=None):
    return Response(200, text=FEED,
                    headers={"Content-Type": "application/xml",
                             "ETag": '"feed-1"'})


#: `build_pdf` serialises object streams as latin-1, so synthetic fixtures stay
#: ASCII. That is a limit of the test helper, not of the extractor: the live
#: 2026-08-25 Joint Committee PDF extracts 3,975 characters of Japanese cleanly
#: (status `ok`). What the adapter itself must be shown to do is pass extracted
#: text through unchanged, which `test_japanese_text_is_preserved_as_published`
#: checks directly against the extractor boundary.
def pdf_ok(body="Japan-US Joint Committee agreement notice", etag='"pdf-1"'):
    data = build_pdf([body])
    return Response(200, content=data,
                    headers={"Content-Type": "application/pdf", "ETag": etag,
                             "Last-Modified": "Tue, 25 Aug 2026 06:08:25 GMT"})


def adapter(routes, **kw):
    class Source:
        slug = "jp_mod_releases"
    return jp_mod.JPModAdapter(Source(), session=Session(routes),
                               sleep=lambda _s: None, **kw)


WINDOW = CollectionWindow(target_date=date(2026, 8, 26), lookback_days=30)


# --------------------------------------------------------------------- robots

class TestRobotsIsObeyed(unittest.TestCase):

    def test_the_live_rules_are_parsed(self):
        rules = jp_mod.parse_robots(
            "User-agent: *\nDisallow: /a/\nDisallow: /sp/j/\n")
        self.assertEqual(rules, ["/a/", "/sp/j/"])

    def test_rules_for_other_agents_do_not_apply(self):
        rules = jp_mod.parse_robots(
            "User-agent: Bingbot\nDisallow: /\n\nUser-agent: *\nDisallow: /a/\n")
        self.assertEqual(rules, ["/a/"])

    def test_comments_and_blank_lines_are_ignored(self):
        rules = jp_mod.parse_robots(
            "# comment\nUser-agent: *\n\nDisallow: /a/  # trailing\n")
        self.assertEqual(rules, ["/a/"])

    def test_a_disallowed_path_raises(self):
        a = adapter({})
        with self.assertRaises(jp_mod.RobotsDisallowed):
            a.assert_robots_allows("User-agent: *\nDisallow: /j/\n", PDF_URL)

    def test_the_paths_this_adapter_uses_are_allowed_by_the_live_file(self):
        a = adapter({})
        live = "User-agent: *\nDisallow: /a/\nDisallow: /sp/j/\n"
        for url in jp_mod.FEEDS + (PDF_URL, HTML_URL):
            with self.subTest(url=url):
                a.assert_robots_allows(live, url)   # must not raise

    def test_an_empty_robots_file_falls_back_to_the_measured_rules(self):
        a = adapter({})
        with self.assertRaises(jp_mod.RobotsDisallowed):
            a.assert_robots_allows("", "https://www.mod.go.jp/a/secret.pdf")


# ------------------------------------------------------------------ discovery

class TestDiscovery(unittest.TestCase):

    def routes(self):
        return {jp_mod.FEEDS[0]: feed_ok, jp_mod.FEEDS[1]: feed_ok}

    def test_the_real_feed_yields_its_items(self):
        a = adapter(self.routes())
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(result.references), 6)

    def test_links_are_canonicalised_to_absolute_https(self):
        a = adapter(self.routes())
        for ref in a.discover(WINDOW).references:
            with self.subTest(url=ref.url):
                self.assertTrue(ref.url.startswith("https://www.mod.go.jp/"))

    def test_the_two_feeds_are_merged_without_duplicating_a_url(self):
        a = adapter(self.routes())
        refs = a.discover(WINDOW).references
        self.assertEqual(len(refs), len({r.url for r in refs}))

    def test_titles_are_captured_from_the_feed(self):
        a = adapter(self.routes())
        a.discover(WINDOW)
        self.assertEqual(a._titles[PDF_URL], "日米合同委員会合意について")

    def test_publication_dates_are_parsed(self):
        a = adapter(self.routes())
        refs = {r.url: r.hint_published_date for r in a.discover(WINDOW).references}
        self.assertEqual(refs[PDF_URL], "2026-08-25")

    def test_a_malformed_feed_is_a_listing_failure_not_an_empty_day(self):
        a = adapter({jp_mod.FEEDS[0]: Response(200, text="<rss><broken>",
                                               headers={"Content-Type": "application/xml"}),
                     jp_mod.FEEDS[1]: Response(200, text="<rss><broken>",
                                               headers={"Content-Type": "application/xml"})})
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.LISTING_FAILURE)
        self.assertTrue(result.failed_endpoints)

    def test_one_working_feed_still_discovers(self):
        a = adapter({jp_mod.FEEDS[0]: feed_ok, jp_mod.FEEDS[1]: Response(500)})
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.OK)
        self.assertEqual(result.failed_endpoints, [jp_mod.FEEDS[1]])

    def test_a_304_feed_is_not_a_failure(self):
        a = adapter({jp_mod.FEEDS[0]: feed_ok, jp_mod.FEEDS[1]: Response(304)})
        result = a.discover(WINDOW)
        self.assertEqual(result.status, st.OK)
        self.assertEqual(result.failed_endpoints, [])

    def test_conditional_headers_are_sent_when_validators_are_known(self):
        a = adapter(self.routes(),
                    validators={jp_mod.FEEDS[0]: {"etag": '"feed-1"'}})
        a.discover(WINDOW)
        sent = dict(a._session.calls[0][1])
        self.assertEqual(sent.get("If-None-Match"), '"feed-1"')

    def test_the_honest_user_agent_is_sent_on_every_request(self):
        a = adapter(self.routes())
        a.discover(WINDOW)
        for url, headers in a._session.calls:
            with self.subTest(url=url):
                self.assertEqual(headers["User-Agent"], jp_mod.USER_AGENT)

    def test_the_user_agent_names_the_project_and_is_not_a_browser(self):
        ua = jp_mod.USER_AGENT
        self.assertIn("ChinaMilWatch", ua)
        self.assertIn("http", ua)
        for browser in ("Mozilla", "Chrome", "Safari", "AppleWebKit", "Gecko"):
            with self.subTest(browser=browser):
                self.assertNotIn(browser, ua)


# ------------------------------------------------------ the challenge contract

class TestChallengedPathsAreRecordedNotFought(unittest.TestCase):

    def test_html_is_not_even_requested(self):
        a = adapter({jp_mod.FEEDS[0]: feed_ok, jp_mod.FEEDS[1]: feed_ok})
        refs = a.discover(WINDOW).references
        a._session.calls.clear()
        html = [r for r in refs if r.url == HTML_URL][0]
        capture = a.fetch(html)
        self.assertEqual(capture.status, st.ACCESS_CHALLENGED)
        self.assertEqual(a._session.calls, [],
                         "a known-challenged path must cost no request")

    def test_a_challenge_on_a_pdf_is_recorded_as_a_challenge(self):
        a = adapter({PDF_URL: challenge()})
        a._titles[PDF_URL] = "t"
        capture = a.fetch(_ref(PDF_URL))
        self.assertEqual(capture.status, st.ACCESS_CHALLENGED)

    def test_a_challenge_is_never_retried(self):
        a = adapter({PDF_URL: challenge()})
        a.fetch(_ref(PDF_URL))
        self.assertEqual(len(a._session.calls), 1)

    def test_a_challenge_served_with_200_is_still_a_challenge(self):
        served = Response(200, text=CHALLENGE_BODY,
                          headers={"Content-Type": "text/html; charset=UTF-8"})
        a = adapter({PDF_URL: served})
        self.assertEqual(a.fetch(_ref(PDF_URL)).status, st.ACCESS_CHALLENGED)

    def test_a_challenge_is_not_an_extraction_failure(self):
        a = adapter({PDF_URL: challenge()})
        capture = a.fetch(_ref(PDF_URL))
        self.assertEqual(a.extract(capture).status, st.ACCESS_CHALLENGED)

    def test_challenged_is_a_failure_status_but_not_a_success(self):
        self.assertIn(st.ACCESS_CHALLENGED, st.FAILURE_STATUSES)
        self.assertNotIn(st.ACCESS_CHALLENGED, st.SUCCESS_STATUSES)

    def test_challenged_urls_are_counted(self):
        a = adapter({jp_mod.FEEDS[0]: feed_ok, jp_mod.FEEDS[1]: feed_ok})
        for ref in a.discover(WINDOW).references:
            a.fetch(ref)
        self.assertEqual(len(a.challenged), 5)      # 5 html of 6 fixture items

    def test_a_500_is_retried_but_a_403_is_not(self):
        seen = {"n": 0}

        def flaky(_h):
            seen["n"] += 1
            return Response(500) if seen["n"] == 1 else pdf_ok()

        a = adapter({PDF_URL: flaky})
        a._titles[PDF_URL] = "t"
        capture = a.fetch(_ref(PDF_URL))
        self.assertEqual(capture.status, st.OK)
        self.assertEqual(seen["n"], 2)


def _ref(url):
    from core.collection.contract import CandidateReference
    return CandidateReference(url=url, source_slug="jp_mod_releases",
                              hint_published_date="2026-08-25")


# -------------------------------------------------------------- pdf extraction

class TestPdfExtraction(unittest.TestCase):

    def _extract(self, response, title="日米合同委員会合意について"):
        a = adapter({PDF_URL: response})
        a._titles[PDF_URL] = title
        return a, a.extract(a.fetch(_ref(PDF_URL)))

    def test_a_text_bearing_pdf_becomes_one_document(self):
        _, result = self._extract(pdf_ok())
        self.assertEqual(result.status, st.OK)
        self.assertEqual(len(result.documents), 1)

    def test_the_document_carries_the_feed_title(self):
        _, result = self._extract(pdf_ok())
        self.assertEqual(result.documents[0].title_original,
                         "日米合同委員会合意について")

    def test_japanese_text_is_preserved_as_published(self):
        """
        The adapter must hand extracted text through byte-for-byte: no
        transliteration, no normalisation, no truncation. Stubbed at the
        extractor boundary because the synthetic PDF helper is ASCII-only.
        """
        japanese = "防衛省 統合幕僚監部 発表 令和8年8月25日"
        a = adapter({PDF_URL: pdf_ok()})
        a._titles[PDF_URL] = "日米合同委員会合意について"
        capture = a.fetch(_ref(PDF_URL))

        real = pdf_text.extract_pdf_text
        pdf_text.extract_pdf_text = lambda data, **kw: pdf_text.PdfExtraction(
            status=pdf_text.OK, text=japanese)
        try:
            result = a.extract(capture)
        finally:
            pdf_text.extract_pdf_text = real

        self.assertEqual(result.documents[0].text_original, japanese)
        self.assertEqual(result.documents[0].title_original,
                         "日米合同委員会合意について")

    def test_the_language_tag_follows_the_path(self):
        _, result = self._extract(pdf_ok())
        self.assertEqual(result.documents[0].language_tag, "ja")

    def test_a_scanned_pdf_is_never_stored_as_an_empty_document(self):
        blank = build_pdf([""])
        a = adapter({PDF_URL: Response(200, content=blank,
                                       headers={"Content-Type": "application/pdf"})})
        a._titles[PDF_URL] = "t"
        result = a.extract(a.fetch(_ref(PDF_URL)))
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(result.documents, [])
        self.assertIn(pdf_text.NO_TEXT_LAYER, result.error_detail)

    def test_no_ocr_is_attempted(self):
        import processing.pdf_text as m
        source = Path(m.__file__).read_text(encoding="utf-8").lower()
        for word in ("ocr", "tesseract", "pytesseract"):
            with self.subTest(word=word):
                self.assertNotIn("import " + word, source)

    def test_an_untitled_document_is_refused_rather_than_stored(self):
        a = adapter({PDF_URL: pdf_ok()})
        result = a.extract(a.fetch(_ref(PDF_URL)))       # no title registered
        self.assertEqual(result.status, st.EXTRACTION_FAILURE)
        self.assertEqual(result.documents, [])

    def test_an_oversized_pdf_is_refused_unread(self):
        big = b"%PDF-" + b"0" * (jp_mod.MAX_BODY_BYTES + 1)
        a = adapter({PDF_URL: Response(200, content=big,
                                       headers={"Content-Type": "application/pdf"})})
        capture = a.fetch(_ref(PDF_URL))
        self.assertEqual(capture.status, st.OVERSIZED_RESPONSE)

    def test_html_served_where_a_pdf_was_expected_is_flagged(self):
        a = adapter({PDF_URL: Response(200, content=b"<html>nope</html>",
                                       headers={"Content-Type": "text/html"},
                                       text="<html>nope</html>")})
        capture = a.fetch(_ref(PDF_URL))
        self.assertIn(capture.status,
                      (st.UNEXPECTED_CONTENT_TYPE, st.ACCESS_CHALLENGED))

    def test_a_304_pdf_is_a_duplicate_not_a_failure(self):
        a = adapter({PDF_URL: Response(304)})
        capture = a.fetch(_ref(PDF_URL))
        self.assertEqual(capture.status, st.OK_ALL_DUPLICATES)


# ------------------------------------------------------------- deduplication

class TestDeduplication(unittest.TestCase):

    def test_identity_is_the_canonical_url(self):
        self.assertEqual(
            jp_mod.canonical_url("/j/press/news/2026/08/25a.pdf"),
            jp_mod.canonical_url(
                "https://www.mod.go.jp/j/press/news/2026/08/25a.pdf?utm=x#frag"))

    def test_an_offsite_link_has_no_identity(self):
        self.assertIsNone(jp_mod.canonical_url("https://example.com/x.pdf"))

    def test_recurring_titles_are_kept_as_separate_records(self):
        """
        Ministry titles repeat legitimately. 「日米合同委員会合意について」 is
        published again every time the Joint Committee agrees anything, and
        title-level deduplication would collapse a year of distinct agreements
        into one row.
        """
        a = adapter({})
        same = "日米合同委員会合意について"
        for path in ("/j/press/news/2026/08/25a.pdf",
                     "/j/press/news/2026/07/14a.pdf",
                     "/j/press/news/2026/06/02a.pdf"):
            a._titles[jp_mod.canonical_url(path)] = same
        self.assertEqual(len(a._titles), 3,
                         "distinct URLs with one recurring title must stay "
                         "three records")

    def test_the_adapter_source_contains_no_title_level_dedup(self):
        source = Path(jp_mod.__file__).read_text(encoding="utf-8")
        lowered = source.lower()
        for smell in ("seen_titles", "by_title", "dedup_title", "title in seen"):
            with self.subTest(smell=smell):
                self.assertNotIn(smell, lowered)


# ------------------------------------------------------------------- isolation

class TestIsolation(unittest.TestCase):

    def test_the_adapter_never_names_the_production_database(self):
        source = Path(jp_mod.__file__).read_text(encoding="utf-8")
        for forbidden in ("pla_watch.db", "DB_PATH", "OUTPUT_DIR", "output/"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_adapter_imports_nothing_from_the_production_pipeline(self):
        source = Path(jp_mod.__file__).read_text(encoding="utf-8")
        for forbidden in ("import pipeline", "from pipeline",
                          "import storage", "from storage",
                          "from config import"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_adapter_makes_no_analysis_call(self):
        source = Path(jp_mod.__file__).read_text(encoding="utf-8").lower()
        for forbidden in ("anthropic", "openai", "claude", "completion"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_no_keyword_editorial_filter_is_applied(self):
        """
        Collection policy: collect every qualifying official record. A keyword
        filter inside the collector would silently sample the ministry's own
        record while the counters claimed completeness.
        """
        source = Path(jp_mod.__file__).read_text(encoding="utf-8")
        for forbidden in ("RELEVANCE_KEYWORDS", "KEYWORDS", "relevance_score"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


# ------------------------------------------------------------------- politeness

class TestRequestDiscipline(unittest.TestCase):

    def test_requests_are_spaced(self):
        slept = []
        class Source:
            slug = "jp_mod_releases"
        a = jp_mod.JPModAdapter(
            Source(),
            session=Session({jp_mod.FEEDS[0]: feed_ok, jp_mod.FEEDS[1]: feed_ok}),
            sleep=slept.append)
        a.discover(WINDOW)
        self.assertTrue(slept, "discovery must pause between feed requests")
        self.assertTrue(all(s >= 1.0 for s in slept))

    def test_the_retry_budget_is_small(self):
        self.assertLessEqual(jp_mod.MAX_RETRIES, 2)

    def test_there_is_no_parallelism_in_the_adapter(self):
        source = Path(jp_mod.__file__).read_text(encoding="utf-8")
        for forbidden in ("ThreadPool", "concurrent.futures", "asyncio",
                          "multiprocessing"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()


class TestTheAdapterIsUsableWithoutAnInjectedSession(unittest.TestCase):
    """
    Every other test in this file injects a stub session, so none of them would
    notice `self._session` being None. The first live dry run did: the transport
    raised AttributeError inside its own try/except and the run reported
    `listing_failure`, which reads as "the ministry's feed is down" rather than
    "this collector was never wired up".
    """

    def test_a_default_session_is_created(self):
        class Source:
            slug = "jp_mod_releases"
        a = jp_mod.JPModAdapter(Source())
        self.assertIsNotNone(a._session)
        self.assertTrue(hasattr(a._session, "get"))

    def test_an_injected_session_still_wins(self):
        class Source:
            slug = "jp_mod_releases"
        stub = Session({})
        a = jp_mod.JPModAdapter(Source(), session=stub)
        self.assertIs(a._session, stub)
