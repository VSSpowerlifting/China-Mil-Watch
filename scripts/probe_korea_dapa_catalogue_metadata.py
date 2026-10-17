"""Separately owner-authorized DAPA public-data catalogue JSON identity probe.

Reads at most robots.txt and the exact public Schema.org metadata record.
No HWPX or data-file GET, article collection, state write, source grant,
publications, log of government JSON or redirect/fallback to other hosts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urlsplit

from scripts.probe_vietnam_mod_defrel_access import NoRedirect
from scripts.qualify_korea_dapa_official_catalogue import (
    CatalogueHold, CATALOGUE_JSON_URL, MAX_INPUT_BYTES, qualify,
)

HOST = "https://www.data.go.kr"
ROBOTS = HOST + "/robots.txt"
JSON_URL = CATALOGUE_JSON_URL
USER_AGENT = ("IndoPacificRecord/1.0 "
              "(+https://indopacificrecord.org; public catalogue metadata audit)")
MAX_ROBOTS = 32768
MAX_JSON = MAX_INPUT_BYTES
TIMEOUT = 15
PAUSE_SECONDS = 2.0
SCHEMA = "ipr-korea-dapa-public-data-catalogue-one-time-access/1"


class ProbeHold(ValueError):
    """Only fixed reason codes; never raise/log publisher content."""


def get_once(url, limit, *, opener=None):
    """One exact HTTPS endpoint GET without redirects, cookies, retries or fallback."""
    if (url, limit) not in ((ROBOTS, MAX_ROBOTS), (JSON_URL, MAX_JSON)):
        raise ProbeHold("catalogue_destination_not_allowlisted")
    client = opener or urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/plain" if url == ROBOTS else "application/json",
    })
    try:
        with client.open(req, timeout=TIMEOUT) as response:
            if response.status != 200 or response.geturl() != url:
                raise ProbeHold("catalogue_http_status_or_redirect")
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if url == ROBOTS:
                if kind != "text/plain":
                    raise ProbeHold("catalogue_robots_content_type")
            elif kind not in ("application/json", "application/ld+json"):
                raise ProbeHold("catalogue_json_content_type")
            content = response.read(limit + 1)
            if not content or len(content) > limit:
                raise ProbeHold("catalogue_empty_or_oversized")
            return content
    except urllib.error.HTTPError:
        raise ProbeHold("catalogue_http_denied_or_redirected") from None
    except (OSError, TimeoutError, urllib.error.URLError):
        raise ProbeHold("catalogue_publisher_unavailable") from None


def check_robots(raw):
    try:
        txt = raw.decode("utf-8-sig")
    except UnicodeError:
        raise ProbeHold("catalogue_robots_not_utf8") from None
    if "<html" in txt.lower() or not any(
        line.strip().lower().startswith("user-agent:") for line in txt.splitlines()
    ):
        raise ProbeHold("catalogue_robots_missing_or_challenged")
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(txt.splitlines())
    if not parser.can_fetch(USER_AGENT, JSON_URL):
        raise ProbeHold("catalogue_robots_disallows_json")
    return True


def observe(*, fetch=get_once, sleep=time.sleep):
    out = {
        "schema": SCHEMA,
        "state": "HOLD",
        "host": "www.data.go.kr",
        "catalogue_id": "15118819",
        "requests_attempted": 0,
        "robots_allowed": False,
        "json_retrieved": False,
        "catalogue_identity_verified": False,
        "item_records_verified": 0,
        "article_requests": 0,
        "hwpx_requests": 0,
        "publication_authorized": False,
        "production_written": False,
        "publisher_body_logged": False,
    }
    try:
        out["requests_attempted"] = 1
        check_robots(fetch(ROBOTS, MAX_ROBOTS))
        out["robots_allowed"] = True
        sleep(PAUSE_SECONDS)
        out["requests_attempted"] = 2
        raw = fetch(JSON_URL, MAX_JSON)
        out["json_retrieved"] = True
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise ProbeHold("catalogue_json_invalid") from None
        try:
            receipt = qualify(payload)
        except CatalogueHold:
            raise ProbeHold("catalogue_metadata_identity_hold") from None
        # Receipt fields originate from exact publisher/version/rights-shape
        # matches. No raw publisher JSON, article, HWPX link or title printed.
        out["catalogue_identity_verified"] = True
        out["catalogue_json_sha256"] = hashlib.sha256(raw).hexdigest()
        out["verified_dataset_version"] = receipt["verified_dataset_version"]
        out["declared_rows_independently_verified"] = False
        out["state"] = "CATALOGUE_METADATA_ONLY_VERIFIED"
    except ProbeHold as exc:
        out["reason_code"] = str(exc)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--approve-one-time-data-go-kr-metadata", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_one_time_data_go_kr_metadata:
        parser.error("explicit separate www.data.go.kr authorization required")
    result = observe()
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0 if result["state"] == "CATALOGUE_METADATA_ONLY_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
