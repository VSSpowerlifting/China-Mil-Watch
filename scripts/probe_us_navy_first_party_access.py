"""Read-only access canary for bounded first-party U.S. institutional listings.

No feed collection, archive, metadata admission, Pages write or retries.
Refuse redirects, unusable robots policies and cross-origin content. This is
NOT a substitute for human source/rights review or reliability qualification.
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

SCHEMA = "ipr-us-first-party-navy-access-canary/1"
AGENT = "IndoPacificRecordResearchBot/1.0 (+https://indopacificrecord.org/about.html)"
SOURCES = (
    ("seventh_fleet", "www.c7f.navy.mil", "/Media/News/"),
    ("pacific_fleet", "www.cpf.navy.mil", "/Newsroom/News/"),
    ("us_china_commission", "www.uscc.gov", "/press-releases"),
)
TIMEOUT = 12
MAX_ROBOTS_BYTES = 128_000
MAX_LISTING_BYTES = 160_000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class AccessHold(ValueError):
    pass


def validate_targets(sources=SOURCES):
    if sources != SOURCES:
        raise AccessHold("source_hosts_or_paths_changed")
    if any(host not in ("www.c7f.navy.mil", "www.cpf.navy.mil", "www.uscc.gov") or not path.startswith("/")
           or "?" in path or ".." in path
           for _, host, path in sources):
        raise AccessHold("untrusted_source_route")
    return sources


def _fetch(opener, url, limit):
    req = urllib.request.Request(
        url, headers={"User-Agent": AGENT, "Accept": "text/plain,text/html"})
    try:
        with opener.open(req, timeout=TIMEOUT) as response:
            status = response.getcode()
            actual = response.geturl()
            if status != 200 or actual != url:
                return None, "unexpected_http_or_redirect"
            raw = response.read(limit + 1)
            if len(raw) > limit:
                return None, "oversize_response"
            return (raw, "ok") if raw else (None, "empty_response")
    except urllib.error.HTTPError as exc:
        return None, "http_" + str(exc.code)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None, "transport_or_policy_unavailable"


def probe_one(name, host, path, opener):
    robots_url = "https://" + host + "/robots.txt"
    listing_url = "https://" + host + path
    result = {"source": name, "host": host, "listing": path,
              "robots_policy": "unavailable", "listing_reachable": False,
              "collection_authorized": False, "source_day_qualified": False}
    policy, status = _fetch(opener, robots_url, MAX_ROBOTS_BYTES)
    if status != "ok":
        result["robots_policy"] = status
        return result
    try:
        text = policy.decode("utf-8")
    except UnicodeError:
        result["robots_policy"] = "non_utf8_policy"
        return result
    # App shells and anti-bot challenges are NOT robots files.
    if "<html" in text.lower() or "<script" in text.lower() or (
        "user-agent:" not in text.lower()):
        result["robots_policy"] = "not_a_usable_robots_policy"
        return result
    robots = urllib.robotparser.RobotFileParser(robots_url)
    robots.parse(text.splitlines())
    if not robots.can_fetch(AGENT, listing_url):
        result["robots_policy"] = "disallows_listings"
        return result
    result["robots_policy"] = "permits_bounded_listing_request"
    body, listing_status = _fetch(opener, listing_url, MAX_LISTING_BYTES)
    if listing_status == "ok" and body is not None and (
        b"<html" in body.lower() or b"<!doctype" in body.lower()):
        result["listing_reachable"] = True
    else:
        result["listing_failure"] = (listing_status if listing_status != "ok"
                                    else "not_an_html_listing")
    # Robots allow is not source use permission, safe collector authentication,
    # originality proof, reliability, completeness or publication authority.
    return result


def run(opener=None):
    validate_targets()
    if opener is None:
        opener = urllib.request.build_opener(NoRedirect)
    rows = [probe_one(*p, opener) for p in SOURCES]
    return {"schema": SCHEMA, "scope": "one_bounded_manual_http_probe",
            "results": rows, "originals_stored": 0, "records_collected": 0,
            "production_records_written": 0, "website_changed": False,
            "new_source_day_claimed": False,
            "all_sources_collection_authorized": False}


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-authorized-readonly-probe",
                        action="store_true", required=True)
    opts = parser.parse_args(args)
    if not opts.owner_authorized_readonly_probe:
        raise SystemExit("Missing explicit access-probe authorization")
    print(json.dumps(run(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
