"""Network-free tests for the one-time journal Actions probe."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import probe_vietnam_journal as probe


class FakeResponse:
    def __init__(self, url, text, status=200, content_type="text/html",
                 location=None, challenge=False):
        self.url = url
        self.status_code = status
        self.data = text.encode("utf-8")
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        if challenge:
            self.headers["Cf-Mitigated"] = "challenge"
        self.closed = False

    def iter_content(self, size):
        yield self.data

    def close(self):
        self.closed = True


class Cookies:
    def __init__(self):
        self.clear_count = 0

    def clear(self):
        self.clear_count += 1


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.seen = []
        self.headers = {}
        self.trust_env = True
        self.cookies = Cookies()

    def get(self, url, *, timeout, allow_redirects, stream):
        assert timeout == probe.TIMEOUT and not allow_redirects and stream
        assert self.headers["User-Agent"] == probe.USER_AGENT
        assert self.headers["Accept-Encoding"] == "identity"
        self.seen.append(url)
        if not self.responses:
            raise AssertionError("probe made an unbudgeted request: " + url)
        response = self.responses.pop(0)
        assert response.url == url, (response.url, url)
        return response


def robots(host, policy="User-agent: *\nAllow: /\n", status=200, ctype="text/plain"):
    return FakeResponse("https://" + host + "/robots.txt", policy,
                        status=status, content_type=ctype)


def listing(url, article):
    return FakeResponse(url, '<html><body>'
                        '<a href="' + article + '">Synthetic listing headline</a>'
                        '</body></html>')


def article(url, stamp, title="Synthetic article headline"):
    return FakeResponse(url, '<html><head><meta property="og:title" content="' +
                        title + '"></head><body><h1>' + title + '</h1>'
                        '<time>' + stamp + '</time>'
                        '<div class="article-content"><p>Temporary test text; '
                        'do not retain publisher text.</p></div></body></html>')


def happy_responses():
    d, m = probe.HOSTS
    return [
        robots(d[1]), listing(d[2], d[3]),
        article(d[3], "Wednesday, September 30, 2026, 14:48 (GMT+7)"),
        robots(m[1]), listing(m[2], m[3]),
        article(m[3], "9/30/2026 2:48:13 PM"),
    ]


class BoundedJournalProbe(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.tmp = Path(t.name)
        self.out = self.tmp / "probe.json"
        self.sleeper = patch("scripts.probe_vietnam_journal.time.sleep")
        self.sleeper.start()
        self.addCleanup(self.sleeper.stop)

    def run_with(self, responses):
        session = FakeSession(responses)
        result = probe.run(self.out, session=session)
        return result, session

    def test_two_independent_robots_readings_and_exact_six_gets(self):
        result, session = self.run_with(happy_responses())
        self.assertEqual(result["requests_made"], 6)
        self.assertEqual(len(session.seen), 6)
        self.assertEqual([row["gate"] for row in result["hosts"]],
                         ["access_ok_structure_needs_human_review"] * 2)
        self.assertEqual(session.cookies.clear_count, 6)
        self.assertFalse(session.trust_env)
        self.assertTrue(result["cross_host_parity"]["same_article_identity"])
        self.assertTrue(result["cross_host_parity"]["same_canonical_url"])
        self.assertTrue(result["cross_host_parity"]["same_title_hash"])
        self.assertEqual(result["cross_host_parity"]["date_overlap"], ["2026-09-30"])

    def test_only_metadata_and_hashes_are_retained(self):
        result, _ = self.run_with(happy_responses())
        text = self.out.read_text(encoding="utf-8")
        self.assertNotIn("Temporary test text", text)
        self.assertNotIn("Synthetic article headline", text)
        self.assertNotIn("<html>", text)
        self.assertFalse(result["source_article_bytes_retained"])
        self.assertEqual(result["rights_to_republish"], "not_established")
        self.assertFalse(result["production_written"])
        self.assertFalse(result["shadow_state_written"])
        self.assertEqual(result["hosts"][0]["article"]["candidate_dates"], ["2026-09-30"])
        self.assertFalse(result["hosts"][0]["article"]["body_extraction_verified"])

    def test_desktop_disallow_never_falls_back_to_mobile(self):
        m = probe.HOSTS[1]
        responses = [robots("tapchiqptd.vn", "User-agent: *\nDisallow: /en/\n"),
                     robots(m[1]), listing(m[2], m[3]),
                     article(m[3], "9/30/2026 2:48:13 PM")]
        result, session = self.run_with(responses)
        self.assertEqual(result["requests_made"], 4)
        self.assertFalse(result["hosts"][0]["listing"]["request_made"])
        self.assertFalse(result["hosts"][0]["article"]["request_made"])
        self.assertEqual(result["hosts"][0]["gate"], "robots_disallows_target")
        self.assertEqual(result["hosts"][1]["gate"],
                         "access_ok_structure_needs_human_review")
        self.assertTrue(all("tapchiqptd.vn/en/" not in x or x.startswith("https://m.")
                            for x in session.seen if not x.endswith("/robots.txt")))

    def test_missing_and_html_robots_policy_refuse_both_hosts(self):
        d, m = probe.HOSTS
        result, session = self.run_with([
            robots(d[1], "<html>script shell</html>", ctype="text/html"),
            robots(m[1], "", status=404)])
        self.assertEqual(result["requests_made"], 2)
        self.assertEqual(len(session.seen), 2)
        self.assertEqual(result["hosts"][0]["gate"], "robots_policy_unverified")
        self.assertEqual(result["hosts"][1]["gate"], "robots_policy_unverified")

    def test_inaccessible_listing_prevents_article_fetch(self):
        d, m = probe.HOSTS
        responses = [
            robots(d[1]), FakeResponse(d[2], "", status=403),
            robots(m[1]), listing(m[2], m[3]),
            article(m[3], "9/30/2026 2:48:13 PM"),
        ]
        result, session = self.run_with(responses)
        self.assertEqual(result["requests_made"], 5)
        self.assertEqual(result["hosts"][0]["gate"], "listing_inaccessible")
        self.assertFalse(result["hosts"][0]["article"]["request_made"])
        self.assertTrue(result["hosts"][1]["article"]["request_made"])
        self.assertEqual(len(session.seen), 5)

    def test_challenge_or_redirect_stops_downstream_requests(self):
        d, m = probe.HOSTS
        result, _ = self.run_with([
            robots(d[1]),
            FakeResponse(d[2], "<html>Just a moment</html>", challenge=True),
            robots(m[1], "", status=500)])
        self.assertEqual(result["requests_made"], 3)
        self.assertEqual(result["hosts"][0]["listing"]["verdict"], "challenge_refused")
        self.assertEqual(result["hosts"][0]["gate"], "listing_inaccessible")
        self.assertFalse(result["hosts"][0]["article"]["request_made"])

    def test_unlisted_sample_article_never_fetched(self):
        d, m = probe.HOSTS
        blank = '<html><body><a href="https://tapchiqptd.vn/en/news/other/26937.html">Other</a></body></html>'
        result, _ = self.run_with([
            robots(d[1]), FakeResponse(d[2], blank),
            robots(m[1]), FakeResponse(m[2], blank)])
        self.assertEqual(result["requests_made"], 4)
        self.assertTrue(all(row["gate"] == "article_not_in_observed_listing"
                            for row in result["hosts"]))
        self.assertTrue(all(not row["article"]["request_made"] for row in result["hosts"]))

    def test_six_request_budget_is_enforced_even_if_called_again(self):
        d = probe.HOSTS[0]
        session = FakeSession([])
        allowance = {"requests": 6}
        with self.assertRaisesRegex(probe.ProbeRefused, "cap exceeded"):
            probe.response_probe(session, d[2], allowance, {})
        self.assertEqual(session.seen, [])

    def test_cannot_write_to_repo_or_overwrite_prior_evidence(self):
        with self.assertRaisesRegex(probe.ProbeRefused, "outside the repository"):
            probe.run(probe.ROOT / "probe.json", session=FakeSession([]))
        self.out.write_text("immutable", encoding="utf-8")
        with self.assertRaisesRegex(probe.ProbeRefused, "already exists"):
            probe.run(self.out, session=FakeSession([]))
        self.assertEqual(self.out.read_text(), "immutable")

    def test_synthetic_page_parsing_exposes_no_source_text(self):
        raw = '<html><head><meta property="og:title" content="Title A"></head>' \
              '<body><time>Wednesday, September 30, 2026, 14:48 (GMT+7)</time>' \
              '<div class="article-content"><p>Text X</p></div></body></html>'
        report = probe.summary(raw, article=True)
        self.assertEqual(report["title_hash"], hashlib.sha256(b"Title A").hexdigest())
        self.assertEqual(report["candidate_dates"], ["2026-09-30"])
        self.assertEqual(report["body_selector_diagnostics"][".article-content"]["max_text_length"], 6)
        self.assertFalse(report["body_extraction_verified"])


if __name__ == "__main__":
    unittest.main()
