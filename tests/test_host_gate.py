"""
Tests for core.collection.host_gate: per-host spacing shared by processes.

The unit tests drive the gate with a fake clock. The process tests start real
child processes against a loopback HTTP server on 127.0.0.1 and measure, at
the server, when each request arrived and when its response finished. No test
here reaches any host but 127.0.0.1.
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.collection.host_gate import MARGIN, MAX_INTERVAL, GateError, HostGate  # noqa: E402


class Clock:
    """Wall time that only moves when the gate sleeps or a test advances it."""

    def __init__(self, start=1_000_000.0):
        self.now = start
        self.sleeps = []

    def wall(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class GateUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "gate"
        self.clock = Clock()
        self.gate = HostGate(self.dir, sleeper=self.clock.sleep, wall=self.clock.wall)

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, host="moit.gov.vn", interval=2.0, duration=0.5, gate=None):
        with (gate or self.gate).slot(host, interval) as slot:
            self.clock.now += duration
        return slot

    def test_first_request_does_not_wait(self):
        slot = self.request()
        self.assertEqual(slot.waited, 0.0)
        self.assertIsNone(slot.previous_end)
        record = self.gate.record("moit.gov.vn")
        self.assertEqual(record["last_end"], slot.ended)
        self.assertIsNone(record["open_since"])
        self.assertEqual(record["interval"], 2.0)

    def test_wait_runs_from_the_end_of_the_previous_request(self):
        first = self.request(duration=5.0)          # a slow response
        second = self.request()
        self.assertAlmostEqual(second.started - first.ended, 2.0 + MARGIN)
        self.assertEqual(second.previous_end, first.ended)

    def test_elapsed_time_counts_toward_the_interval(self):
        first = self.request()
        self.clock.now += 1.5
        second = self.request()
        self.assertAlmostEqual(second.waited, 0.5 + MARGIN)
        self.assertGreaterEqual(second.started - first.ended, 2.0)

    def test_no_wait_once_the_interval_has_passed(self):
        self.request()
        self.clock.now += 2.0
        self.assertEqual(self.request().waited, 0.0)

    def test_a_failed_request_still_records_its_end(self):
        with self.assertRaises(ConnectionError):
            with self.gate.slot("moit.gov.vn", 2.0):
                self.clock.now += 0.7
                raise ConnectionError("reset")
        record = self.gate.record("moit.gov.vn")
        self.assertIsNone(record["open_since"])
        self.assertEqual(record["last_end"], self.clock.now)
        failed_end = self.clock.now
        self.assertGreaterEqual(self.request().started - failed_end, 2.0)

    def test_recorded_interval_never_decreases(self):
        self.request(interval=5.0)
        second = self.request(interval=2.0)
        self.assertEqual(second.interval, 5.0)
        self.assertAlmostEqual(second.waited, 5.0 + MARGIN)
        self.assertEqual(self.gate.record("moit.gov.vn")["interval"], 5.0)

    def test_require_raises_the_interval_for_the_next_request(self):
        with self.gate.slot("moit.gov.vn", 2.0) as slot:
            self.clock.now += 0.3
            slot.require(3.0)
        end = self.clock.now
        self.assertEqual(self.gate.record("moit.gov.vn")["interval"], 3.0)
        nxt = self.request(interval=2.0)
        self.assertEqual(nxt.interval, 3.0)
        self.assertAlmostEqual(nxt.started - end, 3.0 + MARGIN)

    def test_require_never_lowers_the_interval(self):
        self.request(interval=6.0)
        self.clock.now += 10
        with self.gate.slot("moit.gov.vn", 2.0) as slot:
            slot.require(3.0)
            slot.require(1.0)
        self.assertEqual(slot.required, 3.0)
        self.assertEqual(self.gate.record("moit.gov.vn")["interval"], 6.0)

    def test_require_rejects_out_of_range_intervals(self):
        with self.gate.slot("moit.gov.vn", 2.0) as slot:
            for bad in (0, -1, MAX_INTERVAL + 1):
                with self.assertRaises(GateError):
                    slot.require(bad)

    def test_require_inside_a_failed_request_is_still_recorded(self):
        with self.assertRaises(ValueError):
            with self.gate.slot("moit.gov.vn", 2.0) as slot:
                slot.require(4.0)
                raise ValueError("later failure")
        self.assertEqual(self.gate.record("moit.gov.vn")["interval"], 4.0)

    def test_seed_lengthens_but_never_lowers(self):
        self.gate.seed("moit.gov.vn", self.clock.now - 0.5)
        slot = self.request()
        self.assertAlmostEqual(slot.waited, 1.5 + MARGIN)
        before = self.gate.record("moit.gov.vn")["last_end"]
        self.gate.seed("moit.gov.vn", before - 100)
        self.assertEqual(self.gate.record("moit.gov.vn")["last_end"], before)

    def test_a_future_record_waits_at_most_the_interval(self):
        self.gate.seed("moit.gov.vn", self.clock.now + 3600)
        self.assertAlmostEqual(self.request().waited, 2.0 + MARGIN)

    def test_an_open_record_waits_the_full_interval(self):
        record_path = self.dir / "moit.gov.vn.json"
        record_path.write_text(json.dumps({
            "host": "moit.gov.vn", "interval": 2.0, "last_end": self.clock.now - 500,
            "open_since": self.clock.now - 400, "pid": 999999}))
        slot = self.request()
        self.assertTrue(slot.recovered_open)
        self.assertAlmostEqual(slot.waited, 2.0 + MARGIN)

    def test_hosts_are_independent(self):
        self.request(host="moit.gov.vn", interval=5.0)
        other = self.request(host="congan.com.vn")
        self.assertEqual(other.waited, 0.0)
        self.assertEqual(other.interval, 2.0)
        self.assertEqual(self.gate.record("congan.com.vn")["last_end"], other.ended)
        self.assertEqual(self.gate.record("moit.gov.vn")["interval"], 5.0)

    def test_bad_host_names_are_refused(self):
        for host in ("", "MOIT.gov.vn", "../x", "a/b", "moit.gov.vn.", None, "a b"):
            with self.assertRaises(GateError, msg=repr(host)):
                with self.gate.slot(host, 2.0):
                    pass

    def test_interval_bounds(self):
        for bad in (0, -2, MAX_INTERVAL + 0.1):
            with self.assertRaises(GateError):
                with self.gate.slot("moit.gov.vn", bad):
                    pass

    def test_damaged_records_are_never_read_as_no_previous_request(self):
        path = self.dir / "moit.gov.vn.json"
        for text in ("{not json", json.dumps({"last_end": "soon"}), "[]",
                     json.dumps({"interval": 0}), json.dumps({"interval": 999})):
            path.write_text(text)
            with self.assertRaises(GateError, msg=text):
                with self.gate.slot("moit.gov.vn", 2.0):
                    pass

    def test_symlinked_directory_and_lock_are_refused(self):
        real = Path(self.tmp.name) / "real"
        real.mkdir()
        link = Path(self.tmp.name) / "link"
        link.symlink_to(real)
        with self.assertRaises(GateError):
            HostGate(link)
        target = Path(self.tmp.name) / "elsewhere"
        target.write_text("")
        (self.dir / "moit.gov.vn.lock").symlink_to(target)
        with self.assertRaises(OSError):
            with self.gate.slot("moit.gov.vn", 2.0):
                pass

    def test_lock_timeout(self):
        gate = HostGate(self.dir, sleeper=self.clock.sleep, wall=self.clock.wall,
                        lock_timeout=0.2)
        with self.gate.slot("moit.gov.vn", 2.0):
            with self.assertRaises(GateError):
                with gate.slot("moit.gov.vn", 2.0):
                    pass

    def test_lock_is_held_for_the_whole_request(self):
        other = HostGate(self.dir, lock_timeout=0.1)
        with self.gate.slot("moit.gov.vn", 2.0):
            with self.assertRaises(GateError):
                other.record("moit.gov.vn")
        other.record("moit.gov.vn")         # released afterwards

    def test_no_temporary_files_are_left(self):
        self.request()
        self.request()
        self.gate.seed("moit.gov.vn", self.clock.now)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()),
                         ["moit.gov.vn.json", "moit.gov.vn.lock"])


# ── real processes against a loopback server ─────────────────────────────────

CHILD = textwrap.dedent("""
    import json, sys, time
    sys.path.insert(0, sys.argv[1])
    from core.collection.host_gate import HostGate
    from scraper.sources.vn_shadow_http import Refusal, ShadowHttpAdapter

    class Probe(ShadowHttpAdapter):
        def discover(self, window): raise NotImplementedError
        def fetch(self, ref): raise NotImplementedError
        def extract(self, capture): raise NotImplementedError
        def _challenged(self, headers, text): return False

    mode, gate_dir, base = sys.argv[2], sys.argv[3], sys.argv[4]
    gate = HostGate(gate_dir)
    out = {"mode": mode}
    if mode == "hold":                       # hold one host's slot, without HTTP
        host, seconds = sys.argv[5], float(sys.argv[6])
        with gate.slot(host, 2.0) as slot:
            out["started"] = slot.started
            print(json.dumps(out), flush=True)
            time.sleep(seconds)
        sys.exit(0)
    adapter = Probe(source=type("S", (), {"slug": "gate_probe"})(), gate=gate)
    adapter.robots_url = base + "/robots.txt"
    out["entered"] = time.time()             # about to ask the gate
    try:
        if mode == "robots":
            adapter._load_robots("listing_failure")
            out["interval"] = adapter._interval
        else:
            adapter._get(base + sys.argv[5], 4096, "fetch_failure")
    except Refusal as exc:
        out["refusal"] = exc.status
    out["log"] = adapter.request_log
    print(json.dumps(out), flush=True)
