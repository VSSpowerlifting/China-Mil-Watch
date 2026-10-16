"""Manual robots-first availability observation for DAPA's OWN official site.

This is an independent OFF-BY-DEFAULT source lead, not an alternative way to
circumvent a failed korea.kr request. No crawling, retries, document requests,
file persistence, author attribution, reuse clearance, or production writes.
The one-time approval for korea.kr does NOT authorize this separate host.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

from scripts.probe_vietnam_mod_defrel_access import NoRedirect

HOST = "https://www.dapa.go.kr"
ROBOTS = HOST + "/robots.txt"
LISTING = HOST + "/dapa/doc/selectDocList.do?bbsSeq=326&menuSeq=3069"
USER_AGENT = "IndoPacificRecord/1.0 (+https://indopacificrecord.org; DAPA metadata-only source research)"
SCHEMA = "ipr-korea-dapa-native-listing-access/1"
MAX_ROBOTS = 32768
MAX_LISTING = 350000
MAX_SAMPLES = 6
TIMEOUT = 15
PAUSE = 2.0


class AccessHold(ValueError):
    """Fixed codes only. Never reveal source response bodies or secrets."""


def fetch_once(url, cap, *, opener=None):
    if (url, cap) not in ((ROBOTS, MAX_ROBOTS), (LISTING, MAX_LISTING)):
        raise AccessHold("unapproved_dapa_native_destination")
    client = opener or urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/plain" if url == ROBOTS else "text/html",
    })
    try:
        with client.open(req, timeout=TIMEOUT) as response:
            if response.status != 200 or response.geturl() != url:
                raise AccessHold("publisher_http_status_or_redirect")
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind != ("text/plain" if url == ROBOTS else "text/html"):
                raise AccessHold("publisher_content_type_unexpected")
            content = response.read(cap + 1)
            if not content or len(content) > cap:
                raise AccessHold("publisher_body_empty_or_oversize")
            return content
    except urllib.error.HTTPError:
        raise AccessHold("publisher_http_denied_or_redirected") from None
    except (TimeoutError, OSError, urllib.error.URLError):
        raise AccessHold("publisher_network_unavailable") from None


def robots_allow(data):
    try:
        body = data.decode("utf-8-sig")
    except UnicodeError:
        raise AccessHold("publisher_robots_not_utf8") from None
    if "<html" in body.lower() or not any(
        line.strip().lower().startswith("user-agent:") for line in body.splitlines()
    ):
        raise AccessHold("publisher_robots_unreadable_or_challenged")
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(body.splitlines())
    if not robots.can_fetch(USER_AGENT, LISTING):
        raise AccessHold("publisher_robots_disallow_listing")
    return True


def provisional_doc_sequence(href):
    """Parser-only numeric lead; NEVER a confirmed item identity or issuer."""
    if not isinstance(href, str) or not (0 < len(href) < 2000):
        return None
    parsed = urlsplit(urljoin(LISTING, href))
    if (parsed.scheme != "https" or parsed.netloc != "www.dapa.go.kr"
            or parsed.path != "/dapa/doc/selectDoc.do"
            or parsed.fragment or parsed.username or parsed.password):
        return None
    try:
        query = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        return None
    if (set(query) - {"bbsSeq", "docSeq", "menuSeq"}
            or any(len(values) != 1 for values in query.values())
            or query.get("bbsSeq") != ["326"]
            or ("menuSeq" in query and query["menuSeq"] != ["3069"])):
        return None
    number = query.get("docSeq", [""])[0]
    return number if re.fullmatch(r"[1-9][0-9]{0,19}", number) else None


class Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = 0
        self.docseq = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        self.links += 1
        seq = provisional_doc_sequence(dict(attrs).get("href"))
        if seq is not None:
            self.docseq.add(seq)


def inspect_listing(data):
    try:
        body = data.decode("utf-8-sig")
    except UnicodeError:
        raise AccessHold("publisher_listing_not_utf8") from None
    first = body[:18000].lower()
    if any(marker in first for marker in (
        "captcha", "verify you are human", "cf-mitigated", "just a moment",
        "access denied",
    )):
        raise AccessHold("publisher_listing_challenge")
    if "<html" not in first or "<a " not in body.lower():
        raise AccessHold("publisher_listing_unrecognized_markup")
    parser = Anchors()
    try:
        parser.feed(body)
        parser.close()
    except (ValueError, TypeError):
        raise AccessHold("publisher_listing_invalid_markup") from None
    ids = sorted(parser.docseq, key=lambda value: int(value))
    return {
        "observed_anchor_count": parser.links,
        "provisional_docseq_count": len(ids),
        "sample_unverified_docseq": ids[:MAX_SAMPLES],
        "zero_matching_links_is_not_zero_publications": len(ids) == 0,
    }


def probe(*, fetch=fetch_once, sleep=time.sleep):
    record = {
        "schema": SCHEMA,
        "publisher": "www.dapa.go.kr",
        "surface": "dapa_native_press_releases_bbsSeq_326",
        "state": "blocked",
        "requests_attempted": 0,
        "robots_checked": False,
        "listing_checked": False,
        "article_requests": 0,
        "attachment_requests": 0,
        "original_text_saved": False,
        "dapa_issuer_per_article_verified": False,
        "rights_cleared": False,
        "collector_enabled": False,
        "production_published": False,
    }
    try:
        record["requests_attempted"] = 1
        robots_allow(fetch(ROBOTS, MAX_ROBOTS))
        record["robots_checked"] = True
        sleep(PAUSE)
        record["requests_attempted"] = 2
        record.update(inspect_listing(fetch(LISTING, MAX_LISTING)))
        record["listing_checked"] = True
        record["state"] = "listing_shape_observed_unverified"
    except AccessHold as exc:
        record["reason_code"] = str(exc)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--approve-one-time-direct-dapa-access", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_one_time_direct_dapa_access:
        parser.error("separate first-party DAPA host permission required")
    report = probe()
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0 if report["state"] == "listing_shape_observed_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
