#!/usr/bin/env python3
"""One-shot, fail-closed National Defence Journal Actions access/structure probe.

At most 6 GETs total: robots, exact English homepage, one known article on
each of the two hosts. No browser automation, retries, redirect following,
cookies, full-text artifact, state branch, ingestion, or production writes.
The output contains only response metadata/hashes and structural diagnostics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests
from bs4 import BeautifulSoup
from core.collection.vietnam_identity import USER_AGENT
from scraper.sources import vn_defence_journal as journal
from scraper.sources.desk_shadow_http import robots_allows, robots_policy, Refused

PROBE_SCHEMA = "vietnam-journal-access-proof/1"
MAX_BYTES = 512_000
TIMEOUT = 20
MAX_REQUESTS = 6
MAX_DELAY = 120
ARTICLE_DESKTOP = (
    "https://tapchiqptd.vn/en/theory-and-practice/"
    "military-technical-academy-proactively-embraces-international-integration-and-elevates-int/"
    "26936.html")
ARTICLE_MOBILE = (
    "https://m.tapchiqptd.vn/en/theory-and-practice/"
    "military-technical-academy-proactively-embraces-international-integration-and-elevates-int-26936.html")
HOSTS = (
    ("desktop", "tapchiqptd.vn", journal.DESKTOP, ARTICLE_DESKTOP),
    ("mobile", "m.tapchiqptd.vn", journal.MOBILE, ARTICLE_MOBILE),
)
DATE_DESKTOP = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December) [0-9]{1,2}, [0-9]{4}, [0-9]{2}:[0-9]{2} \(GMT\+7\)")
DATE_MOBILE = re.compile(
    r"\b[0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9]{1,2}:[0-9]{2}:[0-9]{2} (?:AM|PM)\b")
CONTENT_SELECTORS = (
    "[itemprop='articleBody']", ".article-content", ".article-body",
    ".detail-content", ".content-detail", ".news-content",
    ".content-news", ".article-detail", "#article-content",
)


class ProbeRefused(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def summary(html, article=False):
    """Ephemeral DOM inspection, never return HTML or article prose."""
    soup = BeautifulSoup(html, "html.parser")
    if not soup.html or not soup.body:
        raise ProbeRefused("incomplete HTML layout")
    if article:
        title = soup.select_one('meta[property="og:title"]')
        heading = soup.select_one("h1") or soup.select_one("h2")
        candidate = (title.get("content", "").strip() if title else
                     heading.get_text(" ", strip=True) if heading else "")
        dates = set()
        for text in soup.stripped_strings:
            if len(text) > 350:
                continue
            for pattern in (DATE_DESKTOP, DATE_MOBILE):
                for match in pattern.finditer(text):
                    try:
                        dates.add(journal.stated_date(match.group()))
                    except ValueError:
                        pass
        dom = {}
        for selector in CONTENT_SELECTORS:
            nodes = soup.select(selector)
            if nodes:
                dom[selector] = {"nodes": len(nodes),
                                 "max_text_length": max(len(x.get_text(" ", strip=True))
                                                        for x in nodes)}
        return {"title_hash": sha256(candidate.encode("utf-8")) if candidate else None,
                "title_present": bool(candidate),
                "candidate_dates": sorted(dates),
                "body_selector_diagnostics": dom,
                "body_extraction_verified": False,
                "full_text_retained": False}
    return {"html_document_present": True}


def response_probe(session, url, allowance, gate, monotonic=time.monotonic, sleeper=time.sleep):
    """One request with exact host gate and bounded payload. No raw bytes in report."""
    if allowance["requests"] >= MAX_REQUESTS:
        raise ProbeRefused("six-request aggregate cap exceeded")
    host = urlsplit(url).netloc
    if host not in journal.HOSTS or urlsplit(url).scheme != "https":
        raise ProbeRefused("foreign host")
    last = gate.get(host)
    if last is not None:
        sleeper(max(0.0, allowance.get("delay", {}).get(host, 2.0) -
                    (monotonic() - last)))
    allowance["requests"] += 1
    resp = None
    try:
        resp = session.get(url, timeout=TIMEOUT, allow_redirects=False, stream=True)
        data = bytearray()
        for chunk in resp.iter_content(32768):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise ProbeRefused("response exceeds byte ceiling")
        raw = bytes(data)
        ctype = resp.headers.get("Content-Type", "")
        result = {
            "url": url, "http_status": resp.status_code,
            "content_type": ctype.split(";", 1)[0].strip().lower(),
            "redirect_location_present": bool(resp.headers.get("Location")),
            "cf_mitigated": bool(resp.headers.get("Cf-Mitigated")),
            "bytes": len(raw), "sha256": sha256(raw),
            "source_body_preserved": False,
        }
        if resp.url != url or 300 <= resp.status_code < 400:
            result["verdict"] = "redirect_refused"
            return result, None
        if resp.status_code != 200:
            result["verdict"] = "http_non_200"
            return result, None
        if resp.headers.get("Content-Encoding", "identity").lower() != "identity":
            result["verdict"] = "encoded_response_refused"
            return result, None
        if not (result["content_type"] in ("text/html", "text/plain")):
            result["verdict"] = "unsupported_content_type"
            return result, None
        try:
            text = raw.decode("utf-8", "strict")
        except UnicodeError:
            result["verdict"] = "invalid_utf8"
            return result, None
        if (resp.headers.get("Cf-Mitigated") or re.search(
                r"cf-chl|challenge-platform|just a moment|captcha|access denied",
                text[:4000], re.I)):
            result["verdict"] = "challenge_refused"
            return result, None
        result["verdict"] = "received"
        return result, text
    except requests.RequestException as exc:
        return {"url": url, "verdict": "transport_failure",
                "error_type": type(exc).__name__,
                "source_body_preserved": False}, None
    except ProbeRefused as exc:
        return {"url": url, "verdict": "bounded_refusal",
                "reason": str(exc), "source_body_preserved": False}, None
    finally:
        if resp is not None:
            resp.close()
        session.cookies.clear()
        gate[host] = monotonic()


def evaluate_host(label, host, listing, article, session, allowance, gate):
    """An independent host policy. Never use mobile to bypass desktop refusal."""
    row = {"presentation": label, "host": host, "listing_url": listing,
           "article_url": article, "robots": None,
           "listing": {"request_made": False},
           "article": {"request_made": False}}
    meta, body = response_probe(session, "https://" + host + "/robots.txt",
                                allowance, gate)
    row["robots"] = meta
    if meta.get("verdict") != "received" or meta["content_type"] != "text/plain":
        row["gate"] = "robots_policy_unverified"
        return row
    if not body.strip() or body.lstrip("\ufeff \r\n\t").startswith("<"):
        row["gate"] = "robots_policy_unreadable"
        return row
    try:
        rules, delay = robots_policy(body)
    except (Refused, ValueError):
        row["gate"] = "robots_policy_malformed"
        return row
    if delay > MAX_DELAY:
        row["gate"] = "crawl_delay_exceeds_probe_budget"
        return row
    allowance.setdefault("delay", {})[host] = delay
    row["robots"]["policy_parsed"] = True
    allowed_listing = robots_allows(rules, listing)
    allowed_article = robots_allows(rules, article)
    row["robots"]["listing_allowed"] = allowed_listing
    row["robots"]["article_allowed"] = allowed_article
    if not allowed_listing or not allowed_article:
        row["gate"] = "robots_disallows_target"
        return row
    row["listing"]["request_made"] = True
    listing_meta, html = response_probe(session, listing, allowance, gate)
    row["listing"].update(listing_meta)
    if html is None or listing_meta.get("content_type") != "text/html":
        row["gate"] = "listing_inaccessible"
        return row
    try:
        hints = journal.discovery_links(html, listing)
    except ValueError as exc:
        row["gate"] = "listing_structure_unproven"
        row["listing"]["parse_error_type"] = type(exc).__name__
        return row
    row["listing"].update(summary(html))
    row["listing"]["unique_article_ids"] = len(hints)
    row["listing"]["sample_id_discovered"] = any(
        x["identity"] == journal.article_identity(article) for x in hints)
    if not row["listing"]["sample_id_discovered"]:
        row["gate"] = "article_not_in_observed_listing"
        return row
    row["article"]["request_made"] = True
    article_meta, page = response_probe(session, article, allowance, gate)
    row["article"].update(article_meta)
    if page is None or article_meta.get("content_type") != "text/html":
        row["gate"] = "article_inaccessible"
        return row
    try:
        row["article"].update(summary(page, article=True))
    except ProbeRefused:
        row["gate"] = "article_html_structure_unproven"
        return row
    row["article"]["identity"] = journal.article_identity(article)
    row["article"]["canonical_url"] = journal.canonical_article_url(article)
    row["gate"] = "access_ok_structure_needs_human_review"
    return row


def run(out, session=None):
    out = Path(out)
    if out.is_symlink() or out.resolve() == ROOT or ROOT in out.resolve().parents:
        raise ProbeRefused("evidence output must be outside the repository")
    if out.exists():
        raise ProbeRefused("evidence output already exists")
    session = session or requests.Session()
    session.trust_env = False
    session.headers.update({
        "User-Agent": USER_AGENT, "Accept-Encoding": "identity",
        "Accept": "text/plain,text/html",
    })
    requests_made = {"requests": 0}
    gate = {}
    hosts = []
    for label, host, listing, article in HOSTS:
        hosts.append(evaluate_host(label, host, listing, article,
                                   session, requests_made, gate))
    verdicts = [row["gate"] for row in hosts]
    parity = None
    if all(v == "access_ok_structure_needs_human_review" for v in verdicts):
        a, b = (row["article"] for row in hosts)
        parity = {"same_canonical_url": a["canonical_url"] == b["canonical_url"],
                  "same_article_identity": a["identity"] == b["identity"],
                  "same_title_hash": a["title_hash"] == b["title_hash"],
                  "date_overlap": sorted(set(a["candidate_dates"]) &
                                         set(b["candidate_dates"]))}
    report = {"schema": PROBE_SCHEMA, "collector_identity": USER_AGENT,
              "source_slug": journal.SOURCE_SLUG,
              "max_requests": MAX_REQUESTS, "requests_made": requests_made["requests"],
              "redirects_followed": False, "cookies_reused": False,
              "browser_or_proxy_used": False, "source_article_bytes_retained": False,
              "shadow_state_written": False, "production_written": False,
              "rights_to_republish": "not_established", "hosts": hosts,
              "cross_host_parity": parity,
              "decision": "offline_only_pending_review"}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) +
                   "\n", encoding="utf-8")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        report = run(args.out)
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    except (ProbeRefused, OSError, ValueError) as exc:
        print("journal probe refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
