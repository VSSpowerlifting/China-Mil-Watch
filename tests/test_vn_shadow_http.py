"""
Tests for scraper.sources.vn_shadow_http, the transport every Vietnam shadow
adapter shares, and for the committed ministry probe fixtures it is checked
against. No test here opens a socket.
"""

import ast
import hashlib
import json
import math
import re
import socket
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection import status as st  # noqa: E402
from core.collection.host_gate import HostGate  # noqa: E402
from scraper.sources import vn_shadow_http as http  # noqa: E402
from scraper.sources.vn_shadow_http import (  # noqa: E402
    REQUEST_INTERVAL, Refusal, ShadowHttpAdapter, parse_robots, robots_crawl_delay,
    rules_file_problem)

FIXTURES = ROOT / "tests" / "fixtures" / "vn_ministries"
MANIFEST = json.loads((FIXTURES / "requests.json").read_text(encoding="utf-8"))


def setUpModule():
    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to open a socket")
    setUpModule.saved = socket.socket.connect
    socket.socket.connect = refuse


def tearDownModule():
    socket.socket.connect = setUpModule.saved


# ── fixture provenance ──────────────────────────────────────────────────────

class FixtureProvenanceTests(unittest.TestCase):
    def test_every_exact_fixture_matches_its_recorded_wire_hash(self):
        named = {}
        for row in MANIFEST["requests"]:
            if row.get("fixture"):
                self.assertTrue(row["exact_wire_bytes"], row["seq"])
                body = (FIXTURES / row["fixture"]).read_bytes()
                self.assertEqual(hashlib.sha256(body).hexdigest(), row["sha256"], row["seq"])
                self.assertEqual(len(body), row["bytes"], row["seq"])
                named[row["fixture"]] = row["sha256"]
        on_disk = {p.name for p in FIXTURES.glob("*.bin")}
        self.assertEqual(on_disk, set(named))
        derived = {r["derived_fixture"]["file"] for r in MANIFEST["requests"]
                   if r.get("derived_fixture")}
        self.assertEqual({p.name for p in FIXTURES.glob("derived-*")}, derived)
        self.assertEqual({p.name for p in FIXTURES.iterdir() if p.name != "__pycache__"},
                         set(named) | derived | {"requests.json", "derive_moit_fixture.py"})

    def test_moit_pages_are_committed_only_as_derived_fixtures(self):
        # moit.gov.vn asks for written consent before reuse. Its robots.txt is
        # a rules file, not a page, and is the only exact bytes kept from it.
        for row in MANIFEST["requests"]:
            if not row["url"].startswith("https://moit.gov.vn/"):
                continue
            if row["url"] == "https://moit.gov.vn/robots.txt":
                continue
            self.assertIsNone(row.get("fixture"), row["seq"])

    def test_the_derivation_keeps_dates_and_equalities_and_drops_prose(self):
        sys.path.insert(0, str(FIXTURES))
        try:
            import derive_moit_fixture as derive
        finally:
            sys.path.remove(str(FIXTURES))
        page = ('<html><head><meta name="description" content="Bộ Công Thương họp">'
                '<meta property="article:published_time" content="2026-09-30T21:26:36+0700">'
                '</head><body><span class="post-date left">Thứ 4, 30/09/2026 | 21:22</span>'
                '<a title="Tiêu đề" href="/tin-tuc/a.html">Tiêu đề</a><h1> Tiêu&nbsp;đề </h1>'
                '<script>var c="eyJhIjoxfQ==";</script><p>30/09/2026</p></body></html>')
        out = derive.derive(page)
        self.assertNotIn("Bộ Công Thương họp", out)
        self.assertNotIn(">Tiêu đề<", out)
        for kept in ('content="2026-09-30T21:26:36+0700"', "Thứ 4, 30/09/2026 | 21:22",
                     'href="/tin-tuc/a.html"', 'var c="eyJhIjoxfQ==";', "<p>30/09/2026</p>"):
            self.assertIn(kept, out)
        self.assertEqual(derive.placeholder("Tiêu đề").strip(),
                         derive.placeholder(" Tiêu  đề ").strip())
        self.assertNotEqual(derive.placeholder("Tiêu đề"), derive.placeholder("Tiêu đề khác"))

    def test_derived_fixtures_name_the_original_and_never_claim_exact_bytes(self):
        for row in MANIFEST["requests"]:
            derived = row.get("derived_fixture")
            if not derived:
                continue
            self.assertIsNone(row.get("fixture"), row["seq"])
            self.assertTrue(derived["file"].startswith("derived-"), derived)
            body = (FIXTURES / derived["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(), derived["sha256"])
            self.assertNotEqual(derived["sha256"], row["sha256"])
            self.assertEqual(derived["original_sha256"], row["sha256"])

    def test_no_cookie_value_or_token_is_committed(self):
        attributes = {"expires", "max-age", "path", "domain", "samesite"}
        for row in MANIFEST["requests"]:
            for name, value in (row.get("headers") or {}).items():
                if name.lower() != "set-cookie":
                    continue
                for cname, cvalue in re.findall(r"(?:^|[;,]\s*)([\w.-]+)=([^;,]*)", value):
                    if cname.lower() not in attributes:
                        self.assertEqual(cvalue, "<redacted>", (row["seq"], cname))
        for path in FIXTURES.iterdir():
            text = path.read_bytes().decode("utf-8", "replace")
            # A JWT is three dot-joined base64url segments; moit.gov.vn's
            # widget configs are single base64 JSON strings and are allowed.
            self.assertIsNone(re.search(r"eyJ[A-Za-z0-9_-]{10,}\.", text), path.name)
            self.assertIsNone(re.search(r"(?:incap_ses|visid_incap)_[\d_]+=(?!<redacted>)", text),
                              path.name)
            self.assertIsNone(re.search(r"AUTH_BEARER\w*=(?!<redacted>)", text), path.name)
            for value in re.findall(r"document\.cookie\s*=\s*[\"'][\w.-]+=([^;\"'\s]*)", text):
                self.assertEqual(value, "<redacted>", path.name)

    def test_identity_is_the_collector_identity(self):
        self.assertEqual(MANIFEST["user_agent"], http.USER_AGENT)
        self.assertLessEqual(MANIFEST["used"]["total"], MANIFEST["written_cap"]["aggregate"])
        for group, used in MANIFEST["used"]["per_group"].items():
            self.assertLessEqual(used, MANIFEST["written_cap"]["groups"][group], group)


# ── rules files, on the real bytes ───────────────────────────────────────────

class RulesFileTests(unittest.TestCase):
    def body(self, name):
        return (FIXTURES / name).read_bytes()

    def test_real_rules_files_pass_whatever_their_header(self):
        for name in ("mps-robots.bin", "moit-robots.bin", "vntr-moit-robots.bin"):
            self.assertIsNone(rules_file_problem(self.body(name)), name)

    def test_challenge_and_app_shell_are_not_rules_files(self):
        for name in ("derived-mond-robots-challenge.html", "mof-robots-app-shell.bin"):
            self.assertIsNotNone(rules_file_problem(self.body(name)), name)

    def test_parsed_rules_match_the_recorded_reading(self):
        recorded = MANIFEST["robots"]
        for host, name in (("bocongan.gov.vn", "mps-robots.bin"),
                           ("moit.gov.vn", "moit-robots.bin"),
                           ("vntr.moit.gov.vn", "vntr-moit-robots.bin")):
            rules = http.robots_rules(parse_robots(self.body(name).decode("utf-8")))
            self.assertEqual([list(r) for r in rules], recorded[host]["rules"], host)

    def test_edge_cases(self):
        self.assertIsNotNone(rules_file_problem(b"\xff\xfe"))
        self.assertIsNotNone(rules_file_problem(b"Disallow: /\n"))
        self.assertIsNotNone(rules_file_problem(b"User-agent: *\nfoo bar\n"))
        self.assertIsNone(rules_file_problem("﻿User-agent: *\n# c\n\nAllow: /\n"
                                             .encode("utf-8")))

    def test_crawl_delay_parsing(self):
        def delay(text):
            return robots_crawl_delay(parse_robots(text))
        self.assertEqual(delay("User-agent: *\nCrawl-delay: 7\n"), 7.0)
        self.assertIsNone(delay("User-agent: *\nDisallow: /x\n"))
        for bad in ("soon", "nan", "-3", "inf"):
            self.assertTrue(math.isinf(delay("User-agent: *\nCrawl-delay: %s\n" % bad)), bad)


# ── transport, with a fake session ───────────────────────────────────────────

class FakeRaw:
    def __init__(self, body):
        self.body = body

    def stream(self, size, decode_content=False):
        for i in range(0, len(self.body), size):
            yield self.body[i:i + size]


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code = status
        self.headers = headers if headers is not None else {}
        self.raw = FakeRaw(body)
        self.closed = False

    def close(self):
        self.closed = True


class FakeCookies:
    def clear(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.cookies = FakeCookies()

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class Clock:
    def __init__(self):
        self.now = 1_000_000.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Probe(ShadowHttpAdapter):
    robots_url = "https://moit.gov.vn/robots.txt"

    def discover(self, window):
        raise NotImplementedError

    def fetch(self, ref):
        raise NotImplementedError

    def extract(self, capture):
        raise NotImplementedError

    def _challenged(self, headers, text):
        return "challenge" in text


SOURCE = type("S", (), {"slug": "vn_probe_vi"})()


def probe(responses, gate=None, clock=None):
    clock = clock or Clock()
    return Probe(SOURCE, session=FakeSession(responses), sleeper=clock.sleep, clock=clock,
                 wall=clock, gate=gate), clock


def text(body, ctype="text/plain"):
    return FakeResponse(200, body.encode("utf-8") if isinstance(body, str) else body,
                        {"Content-Type": ctype})


class LoadRobotsTests(unittest.TestCase):
    def load(self, response, gate=None):
        adapter, _ = probe([response], gate=gate)
        try:
            adapter._load_robots(st.LISTING_FAILURE)
        except Refusal as exc:
            return adapter, exc
        return adapter, None

    def test_absent(self):
        for status in (404, 410):
            adapter, refusal = self.load(FakeResponse(status, b"nf", {"Content-Type": "text/html"}))
            self.assertIsNone(refusal)
            self.assertEqual(adapter.robots_status, "absent")
            self.assertEqual(adapter._rules, [])

    def test_no_basis(self):
        for status, expected in ((401, st.AUTH_FAILURE), (403, st.AUTH_FAILURE),
                                 (500, st.LISTING_FAILURE)):
            _, refusal = self.load(FakeResponse(status, b"x", {}))
            self.assertEqual(refusal.status, expected, status)

    def test_redirect_is_never_followed(self):
        _, refusal = self.load(FakeResponse(301, b"", {"Location": "https://x.example/r"}))
        self.assertEqual(refusal.status, st.DISALLOWED_REDIRECT)

    def test_real_moit_file_served_as_html_is_read_with_an_anomaly(self):
        body = (FIXTURES / "moit-robots.bin").read_bytes()
        adapter, refusal = self.load(text(body, "text/html; charset=UTF-8"))
        self.assertIsNone(refusal)
        self.assertEqual(adapter.robots_status, "read")
        self.assertEqual(len(adapter.source_anomalies), 1)
        self.assertIn("robots_content_type", adapter.source_anomalies[0])
        self.assertEqual(adapter.evidence[0]["payload"], body)

    def test_challenge_and_app_shell_are_refused(self):
        for name, ctype in (("derived-mond-robots-challenge.html", "text/html; charset=utf-8,gbk"),
                            ("mof-robots-app-shell.bin", "text/html")):
            adapter, refusal = self.load(text((FIXTURES / name).read_bytes(), ctype))
            self.assertEqual(refusal.status, st.UNEXPECTED_CONTENT_TYPE, name)
            self.assertIsNone(adapter._rules)

    def test_long_and_unparseable_delays_are_refused(self):
        for value in ("121", "soon", "nan", "-1"):
            _, refusal = self.load(text("User-agent: *\nCrawl-delay: %s\n" % value))
            self.assertEqual(refusal.status, st.LISTING_FAILURE, value)
            self.assertIn("Crawl-delay", refusal.detail)

    def test_published_delay_sets_the_interval(self):
        adapter, refusal = self.load(text("User-agent: *\nCrawl-delay: 7\n"))
        self.assertIsNone(refusal)
        self.assertEqual(adapter._interval, 7.0)
        adapter, _ = self.load(text("User-agent: *\nCrawl-delay: 1\n"))
        self.assertEqual(adapter._interval, REQUEST_INTERVAL)


class GatedTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.gate = HostGate(Path(self.tmp.name) / "gate", sleeper=self.clock.sleep,
                             wall=self.clock)

    def tearDown(self):
        self.tmp.cleanup()

    def record(self):
        return self.gate.record("moit.gov.vn")

    def test_a_validated_delay_is_recorded_before_the_slot_closes(self):
        adapter, _ = probe([text("User-agent: *\nCrawl-delay: 5\n")], self.gate, self.clock)
        adapter._load_robots(st.LISTING_FAILURE)
        self.assertEqual(self.record()["interval"], 5.0)
        # A second instance, which has read nothing, still waits 5 s.
        other, _ = probe([text("<html>ok</html>", "text/html")], self.gate, self.clock)
        other._get("https://moit.gov.vn/x", 1000, st.FETCH_FAILURE)
        self.assertEqual(other.request_log[0]["gate_interval_s"], 5.0)
        self.assertGreaterEqual(other.request_log[0]["gate_wait_s"], 5.0)

    def test_a_refused_robots_file_never_records_its_delay(self):
        for body, ctype in (("<html>User-agent: *\nCrawl-delay: 9</html>", "text/html"),
                            ("User-agent: *\nCrawl-delay: 500\n", "text/plain")):
            adapter, _ = probe([text(body, ctype)], self.gate, self.clock)
            with self.assertRaises(Refusal):
                adapter._load_robots(st.LISTING_FAILURE)
            record = self.record()
            self.assertEqual(record["interval"], REQUEST_INTERVAL, body)
            self.assertIsNone(record["open_since"])

    def test_a_transport_failure_records_its_end(self):
        adapter, _ = probe([ConnectionError("reset")], self.gate, self.clock)
        with self.assertRaises(Refusal):
            adapter._get("https://moit.gov.vn/x", 1000, st.FETCH_FAILURE)
        record = self.record()
        self.assertIsNone(record["open_since"])
        self.assertEqual(record["last_end"], self.clock.now)

    def test_a_gate_failure_refuses_without_a_request(self):
        Path(self.gate.directory, "moit.gov.vn.json").write_text("{damaged")
        adapter, _ = probe([text("x")], self.gate, self.clock)
        with self.assertRaises(Refusal) as ctx:
            adapter._get("https://moit.gov.vn/x", 1000, st.FETCH_FAILURE)
        self.assertIn("host gate failed", ctx.exception.detail)
        self.assertEqual(adapter._session.calls, [])

    def test_request_cap(self):
        adapter, _ = probe([text("a"), text("b")], self.gate, self.clock)
        adapter.max_requests = 1
        adapter._get("https://moit.gov.vn/a", 1000, st.FETCH_FAILURE)
        with self.assertRaises(Refusal):
            adapter._get("https://moit.gov.vn/b", 1000, st.FETCH_FAILURE)

    def test_requests_carry_only_the_collector_headers(self):
        adapter, _ = probe([text("a")], self.gate, self.clock)
        adapter._get("https://moit.gov.vn/a", 1000, st.FETCH_FAILURE)
        _, kwargs = adapter._session.calls[0]
        self.assertEqual(kwargs["headers"], http.REQUEST_HEADERS)
        self.assertFalse(kwargs["allow_redirects"])


class IsolationTests(unittest.TestCase):
    def test_transport_imports_nothing_from_production(self):
        tree = ast.parse((ROOT / "scraper" / "sources" / "vn_shadow_http.py").read_text())
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
        allowed = {"core.collection.contract", "core.collection.host_gate",
                   "core.collection.status", "core.collection"}
        for name in names:
            if name.startswith(("core", "scraper", "site", "scripts", "shadow")):
                self.assertIn(name, allowed, name)


if __name__ == "__main__":
    unittest.main()
