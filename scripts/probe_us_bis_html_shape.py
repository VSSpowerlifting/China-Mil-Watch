"""BIS exact-host homepage/news teaser source-structure probe — no collection.

The full /news-updates page exceeded the original 160 KiB request cap. This
read-only probe tests two independently fixed BIS official listing paths with
one shared robots policy, no redirects, no pagination, no article fetch and no
original titles, bodies or media saved. Real output is structural only.
"""
from __future__ import annotations
import json
import re
import urllib.request
import urllib.robotparser
import urllib.parse
from bs4 import BeautifulSoup
from scripts.probe_us_navy_first_party_access import (
    AGENT, NoRedirect, _fetch, MAX_ROBOTS_BYTES
)

SCHEMA="ipr-bis-official-small-listing-canary/1"
HOST="www.bis.gov"
ROBOTS="https://www.bis.gov/robots.txt"
ROUTES=("/", "/enforcement")
MAX_BYTES=650_000
RELEASE_PATH=re.compile(r"/(?:press-release|news-update|enforcement)/[a-z0-9-]+/?\Z")

def run(opener=None):
    opener=opener or urllib.request.build_opener(NoRedirect)
    policy,status=_fetch(opener,ROBOTS,MAX_ROBOTS_BYTES)
    outcome={"schema":SCHEMA,"host":HOST,"routes":[],
       "robots_policy":status,"records_collected":0,
       "source_originals_stored":False,"production_written":False,
       "publisher_content_reproduced":False,"collection_authorized":False}
    if status!="ok" or policy is None:return outcome
    try:text=policy.decode("utf8")
    except UnicodeError:return {**outcome,"robots_policy":"invalid_encoding"}
    if "user-agent:" not in text.lower() or "<html" in text.lower():
        return {**outcome,"robots_policy":"invalid_policy"}
    parser=urllib.robotparser.RobotFileParser(ROBOTS)
    parser.parse(text.splitlines())
    for path in ROUTES:
        url="https://"+HOST+path
        if not parser.can_fetch(AGENT,url):
            outcome["routes"].append({"path":path,"status":"robots_disallowed"})
            continue
        body,stat=_fetch(opener,url,MAX_BYTES)
        row={"path":path,"status":stat}
        if stat=="ok" and body and (b"<html" in body.lower() or b"<!doctype" in body.lower()):
            soup=BeautifulSoup(body,"html.parser")
            # Count independently dated official links, never print original text.
            found=[]
            for a in soup.select("a[href]"):
                resolved=urllib.parse.urlsplit(urllib.parse.urljoin(url,a.get("href","")))
                if resolved.scheme!="https" or resolved.netloc!=HOST or resolved.query or resolved.fragment:
                    continue
                if not RELEASE_PATH.fullmatch(resolved.path):continue
                chain=[];n=a
                for _ in range(6):
                    n=n.parent
                    if not getattr(n,"name",None):break
                    chain.append({"tag":n.name,
                      "classes":(n.get("class") or [])[:4],
                      "time_count":len(n.select("time")),
                      "item_links":len([q for q in n.select("a[href]")
                          if RELEASE_PATH.fullmatch(urllib.parse.urlsplit(
                              urllib.parse.urljoin(url,q.get("href",""))).path)])})
                found.append({"path":resolved.path,"chain":chain})
            row.update({"status":"parsed_html_shape","body_bytes":len(body),
               "release_links_seen":len(found),"time_elements":len(soup.select("time")),
               "sample":found[:5]})
        outcome["routes"].append(row)
    return outcome

if __name__=="__main__":
    print(json.dumps(run(),sort_keys=True))
