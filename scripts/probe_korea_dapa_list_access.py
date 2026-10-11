"""Korea DAPA government portal: at most TWO deliberately authorized GETs.

This is a manual metadata-only access observation, never a collector:
- publisher robots.txt first; STOP if denied, unreadable or challenged;
- only if robots permits, one bounded DAPA-filtered listing GET;
- no press-release article, HWPX, PDF, source body persistence or source grant.

A successful probe never qualifies DAPA, Korea or any use of publisher text.
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

from scripts.review_korea_dapa_source_contract import (
    DAPASourceHold, article_identity, listing_filter,
)
from scripts.probe_vietnam_mod_defrel_access import NoRedirect

HOST = "https://www.korea.kr"
ROBOTS = HOST + "/robots.txt"
DAPA_LISTING = (HOST + "/briefing/pressReleaseList.do?"
                "pWiseMinistry=ministryNews&repCode=B00008&"
                "repCodeType=%EC%A0%95%EB%B6%80%EB%B6%80%EC%B2%98")
USER_AGENT = ("ChinaMilWatch/1.0 (+https://github.com/"
              "VSSpowerlifting/China-Mil-Watch; metadata-only official source research)")
SCHEMA = "ipr-korea-dapa-official-listing-access/1"
MAX_ROBOTS = 32768
MAX_LISTING = 350000
TIMEOUT = 15
SLEEP = 2.0
MAX_IDENTITIES = 6


class AccessRefused(ValueError):
    pass


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchor_count = 0
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        self.anchor_count += 1
        href = dict(attrs).get("href")
        if not isinstance(href, str) or not 0 < len(href) < 2000:
            return
        try:
            ident = article_identity(urljoin(DAPA_LISTING, href))
        except (DAPASourceHold, ValueError):
            return
        self.ids.add(ident["source_identity"])


def request_once(url, limit, *, opener=None):
    """One disclosed, same-URL GET; no redirects, retries or cookie state."""
    if url not in (ROBOTS, DAPA_LISTING):
        raise AccessRefused("nonallowlisted route")
    client = opener or urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/plain" if url == ROBOTS else "text/html",
    }, method="GET")
    try:
        with client.open(req, timeout=TIMEOUT) as response:
            if response.status != 200 or response.geturl() != url:
                raise AccessRefused("HTTP non-200 or redirect")
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind != ("text/plain" if url == ROBOTS else "text/html"):
                raise AccessRefused("unexpected content type")
            content = response.read(limit + 1)
            if not content or len(content) > limit:
                raise AccessRefused("empty or oversized publisher response")
            return content
    except urllib.error.HTTPError as exc:
        raise AccessRefused("HTTP " + str(exc.code)) from None
    except (OSError, TimeoutError, urllib.error.URLError):
        raise AccessRefused("publisher unavailable") from None


def robots_permit(data):
    try:
        body = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AccessRefused("robots not UTF-8") from None
    if "<html" in body.lower() or not any(
        x.strip().lower().startswith("user-agent") for x in body.splitlines()
    ):
        raise AccessRefused("robots absent, replaced or challenged")
    policy = urllib.robotparser.RobotFileParser()
    policy.parse(body.splitlines())
    if not policy.can_fetch(USER_AGENT, DAPA_LISTING):
        raise AccessRefused("robots disallows DAPA listing")
    return True


def inspect_listing(data):
    try:
        body = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AccessRefused("listing not UTF-8") from None
    first = body[:18000].lower()
    if any(x in first for x in (
        "cf-mitigated", "captcha", "verify you are human",
        "just a moment", "access denied",
    )):
        raise AccessRefused("listing is an access challenge")
    if "<html" not in first or "<a " not in body.lower():
        raise AccessRefused("not a normal publisher HTML listing")
    p = Links()
    try:
        p.feed(body)
        p.close()
    except (TypeError, ValueError):
        raise AccessRefused("malformed publisher listing markup") from None
    return {
        "anchor_elements": p.anchor_count,
        "candidate_article_id_count": len(p.ids),
        "sample_candidate_identities": sorted(p.ids)[:MAX_IDENTITIES],
        "zero_candidate_ids_does_not_prove_no_publications": len(p.ids) == 0,
    }


def probe(*, fetch=request_once, sleep=time.sleep):
    listing_filter(DAPA_LISTING)  # Code/issuer filter is a fixed validated URL.
    out = {
        "schema": SCHEMA, "publisher": "www.korea.kr",
        "institution": "방위사업청", "portal_filter": "B00008",
        "state": "blocked", "requests_attempted": 0,
        "robots_checked": False, "listing_checked": False,
        "article_body_requests": 0, "attachment_requests": 0,
        "publisher_article_text_saved": False,
        "source_issuer_attribution_verified": False,
        "source_rights_approved": False,
        "hwpx_pdf_license_approved": False,
        "collector_enabled": False, "korea_desk_activated": False,
    }
    try:
        out["requests_attempted"] = 1
        rules = fetch(ROBOTS, MAX_ROBOTS)
        robots_permit(rules)
        out["robots_checked"] = True
        sleep(SLEEP)
        out["requests_attempted"] = 2
        listing = fetch(DAPA_LISTING, MAX_LISTING)
        out.update(inspect_listing(listing))
        out["listing_checked"] = True
        out["state"] = "metadata_access_observed_filter_not_verified"
    except AccessRefused as exc:
        out["reason"] = str(exc)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approve-one-time-access-check", action="store_true",
                   help="explicitly authorize one robots GET and, if allowed, one listing GET")
    args = p.parse_args(argv)
    if not args.approve_one_time_access_check:
        p.error("network is disabled without explicit one-time authorization")
    data = probe()
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0 if data["state"] == "metadata_access_observed_filter_not_verified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
