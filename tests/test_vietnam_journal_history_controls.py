"""Synthetic-only tests for a disposable journal historical-navigation probe."""
import json
import unittest

from scripts.research_vietnam_journal_history_controls import (
    HOST, KEYWORD, ROBOTS, URLS,
    ProbeRefused, inspect_controls, run_probe,
)


def page(*, link=None, paging="", original_text="SYNTHETIC PUBLISHER PROSE"):
    link = link or (
        "https://tapchiqptd.vn/en/theory-and-practice/"
        "synthetic-article/27001.html"
    )
    return (
        "<html><body><header>Site clock: October 8, 2026</header>"
        '<div class="item"><a href="' + link + '">A fabricated title</a>'
        '<span>09/30/2026</span><p>' + original_text + "</p></div>"
        + paging + "</body></html>"
    )


class FakeResponse:
    def __init__(self, url, content, status=200, mime="text/html", location=None):
        self.url, self.status_code = url, status
        self.body = content.encode("utf-8")
        self.headers = {"Content-Type": mime, "Content-Encoding": "identity"}
        if location is not None:
            self.headers["Location"] = location
        self.closed = False

    def iter_content(self, size):
        yield self.body

    def close(self):
        self.closed = True


class Cookies:
    def clear(self):
        pass


class FakeSession:
    def __init__(self, overrides=None):
        self.trust_env = True
        self.headers = {}
        self.cookies = Cookies()
        self.requested = []
        self.overrides = overrides or {}

    def get(self, url, *, stream, allow_redirects, timeout):
        self.requested.append(url)
        if url in self.overrides:
            return self.overrides[url]
        if url == ROBOTS:
            return FakeResponse(url, "User-agent: *\nAllow: /\n", mime="text/plain")
        if url == KEYWORD:
            paging = ("<div class='pager'><span>[1]</span>"
                      "<a href='javascript:__doPostBack(&quot;pager&quot;,&quot;2&quot;)'>2</a>"
                      "<a href='?cul=en&amp;key=Defence&amp;page=3'>3</a></div>")
            return FakeResponse(url, page(paging=paging))
        return FakeResponse(url, page())


class NavigationProbeTests(unittest.TestCase):
    def test_structural_paging_not_promoted_to_archive_proof(self):
        html = page(paging=(
            '<form action="/Keywords/Keyword.aspx" method="POST">'
            '<input type="hidden" name="__VIEWSTATE" value="secret-do-not-record">'
            '<a onclick="__doPostBack()">2</a>'
            '<a href="?page=3">3</a></form>'))
        signals = inspect_controls(html, KEYWORD)
        self.assertTrue(signals["paging_controls_observed"])
        self.assertFalse(signals["historical_enumeration_proven"])
        self.assertEqual(signals["forms"][0]["method"], "POST")
        self.assertTrue(signals["forms"][0]["has_viewstate"])
        self.assertIn("javascript_postback", [a["kind"] for a in signals["paging_like_controls"]])
        self.assertNotIn("secret-do-not-record", json.dumps(signals))
        self.assertNotIn("page=3", json.dumps(signals))

    def test_no_pager_is_not_historical_completeness(self):
        result = inspect_controls(page(), URLS[1])
        self.assertFalse(result["paging_controls_observed"])
        self.assertFalse(result["pagination_route_verified"])
        self.assertFalse(result["historical_enumeration_proven"])

    def test_one_shot_six_request_proof_is_metadata_only(self):
        session = FakeSession()
        report = run_probe(session, sleeper=lambda _: None)
        self.assertEqual(len(session.requested), 6)
        self.assertEqual(session.requested, list(URLS))
        self.assertEqual(report["request_count"], 6)
        self.assertEqual(report["union_visible_id_count"], 1)
        self.assertEqual(len(report["category_pages"]), 4)
        self.assertTrue(report["keyword"]["controls"]["paging_controls_observed"])
        self.assertFalse(report["article_text_retained"])
        self.assertFalse(report["article_ids_retained"])
        self.assertFalse(report["historical_completeness_proven"])
        self.assertFalse(report["source_enabled"])
        serialized = json.dumps(report)
        self.assertNotIn("SYNTHETIC PUBLISHER PROSE", serialized)
        self.assertNotIn("A fabricated title", serialized)
        self.assertNotIn("vndj-en:27001", serialized)
        self.assertEqual(report["category_pages"][0]["earliest_observed_date_hint"], "2026-09-30")
        self.assertTrue(all(x["link_identity_list_retained"] is False for x in report["category_pages"]))

    def test_robots_disallowed_fails_before_page_get(self):
        session = FakeSession({ROBOTS: FakeResponse(ROBOTS,
            "User-agent: *\nDisallow: /en/\n", mime="text/plain")})
        with self.assertRaisesRegex(ProbeRefused, "robots disallow"):
            run_probe(session, sleeper=lambda _: None)
        self.assertEqual(session.requested, [ROBOTS])

    def test_unexpected_redirect_refused_without_following(self):
        session = FakeSession({KEYWORD: FakeResponse(KEYWORD, page(), location="/elsewhere")})
        with self.assertRaisesRegex(ProbeRefused, "redirect"):
            run_probe(session, sleeper=lambda _: None)
        self.assertEqual(len(session.requested), 6)

    def test_challenge_or_invalid_robots_stop(self):
        session = FakeSession({ROBOTS: FakeResponse(ROBOTS, "<html>Challenge</html>", mime="text/plain")})
        with self.assertRaisesRegex(ProbeRefused, "robots response"):
            run_probe(session, sleeper=lambda _: None)
        self.assertEqual(session.requested, [ROBOTS])

    def test_no_browser_upload_or_html_write_paths(self):
        import inspect
        from scripts import research_vietnam_journal_history_controls
        source = inspect.getsource(research_vietnam_journal_history_controls)
        for forbidden in ("sqlite3", "output/", "screenshot", "proxy=", "selenium",
                          "allow_redirects=True", "from playwright", "iter_pages("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
