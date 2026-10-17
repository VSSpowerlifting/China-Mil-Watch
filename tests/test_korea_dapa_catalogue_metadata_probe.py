"""No-network contracts for owner-only data.go.kr DAPA catalogue JSON probe."""
from __future__ import annotations

import hashlib
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from scripts import probe_korea_dapa_catalogue_metadata as probe
from tests.test_korea_dapa_official_catalogue import official

ALLOW = b"User-agent: *\nAllow: /\n"
DENY = b"User-agent: *\nDisallow: /catalog/\n"


def raw_json():
    return json.dumps(official(), ensure_ascii=False, sort_keys=True).encode("utf-8")


class DapaCatalogueLiveProbeContracts(unittest.TestCase):
    def test_requires_separate_host_approval_without_implicit_network(self):
        with patch.object(probe, "get_once") as fetch, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ex:
                probe.main([])
        self.assertEqual(ex.exception.code, 2)
        fetch.assert_not_called()

    def test_exact_two_authorized_gets_return_only_metadata_hash(self):
        seen, pauses = [], []
        raw = raw_json()
        def fetch(url, cap):
            seen.append((url, cap))
            return ALLOW if url == probe.ROBOTS else raw
        result = probe.observe(fetch=fetch, sleep=pauses.append)
        self.assertEqual(seen, [(probe.ROBOTS, probe.MAX_ROBOTS),
                                (probe.JSON_URL, probe.MAX_JSON)])
        self.assertEqual(pauses, [2.0])
        self.assertEqual(result["state"], "CATALOGUE_METADATA_ONLY_VERIFIED")
        self.assertTrue(result["robots_allowed"])
        self.assertTrue(result["json_retrieved"])
        self.assertTrue(result["catalogue_identity_verified"])
        self.assertEqual(result["catalogue_json_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["item_records_verified"], 0)
        self.assertEqual(result["article_requests"], 0)
        self.assertEqual(result["hwpx_requests"], 0)
        for k in ("publication_authorized", "production_written", "publisher_body_logged",
                  "declared_rows_independently_verified"):
            self.assertFalse(result[k])
        self.assertNotIn("Untrusted description", str(result))
        self.assertNotIn("encodingFormat", str(result))

    def test_disallowing_or_unreadable_robots_refuse_json_access(self):
        for body, reason in (
            (DENY, "catalogue_robots_disallows_json"),
            (b"<html>challenge</html>", "catalogue_robots_missing_or_challenged"),
            (b"not a robots file", "catalogue_robots_missing_or_challenged"),
            (b"\xff", "catalogue_robots_not_utf8"),
        ):
            seen = []
            def fetch(url, cap):
                seen.append(url)
                return body
            with self.subTest(reason=reason):
                result = probe.observe(fetch=fetch,
                                       sleep=lambda _: self.fail("slept after HOLD"))
                self.assertEqual(result["state"], "HOLD")
                self.assertEqual(result["reason_code"], reason)
                self.assertEqual(seen, [probe.ROBOTS])
                self.assertFalse(result["json_retrieved"])

    def test_bad_json_and_mismatched_issuer_or_version_fail_closed(self):
        for value, reason in (
            (b"this is not JSON PRIVATE PRESS TITLE", "catalogue_json_invalid"),
            (json.dumps(dict(official(), alternateName="private"), ensure_ascii=False).encode(),
             "catalogue_metadata_identity_hold"),
            (json.dumps(dict(official(), numberOfRecords=699, license="CC0"),
                        ensure_ascii=False).encode(), "catalogue_metadata_identity_hold"),
        ):
            calls = []
            def fetch(url, cap):
                calls.append(url)
                return ALLOW if url == probe.ROBOTS else value
            with self.subTest(reason=reason):
                result = probe.observe(fetch=fetch, sleep=lambda _: None)
                self.assertEqual(calls, [probe.ROBOTS, probe.JSON_URL])
                self.assertEqual(result["reason_code"], reason)
                self.assertEqual(result["state"], "HOLD")
                self.assertFalse(result["publication_authorized"])
                self.assertFalse(result["catalogue_identity_verified"])
                self.assertNotIn("PRIVATE PRESS TITLE", str(result))

    def test_fetch_limits_content_type_redirect_and_destination(self):
        class Reply:
            def __init__(self, *, dest=probe.ROBOTS, kind="text/plain",
                         data=ALLOW, status=200):
                self.dest, self.kind, self.data, self.status = dest, kind, data, status
                self.headers = {"Content-Type": kind}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return self.dest
            def read(self, limit):
                return self.data[:limit]
        class Opener:
            def __init__(self, reply):
                self.reply = reply
            def open(self, request, timeout):
                return self.reply
        self.assertEqual(probe.get_once(
            probe.ROBOTS, probe.MAX_ROBOTS, opener=Opener(Reply())), ALLOW)
        for reply, code in (
            (Reply(dest="https://www.data.go.kr/other"), "http_status_or_redirect"),
            (Reply(kind="text/html"), "robots_content_type"),
            (Reply(data=b""), "empty_or_oversized"),
            (Reply(data=b"x" * (probe.MAX_ROBOTS + 1)), "empty_or_oversized"),
            (Reply(status=503), "http_status_or_redirect"),
        ):
            with self.subTest(code=code), self.assertRaisesRegex(probe.ProbeHold, code):
                probe.get_once(probe.ROBOTS, probe.MAX_ROBOTS,
                               opener=Opener(reply))
        with self.assertRaisesRegex(probe.ProbeHold, "destination_not_allowlisted"):
            probe.get_once("https://www.data.go.kr/data/15118819/fileData.do",
                           probe.MAX_ROBOTS)
        with self.assertRaisesRegex(probe.ProbeHold, "json_content_type"):
            probe.get_once(probe.JSON_URL, probe.MAX_JSON,
                           opener=Opener(Reply(dest=probe.JSON_URL, kind="text/html",
                                               data=raw_json())))

    def test_stdout_and_credentials_never_include_metadata(self):
        # A sanitized failure remains a failure even with correct owner flag.
        # Critically: patching the transport MUST intercept the main() path;
        # no tests may silently reach a real government website.
        with patch.object(probe, "get_once", side_effect=probe.ProbeHold(
                "catalogue_publisher_unavailable")) as intercepted:
            out = io.StringIO()
            with redirect_stdout(out):
                status = probe.main(["--approve-one-time-data-go-kr-metadata"])
            intercepted.assert_called_once_with(probe.ROBOTS, probe.MAX_ROBOTS)
        self.assertEqual(status, 2)
        result = json.loads(out.getvalue())
        self.assertEqual(result["requests_attempted"], 1)
        self.assertEqual(result["reason_code"], "catalogue_publisher_unavailable")
        self.assertNotIn("www.dapa.go.kr", out.getvalue())
        self.assertFalse(result["publication_authorized"])


if __name__ == "__main__":
    unittest.main()
