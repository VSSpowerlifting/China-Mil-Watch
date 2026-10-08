#!/usr/bin/env python3
"""Disposable, metadata-only National Defence Journal DOM diagnostic.

One research invocation: at most 3 exact-host HTTPS GETs (desktop robots
and two pinned article URLs). No request is made without readable robots
permission. No publisher article text or HTML is written, printed or stored.
Never install this script or its workflow as a production collector.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.collection.vietnam_identity import USER_AGENT
from scraper.sources.desk_shadow_http import robots_allows, robots_policy, Refused

HOST = "tapchiqptd.vn"
ROBOTS = "https://" + HOST + "/robots.txt"
ARTICLES = (
    ("26936", "https://tapchiqptd.vn/en/theory-and-practice/military-technical-academy-proactively-embraces-international-integration-and-elevates-int/26936.html", "military technical academy"),
    ("26919", "https://tapchiqptd.vn/en/research-and-discussion/distinctive-features-of-military-art-in-the-tay-ninh-campaign-of-1966/26919.html", "distinctive features of military art"),
)
MAX_REQUESTS = 3
MAX_BYTES = 256_000
MAX_DELAY = 60
CHALLENGE = re.compile(r"cf-chl|challenge-platform|just a moment|captcha|access denied", re.I)
DATE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s*"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+20\d{2},\s+\d{1,2}:\d{2}\s*\(GMT\+7\)")
CLOCK = re.compile(r"\b\d{1,2}/\d{1,2}/20\d{2}\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\b", re.I)
AUTHOR_MARKER = re.compile(r"\b(?:prof(?:essor)?|ph\.?\s*d\.?|major general|colonel|author)\b", re.I)


class ProbeError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def selector(node):
    """A structural locator made only of tag, id, class, and sibling index."""
    chain = []
    while getattr(node, "name", None) and len(chain) < 9:
        name = str(node.name)
        if not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            break
        ident = node.get("id")
        classes = node.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        classes = [c for c in classes[:3] if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,59}", c)]
        if ident and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,59}", ident):
            part = name + "#" + ident
        else:
            part = name + "".join("." + c for c in classes)
            same = [s for s in (node.parent.children if node.parent else []) if getattr(s, "name", None) == name]
            if len(same) > 1:
                part += ":nth-of-type(" + str(same.index(node) + 1) + ")"
        chain.append(part)
        node = node.parent
    return " > ".join(reversed(chain))


def depth(node):
    n = 0
    while getattr(node, "parent", None):
        n += 1
        node = node.parent
    return n


def node_matches(soup, phrase, limit=9):
    """Match text nodes but return structural metadata only."""
    matches = []
    for s in soup.find_all(string=True):
        if isinstance(s, NavigableString) and phrase.casefold() in " ".join(str(s).split()).casefold():
            parent = s.parent
            path = selector(parent)
            if not any(m["path"] == path for m in matches):
                matches.append({"path": path, "tag": parent.name,
                                "text_chars": len(str(s).strip()),
                                "depth": depth(parent)})
            if len(matches) >= limit:
                break
    return matches


def structure(html, title_phrase):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.html or not soup.body:
        raise ProbeError("unrecognized or partial HTML")
    headers = []
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        headers.append({"path": selector(tag), "level": tag.name,
                        "chars": len(tag.get_text(" ", strip=True))})
    large = []
    for tag in soup.find_all(["article", "section", "main", "div", "td"]):
        chars = len(tag.get_text(" ", strip=True))
        paragraphs = len(tag.find_all(["p"], recursive=True))
        if chars >= 500 and paragraphs >= 2:
            large.append({"path": selector(tag), "depth": depth(tag),
                          "chars": chars, "paragraphs": paragraphs,
                          "direct_child_tags": [c.name for c in tag.children
                                                if getattr(c, "name", None)][:20]})
    # Prefer inner containers to a page-wide wrapper. These remain diagnostics,
    # NOT a parser or proof that the returned prose is the complete article.
    large.sort(key=lambda x: (-x["depth"], -x["chars"]))
    large = large[:25]
    date_nodes, clock_nodes, author_nodes = [], [], []
    for s in soup.find_all(string=True):
        if not isinstance(s, NavigableString):
            continue
        normalized = " ".join(str(s).split())
        if len(normalized) > 400:
            continue
        for regex, destination in ((DATE, date_nodes), (CLOCK, clock_nodes),
                                   (AUTHOR_MARKER, author_nodes)):
            if regex.search(normalized):
                path = selector(s.parent)
                if path not in destination:
                    destination.append(path)
    meta = []
    for tag in soup.select("meta[property],meta[name],time[datetime],link[rel=canonical]"):
        kind = tag.get("property") or tag.get("name") or (
            "time:datetime" if tag.name == "time" else "canonical")
        if re.search(r"(?:title|date|time|author|publish|og:|twitter:|canonical)", kind, re.I):
            meta.append({"tag": tag.name, "key": str(kind)[:70],
                         "value_present": bool(tag.get("content") or tag.get("datetime")
                                               or tag.get("href")),
                         "path": selector(tag)})
    return {
        "document_has_html_and_body": True,
        "title_phrase_matches": node_matches(soup, title_phrase),
        "date_text_paths": date_nodes[:16],
        "other_clock_paths": clock_nodes[:16],
        "author_marker_paths": author_nodes[:16],
        "heading_elements": headers[:24],
        "nested_text_container_candidates": large,
        "metadata_elements": meta[:24],
        "article_extraction_verified": False,
        "original_text_retained": False,
    }


def fetch(session, url, delay, previous):
    """Single bounded request. No redirect, cookie reuse or source-byte output."""
    if urlsplit(url).netloc != HOST or not url.startswith("https://" + HOST + "/"):
        raise ProbeError("unexpected host/path")
    if previous is not None:
        time.sleep(max(0.0, delay - (time.monotonic() - previous)))
    resp = None
    try:
        resp = session.get(url, allow_redirects=False, timeout=20, stream=True)
        raw = bytearray()
        for part in resp.iter_content(32768):
            raw.extend(part)
            if len(raw) > MAX_BYTES:
                raise ProbeError("request exceeds size cap")
        raw = bytes(raw)
        meta = {"url": url, "http": resp.status_code, "bytes": len(raw),
                "sha256": sha(raw), "content_type": resp.headers.get("Content-Type", "").split(";")[0].lower(),
                "redirect_seen": bool(resp.headers.get("Location")) or resp.url != url,
                "challenge_header": bool(resp.headers.get("Cf-Mitigated"))}
        if resp.url != url or resp.status_code != 200 or resp.headers.get("Location"):
            return meta, None
        if resp.headers.get("Content-Encoding", "identity").lower() != "identity":
            return meta, None
        if meta["content_type"] not in ("text/plain", "text/html"):
            return meta, None
        try:
            body = raw.decode("utf-8", "strict")
        except UnicodeError:
            return meta, None
        if meta["challenge_header"] or CHALLENGE.search(body[:4000]):
            return meta, None
        return meta, body
    finally:
        if resp is not None:
            resp.close()
        session.cookies.clear()


def run(out, session=None):
    target = Path(out)
    if target.exists() or target.is_symlink() or ROOT in target.resolve().parents:
        raise ProbeError("output must be new and outside repository")
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT,
                            "Accept": "text/plain,text/html",
                            "Accept-Encoding": "identity"})
    report = {"schema": "vietnam-journal-dom-research/1",
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "collector_identity": USER_AGENT, "source": "National Defence Journal English",
              "request_budget": MAX_REQUESTS, "request_count": 0,
              "browser_used": False, "redirects_followed": False,
              "source_bytes_retained": False, "production_modified": False,
              "access": "unverified", "robots": None, "articles": []}
    previous = None
    robots_meta, robots_text = fetch(session, ROBOTS, 0, previous)
    report["request_count"] += 1
    previous = time.monotonic()
    report["robots"] = robots_meta
    if robots_meta["content_type"] == "text/plain" and robots_text and not robots_text.lstrip().startswith("<"):
        try:
            rules, delay = robots_policy(robots_text)
            if delay > MAX_DELAY:
                report["access"] = "crawl_delay_exceeds_budget"
            else:
                report["access"] = "robots_read"
                for ident, url, title_phrase in ARTICLES:
                    allowed = robots_allows(rules, url)
                    row = {"article_id": ident, "url": url, "robots_allowed": allowed,
                           "request_made": False}
                    if allowed:
                        meta, content = fetch(session, url, delay, previous)
                        report["request_count"] += 1
                        previous = time.monotonic()
                        row.update(response=meta, request_made=True)
                        if meta["content_type"] == "text/html" and content:
                            row["structure"] = structure(content, title_phrase)
                    report["articles"].append(row)
        except (Refused, ValueError) as exc:
            report["access"] = "robots_unreadable_" + type(exc).__name__
    else:
        report["access"] = "robots_inaccessible"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                      encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = run(args.out)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
