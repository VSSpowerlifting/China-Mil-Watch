"""One-shot, no-persistence Japan institutional-route probe from GitHub Actions.

This establishes transport/access evidence only, never source admission.
Exactly two government hosts and four fixed HTML URLs. One robots policy GET
per host; no redirects, cookies, identity switching, challenge handling,
index traversal, retries, body archival or collection. Only counts, hashes and
verdicts are emitted. A retrieved public page does not certify extraction or
rights to republish.
"""
from __future__ import annotations

import hashlib
import html
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

USER_AGENT = ("ChinaMilWatch/1.0 (non-commercial research; project: "
              "https://github.com/VSSpowerlifting/China-Mil-Watch)")
TIMEOUT = 15
MAX_ROBOTS_BYTES = 32768
MAX_HTML_BYTES = 262144
DELAY_SECONDS = 2.0
HOSTS = (
    {
        "host": "www.mofa.go.jp",
        "institution": "Japan Ministry of Foreign Affairs",
        "routes": (
            ("monthly_english_release_archive",
             "https://www.mofa.go.jp/press/release/202610_index.html",
             "Press Releases Archive October 2026"),
            ("english_security_cooperation_release",
             "https://www.mofa.go.jp/press/release/pressite_000001_02711.html",
             "Deputy Secretary of State"),
        ),
    },
    {
        "host": "www.meti.go.jp",
        "institution": "Japan Ministry of Economy, Trade and Industry",
        "routes": (
            ("english_press_listing",
             "https://www.meti.go.jp/english/press/index.html",
             "News Releases"),
            ("english_economic_security_release",
             "https://www.meti.go.jp/english/press/2026/0527_002.html",
             "Japan-Italy Economic Security Consultations"),
        ),
    },
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "noscript", "svg"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script", "noscript", "svg") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def _fetch(url, *, limit, opener):
    """At most one GET; an HTTP error is a verdict, not a new request."""
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
    }, method="GET")
    try:
        response = opener.open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        return {"http_status": exc.code, "reason": "http_refusal_or_redirect"}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"http_status": None, "reason": "transport_" + type(exc).__name__}
    with response:
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        # No more than the fixed byte ceiling, even if Content-Length is false.
        payload = response.read(limit + 1)
        if len(payload) > limit:
            return {"http_status": response.status, "reason": "body_over_limit",
                    "content_type": mime, "at_least_bytes": len(payload)}
        return {"http_status": response.status, "reason": "retrieved",
                "content_type": mime, "byte_count": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "_payload": payload}


def _robots(host, opener, fetch, sleep):
    # Fixed official hostname; neither the manifest nor an RSS feed supplies
    # arbitrary URLs to the probe.
    sleep(DELAY_SECONDS)
    result = fetch("https://" + host + "/robots.txt",
                   limit=MAX_ROBOTS_BYTES, opener=opener)
    policy = {k: v for k, v in result.items() if k != "_payload"}
    if result.get("reason") != "retrieved" or result.get("http_status") != 200:
        return None, dict(policy, verdict="policy_unavailable")
    if result.get("content_type") not in ("text/plain", "text/x-robots", ""):
        return None, dict(policy, verdict="policy_not_plaintext")
    raw = result["_payload"]
    text = raw.decode("utf-8", errors="replace")
    if not any(line.strip().lower().startswith("user-agent:") for line in text.splitlines()):
        return None, dict(policy, verdict="policy_not_robots_directives")
    robot = urllib.robotparser.RobotFileParser()
    robot.parse(text.splitlines())
    return robot, dict(policy, verdict="policy_readable")


def run(*, opener=None, fetch=None, sleep=time.sleep):
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect())
    fetch = fetch or _fetch
    findings = []
    for family in HOSTS:
        host = family["host"]
        robot, policy = _robots(host, opener, fetch, sleep)
        item = {"host": host, "institution": family["institution"],
                "robots": policy, "routes": []}
        for identity, url, marker in family["routes"]:
            parsed = urllib.parse.urlsplit(url)
            if (parsed.scheme != "https" or parsed.hostname != host or
                    parsed.port is not None or parsed.username or parsed.password or
                    parsed.query or parsed.fragment):
                raise ValueError("unexpected candidate URL: " + identity)
            entry = {"route_id": identity, "url": url}
            if robot is None:
                entry["verdict"] = "not_requested_no_policy"
            elif not robot.can_fetch(USER_AGENT, url):
                entry["verdict"] = "not_requested_robots_disallow"
            else:
                sleep(DELAY_SECONDS)
                result = fetch(url, limit=MAX_HTML_BYTES, opener=opener)
                for k, v in result.items():
                    if k != "_payload":
                        entry[k] = v
                if result.get("reason") != "retrieved" or result.get("http_status") != 200:
                    entry["verdict"] = "not_readable"
                elif result.get("content_type") not in ("text/html", "application/xhtml+xml"):
                    entry["verdict"] = "unexpected_content_type"
                else:
                    parser = VisibleText()
                    parser.feed(result["_payload"].decode("utf-8", "replace"))
                    visible = " ".join(parser.text)
                    entry["visible_characters"] = len(visible.strip())
                    entry["expected_marker_found"] = marker.casefold() in visible.casefold()
                    entry["verdict"] = ("html_with_expected_content"
                                        if entry["expected_marker_found"] and
                                        len(visible.strip()) >= 250
                                        else "html_but_content_not_confirmed")
            item["routes"].append(entry)
        findings.append(item)
    return {"schema": "japan-alternative-official-route-probe/1",
            "kind": "noncollecting_egress_access_observation",
            "policy": "no source activation, no redirect or challenge bypass",
            "user_agent": USER_AGENT, "hosts": findings}


def main():
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    print("This probe does not collect documents or qualify a source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
