"""Synthetic no-network Korea DAPA publisher-access test matrix."""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from scripts.probe_korea_dapa_list_access import (
    AccessRefused, DAPA_LISTING, MAX_LISTING, MAX_ROBOTS, ROBOTS,
    inspect_listing, main, probe, request_once, robots_permit,
)

ROBOTS_ALLOW = b"User-agent: *\nAllow: /\nDisallow:\n"
ROBOTS_BLOCK = b"User-agent: *\nDisallow: /briefing/\n"
LISTING = ("""<!doctype html><html><body>
<a href="/briefing/pressReleaseView.do?newsId=156784618">Release A</a>
<a href="/briefing/pressReleaseView.do?newsId=156784618">Duplicate release A</a>
<a href="/briefing/pressReleaseView.do?newsId=156784625&repCode=B00008">Release B</a>
<a href="https://evil.example/briefing/pressReleaseView.do?newsId=156784619">Offsite</a>
<a href="/briefing/pressReleaseView.do?newsId=0">Bad identity</a>
</body></html>""").encode("utf-8")


class KoreaDAPACanaryTests(unittest.TestCase):
    def test_no_network_without_explicit_one_time_flag(self):
        with patch("scripts.probe_korea_dapa_list_access.request_once") as get, \
             redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main([])
        self.assertEqual(raised.exception.code, 2)
        get.assert_not_called()

    def test_one_robots_then_one_listing_metadata_only(self):
        requests, pauses = [], []
        def fake(url, cap):
            requests.append((url, cap))
            return ROBOTS_ALLOW if url == ROBOTS else LISTING
        out = probe(fetch=fake, sleep=pauses.append)
        self.assertEqual(requests, [(ROBOTS, MAX_ROBOTS),
                                    (DAPA_LISTING, MAX_LISTING)])
        self.assertEqual(pauses, [2.0])
        self.assertEqual(out["requests_attempted"], 2)
        self.assertEqual(out["state"], "metadata_access_observed_filter_not_verified")
        self.assertTrue(out["robots_checked"])
        self.assertTrue(out["listing_checked"])
        self.assertEqual(out["candidate_article_id_count"], 2)
        self.assertEqual(out["sample_candidate_identities"],
                         ["korea-dapa-policy:156784618",
                          "korea-dapa-policy:156784625"])
        for key in ("source_issuer_attribution_verified", "source_rights_approved",
                    "hwpx_pdf_license_approved", "collector_enabled",
                    "korea_desk_activated", "publisher_article_text_saved"):
            self.assertFalse(out[key])
        self.assertEqual(out["article_body_requests"], 0)
        self.assertEqual(out["attachment_requests"], 0)
        self.assertNotIn("Release A", str(out))
        self.assertNotIn("evil.example", str(out))

    def test_denied_or_unreadable_robots_refuse_any_listing(self):
        for data, marker in (
            (ROBOTS_BLOCK, "robots disallows"),
            (b"<html>Captcha</html>", "robots absent"),
            (b"not robots content", "robots absent"),
            (b"\xff\xff", "robots not UTF-8"),
        ):
            seen = []
            def fake(url, cap):
                seen.append(url)
                return data
            result = probe(fetch=fake, sleep=lambda _: self.fail("slept after denial"))
            with self.subTest(marker=marker):
                self.assertEqual(result["state"], "blocked")
                self.assertIn(marker, result["reason"])
                self.assertEqual(seen, [ROBOTS])
                self.assertEqual(result["requests_attempted"], 1)

    def test_no_bypass_if_publisher_robots_returns_error(self):
        seen = []
        def fake(url, cap):
            seen.append(url)
            raise AccessRefused("HTTP 403")
        result = probe(fetch=fake, sleep=lambda _: self.fail("slept"))
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["reason"], "HTTP 403")
        self.assertEqual(seen, [ROBOTS])

    def test_challenge_or_widget_only_is_not_publication_silence(self):
        challenge = b"<html><body>verify you are human <a href='/'>.</a></body></html>"
        bad = probe(fetch=lambda u, c: ROBOTS_ALLOW if u == ROBOTS else challenge,
                    sleep=lambda _: None)
        self.assertEqual(bad["reason"], "listing is an access challenge")
        self.assertFalse(bad["listing_checked"])
        widget = b"<html><body><a href='/briefing/!ut/p/nav'>View</a></body></html>"
        out = probe(fetch=lambda u, c: ROBOTS_ALLOW if u == ROBOTS else widget,
                    sleep=lambda _: None)
        self.assertEqual(out["candidate_article_id_count"], 0)
        self.assertTrue(out["zero_candidate_ids_does_not_prove_no_publications"])
        self.assertFalse(out["source_issuer_attribution_verified"])

    def test_wrong_origin_redirect_content_type_and_limits_block(self):
        class Response:
            def __init__(self, *, final=ROBOTS, kind="text/plain",
                         data=ROBOTS_ALLOW, code=200):
                self.final, self.status, self.data = final, code, data
                self.headers = {"Content-Type": kind}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, size):
                return self.data[:size]
            def geturl(self):
                return self.final
        class Opener:
            def __init__(self, resp):
                self.resp = resp
            def open(self, request, timeout):
                return self.resp
        self.assertEqual(request_once(ROBOTS, MAX_ROBOTS,
                                      opener=Opener(Response())), ROBOTS_ALLOW)
        for response, marker in (
            (Response(final="https://www.korea.kr/login"), "redirect"),
            (Response(kind="text/html"), "content type"),
            (Response(data=b"x"*(MAX_ROBOTS+1)), "oversized"),
            (Response(data=b""), "empty"),
        ):
            with self.subTest(marker=marker), self.assertRaisesRegex(AccessRefused, marker):
                request_once(ROBOTS, MAX_ROBOTS, opener=Opener(response))
        with self.assertRaisesRegex(AccessRefused, "nonallowlisted"):
            request_once("https://dapa.go.kr/robots.txt", MAX_ROBOTS)

    def test_malformed_markup_and_invalid_encoding_block(self):
        for response, err in (
            (b"\xff", "listing not UTF-8"),
            (b"text without html", "not a normal"),
            (b"<html>captcha <a href='/'>x</a></html>", "access challenge"),
        ):
            with self.subTest(err=err), self.assertRaisesRegex(AccessRefused, err):
                inspect_listing(response)


if __name__ == "__main__":
    unittest.main()
