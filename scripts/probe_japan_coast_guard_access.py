"""Narrow, noncollecting Japan Coast Guard source-access check on Actions.

One disclosed client, one robots GET and at most five fixed government URLs.
Never follows redirects, solves challenges, stores content, imports collectors,
writes a database, or interprets a policy refusal as permission.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import urlsplit

HOST = "www.kaiho.mlit.go.jp"
UA = ("ChinaMilWatch/1.0 (non-commercial research; project: "
      "https://github.com/VSSpowerlifting/China-Mil-Watch)")
ROUTES = (
    ("archive", "/e/topics_archive/index.html", "Press Release", "html"),
    ("philippines_investigation", "/e/topics_archive/article9455.html",
     "Capacity Building Support for the Philippine Coast Guard", "html"),
    ("philippines_arrest_training", "/e/topics_archive/article9453.html",
     "Capacity Building Support for the Philippine Coast Guard", "html"),
    ("indonesia_bakamla", "/e/topics_archive/article9436.html",
     "Capacity Building Support for the Indonesia Coast Guard Agency", "html"),
    ("sapphire26_original_pdf",
     "/e/topics_archive/upload/260526_2/e260526_2.pdf", None, "pdf"),
)
MAX_ROBOTS = 32768
MAX_HTML = 262144
MAX_PDF = 1048576
INTERVAL = 2.0
TIMEOUT = 15


class RefuseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class MainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.suppressed = 0
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "svg", "noscript"):
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "svg", "noscript") and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data):
        if not self.suppressed:
            self.chunks.append(data)


def get_once(url, limit, *, opener):
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "*/*"}, method="GET")
    try:
        response = opener.open(request, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "result": "http_not_served"}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"status": None, "result": "transport_" + type(exc).__name__}
    with response:
        kind = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        raw = response.read(limit + 1)
        if len(raw) > limit:
            return {"status": response.status, "result": "size_limit",
                    "mime": kind, "minimum_bytes": len(raw)}
        return {"status": response.status, "result": "body_returned",
                "mime": kind, "byte_count": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(), "_raw": raw}


def examine(*, opener=None, request=get_once, sleep=time.sleep):
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}), RefuseRedirect())
    base = "https://" + HOST
    sleep(INTERVAL)
    robots = request(base + "/robots.txt", MAX_ROBOTS, opener=opener)
    policy = {k: v for k, v in robots.items() if k != "_raw"}
    raw = robots.get("_raw")
    robot = None
    # RFC 9309 §2.3.1.3 permits access when /robots.txt is absent (404).
    # Unlike a 403, 429 or 5xx, this status reports no published policy.
    # Treat ONLY an exact 404 as absence; do not equate access refusal with it.
    no_robots_file = (
        robots.get("status") == 404
        and robots.get("result") == "http_not_served"
    )
    if no_robots_file:
        policy["verdict"] = "policy_absent_404_no_robots_restrictions"
    if (robots.get("status") == 200 and isinstance(raw, bytes)
            and robots.get("mime") in ("text/plain", "text/x-robots", "")):
        policy_text = raw.decode("utf-8-sig", errors="replace")
        if any(line.strip().lower().startswith("user-agent:")
               for line in policy_text.splitlines()):
            robot = urllib.robotparser.RobotFileParser()
            robot.parse(policy_text.splitlines())
            policy["verdict"] = "readable"
    if robot is None and not no_robots_file:
        policy["verdict"] = "unreadable_no_further_requests"

    outcomes = []
    for ident, path, marker, kind in ROUTES:
        url = base + path
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != HOST
                or parsed.username or parsed.password or parsed.port
                or parsed.query or parsed.fragment):
            raise AssertionError("unrecognized route")
        item = {"id": ident, "url": url, "kind": kind}
        if robot is None and not no_robots_file:
            item["verdict"] = "blocked_policy_unavailable"
        elif robot is not None and not robot.can_fetch(UA, url):
            item["verdict"] = "blocked_by_robots"
        else:
            sleep(INTERVAL)
            reply = request(url, MAX_PDF if kind == "pdf" else MAX_HTML,
                            opener=opener)
            item.update({k: v for k, v in reply.items() if k != "_raw"})
            if reply.get("status") != 200 or reply.get("result") != "body_returned":
                item["verdict"] = "not_accessible"
            elif kind == "pdf":
                item["verdict"] = ("pdf_signature_observed"
                                   if reply.get("mime") == "application/pdf"
                                   and reply["_raw"].startswith(b"%PDF-")
                                   else "pdf_unverified")
            elif reply.get("mime") not in ("text/html", "application/xhtml+xml"):
                item["verdict"] = "unexpected_mime"
            else:
                parser = MainText()
                parser.feed(reply["_raw"].decode("utf-8", errors="replace"))
                words = " ".join(parser.chunks)
                item["visible_chars"] = len(words.strip())
                item["marker_found"] = marker.casefold() in words.casefold()
                item["verdict"] = (
                    "readable_original_html" if item["marker_found"]
                    and len(words.strip()) >= 400 else "body_not_verified"
                )
        outcomes.append(item)
    return {"schema": "japan-jcg-source-access-v1",
            "mode": "metadata_only_no_archive_no_production",
            "host": HOST, "user_agent": UA,
            "robots": policy, "routes": outcomes}


def main():
    print(json.dumps(examine(), sort_keys=True, indent=2))
    print("A successful probe is not source approval or production qualification.")


if __name__ == "__main__":
    main()
