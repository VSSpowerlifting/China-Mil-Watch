"""Offline tests: Japan alternatives probe must not become a collector."""
import hashlib
import unittest

from scripts.probe_japan_alternative_official_routes import (
    HOSTS, MAX_HTML_BYTES, MAX_ROBOTS_BYTES, NoRedirect, run,
)


def payload(raw, mime="text/html"):
    body = raw.encode("utf-8")
    return {
        "http_status": 200,
        "reason": "retrieved",
        "content_type": mime,
        "byte_count": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "_payload": body,
    }


class RouteProbeTests(unittest.TestCase):
    def fake(self, robots="User-agent: *\\nAllow: /\\n", blocked_urls=(),
             wrong_marker=False):
        called = []
        def request(url, *, limit, opener):
            called.append((url, limit))
            if url.endswith("/robots.txt"):
                return payload(robots, "text/plain")
            if url in blocked_urls:
                return {"http_status": 403, "reason": "http_refusal_or_redirect"}
            title = "unrelated headline" if wrong_marker else next(
                marker for family in HOSTS for _name, route, marker in family["routes"]
                if route == url)
            return payload("<html><body><main><h1>" + title + "</h1>"
                           + "<p>" + "A" * 320 + "</p></main></body></html>")
        return called, request

    def test_bounded_positive_probe_never_leaks_bodies(self):
        called, request = self.fake()
        result = run(opener=object(), fetch=request, sleep=lambda x: None)
        self.assertEqual(len(result["hosts"]), 2)
        self.assertEqual(len(called), 6)
        self.assertEqual(sum(url.endswith("/robots.txt") for url, _ in called), 2)
        self.assertTrue(all(limit == MAX_ROBOTS_BYTES if url.endswith("/robots.txt")
                            else limit == MAX_HTML_BYTES for url, limit in called))
        for item in result["hosts"]:
            self.assertEqual(item["robots"]["verdict"], "policy_readable")
            self.assertEqual(len(item["routes"]), 2)
            self.assertTrue(all(r["verdict"] == "html_with_expected_content"
                                for r in item["routes"]))
        self.assertNotIn("_payload", str(result))
        self.assertNotIn("A" * 100, str(result))
        self.assertIn("noncollecting", result["kind"])

    def test_robots_disallow_stops_all_article_requests(self):
        called, request = self.fake(robots="User-agent: *\\nDisallow: /\\n")
        result = run(opener=object(), fetch=request, sleep=lambda x: None)
        self.assertEqual(len(called), 2)
        self.assertTrue(all(
            route["verdict"] == "not_requested_robots_disallow"
            for host in result["hosts"] for route in host["routes"]))

    def test_missing_unreadable_robots_fails_closed(self):
        called = []
        def request(url, *, limit, opener):
            called.append(url)
            return {"http_status": 403, "reason": "http_refusal_or_redirect"}
        report = run(opener=object(), fetch=request, sleep=lambda x: None)
        self.assertEqual(len(called), 2)
        for host in report["hosts"]:
            self.assertEqual(host["robots"]["verdict"], "policy_unavailable")
            self.assertTrue(all(x["verdict"] == "not_requested_no_policy"
                                for x in host["routes"]))

    def test_html_robots_response_does_not_permit_other_requests(self):
        called = []
        def request(url, *, limit, opener):
            called.append(url)
            return payload("<html>blocked</html>", "text/html")
        out = run(opener=object(), fetch=request, sleep=lambda x: None)
        self.assertEqual(len(called), 2)
        self.assertTrue(all(x["robots"]["verdict"] == "policy_not_plaintext"
                            for x in out["hosts"]))

    def test_transport_403_not_retried(self):
        first_url = HOSTS[0]["routes"][0][1]
        called, request = self.fake(blocked_urls={first_url})
        out = run(opener=object(), fetch=request, sleep=lambda x: None)
        self.assertEqual(len(called), 6)
        self.assertEqual(sum(u == first_url for u, _ in called), 1)
        self.assertEqual(out["hosts"][0]["routes"][0]["verdict"], "not_readable")
        self.assertEqual(out["hosts"][0]["routes"][0]["http_status"], 403)

    def test_unrecognized_body_does_not_count_as_success(self):
        called, request = self.fake(wrong_marker=True)
        out = run(opener=object(), fetch=request, sleep=lambda x: None)
        self.assertEqual(len(called), 6)
        self.assertTrue(all(
            x["verdict"] == "html_but_content_not_confirmed"
            for host in out["hosts"] for x in host["routes"]))

    def test_redirect_handler_refuses_redirect(self):
        handler = NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Redirect",
                                                   {}, "https://elsewhere.example"))

    def test_allowlist_contains_only_official_predeclared_urls(self):
        self.assertEqual([x["host"] for x in HOSTS],
                         ["www.mofa.go.jp", "www.meti.go.jp"])
        self.assertEqual(sum(len(x["routes"]) for x in HOSTS), 4)
        self.assertTrue(all(url.startswith("https://" + item["host"] + "/")
                            for item in HOSTS
                            for _, url, _ in item["routes"]))


if __name__ == "__main__":
    unittest.main()
