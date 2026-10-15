"""Read one Treasury official press listing; print only structural metadata."""
from __future__ import annotations
import collections
import json
import re
import urllib.request
import urllib.robotparser
from bs4 import BeautifulSoup
from scripts.probe_us_navy_first_party_access import AGENT, _fetch, NoRedirect, MAX_ROBOTS_BYTES

ROBOTS="https://home.treasury.gov/robots.txt"
LISTING="https://home.treasury.gov/news/press-releases"
def main():
    op=urllib.request.build_opener(NoRedirect)
    policy,status=_fetch(op,ROBOTS,MAX_ROBOTS_BYTES)
    if status!="ok": raise RuntimeError("treasury_robots_"+status)
    rp=urllib.robotparser.RobotFileParser(ROBOTS)
    rp.parse(policy.decode("utf-8").splitlines())
    if not rp.can_fetch(AGENT,LISTING):raise RuntimeError("treasury_listing_disallowed")
    body,status=_fetch(op,LISTING,160000)
    if status!="ok":raise RuntimeError("treasury_listing_"+status)
    soup=BeautifulSoup(body,"html.parser")
    rows=[]
    for a in soup.select("a[href]"):
        href=a.get("href","")
        if not re.fullmatch(r"(?:https://home\.treasury\.gov)?/news/press-releases/[a-z0-9-]+/?",href):
            continue
        parents=[]
        node=a
        for _ in range(7):
            node=node.parent
            if node is None:break
            if getattr(node,"name",None):
                parents.append({"tag":node.name, "classes":(node.get("class") or [])[:5]})
        rows.append({"path":href[:130],"ancestors":parents})
    print(json.dumps({"source":"home.treasury.gov", "bytes_read":len(body),
       "release_links_seen":len(rows),"sample":rows[:8],
       "views_row":len(soup.select(".views-row")),
       "articles":len(soup.select("article")),
       "time_elements":len(soup.select("time")),
       "date_like_text_count":len(re.findall(
          rb"(?i)(?:October|September|August)\s+\d{1,2},?\s+2026",body)),
       "content_persisted":False,"publication_authorized":False},sort_keys=True))
if __name__=="__main__":main()
