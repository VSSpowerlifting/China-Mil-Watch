"""Offline checks for disposal-only journal DOM research. No publisher text."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import research_vietnam_journal_dom as probe


class Response:
    def __init__(self, url, payload, status=200, ctype="text/html", headers=None):
        self.url, self.status_code = url, status
        self.body = payload.encode("utf-8")
        self.headers = {"Content-Type": ctype}
        self.headers.update(headers or {})
        self.closed = False

    def iter_content(self, size):
        yield self.body

    def close(self):
        self.closed = True


class FakeCookies:
    clears = 0

    def clear(self):
        self.clears += 1


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.seen = []
        self.cookies = FakeCookies()
        self.headers = {}
        self.trust_env = True

    def get(self, url, *, allow_redirects, timeout, stream):
        assert not allow_redirects and timeout == 20 and stream
        assert self.headers["User-Agent"] == probe.USER_AGENT
        assert self.headers["Accept-Encoding"] == "identity"
        self.seen.append(url)
        if not self.responses:
            raise AssertionError("unexpected extra HTTP request")
        response = self.responses.pop(0)
        assert response.url == url, (response.url, url)
        return response


ART = ('<html><head><meta name="description" content="Example"></head>'
       '<body><div id="clock">October 8, 2026</div>'
       '<main><div class="journal-detail">'
       '<div class="published">Wednesday, September 30, 2026, 14:48 (GMT+7)</div>'
       '<h1>Military Technical Academy research</h1>'
       '<div class="content"><p>' + "text " * 200 + '</p><p>' + "more " * 100 + '</p>'
       '<p>By Major General, Prof., PhD TEST AUTHOR</p></div>'
       '</div></main></body></html>')


class JournalDOMTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.out = self.tmp / "research.json"
        stop = patch("scripts.research_vietnam_journal_dom.time.sleep")
        stop.start()
        self.addCleanup(stop.stop)

    def test_structure_is_only_layout_metadata(self):
        m = probe.structure(ART, "military technical academy")
        self.assertTrue(m["title_phrase_matches"])
        self.assertTrue(m["date_text_paths"])
        self.assertTrue(m["author_marker_paths"])
        self.assertTrue(m["nested_text_container_candidates"])
        self.assertFalse(m["article_extraction_verified"])
        raw = json.dumps(m)
        self.assertNotIn("TEST AUTHOR", raw)
        self.assertNotIn("Military Technical Academy research", raw)
        self.assertNotIn("Wednesday, September 30", raw)
        self.assertNotIn("text text text", raw)

    def test_policy_controls_each_article_request(self):
        first, second = probe.ARTICLES
        s = FakeSession([
            Response(probe.ROBOTS, "User-agent: *\nAllow: /en/theory-and-practice/\n"
                     "Disallow: /en/research-and-discussion/\n", ctype="text/plain"),
            Response(first[1], ART),
        ])
        report = probe.run(self.out, session=s)
        self.assertEqual(report["request_count"], 2)
        self.assertEqual(report["access"], "robots_read")
        self.assertTrue(report["articles"][0]["request_made"])
        self.assertFalse(report["articles"][1]["request_made"])
        self.assertFalse(report["articles"][1]["robots_allowed"])
        self.assertEqual(len(s.seen), 2)
        self.assertEqual(s.cookies.clears, 2)

    def test_robots_unavailable_never_fetches_articles(self):
        s = FakeSession([Response(probe.ROBOTS, "", status=503, ctype="text/plain")])
        report = probe.run(self.out, session=s)
        self.assertEqual(report["request_count"], 1)
        self.assertEqual(report["access"], "robots_inaccessible")
        self.assertEqual(report["articles"], [])
        self.assertEqual(len(s.seen), 1)

    def test_two_permitted_articles_never_exceed_three_requests(self):
        s = FakeSession([
            Response(probe.ROBOTS, "User-agent: *\nAllow: /\n", ctype="text/plain"),
            Response(probe.ARTICLES[0][1], ART),
            Response(probe.ARTICLES[1][1], ART)
        ])
        report = probe.run(self.out, session=s)
        self.assertEqual(report["request_count"], 3)
        self.assertEqual(len(report["articles"]), 2)
        self.assertTrue(all(x["request_made"] for x in report["articles"]))
        self.assertFalse(report["source_bytes_retained"])
        self.assertFalse(report["production_modified"])
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn("TEST AUTHOR", text)
        self.assertNotIn("text text", text)

    def test_refuse_existing_output_or_output_in_repository(self):
        self.out.write_text("existing")
        with self.assertRaisesRegex(probe.ProbeError, "output must be new"):
            probe.run(self.out, session=FakeSession([]))
        with self.assertRaisesRegex(probe.ProbeError, "output must be new"):
            probe.run(probe.ROOT / "test.json", session=FakeSession([]))

    def test_http_404_response_is_closed_and_not_parsed(self):
        s = FakeSession([
            Response(probe.ROBOTS, "User-agent: *\nAllow: /\n", ctype="text/plain"),
            Response(probe.ARTICLES[0][1], "<html>error</html>", status=404),
            Response(probe.ARTICLES[1][1], ART),
        ])
        result = probe.run(self.out, session=s)
        self.assertEqual(result["request_count"], 3)
        self.assertTrue(s.responses == [])
        self.assertFalse("structure" in result["articles"][0])
        self.assertTrue("structure" in result["articles"][1])

    def test_malformed_robots_html_fails_closed(self):
        s = FakeSession([Response(probe.ROBOTS, "<html>script</html>", ctype="text/html")])
        result = probe.run(self.out, session=s)
        self.assertEqual(result["access"], "robots_inaccessible")
        self.assertEqual(result["request_count"], 1)

    def test_challenge_does_not_yield_dom_diagnostics(self):
        s = FakeSession([
            Response(probe.ROBOTS, "User-agent: *\nAllow: /\n", ctype="text/plain"),
            Response(probe.ARTICLES[0][1], "<html><body>Just a moment</body></html>",
                     headers={"Cf-Mitigated": "challenge"}),
            Response(probe.ARTICLES[1][1], ART),
        ])
        report = probe.run(self.out, session=s)
        self.assertNotIn("structure", report["articles"][0])
        self.assertIn("structure", report["articles"][1])


if __name__ == "__main__":
    unittest.main()
