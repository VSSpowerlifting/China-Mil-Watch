"""Offline tests for the fixed-route Coast Guard feasibility probe."""
import hashlib
import unittest

from scripts.probe_japan_coast_guard_access import (
    HOST, MAX_PDF, MAX_HTML, MAX_ROBOTS, ROUTES, RefuseRedirect, examine,
)


def record(data, kind="text/html"):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return {"status": 200, "result": "body_returned", "mime": kind,
            "_raw": data, "byte_count": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


class CoastGuardAccessSafetyTests(unittest.TestCase):
    def simulate(self, *, robots="User-agent: *\nAllow: /\n", fail_route=None):
        requested = []

        def fetch(url, limit, *, opener):
            requested.append((url, limit))
            if url.endswith("/robots.txt"):
                return record(robots, "text/plain")
            if url == fail_route:
                return {"status": 403, "result": "http_not_served"}
            for _, path, marker, kind in ROUTES:
                if url.endswith(path):
                    if kind == "pdf":
                        return record(b"%PDF-1.7" + b"A" * 550, "application/pdf")
                    body = "<html><main><h1>" + marker + "</h1><p>" + (
                        "This is test text from the government page. " * 20
                    ) + "</p></main></html>"
                    return record(body)
            raise AssertionError("unexpected network call")

        return requested, fetch

    def test_bounded_success_with_valid_policy(self):
        requests, fetch = self.simulate()
        data = examine(opener=object(), request=fetch, sleep=lambda _: None)
        self.assertEqual(len(requests), 1 + len(ROUTES))
        self.assertEqual(data["robots"]["verdict"], "readable")
        self.assertEqual([r["verdict"] for r in data["routes"]],
                         ["readable_original_html"] * 4 +
                         ["pdf_signature_observed"])
        self.assertEqual(requests[0][1], MAX_ROBOTS)
        self.assertEqual(requests[-1][1], MAX_PDF)
        self.assertEqual(requests[1][1], MAX_HTML)
        self.assertNotIn("_raw", str(data))
        self.assertNotIn("This is test text", str(data))

    def test_disallow_prevents_any_document_access(self):
        calls, fetch = self.simulate(robots="User-agent: *\nDisallow: /\n")
        results = examine(opener=object(), request=fetch, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual([x["verdict"] for x in results["routes"]],
                         ["blocked_by_robots"] * len(ROUTES))

    def test_robots_403_fails_closed(self):
        calls = []
        def get(url, limit, *, opener):
            calls.append(url)
            return {"status": 403, "result": "http_not_served"}
        output = examine(opener=object(), request=get, sleep=lambda _: None)
        self.assertEqual(len(calls), 1)
        self.assertEqual(output["robots"]["verdict"],
                         "unreadable_no_further_requests")
        self.assertTrue(all(x["verdict"] == "blocked_policy_unavailable"
                            for x in output["routes"]))

    def test_html_challenge_does_not_count_as_source(self):
        target = "https://" + HOST + ROUTES[1][1]
        calls, fetch = self.simulate(fail_route=target)
        results = examine(opener=object(), request=fetch, sleep=lambda _: None)
        self.assertEqual(results["routes"][1]["verdict"], "not_accessible")
        self.assertEqual(sum(u == target for u, _ in calls), 1)

    def test_redirect_is_not_followed(self):
        handler = RefuseRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "move",
                                                   {}, "https://new.example/"))

    def test_fixed_allowlist_is_one_official_host(self):
        self.assertEqual(len(ROUTES), 5)
        self.assertEqual(HOST, "www.kaiho.mlit.go.jp")
        self.assertEqual(sum(1 for r in ROUTES if r[3] == "pdf"), 1)
        self.assertTrue(all(path.startswith("/e/topics_archive/")
                            for _, path, _, _ in ROUTES))


if __name__ == "__main__":
    unittest.main()
