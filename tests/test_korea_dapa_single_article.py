"""Synthetic-only single-item DAPA publisher URL/date canary; zero live HTTP."""
from __future__ import annotations

import hashlib
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from scripts import probe_korea_dapa_single_article as sut

ALLOW = b"User-agent: *\nAllow: /\n"
DENY = b"User-agent: *\nDisallow: /dapa/doc/selectDoc.do\n"
HTML = ("""<!DOCTYPE html><html lang="ko"><head><title>PRIVATE FAKE DAPA TITLE</title>
<script>const irrelevant="2026-09-18";</script></head><body>
<section><span>게시일</span><span>2026-09-18</span>
<div>PRIVATE TEXT MUST NOT BE LOGGED</div></section></body></html>""").encode("utf-8")


class SingleArticleIdentityCanary(unittest.TestCase):
    def test_explicit_flag_required_before_even_a_robots_get(self):
        with patch.object(sut, "get_once") as fetch, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                sut.main([])
        fetch.assert_not_called()

    def test_robots_first_one_known_article_and_no_content_publication(self):
        calls, sleeps = [], []
        def fake(url, limit):
            calls.append((url, limit))
            return ALLOW if url == sut.ROBOTS else HTML
        result = sut.observe(fetch=fake, sleep=sleeps.append)
        self.assertEqual(calls, [(sut.ROBOTS, sut.ROBOT_BYTES),
                                 (sut.ARTICLE, sut.ARTICLE_BYTES)])
        self.assertEqual(sleeps, [2.0])
        self.assertEqual(result["state"],
                         "DAPA_ONE_OFFICIAL_DOCUMENT_ROUTE_AND_DATE_MARKER_OBSERVED")
        self.assertEqual(result["provisional_docseq"], "59180")
        self.assertTrue(result["date_marker_matches_indexed_item"])
        self.assertEqual(result["document_sha256"], hashlib.sha256(HTML).hexdigest())
        for key in ("individual_dapa_issuer_verified",
                    "article_linked_to_live_listing_row", "source_content_licensed",
                    "article_text_captured", "collection_enabled",
                    "production_published", "title_or_publisher_text_saved"):
            self.assertFalse(result[key])
        self.assertEqual(result["file_or_attachment_requests"], 0)
        self.assertNotIn("PRIVATE", str(result))
        self.assertNotIn("FAKE DAPA TITLE", str(result))

    def test_robots_denial_and_network_unavailability_never_fetch_article(self):
        for raw, code in (
            (DENY, "dapa_article_robots_denies_document"),
            (b"no user agent", "dapa_article_robots_not_readable"),
            (b"<html>captcha</html>", "dapa_article_robots_not_readable"),
            (b"\xff", "dapa_article_robots_not_utf8"),
        ):
            called = []
            def fetch(url, limit):
                called.append(url)
                return raw
            result = sut.observe(fetch=fetch, sleep=lambda _: self.fail("slept"))
            with self.subTest(code=code):
                self.assertEqual(result["state"], "HOLD")
                self.assertEqual(result["reason_code"], code)
                self.assertEqual(called, [sut.ROBOTS])
        with patch.object(sut, "get_once",
                          side_effect=sut.Hold("dapa_article_publisher_unavailable")) as net:
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(sut.main(
                    ["--authorize-one-item-official-article-get"]), 2)
            net.assert_called_once_with(sut.ROBOTS, sut.ROBOT_BYTES)
            self.assertNotIn("PRIVATE", out.getvalue())
            self.assertFalse(json.loads(out.getvalue())["production_published"])

    def test_date_in_script_or_unlabeled_date_cannot_certify_release(self):
        for body in (
            b"<html><body><script>var date='2026-09-18';</script></body></html>",
            b"<html><body>2026-09-18 with no date label</body></html>",
            b"<html><body>\xea\xb2\x8c\xec\x8b\x9c\xec\x9d\xbc 2026-09-19</body></html>",
        ):
            with self.subTest(body=body):
                result = sut.observe(
                    fetch=lambda url, cap: ALLOW if url == sut.ROBOTS else body,
                    sleep=lambda _: None)
                self.assertEqual(result["reason_code"],
                                 "dapa_article_expected_date_not_proven")
                self.assertFalse(result["production_published"])

    def test_non_html_challenge_and_invalid_encoding_fail_closed(self):
        for body, code in (
            (b"PRIVATE PRESS ARTICLE", "dapa_article_challenge_or_non_html"),
            (b"<html>captcha content</html>", "dapa_article_challenge_or_non_html"),
            (b"\xff", "dapa_article_html_not_utf8"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(sut.Hold, code):
                sut.inspect_article(body)

    def test_only_two_exact_destinations_with_no_redirects(self):
        class Reply:
            def __init__(self, *, url=sut.ROBOTS, kind="text/plain",
                         raw=ALLOW, status=200):
                self.url, self.kind, self.raw, self.status = url, kind, raw, status
                self.headers = {"Content-Type": kind}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return self.url
            def read(self, n):
                return self.raw[:n]
        class Client:
            def __init__(self, response):
                self.response = response
            def open(self, request, timeout):
                return self.response
        self.assertEqual(sut.get_once(sut.ROBOTS, sut.ROBOT_BYTES,
                                      opener=Client(Reply())), ALLOW)
        for resp, reason in (
            (Reply(url="https://www.dapa.go.kr/other"), "http_status_or_redirect"),
            (Reply(status=403), "http_status_or_redirect"),
            (Reply(kind="text/html"), "unexpected_content_type"),
            (Reply(raw=b""), "empty_or_oversized_response"),
            (Reply(raw=b"x" * (sut.ROBOT_BYTES + 1)), "empty_or_oversized_response"),
        ):
            with self.subTest(reason=reason), self.assertRaisesRegex(sut.Hold, reason):
                sut.get_once(sut.ROBOTS, sut.ROBOT_BYTES, opener=Client(resp))
        with self.assertRaisesRegex(sut.Hold, "destination_not_allowlisted"):
            sut.get_once(sut.HOST + "/dapa/doc/selectDocList.do?bbsSeq=326",
                         sut.ARTICLE_BYTES)


if __name__ == "__main__":
    unittest.main()
