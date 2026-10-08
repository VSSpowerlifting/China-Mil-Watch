#!/usr/bin/env python3
"""One-shot English National Defence Journal category discovery feasibility.

Research only, no collector/state. At most five HTTPS GETs:
one robots policy + four fixed official category URLs. Records structural
metadata, numeric IDs and page-date hints, not titles, HTML or article prose.
No arbitrary pagination URL is fetched. This is a disposable Actions probe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.collection.vietnam_identity import USER_AGENT
from scraper.sources.desk_shadow_http import robots_allows, robots_policy, Refused

HOST = "tapchiqptd.vn"
ORIGIN = "https://" + HOST
ROBOTS = ORIGIN + "/robots.txt"
CATEGORIES = (
    ("news", ORIGIN + "/en/news-54.html"),
    ("theory-and-practice", ORIGIN + "/en/theory-and-practice-56.html"),
    ("events-and-comments", ORIGIN + "/en/events-and-comments-57.html"),
    ("research-and-discussion", ORIGIN + "/en/research-and-discussion-58.html"),
)
ARTICLE = re.compile(r"^/en/(news|theory-and-practice|events-and-comments|research-and-discussion)/[a-z0-9-]+/(\d{4,9})\.html$")
STAMP = re.compile(
    r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
    r"(January|February|March|April|May|June|July|August|September|October|November|December) "
    r"\d{1,2}, \d{4}, \d{2}:\d{2} \(GMT\+7\)")
SHORT_DATE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
MAX_BYTES = 256_000
MAX_REQUESTS = 5
MAX_DELAY = 90


class Refusal(ValueError):
    pass


def get(session, url):
    """Exactly one bounded request; redirects, encoding/challenges fail closed."""
    response = None
    try:
        response = session.get(url, timeout=20, stream=True, allow_redirects=False)
        buffer = bytearray()
        for block in response.iter_content(32768):
            buffer.extend(block)
            if len(buffer) > MAX_BYTES:
                raise Refusal("response exceeds byte ceiling")
        raw = bytes(buffer)
        meta = {"url": url, "status": response.status_code, "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "content_type": response.headers.get("Content-Type","").split(";")[0].strip().lower()}
        if (response.url != url or response.headers.get("Location") or response.status_code != 200):
            raise Refusal("redirect or inaccessible URL")
        if response.headers.get("Content-Encoding","identity").lower() != "identity":
            raise Refusal("unexpected compression")
        if response.headers.get("Cf-Mitigated"):
            raise Refusal("access challenge")
        if meta["content_type"] not in ("text/plain", "text/html"):
            raise Refusal("unrecognized response type")
        text = raw.decode("utf-8", "strict")
        if re.search(r"cf-chl|challenge-platform|just a moment|captcha", text[:3500], re.I):
            raise Refusal("challenge response")
        return meta, text
    finally:
        if response is not None:
            response.close()
        session.cookies.clear()


def page_evidence(html, category):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.html or not soup.body:
        raise Refusal("no complete HTML layout")
    seen = {}
    contextual = []
    link_counts = Counter()
    for anchor in soup.select("a[href]"):
        original = anchor["href"].strip()
        target = urljoin(ORIGIN, original)
        parts = urlsplit(target)
        if (parts.scheme != "https" or parts.netloc != HOST or parts.query
                or parts.fragment):
            continue
        match = ARTICLE.fullmatch(parts.path)
        if not match:
            continue
        sector, article_id = match.groups()
        link_counts[sector] += 1
        if article_id not in seen:
            seen[article_id] = {"id": article_id, "category": sector,
                                "canonical_url": target, "matches": 0,
                                "listing_date_hint": None}
        elif seen[article_id]["canonical_url"] != target:
            raise Refusal("numeric ID has inconsistent canonical URLs")
        seen[article_id]["matches"] += 1
        # A date is a hint only if local to the anchor, never taken from the
        # page header, sidebar, or other arbitrary page text. A future
        # collector must separately validate dates against article pages.
        parent = anchor
        for steps in range(3):
            parent = parent.parent
            if parent is None or parent.name == "body":
                break
            if parent.name not in ("li", "p", "div", "td", "article"):
                continue
            direct = " ".join(x.strip() for x in parent.stripped_strings)
            if len(direct) > 550:
                continue
            stamps = STAMP.findall(direct)
            date_str = STAMP.search(direct)
            if len(stamps) == 1 and date_str:
                try:
                    parsed = datetime.strptime(date_str.group(), "%A, %B %d, %Y, %H:%M (GMT+7)")
                except ValueError:
                    continue
                seen[article_id]["listing_date_hint"] = parsed.date().isoformat()
                break
            short = SHORT_DATE.findall(direct)
            if len(short) == 1:
                try:
                    seen[article_id]["listing_date_hint"] = datetime.strptime(short[0],"%m/%d/%Y").date().isoformat()
                    break
                except ValueError:
                    pass
    # Control discovery only; do NOT navigate query strings or postback.
    form_elements = []
    for tag in soup.find_all(["a","button","input","select"]):
        attrs = [k for k in ("href","onclick","id","name","class","type","value") if tag.has_attr(k)]
        details = " ".join(str(tag.get(k,""))[:120] for k in attrs)
        if re.search(r"\b(next|previous|older|page|pagination|__doPostBack|pager|loadmore)\b", details, re.I):
            form_elements.append({
                "tag": tag.name, "attr_names": attrs,
                "id": str(tag.get("id",""))[:90],
                "class_names": (tag.get("class",[]) or [])[:8],
                "href_is_hash": tag.get("href") == "#",
                "href_has_query": "?" in str(tag.get("href","")),
                "onclick_present": tag.has_attr("onclick"),
                "onclick_hash": hashlib.sha256(str(tag.get("onclick","")).encode()).hexdigest() if tag.has_attr("onclick") else None,
            })
    return {"category": category, "article_count": len(seen),
            "article_links_total": sum(link_counts.values()),
            "link_categories": dict(sorted(link_counts.items())),
            "article_id_inventory": [seen[k] for k in sorted(seen)],
            "date_hint_count": sum(v["listing_date_hint"] is not None for v in seen.values()),
            "pagination_control_candidates": form_elements[:25],
            "pagination_access_proven": False,
            "chronological_completeness_proven": False}


def run(destination, session=None):
    out = Path(destination)
    if (out.exists() or out.is_symlink() or out.resolve() == ROOT
            or ROOT in out.resolve().parents):
        raise Refusal("output must be a new file outside the checkout")
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Encoding":"identity",
                            "Accept":"text/html,text/plain"})
    report = {"schema":"vietnam-journal-category-discovery/1", "source":"National Defence Journal English",
              "request_limit":MAX_REQUESTS, "request_count":0,
              "rights_to_archive_article_body":"not_established",
              "article_html_retained":False,"article_text_retained":False,
              "source_state_modified":False,"production_modified":False,
              "category_pages":[]}
    count = 0
    robots_meta, policy = get(session, ROBOTS)
    count += 1
    report["robots"] = robots_meta
    if robots_meta["content_type"] != "text/plain" or not policy.strip() or policy.lstrip().startswith("<"):
        raise Refusal("robots policy missing or unreadable")
    try:
        rules, delay = robots_policy(policy)
    except (Refused, ValueError) as exc:
        raise Refusal("robots policy invalid") from exc
    if delay > MAX_DELAY:
        raise Refusal("robots crawl-delay exceeds bounded research window")
    last = time.monotonic()
    for name, url in CATEGORIES:
        if not robots_allows(rules, url):
            report["category_pages"].append({"category":name,"url":url,"robots_allowed":False})
            continue
        time.sleep(max(0, max(2,delay) - (time.monotonic()-last)))
        if count >= MAX_REQUESTS:
            raise Refusal("aggregate request limit exceeded")
        meta, html = get(session,url)
        count += 1
        last = time.monotonic()
        result = page_evidence(html, name)
        result["response"] = meta
        result["robots_allowed"] = True
        report["category_pages"].append(result)
    report["request_count"] = count
    # Sitewide numeric IDs must have one canonical URL across all pages.
    all_ids = {}
    for category in report["category_pages"]:
        for record in category.get("article_id_inventory",[]):
            key = record["id"]
            if key in all_ids and all_ids[key] != record["canonical_url"]:
                raise Refusal("cross-category article ID collision")
            all_ids[key] = record["canonical_url"]
    report["unique_ids_across_pages"] = len(all_ids)
    report["all_four_sections_measured"] = len(report["category_pages"]) == 4 and all(
        page.get("response",{}).get("status")==200 for page in report["category_pages"])
    report["listing_completeness_proven"] = False
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    result=run(args.out)
    print(json.dumps({"request_count":result["request_count"],
                      "unique_ids_across_pages":result["unique_ids_across_pages"],
                      "categories":[{"category":p["category"],"count":p.get("article_count"),
                                     "dated":p.get("date_hint_count"),
                                     "pagination_candidates":len(p.get("pagination_control_candidates",[]))}
                                    for p in result["category_pages"]],
                      "listing_completeness_proven":False},indent=2))
if __name__ == "__main__":
    main()
