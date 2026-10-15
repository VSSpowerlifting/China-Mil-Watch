"""BIS exact first-party homepage teaser -> dated official URL/issuer only.

Reads robots.txt followed by one bounded homepage if policy allows. Does not
fetch individual articles, /news-updates, headlines, bodies, media or analysis.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date, datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup, Tag
from scripts.probe_us_navy_first_party_access import AGENT, MAX_ROBOTS_BYTES, NoRedirect, _fetch

SCHEMA = "ipr-us-bis-homepage-official-link-metadata/1"
HOST = "www.bis.gov"
INDEX = "https://www.bis.gov/"
ROBOTS = "https://www.bis.gov/robots.txt"
ISSUER = "us_bureau_of_industry_and_security"
FAMILY = "us_bis_homepage_press_release_teasers"
MAX_BYTES = 160_000
MAX_ROWS = 20
RELEASE = re.compile(r"/press-release/(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)/?\Z")
HUMAN = re.compile(r"(?i)\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-9]{1,2}),\s+(20[0-9]{2})\b")
MONTHS = dict(zip(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"), range(1, 13)))

class BISHold(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise BISHold(reason)

def canonical(raw):
    if not isinstance(raw, str) or any(x in raw for x in "\r\n\t"):
        return None
    try:
        value = urllib.parse.urlsplit(urllib.parse.urljoin(INDEX, raw))
    except (ValueError, TypeError):
        return None
    if (value.scheme != "https" or value.netloc != HOST or value.query
            or value.fragment or value.username or value.password
            or "%" in value.path or "\\" in value.path):
        return None
    match = RELEASE.fullmatch(value.path)
    if match is None:
        return None
    slug = match["slug"]
    return "https://" + HOST + "/press-release/" + slug, slug

def posted_day(card):
    text = card.get_text(" ", strip=True)
    need(0 < len(text) <= 3500, "unbounded_or_empty_release_card")
    matches = list(HUMAN.finditer(text))
    need(len(matches) == 1, "non_unique_or_missing_card_date")
    found = matches[0]
    try:
        return date(int(found[3]), MONTHS[found[1].lower()], int(found[2])).isoformat()
    except ValueError:
        raise BISHold("invalid_publisher_date") from None

def extract(html, *, as_of):
    need(type(html) is bytes and 100 <= len(html) <= MAX_BYTES
         and (b"<html" in html.lower() or b"<!doctype" in html.lower()),
         "not_a_bounded_bis_homepage")
    soup = BeautifulSoup(html, "html.parser")
    # PR #692's real publisher DOM: 4 separately dated cards, each li.p-4.
    # The enclosing ul carries multiple release links and cannot supply dates.
    cards = soup.select("section.py-8 ul.grid > li.p-4")
    need(bool(cards), "homepage_teaser_structure_missing")
    unique = {}
    for card in cards:
        need(isinstance(card, Tag), "invalid_release_card")
        releases = [entry for anchor in card.select("a[href]")
                    if (entry := canonical(anchor["href"])) is not None]
        if not releases:
            continue  # Unrelated homepage teasers are not press releases.
        need(len(releases) == 1, "multiple_press_links_in_card")
        url, slug = releases[0]
        day = posted_day(card)
        need("2025-01-01" <= day <= as_of, "publisher_date_out_of_range")
        identity = "us-bis-homepage-press:" + slug
        row = {"source_identity": identity,
               "canonical_official_url": url,
               "publisher_posted_date": day,
               "official_issuer": ISSUER,
               "official_publisher": HOST,
               "publisher_listing_url": INDEX}
        if identity in unique:
            need(unique[identity] == row, "conflicting_press_identity")
        unique[identity] = row
    need(1 <= len(unique) <= MAX_ROWS, "no_independently_dated_homepage_releases")
    return sorted(unique.values(),
                  key=lambda row: (row["publisher_posted_date"], row["source_identity"]),
                  reverse=True)

def collect(*, opener=None, as_of=None):
    as_of = as_of or datetime.now(timezone.utc).date().isoformat()
    try:
        need(isinstance(as_of, str) and date.fromisoformat(as_of).isoformat() == as_of,
             "invalid_observation_day")
    except (ValueError, TypeError):
        raise BISHold("invalid_observation_day") from None
    opener = opener or urllib.request.build_opener(NoRedirect)
    policy, status = _fetch(opener, ROBOTS, MAX_ROBOTS_BYTES)
    need(status == "ok" and policy is not None, "bis_robots_" + status)
    try:
        text = policy.decode("utf-8")
    except UnicodeError:
        raise BISHold("bis_robots_not_utf8") from None
    need("user-agent:" in text.lower() and "<html" not in text.lower()
         and "<script" not in text.lower(), "bis_robots_not_usable")
    parser = urllib.robotparser.RobotFileParser(ROBOTS)
    parser.parse(text.splitlines())
    need(parser.can_fetch(AGENT, INDEX), "bis_homepage_robots_disallow")
    payload, status = _fetch(opener, INDEX, MAX_BYTES)
    need(status == "ok" and payload is not None, "bis_homepage_" + status)
    rows = extract(payload, as_of=as_of)
    return {"schema": SCHEMA, "source_host": HOST,
            "source_family": FAMILY,
            "publisher": "U.S. Department of Commerce, Bureau of Industry and Security",
            "issuer": ISSUER,
            "collection_mode": "bounded_exact_homepage_metadata_only",
            "observed_on_utc": as_of,
            "official_listing_url": INDEX,
            "official_listing_sha256": hashlib.sha256(payload).hexdigest(),
            "rows": rows, "visible_dated_rows": len(rows),
            "original_titles_copied": False, "bodies_copied": False,
            "document_media_copied": False, "analysis_performed": False,
            "publication_authorized_by_collector": False,
            "production_records_written": 0,
            "complete_publisher_history_claimed": False}

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-authorized-readonly-collection",
                        action="store_true", required=True)
    parser.add_argument("--private-output", default="")
    args = parser.parse_args(argv)
    try:
        packet = collect()
        if args.private_output:
            path = Path(args.private_output)
            need(path.is_absolute() and not path.exists()
                 and not path.is_symlink() and path.parent.is_dir(),
                 "private_output_must_be_new_absolute_file")
            with path.open("x", encoding="utf-8") as output:
                json.dump(packet, output, sort_keys=True, separators=(",", ":"))
                output.write("\n")
            path.chmod(0o600)
        print(json.dumps({"schema": SCHEMA, "status": "PASS_METADATA_ONLY",
                          "verified_official_link_rows": len(packet["rows"]),
                          "listing_sha256": packet["official_listing_sha256"],
                          "originals_retained": False, "production_records": 0,
                          "site_modified": False, "scheduled_day_qualified": False},
                         sort_keys=True))
        return 0
    except (BISHold, ValueError, OSError) as exc:
        print(json.dumps({"schema": SCHEMA, "status": "HOLD",
                          "reason": str(exc) if isinstance(exc, BISHold)
                                    else "source_or_state_unavailable",
                          "production_records": 0, "site_modified": False,
                          "scheduled_day_qualified": False}, sort_keys=True))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
