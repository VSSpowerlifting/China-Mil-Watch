"""Vietnam MOD Defence Relations: manually approved, bounded listing-access canary.

At most TWO first-party GETs (robots.txt and one listing). The probe
does not fetch articles, persist publisher bodies, scrape around denials,
create records, collect automatically, call a model or approve source rights.
No network request occurs without --approve-live-probe.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import urljoin

from scripts.review_vietnam_mod_portal_links import (
    article_identity, MODCanaryRefused,
)

BASE = "https://mod.gov.vn"
ROBOTS = BASE + "/robots.txt"
LISTING = BASE + "/en/news/sa-en-news/sa-en-news-rela"
UA = ("ChinaMilWatch/1.0 (non-commercial research; project: "
      "https://github.com/VSSpowerlifting/China-Mil-Watch)")
SCHEMA = "ipr-vn-mod-en-defrel-access-observation/1"
MAX_ROBOTS = 65536
MAX_LISTING = 393216
TIMEOUT = 15
INTERVAL = 2.0
SAMPLE_CAP = 8


class ProbeBlocked(ValueError):
    """A negative observation, NOT permission to try a different route."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class DetailLinks(HTMLParser):
    """Observe URLs only. No article body, titles, bylines or page HTML saved."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.identities = set()
        self.anchor_count = 0

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        self.anchor_count += 1
        href = dict(attrs).get("href")
        if not href or len(href) > 1800:
            return
        url = urljoin(LISTING, href)
        try:
            identity = article_identity(url)
        except MODCanaryRefused:
            return
        self.identities.add(identity["source_identity"])


def get_once(url, cap, *, opener=None):
    """Same-origin/no-redirect bounded GET; no automatic retries or cookies."""
    if url not in (ROBOTS, LISTING):
        raise ProbeBlocked("non-allowlisted-request")
    client = opener or urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "text/plain" if url == ROBOTS
                      else "text/html"},
    )
    try:
        with client.open(req, timeout=TIMEOUT) as response:
            if response.geturl() != url:
                raise ProbeBlocked("redirect-or-different-final-url")
            if response.status != 200:
                raise ProbeBlocked("http-status-" + str(response.status))
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            required = "text/plain" if url == ROBOTS else "text/html"
            if content_type != required:
                raise ProbeBlocked("unexpected-content-type")
            data = response.read(cap + 1)
            if len(data) > cap:
                raise ProbeBlocked("body-too-large")
            if not data:
                raise ProbeBlocked("empty-response")
            return data
    except urllib.error.HTTPError as exc:
        raise ProbeBlocked("http-status-" + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProbeBlocked("access-unavailable") from None


def validate_robots(data):
    """A readable, explicit allow from publisher robots is necessary, not sufficient."""
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ProbeBlocked("robots-not-utf8") from None
    if "<html" in content.lower() or "<!doctype" in content.lower():
        raise ProbeBlocked("robots-is-html")
    if not any(line.lstrip().lower().startswith("user-agent:") for line in content.splitlines()):
        raise ProbeBlocked("robots-missing-user-agent")
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(content.splitlines())
    if not parser.can_fetch(UA, LISTING):
        raise ProbeBlocked("robots-disallow-listing")
    return True


def inspect_listing(data):
    try:
        page = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ProbeBlocked("listing-not-utf8") from None
    initial = page[:20000].casefold()
    if any(mark in initial for mark in (
        "cf-mitigated", "just a moment", "enable javascript and cookies",
        "captcha", "access denied", "verify you are human",
    )):
        raise ProbeBlocked("challenge-or-denial-page")
    if "<html" not in initial or "<a " not in page.casefold():
        raise ProbeBlocked("not-a-normal-listing")
    parser = DetailLinks()
    try:
        parser.feed(page)
        parser.close()
    except (ValueError, TypeError):
        raise ProbeBlocked("malformed-listing") from None
    return {
        "link_elements_seen": parser.anchor_count,
        "recognized_stable_detail_id_count": len(parser.identities),
        "example_identity_keys": sorted(parser.identities)[:SAMPLE_CAP],
        "zero_ids_may_mean_widget_navigation": len(parser.identities) == 0,
    }


def probe(*, request=get_once, sleep=time.sleep):
    """Never bypass denial; never claim qualification from a green access check."""
    result = {
        "schema": SCHEMA,
        "source": "vietnam-mod-english-defence-relations",
        "status": "blocked",
        "robots_checked": False,
        "listing_checked": False,
        "requests_attempted": 0,
        "article_bodies_fetched": 0,
        "source_rights_approved": False,
        "collection_enabled": False,
        "shadow_state_created": False,
        "model_use_approved": False,
        "production_admission_approved": False,
        "evidence_of_current_week_coverage": False,
    }
    result["requests_attempted"] = 1
    try:
        robots = request(ROBOTS, MAX_ROBOTS)
        validate_robots(robots)
        result["robots_checked"] = True
        sleep(INTERVAL)
        result["requests_attempted"] = 2
        listing = request(LISTING, MAX_LISTING)
        summary = inspect_listing(listing)
        result["listing_checked"] = True
        result.update(summary)
        result["status"] = "metadata-access-observed-not-source-approved"
    except ProbeBlocked as exc:
        result["blocked_reason"] = str(exc)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-live-probe", action="store_true",
                        help="explicit one-time live GET authorization; no collection")
    args = parser.parse_args(argv)
    if not args.approve_live_probe:
        parser.error("refusing all live network use without --approve-live-probe")
    result = probe()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "metadata-access-observed-not-source-approved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
