"""Treasury official first-party press listing -> dated URL/issuer metadata.

Exact policy-first, one-listing observation. Never fetches article bodies,
stores headlines, claims complete coverage or authorizes publication.
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
from scripts.probe_us_navy_first_party_access import (
    AGENT, MAX_ROBOTS_BYTES, NoRedirect, _fetch
)

SCHEMA = "ipr-us-treasury-firstparty-official-link-metadata/1"
HOST = "home.treasury.gov"
INDEX = "https://home.treasury.gov/news/press-releases"
ROBOTS = "https://home.treasury.gov/robots.txt"
ISSUER = "us_department_treasury"
MAX_BYTES = 160_000
MAX_ROWS = 75
ID = re.compile(r"/news/press-releases/(?P<slug>sb[0-9]{4,6})/?\Z")
ISO = re.compile(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}")
HUMAN = re.compile(
    r"(?i)\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+([0-9]{1,2}),?\s+(20[0-9]{2})\b"
)
MONTHS = dict(zip(("january","february","march","april","may","june",
    "july","august","september","october","november","december"),range(1,13)))

class TreasuryHold(ValueError):
    pass

def require(ok, reason):
    if not ok: raise TreasuryHold(reason)

def canonical(raw):
    try:
        value=urllib.parse.urlsplit(urllib.parse.urljoin(INDEX,raw))
    except (ValueError,TypeError):
        return None
    if (value.scheme!="https" or value.netloc!=HOST or value.query or
        value.fragment or value.username or value.password or
        "%" in value.path):
        return None
    match=ID.fullmatch(value.path)
    if match is None: return None
    return ("https://"+HOST+"/news/press-releases/"+match["slug"],match["slug"])

def posted_date(tag):
    require(isinstance(tag,Tag),"date_element_missing")
    text=tag.get("datetime","")
    if text:
        require(isinstance(text,str) and ISO.match(text),"invalid_date_attribute")
        value=date.fromisoformat(text[:10])
        return value.isoformat()
    text=tag.get_text(" ",strip=True)
    match=HUMAN.search(text)
    require(match is not None,"publisher_date_missing")
    value=date(int(match[3]),MONTHS[match[1].lower()],int(match[2]))
    return value.isoformat()

def extract(html, *, as_of):
    require(type(html) is bytes and 100 <= len(html) <= MAX_BYTES
       and (b"<html" in html.lower() or b"<!doctype" in html.lower()),
       "not_a_valid_treasury_listing")
    soup=BeautifulSoup(html,"html.parser")
    items={}
    for anchor in soup.select("h3.featured-stories__headline a[href]"):
        resolved=canonical(anchor.get("href",""))
        if resolved is None: continue
        url,slug=resolved
        headline=anchor.find_parent("h3",class_="featured-stories__headline")
        card=headline.parent if headline is not None else None
        # The Oct 15 real Treasury DOM has exactly ONE publisher date and
        # ONE release link in this immediate per-item div. The shared
        # .featured-stories list encloses TEN dated items and is unsafe.
        require(isinstance(card,Tag) and card.name=="div" and
                isinstance(card.parent,Tag) and
                "content--2col__body" in (card.parent.get("class") or []),
                "release_card_boundary_missing")
        dates=card.select("time")
        require(len(dates)==1,"non_unique_press_card_date")
        day=posted_date(dates[0])
        require("2025-01-01" <= day <= as_of, "publisher_date_out_of_range")
        candidates={canonical(a["href"]) for a in card.select("a[href]")
                    if canonical(a["href"]) is not None}
        require(len(candidates)==1 and resolved in candidates,
                "cross_release_card_date_risk")
        ident="us-treasury-press:"+slug
        row={"source_identity":ident,"canonical_official_url":url,
             "publisher_posted_date":day,"official_issuer":ISSUER,
             "official_publisher":HOST,"publisher_listing_url":INDEX}
        if ident in items: require(items[ident]==row,"conflicting_source_id")
        items[ident]=row
    require(1 <= len(items) <= MAX_ROWS,"no_independently_dated_treasury_releases")
    return sorted(items.values(),key=lambda r:
        (r["publisher_posted_date"],r["source_identity"]),reverse=True)

def collect(*,opener=None,as_of=None):
    as_of=as_of or datetime.now(timezone.utc).date().isoformat()
    try:
        require(date.fromisoformat(as_of).isoformat()==as_of,"invalid_observation_date")
    except (ValueError,TypeError):
        raise TreasuryHold("invalid_observation_date") from None
    opener=opener or urllib.request.build_opener(NoRedirect)
    policy,status=_fetch(opener,ROBOTS,MAX_ROBOTS_BYTES)
    require(status=="ok" and policy is not None,"treasury_robots_"+status)
    try: text=policy.decode("utf-8")
    except UnicodeError: raise TreasuryHold("robots_not_utf8") from None
    require("user-agent:" in text.lower() and "<html" not in text.lower()
            and "<script" not in text.lower(),"treasury_robots_invalid")
    checker=urllib.robotparser.RobotFileParser(ROBOTS)
    checker.parse(text.splitlines())
    require(checker.can_fetch(AGENT,INDEX),"treasury_listing_robots_disallow")
    payload,status=_fetch(opener,INDEX,MAX_BYTES)
    require(status=="ok" and payload is not None,"treasury_listing_"+status)
    rows=extract(payload,as_of=as_of)
    return {"schema":SCHEMA,"source_host":HOST,
            "source_family":"us_treasury_press_releases",
            "publisher":"U.S. Department of the Treasury","issuer":ISSUER,
            "collection_mode":"bounded_official_listing_metadata_only",
            "observed_on_utc":as_of,"official_listing_url":INDEX,
            "official_listing_sha256":hashlib.sha256(payload).hexdigest(),
            "rows":rows,"visible_dated_rows":len(rows),
            "original_titles_copied":False,"bodies_copied":False,
            "document_media_copied":False,"analysis_performed":False,
            "publication_authorized_by_collector":False,
            "production_records_written":0,
            "complete_publisher_history_claimed":False}

def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--owner-authorized-readonly-collection",action="store_true",required=True)
    ap.add_argument("--private-output",default="")
    args=ap.parse_args(argv)
    try:
        packet=collect()
        if args.private_output:
            path=Path(args.private_output)
            require(path.is_absolute() and not path.exists() and
                    not path.is_symlink() and path.parent.is_dir(),
                    "private_output_must_be_new_absolute_file")
            with path.open("x",encoding="utf8") as fh:
                json.dump(packet,fh,sort_keys=True,separators=(",",":"))
                fh.write("\n")
            path.chmod(0o600)
        print(json.dumps({"schema":SCHEMA,"status":"PASS_METADATA_ONLY",
             "verified_official_link_rows":len(packet["rows"]),
             "listing_sha256":packet["official_listing_sha256"],
             "originals_retained":False,"production_records":0,
             "site_modified":False},sort_keys=True))
        return 0
    except (TreasuryHold,ValueError,OSError) as e:
        print(json.dumps({"schema":SCHEMA,"status":"HOLD",
             "reason":str(e) if isinstance(e,TreasuryHold) else
                 "source_or_state_unavailable",
             "production_records":0,"site_modified":False},sort_keys=True))
        return 2

if __name__=="__main__":raise SystemExit(main())
