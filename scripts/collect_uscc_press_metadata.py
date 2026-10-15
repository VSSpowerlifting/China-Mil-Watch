"""USCC official press-release listing -> bounded URL/date/issuer metadata only.

A successful run is a truthful *listing observation*, not completeness,
publisher-content preservation, production database admission or source-use
approval. No individual press article, title, body, attachment or image is read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.robotparser
from datetime import date, datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from scripts.probe_us_navy_first_party_access import AGENT, MAX_ROBOTS_BYTES, NoRedirect, _fetch
import urllib.request

SCHEMA = "ipr-uscc-firstparty-official-link-metadata/1"
HOST = "www.uscc.gov"
INDEX = "https://www.uscc.gov/press-releases"
ROBOTS = "https://www.uscc.gov/robots.txt"
MAX_BYTES = 160_000
MAX_ROWS = 75
ID = re.compile(r"/press-releases/(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)/\Z")
DATE_US = re.compile(r"(?<!\d)(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>20\d{2})(?!\d)")
DATE_ISO = re.compile(r"(?<!\d)(?P<year>20\d{2})-(?P<month>\d{2})-(?P<day>\d{2})(?!\d)")

class USCCHold(ValueError):
    pass

def need(ok, reason):
    if not ok:
        raise USCCHold(reason)

def parse_day(text):
    us = DATE_US.search(text)
    iso = DATE_ISO.search(text)
    match = us if us else iso
    if not match:
        return None
    try:
        parsed = date(int(match["year"]),int(match["month"]),int(match["day"]))
    except ValueError:
        return None
    return parsed.isoformat()

def canonical(raw):
    url = urllib.parse.urlsplit(urllib.parse.urljoin(INDEX, raw))
    if (url.scheme != "https" or url.netloc != HOST or url.query
            or url.fragment or url.username or url.password):
        return None
    path = url.path
    match = ID.fullmatch(path.rstrip("/")+"/")
    if match is None:
        return None
    return "https://" + HOST + path.rstrip("/"), match["slug"]

def find_listing_date(anchor):
    # A date from a sibling card or global page header must never be joined
    # to another release. The smallest recognized card is the proof boundary.
    card = anchor.find_parent(class_="views-row") or anchor.find_parent("article")
    if not isinstance(card, Tag):
        return None
    text = card.get_text(" ", strip=True)
    if not text or len(text)>2200:
        return None
    verified = parse_day(text)
    if verified is None:
        return None
    links = {
        x for item in card.find_all("a", href=True)
        if (x := canonical(item["href"])) is not None
    }
    if len(links) != 1 or canonical(anchor["href"]) not in links:
        return None
    return verified


def extract(html, *, as_of):
    need(type(html) is bytes and len(html) <= MAX_BYTES
         and (b"<html" in html.lower() or b"<!doctype" in html.lower()),
         "not_an_official_html_listing")
    soup=BeautifulSoup(html,"html.parser")
    need(soup.find("a") is not None,"no_publisher_links")
    unique={}
    for anchor in soup.find_all("a",href=True):
        c=canonical(anchor["href"])
        if c is None:
            continue
        url,slug=c
        # Page navigation/sidebars are not listing entries; only a bounded
        # official listing card may provide an authoritative date.
        if not (anchor.find_parent(class_="views-row") or
                anchor.find_parent("article")):
            continue
        stamp=find_listing_date(anchor)
        need(stamp is not None, "dated_official_listing_card_missing")
        need(stamp <= as_of and "2025-01-01" <= stamp, "untrusted_source_date")
        ident="uscc-press:"+slug
        row={"source_identity":ident,"canonical_official_url":url,
             "publisher_posted_date":stamp,
             "official_issuer":"us_china_economic_security_review_commission",
             "official_publisher":"www.uscc.gov",
             "publisher_listing_url":INDEX}
        if ident in unique:
            need(unique[ident]==row,"duplicate_press_identity_disagrees")
        unique[ident]=row
    need(1 <= len(unique) <= MAX_ROWS,"no_verifiable_dated_press_items")
    return sorted(unique.values(), key=lambda x:(x["publisher_posted_date"],x["source_identity"]),reverse=True)

def collect(*, opener=None, as_of=None):
    as_of=as_of or datetime.now(timezone.utc).date().isoformat()
    need(date.fromisoformat(as_of).isoformat()==as_of,"invalid_observation_day")
    opener=opener or urllib.request.build_opener(NoRedirect)
    policy,status=_fetch(opener,ROBOTS,MAX_ROBOTS_BYTES)
    need(status=="ok" and policy is not None,"uscc_robots_"+status)
    try:
        text=policy.decode("utf-8")
    except UnicodeError:
        raise USCCHold("uscc_robots_not_text") from None
    need("user-agent:" in text.lower() and "<html" not in text.lower()
         and "<script" not in text.lower(),"uscc_robots_not_usable")
    parser=urllib.robotparser.RobotFileParser(ROBOTS)
    parser.parse(text.splitlines())
    need(parser.can_fetch(AGENT,INDEX),"uscc_listing_disallowed_by_policy")
    payload,status=_fetch(opener,INDEX,MAX_BYTES)
    need(status=="ok" and payload is not None,"uscc_listing_"+status)
    rows=extract(payload,as_of=as_of)
    return {"schema":SCHEMA,"source_host":HOST,"source_family":"uscc_press_releases",
            "publisher":"U.S.-China Economic and Security Review Commission",
            "issuer":"us_china_economic_security_review_commission",
            "collection_mode":"bounded_official_listing_metadata_only",
            "observed_on_utc":as_of,
            "official_listing_url":INDEX,
            "official_listing_sha256":hashlib.sha256(payload).hexdigest(),
            "rows":rows,"visible_dated_rows":len(rows),
            "original_titles_copied":False,"bodies_copied":False,
            "document_media_copied":False,"analysis_performed":False,
            "publication_authorized_by_collector":False,
            "production_records_written":0,
            "complete_publisher_history_claimed":False}

def main(args=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--owner-authorized-readonly-collection",
                    action="store_true",required=True)
    ap.add_argument("--private-output", default="")
    arg=ap.parse_args(args)
    try:
        result=collect()
        output=json.dumps(result,sort_keys=True,ensure_ascii=False,
                          separators=(",",":"))+"\n"
        if arg.private_output:
            f=Path(arg.private_output)
            need(f.is_absolute() and not f.exists() and not f.is_symlink()
                 and f.parent.is_dir(),"output_must_be_new_absolute_file")
            fd=f.open("x",encoding="utf-8")
            with fd as stream:
                stream.write(output)
            f.chmod(0o600)
        # Only factual metadata in stdout, NEVER a publisher body/headline.
        print(json.dumps({"schema":SCHEMA,"status":"PASS_METADATA_ONLY",
                          "source_host":HOST,
                          "verified_official_link_rows":result["visible_dated_rows"],
                          "listing_sha256":result["official_listing_sha256"],
                          "source_originals_copied":False,
                          "production_rows":0,
                          "public_page_modified":False},sort_keys=True))
        return 0
    except (USCCHold, ValueError, OSError) as exc:
        reason=str(exc) if isinstance(exc,USCCHold) else "source_or_state_unavailable"
        print(json.dumps({"schema":SCHEMA,"status":"HOLD","reason":reason,
                          "source_day_qualified":False,
                          "production_rows":0,"public_page_modified":False},
                         sort_keys=True))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
