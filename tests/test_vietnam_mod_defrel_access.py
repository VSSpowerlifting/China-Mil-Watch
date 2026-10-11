"""No-network tests of MOD robots/listing canary; no live permission or source use."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.probe_vietnam_mod_defrel_access import (
    BASE, LISTING, ROBOTS, MAX_LISTING, MAX_ROBOTS, SAMPLE_CAP,
    ProbeBlocked, get_once, inspect_listing, main, probe, validate_robots,
)

DETAIL = (BASE + "/en/detail?current=true&urile="
          "wcm%3Apath%3A%2Fmod%2Fsa-mod-en%2Fsa-en-news%2Fsa-en-news-rela%2F"
          "general-phan-van-giang-receives-japanese-ambassador-to-vietnam-2026")
ROBOTS_OK = b"User-agent: *\nAllow: /en/news/\nDisallow: /internal/\n"
HTML = ('<!doctype html><html><body><a href="' + DETAIL +
        '">A real publication</a><a href="' + DETAIL +
        '">Duplicate</a><a href="https://evil.example/en/detail?current=true">'
        'Evil</a><a href="/en/news/!ut/p/session">Navigation</a></body></html>').encode("utf-8")


class MODListingProbeTests(unittest.TestCase):
    def test_explicit_opt_in_required_before_any_network(self):
        with patch("scripts.probe_vietnam_mod_defrel_access.get_once") as req, \
             redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as exc:
                main([])
        self.assertEqual(exc.exception.code, 2)
        req.assert_not_called()

    def test_positive_robot_listing_is_not_permission_to_archive_or_publish(self):
        requested, pauses = [], []

        def local_request(url, cap):
            requested.append((url, cap))
            return ROBOTS_OK if url == ROBOTS else HTML

        result = probe(request=local_request, sleep=pauses.append)
        self.assertEqual(requested, [(ROBOTS, MAX_ROBOTS), (LISTING, MAX_LISTING)])
        self.assertEqual(pauses, [2.0])
        self.assertEqual(result["status"], "metadata-access-observed-not-source-approved")
        self.assertEqual(result["requests_attempted"], 2)
        self.assertTrue(result["robots_checked"])
        self.assertTrue(result["listing_checked"])
        self.assertEqual(result["recognized_stable_detail_id_count"], 1)
        self.assertEqual(len(result["example_identity_keys"]), 1)
        self.assertLessEqual(len(result["example_identity_keys"]), SAMPLE_CAP)
        for flag in ("source_rights_approved", "collection_enabled",
                     "shadow_state_created", "model_use_approved",
                     "production_admission_approved",
                     "evidence_of_current_week_coverage"):
            self.assertFalse(result[flag])
        self.assertEqual(result["article_bodies_fetched"], 0)
        self.assertNotIn("A real publication", str(result))
        self.assertNotIn("evil.example", str(result))

    def test_missing_robots_refusal_never_requests_listing(self):
        requested = []

        def denied(url, cap):
            requested.append(url)
            raise ProbeBlocked("http-status-403")
        result = probe(request=denied, sleep=lambda _: self.fail("slept"))
        self.assertEqual(requested, [ROBOTS])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocked_reason"], "http-status-403")
        self.assertEqual(result["requests_attempted"], 1)

    def test_robots_disallow_challenge_and_wrong_robots_are_fail_closed(self):
        for raw, reason in [
            (b"User-agent: *\nDisallow: /\n", "robots-disallow-listing"),
            (b"<html><body>robots goes to a challenge</body></html>",
             "robots-is-html"),
            (b"all access is allowed", "robots-missing-user-agent"),
        ]:
            with self.subTest(reason=reason):
                listing_called = []
                def request(url, cap):
                    listing_called.append(url)
                    return raw
                result = probe(request=request, sleep=lambda _: None)
                self.assertEqual(result["blocked_reason"], reason)
                self.assertEqual(listing_called, [ROBOTS])

    def test_listing_denial_refused_with_correct_robots(self):
        result = probe(
            request=lambda url, cap: ROBOTS_OK if url == ROBOTS
            else b"<html><body>verify you are human <a href='/a'>x</a></body></html>",
            sleep=lambda _: None,
        )
        self.assertEqual(result["blocked_reason"], "challenge-or-denial-page")
        self.assertFalse(result["listing_checked"])

    def test_widget_url_only_does_not_invent_article_coverage(self):
        page = b"<html><body><a href='/en/news/!ut/p/somestate'>A</a></body></html>"
        obs = inspect_listing(page)
        self.assertTrue(obs["zero_ids_may_mean_widget_navigation"])
        self.assertEqual(obs["recognized_stable_detail_id_count"], 0)

    def test_unverified_canonical_url_is_counted_not_collected(self):
        obs = inspect_listing(HTML)
        self.assertEqual(obs["recognized_stable_detail_id_count"], 1)
        self.assertEqual(obs["link_elements_seen"], 4)

    def test_transport_does_not_follow_redirects_or_persist_body(self):
        class Response:
            def __init__(self, final=ROBOTS, content=ROBOTS_OK, status=200,
                         content_type="text/plain"):
                self.final = final
                self.content = content
                self.status = status
                self.headers = {"Content-Type": content_type}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            def geturl(self):
                return self.final
            def read(self, max_bytes):
                return self.content[:max_bytes]

        class Opener:
            def __init__(self, result):
                self.result = result
            def open(self, req, timeout):
                self.request = req
                self.timeout = timeout
                return self.result

        self.assertEqual(get_once(ROBOTS, MAX_ROBOTS, opener=Opener(Response())),
                         ROBOTS_OK)
        for response, reason in [
            (Response(final=BASE + "/login"), "redirect-or-different-final-url"),
            (Response(content_type="text/html"), "unexpected-content-type"),
            (Response(content=b"x" * (MAX_ROBOTS + 1)), "body-too-large"),
            (Response(content=b""), "empty-response"),
        ]:
            with self.subTest(reason=reason), self.assertRaisesRegex(ProbeBlocked, reason):
                get_once(ROBOTS, MAX_ROBOTS, opener=Opener(response))
        with self.assertRaisesRegex(ProbeBlocked, "non-allowlisted"):
            get_once("https://evil.example/robots.txt", MAX_ROBOTS)

    def test_invalid_encoding_and_html_refusal(self):
        for f, raw, expected in [
            (validate_robots, b"\xff\xfe", "robots-not-utf8"),
            (inspect_listing, b"\xff", "listing-not-utf8"),
            (inspect_listing, b"<html>403 Access denied <a href='/'>a</a></html>",
             "challenge-or-denial-page"),
            (inspect_listing, b"not html", "not-a-normal-listing"),
        ]:
            with self.subTest(expected=expected), self.assertRaisesRegex(ProbeBlocked, expected):
                f(raw)


if __name__ == "__main__":
    unittest.main()
