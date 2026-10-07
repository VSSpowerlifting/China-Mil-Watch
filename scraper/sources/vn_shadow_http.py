"""
Transport and robots policy shared by the Vietnam shadow adapters.

Every Vietnam shadow adapter sends the same identity, makes one request at a
time, follows no redirect, returns no cookie, reads a bounded body and spaces
its requests from the END of the previous one. That code was written for the
Government News adapter (`vn_vgp.py`) and moved here so the ministry adapters
cannot drift from it; the one behavioural change in the move is that a
Crawl-delay that is not a finite, non-negative number is read as infinite and
refused. Each adapter keeps its own page rules: what its
publisher's frame looks like, what a challenge on its host looks like, how its
listing and articles are read.

One addition: an optional host gate (`core.collection.host_gate.HostGate`).
An adapter's own spacing cannot see another process. With a gate, every
process that names the same gate directory spaces its requests to a host from
the end of the last request ANY of them made to it, and a Crawl-delay read from
robots.txt is recorded with that request's end, so it binds the next request
from any process. The runner always passes one; tests that exercise a single
adapter may leave it out.

Nothing here is registered in a production desk manifest, and nothing here can
reach `pla_watch.db` or `output/`.
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from core.collection import status as st
from core.collection.contract import SourceAdapter
from core.collection.host_gate import MAX_INTERVAL, GateError

#: The repository's complete shadow-collector identity, unchanged, as every
#: other shadow adapter sends it and as the 2026-10-06 UTC probes sent it.
USER_AGENT = ("ChinaMilWatch-ShadowCollector/0.1 "
              "(+https://chinamilwatch.org; research archive; contact via site)")
#: The only request headers these adapters set. `Accept-Encoding: identity` asks
#: for the bytes as stored; a compressed reply is refused rather than decoded,
#: so a stored capture is always the bytes that crossed the wire.
REQUEST_HEADERS = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
ROBOTS_TOKENS = ("chinamilwatch-shadowcollector", "chinamilwatch")

REQUEST_TIMEOUT = 30
REQUEST_INTERVAL = 2.0          # seconds; a longer published Crawl-delay wins
MAX_CRAWL_DELAY = 120.0         # a longer published delay is refused, not shortened
MAX_BODY_BYTES = 2_000_000
MAX_ROBOTS_BYTES = 512 * 1024

_ASCII_WS = re.compile(r"[ \t\n\r\f]+")

CHALLENGE_RE = re.compile(
    r"<title>\s*(?:just a moment|attention required)|cf-browser-verification|"
    r"_cf_chl_opt|id=[\"']challenge-form[\"']|"
    r"enable javascript and cookies to continue|"
    r"checking your browser before accessing|"
    r"class=[\"'][^\"']*\b(?:g-recaptcha|h-captcha)\b", re.I)

#: The directives a robots.txt rules file may hold (RFC 9309 plus the two
#: widely published extensions, `Sitemap` and `Host`).
ROBOTS_DIRECTIVES = frozenset(("user-agent", "allow", "disallow", "crawl-delay",
                               "sitemap", "host"))
#: A tag, a declaration or a processing instruction: the mark of a web page.
_MARKUP = re.compile(r"<[A-Za-z!/?]")


class Refusal(Exception):
    """A collection stage that must stop, with the status that names why."""

    def __init__(self, status: str, detail: str, endpoint: Optional[str] = None,
                 http_status: Optional[int] = None):
        super().__init__(detail)
        self.status, self.detail, self.endpoint = status, detail, endpoint
        self.http_status = http_status


@dataclass(frozen=True)
class Raw:
    url: str
    status: int
    headers: Dict[str, str]     # lower-cased names
    body: bytes
    oversized: bool
    retrieved_at: str


# ── pure helpers, unit-testable without a network ────────────────────────────

def squash(text: str) -> str:
    """
    Collapse runs of the ASCII whitespace HTML collapses (space, tab, CR, LF,
    FF) and trim them at the ends. NBSP, soft hyphens and every other character
    stay exactly as published; `str.split()` would turn NBSP into a space.
    """
    return _ASCII_WS.sub(" ", text or "").strip(" \t\n\r\f")


def parse_robots(text: str) -> List[dict]:
    """
    `[{"agents": [...], "rules": [(allow, pattern)], "crawl_delay": float|None}]`.
    Consecutive `User-agent` lines share a group; one after a rule line starts
    a new one. An empty `Allow:`/`Disallow:` value is no rule at all.
    """
    groups: List[dict] = []
    current: Optional[dict] = None
    in_rules = False
    for line in (text or "").lstrip("﻿").splitlines():
        name, sep, value = line.split("#", 1)[0].partition(":")
        if not sep:
            continue
        name, value = name.strip().lower(), value.strip()
        if name == "user-agent":
            if current is None or in_rules:
                current = {"agents": [], "rules": [], "crawl_delay": None}
                groups.append(current)
                in_rules = False
            current["agents"].append(value.lower())
        elif current is not None and name in ("allow", "disallow"):
            in_rules = True
            if value:
                current["rules"].append((name == "allow", value))
        elif current is not None and name == "crawl-delay":
            in_rules = True
            try:
                delay = float(value)
            except ValueError:
                delay = float("nan")
            # Unreadable, negative or not a number: refuse, never guess low.
            current["crawl_delay"] = delay if math.isfinite(delay) and delay >= 0 else float("inf")
    return groups


def _governing(groups: List[dict]) -> List[dict]:
    """Every group naming this collector, combined; only when none does, every `*` group."""
    named = [g for g in groups if any(a in ROBOTS_TOKENS for a in g["agents"])]
    return named or [g for g in groups if "*" in g["agents"]]


def robots_rules(groups: List[dict]) -> List[Tuple[bool, str]]:
    return [rule for g in _governing(groups) for rule in g["rules"]]


def robots_crawl_delay(groups: List[dict]) -> Optional[float]:
    delays = [g["crawl_delay"] for g in _governing(groups) if g["crawl_delay"] is not None]
    return max(delays) if delays else None


def robots_allows(rules, target: str) -> bool:
    """RFC 9309: longest match wins, Allow wins a tie, `*` wildcard, `$` anchor."""
    best = (-1, True)
    for allow, pattern in rules:
        anchored = pattern.endswith("$")
        body = re.escape(pattern[:-1] if anchored else pattern).replace(r"\*", ".*")
        if re.match(body + ("$" if anchored else ""), target):
            best = max(best, (len(pattern), allow))
    return best[1]


def rules_file_problem(body: bytes) -> Optional[str]:
    """
    Why a 200 robots.txt body is not a rules file, or None when it is one.

    The body decides, not the Content-Type header. It must be UTF-8, hold no
    markup at all, hold at least one `User-agent` line, and every line that is
    not blank or a comment must be a known directive. An HTML page, an app
    shell or a script challenge fails; a genuine rules file served as
    `text/html` (moit.gov.vn, 2026-10-06 UTC) passes, and the caller records
    the header as an anomaly. This is the reading written into the 2026-10-06
    request budget before it was applied; it is for the owner to confirm.
    """
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return "the body is not UTF-8"
    if _MARKUP.search(text):
        return "the body holds markup"
    agents = 0
    for number, line in enumerate(text.lstrip("﻿").splitlines(), 1):
        content = line.split("#", 1)[0].strip()
        if not content:
            continue
        name, sep, _ = content.partition(":")
        name = name.strip().lower()
        if not sep or name not in ROBOTS_DIRECTIVES:
            return "line %d is not a robots directive" % number
        agents += name == "user-agent"
    if not agents:
        return "the body names no User-agent"
    return None


def transport_status(exc: Exception, default: str) -> str:
    return st.TIMEOUT if isinstance(exc, requests.exceptions.Timeout) else default


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _instant(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="microseconds")


# ── the shared adapter base ──────────────────────────────────────────────────

class ShadowHttpAdapter(SourceAdapter):
    """
    Transport for one Vietnam shadow source. A subclass names its robots.txt
    URL and says what a challenge on its host looks like; it does everything
    else (discovery, retrieval, extraction) itself.
    """

    #: https://<host>/robots.txt for the one host a subclass requests.
    robots_url: str = ""

    def __init__(self, source, session=None, sleeper=time.sleep, clock=time.monotonic,
                 max_requests: Optional[int] = None, gate=None,
                 wall: Callable[[], float] = time.time) -> None:
        super().__init__(source)
        self._session = session or requests.Session()
        self._sleep = sleeper
        self._clock = clock
        self._wall = wall
        self._host_gate = gate
        self._last_request: Optional[float] = None
        self._rules: Optional[List[Tuple[bool, str]]] = None
        self._interval = REQUEST_INTERVAL
        #: Hard ceiling on requests this instance will make; the runner sets it.
        self.max_requests = max_requests
        #: Every request made, in order: url, status, bytes, redirect target,
        #: the wall-clock instants it started and ended, and any gate wait.
        self.request_log: List[dict] = []
        #: Exact bytes of robots.txt and the listing, for the runner to store.
        self.evidence: List[dict] = []
        self.robots_status: Optional[str] = None
        #: Observations about the source that belong to no one document.
        self.source_anomalies: List[str] = []

    # -- page rules a subclass supplies ----------------------------------------

    def _challenged(self, headers: Dict[str, str], text: str) -> bool:
        """True when `text` is an access challenge rather than this publisher's page."""
        raise NotImplementedError

    # -- transport ------------------------------------------------------------

    def _get(self, url: str, limit: int, generic: str,
             settle: Optional[Callable[[Raw], Optional[float]]] = None) -> Raw:
        """
        One polite request: honest identity, no redirect followed, no cookie
        returned, bounded read, spaced from the END of the previous attempt.
        Never retried within a run. With a host gate the spacing also holds
        across processes, and no two of them have a request to one host in
        flight at once. `settle`, when given, inspects the response before the
        gate slot is released (and may refuse it); a delay it returns is
        recorded with this request's end, so it binds the host's next request
        from any process.
        """
        if self.max_requests is not None and len(self.request_log) >= self.max_requests:
            raise Refusal(generic, "request cap of %d reached before %s"
                          % (self.max_requests, url), url)
        if self._last_request is not None:
            wait = self._interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        if self._host_gate is None:
            raw = self._exchange(url, limit, generic, None)
            if settle is not None:
                settle(raw)
            return raw
        try:
            with self._host_gate.slot(urlparse(url).hostname or "", self._interval) as slot:
                raw = self._exchange(url, limit, generic, slot)
                delay = settle(raw) if settle is not None else None
                if delay is not None and delay > 0:
                    slot.require(min(delay, MAX_INTERVAL))
                    # Preserve the newly learned requirement in the request
                    # ledger too, so a fresh machine can seed it even when
                    # robots was the run's last request.
                    self.request_log[-1]["gate_interval_s"] = max(slot.interval, slot.required)
                return raw
        except (GateError, OSError) as exc:
            # The request was not sent, or its end could not be recorded. Either
            # way the run stops: spacing that cannot be shown is not assumed.
            raise Refusal(generic, "%s: the host gate failed (%s)" % (url, exc), url)

    def _exchange(self, url: str, limit: int, generic: str, slot) -> Raw:
        log = {"url": url, "requested_at": now_utc(), "status": None, "bytes": None}
        if slot is not None:
            log["gate_wait_s"] = round(slot.waited, 3)
            log["gate_interval_s"] = slot.interval
        self.request_log.append(log)
        log["started_utc"] = _instant(self._wall())
        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT, stream=True,
                                     allow_redirects=False, headers=dict(REQUEST_HEADERS))
        except Exception as exc:
            self._last_request = self._clock()
            log["ended_utc"] = _instant(self._wall())
            log["error"] = type(exc).__name__
            raise Refusal(transport_status(exc, generic),
                          "%s unreachable: %s" % (url, type(exc).__name__), url)
        try:
            self._session.cookies.clear()
            headers = {k.lower(): v for k, v in (resp.headers or {}).items()}
            log["status"] = resp.status_code
            if resp.status_code in (429, 503) or "retry-after" in headers:
                log["stop_host"] = True
                raise Refusal(generic, "%s: host requested a stop (HTTP %d)" %
                              (url, resp.status_code), url, resp.status_code)
            if headers.get("location"):
                log["location"] = headers["location"]
            encoding = headers.get("content-encoding", "").strip().lower()
            if encoding not in ("", "identity"):
                raise Refusal(st.UNEXPECTED_CONTENT_TYPE,
                              "%s was sent with Content-Encoding %r despite "
                              "Accept-Encoding: identity" % (url, encoding),
                              url, resp.status_code)
            declared = headers.get("content-length", "")
            oversized = declared.isdigit() and int(declared) > limit
            chunks, size = [], 0
            if not oversized:
                for chunk in resp.raw.stream(65536, decode_content=False):
                    size += len(chunk)
                    if size > limit:
                        oversized = True
                        break
                    chunks.append(chunk)
            body = b"" if oversized else b"".join(chunks)
            log["bytes"] = len(body)
            return Raw(url, resp.status_code, headers, body, oversized, now_utc())
        except Refusal:
            raise
        except Exception as exc:
            log["error"] = type(exc).__name__
            raise Refusal(transport_status(exc, generic),
                          "%s: read failed (%s)" % (url, type(exc).__name__), url)
        finally:
            resp.close()
            self._last_request = self._clock()
            log["ended_utc"] = _instant(self._wall())

    def _gate(self, raw: Raw) -> None:
        """Status-independent refusals: redirects, cookie gates, size, challenges."""
        if 300 <= raw.status < 400:
            target = urljoin(raw.url, raw.headers.get("location", ""))
            if target == raw.url and "set-cookie" in raw.headers:
                raise Refusal(st.ACCESS_CHALLENGED,
                              "cookie gate: HTTP %d back to the same URL while setting a "
                              "cookie. Cookies are never returned, so this collector does not "
                              "pass it" % raw.status, raw.url, raw.status)
            raise Refusal(st.DISALLOWED_REDIRECT, "HTTP %d redirect to %s was not followed"
                          % (raw.status, raw.headers.get("location", "?")), raw.url, raw.status)
        if raw.oversized:
            raise Refusal(st.OVERSIZED_RESPONSE, "response exceeds the byte limit",
                          raw.url, raw.status)
        if self._challenged(raw.headers, raw.body.decode("utf-8", "replace")):
            raise Refusal(st.ACCESS_CHALLENGED,
                          "an access challenge was served instead of the document",
                          raw.url, raw.status)

    def _screen(self, raw: Raw, generic: str) -> str:
        """A usable HTML body as text, or a refusal that names the reason."""
        self._gate(raw)
        if raw.status in (401, 403):
            raise Refusal(st.AUTH_FAILURE, "HTTP %d" % raw.status, raw.url, raw.status)
        if raw.status != 200:
            raise Refusal(generic, "HTTP %d" % raw.status, raw.url, raw.status)
        ctype = raw.headers.get("content-type", "")
        charset = re.search(r"charset=([^;\s]+)", ctype, re.I)
        if (not ctype.lower().startswith("text/html")
                or (charset and charset.group(1).strip("\"'").lower() not in ("utf-8", "utf8"))):
            raise Refusal(st.UNEXPECTED_CONTENT_TYPE,
                          "content-type %r, expected UTF-8 HTML" % ctype, raw.url, raw.status)
        try:
            return raw.body.decode("utf-8")
        except UnicodeDecodeError:
            raise Refusal(st.UNEXPECTED_CONTENT_TYPE, "body is not valid UTF-8",
                          raw.url, raw.status)

    def _keep(self, role: str, raw: Raw) -> None:
        self.evidence.append({
            "role": role, "url": raw.url, "http_status": raw.status,
            "content_type": raw.headers.get("content-type"),
            "payload_bytes": len(raw.body),
            "payload_sha256": hashlib.sha256(raw.body).hexdigest(),
            "retrieved_at": raw.retrieved_at, "payload": raw.body})

    # -- policy ---------------------------------------------------------------

    def _robots_problem(self, raw: Raw) -> Optional[str]:
        """Why a 200 robots.txt response is not a rules file, or None. The body decides."""
        problem = rules_file_problem(raw.body)
        return "robots.txt is not a rules file: %s" % problem if problem else None

    def _load_robots(self, generic: str) -> None:
        """
        Read robots.txt for this run, or refuse. 404/410 state no restriction;
        401/403 is no permission basis; a redirect, or a 200 that is not a
        rules file (see `_robots_problem`), is never read as allow-all. A rules
        file served under a Content-Type other than text/plain is read, and
        the header is recorded as a source anomaly. A published Crawl-delay
        longer than 2 s is honoured.

        The file is validated while the host's gate slot is still held, and a
        validated Crawl-delay is recorded with the request's end. A process
        queued behind this one therefore waits the published delay, never the
        2 s default; the gate's recorded interval never decreases.
        """
        self._rules, self._interval = None, REQUEST_INTERVAL
        robots = self.robots_url
        read: dict = {}

        def settle(raw: Raw) -> Optional[float]:
            self._gate(raw)
            if raw.status in (404, 410):
                return None
            if raw.status in (401, 403):
                raise Refusal(st.AUTH_FAILURE, "robots.txt returned HTTP %d; no basis to "
                              "conclude collection is permitted" % raw.status, robots, raw.status)
            if raw.status != 200:
                raise Refusal(generic, "robots.txt returned HTTP %d" % raw.status,
                              robots, raw.status)
            problem = self._robots_problem(raw)
            if problem:
                raise Refusal(st.UNEXPECTED_CONTENT_TYPE, problem, robots, raw.status)
            groups = parse_robots(raw.body.decode("utf-8"))
            delay = robots_crawl_delay(groups)
            if delay is not None and delay > MAX_CRAWL_DELAY:
                raise Refusal(generic, "robots.txt publishes a Crawl-delay of %s s, longer than "
                              "a bounded run honours (%s s); refusing rather than shortening it"
                              % (delay, MAX_CRAWL_DELAY), robots, raw.status)
            read["groups"] = groups
            return delay

        raw = self._get(robots, MAX_ROBOTS_BYTES, generic, settle=settle)
        if "groups" not in read:                       # 404 or 410
            self._rules, self.robots_status = [], "absent"
            return
        ctype = raw.headers.get("content-type", "")
        if not ctype.lower().startswith("text/plain"):
            self.source_anomalies.append(
                "robots_content_type: %s is a rules file served as %r" % (robots, ctype))
        groups = read["groups"]
        self._interval = max(REQUEST_INTERVAL, robots_crawl_delay(groups) or 0.0)
        self._rules, self.robots_status = robots_rules(groups), "read"
        self._keep("robots", raw)

    def _permits(self, url: str) -> bool:
        parts = urlparse(url)
        return robots_allows(self._rules or [],
                             parts.path + ("?" + parts.query if parts.query else ""))