""")


class Server:
    """Loopback HTTP server that records when each request arrived and finished."""

    def __init__(self, robots_body=b"User-agent: *\nDisallow: /private\n",
                 robots_ctype="text/plain", robots_delay=0.25):
        self.events = []
        self.lock = threading.Lock()
        self.arrived = {}
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_GET(self):
                arrived = time.time()
                with server.lock:
                    server.arrived.setdefault(self.path, threading.Event()).set()
                if self.path == "/robots.txt":
                    time.sleep(robots_delay)
                    body, ctype = robots_body, robots_ctype
                elif self.path == "/slow":
                    time.sleep(30)
                    body, ctype = b"late", "text/html"
                elif self.path == "/fail":
                    time.sleep(0.25)
                    server.note(self.path, arrived, time.time())
                    self.close_connection = True
                    self.connection.shutdown(2)
                    return
                else:
                    time.sleep(0.25)
                    body, ctype = b"<html>ok</html>", "text/html; charset=utf-8"
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    self.wfile.flush()
                except OSError:
                    pass
                server.note(self.path, arrived, time.time())

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def note(self, path, arrived, finished):
        with self.lock:
            self.events.append({"path": path, "arrived": arrived, "finished": finished})

    def wait_arrival(self, path, timeout=10):
        with self.lock:
            event = self.arrived.setdefault(path, threading.Event())
        if not event.wait(timeout):
            raise AssertionError("%s never arrived" % path)

    def get(self, path, index=0):
        return [e for e in self.events if e["path"] == path][index]

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class GateProcessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.gate_dir = os.path.join(self.tmp.name, "gate")
        self.servers = []

    def tearDown(self):
        for server in self.servers:
            server.close()
        self.tmp.cleanup()

    def server(self, **kw):
        server = Server(**kw)
        self.servers.append(server)
        return server

    def spawn(self, mode, base, *args):
        return subprocess.Popen(
            [sys.executable, "-W", "ignore", "-c", CHILD, str(ROOT), mode,
             self.gate_dir, base] + [str(a) for a in args],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(ROOT))

    def finish(self, proc, timeout=60):
        out, err = proc.communicate(timeout=timeout)
        self.assertEqual(proc.returncode, 0, err)
        return json.loads(out.strip().splitlines()[-1])

    def test_queued_process_honours_a_crawl_delay_read_by_the_first(self):
        # A reads robots.txt, which is slow and publishes Crawl-delay 3. B is
        # started while A's request is in flight; it has read no robots.txt
        # and asks for the 2 s default. It must still wait 3 s from A's end.
        srv = self.server(robots_body=b"User-agent: *\nCrawl-delay: 3\n", robots_delay=3.0)
        a = self.spawn("robots", srv.base)
        srv.wait_arrival("/robots.txt")
        b = self.spawn("get", srv.base, "/page")
        ra, rb = self.finish(a), self.finish(b)
        self.assertEqual(ra["interval"], 3.0)
        self.assertNotIn("refusal", rb)
        robots, page = srv.get("/robots.txt"), srv.get("/page")
        # B really queued: it asked the gate while A's response was in flight.
        self.assertLess(rb["entered"], robots["finished"])
        self.assertGreaterEqual(page["arrived"] - robots["finished"], 3.0)
        self.assertEqual(rb["log"][0]["gate_interval_s"], 3.0)
        record = json.loads(Path(self.gate_dir, "127.0.0.1.json").read_text())
        self.assertEqual(record["interval"], 3.0)

    def test_an_unvalidated_crawl_delay_is_never_recorded(self):
        # A robots.txt served as a web page is refused; any delay it seems to
        # publish must not reach the gate.
        srv = self.server(robots_body=b"<html>User-agent: *\nCrawl-delay: 9\n</html>",
                          robots_ctype="text/html")
        result = self.finish(self.spawn("robots", srv.base))
        self.assertEqual(result["refusal"], "unexpected_content_type")
        record = json.loads(Path(self.gate_dir, "127.0.0.1.json").read_text())
        self.assertEqual(record["interval"], 2.0)
        self.assertIsNone(record["open_since"])

    def test_concurrent_processes_never_overlap_and_are_spaced(self):
        srv = self.server()
        procs = [self.spawn("get", srv.base, "/p%d" % i) for i in range(3)]
        for proc in procs:
            self.assertNotIn("refusal", self.finish(proc))
        events = sorted(srv.events, key=lambda e: e["arrived"])
        self.assertEqual(len(events), 3)
        for prev, nxt in zip(events, events[1:]):
            self.assertGreaterEqual(nxt["arrived"] - prev["finished"], 2.0)

    def test_consecutive_runs_are_spaced(self):
        srv = self.server()
        self.finish(self.spawn("get", srv.base, "/first"))
        self.finish(self.spawn("get", srv.base, "/second"))
        self.assertGreaterEqual(srv.get("/second")["arrived"] - srv.get("/first")["finished"],
                                2.0)

    def test_a_failed_exchange_is_spaced_from_its_failure(self):
        srv = self.server()
        failed = self.finish(self.spawn("get", srv.base, "/fail"))
        self.assertIn("refusal", failed)
        self.assertIn("error", failed["log"][0])
        self.finish(self.spawn("get", srv.base, "/after"))
        self.assertGreaterEqual(srv.get("/after")["arrived"] - srv.get("/fail")["finished"],
                                2.0)

    def test_a_killed_process_leaves_an_open_record_and_the_next_waits_in_full(self):
        srv = self.server()
        a = self.spawn("get", srv.base, "/slow")
        srv.wait_arrival("/slow")
        os.kill(a.pid, signal.SIGKILL)
        a.wait(timeout=10)
        killed = time.time()
        # Read without the lock: the dead holder's record is still open.
        record = json.loads(Path(self.gate_dir, "127.0.0.1.json").read_text())
        self.assertIsNotNone(record["open_since"])
        self.assertEqual(record["pid"], a.pid)
        result = self.finish(self.spawn("get", srv.base, "/next"))
        self.assertNotIn("refusal", result)
        self.assertGreaterEqual(srv.get("/next")["arrived"] - killed, 2.0)
        self.assertGreaterEqual(result["log"][0]["gate_wait_s"], 2.0)
        self.assertIsNone(json.loads(
            Path(self.gate_dir, "127.0.0.1.json").read_text())["open_since"])

    def test_independent_hosts_do_not_wait_for_each_other(self):
        holder = self.spawn("hold", "-", "moit.gov.vn", 3)
        first = json.loads(holder.stdout.readline())
        other = self.finish(self.spawn("hold", "-", "congan.com.vn", 0))
        self.assertLess(other["started"] - first["started"], 2.0)
        same = self.spawn("hold", "-", "moit.gov.vn", 0)
        holder.wait(timeout=30)
        later = self.finish(same)
        self.assertGreaterEqual(later["started"] - first["started"], 3.0 + 2.0)


if __name__ == "__main__":
    unittest.main()
