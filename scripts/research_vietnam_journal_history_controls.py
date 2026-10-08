"""One-shot, bounded journal HTML control inspection for #154 (research only).

Production has NO dependency on this script. It is called from an unmerged
disposable PR workflow exactly once; no schedules, collector activation,
source-body artifacts, article capture, or pages beyond six allowlisted GETs.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from scraper.sources.vn_journal_listing import (
    CATEGORY_URLS, parse_category_html, merge_category_observations,
)

HOST = "https://tapchiqptd.vn"
ROBOTS = HOST + "/robots.txt"
KEYWORD = HOST + "/Keywords/Keyword.aspx?cul=en&key=Defence"
URLS = (ROBOTS,) + tuple(CATEGORY_URLS.values()) + (KEYWORD,)
MAX_GET = 6
MAX_RESPONSE = 256_000
PAGE_RE = re.compile(r"^(?:\[?\d{1,3}\]?|next|previous|first|last|[<>|. ]{1,6})$", re.I)


class ProbeRefused(ValueError):
    """An access/policy/shape assumption failed; stop without alternative."""


def _path_of_href(href, base):
    """Never include form tokens, arbitrary query strings, or external hosts."""
    try:
        resolved = urlsplit(urljoin(base, href))
        if (resolved.scheme != "https" or resolved.netloc != "tapchiqptd.vn"
                or resolved.username or resolved.password or resolved.port is not None):
            return None
        return resolved.path
    except ValueError:
        return None


def inspect_controls(html, source_url):
    """Report *structural* navigation clues, never publisher prose or HTML."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.html is None or soup.body is None:
        raise ProbeRefused("not a complete HTML page")
    anchors = []
    for a in soup.select("a[href], button"):
        label = a.get_text(" ", strip=True)
        # Capture only explicit paging-like labels, and never site headings.
        if len(label) > 14 or not PAGE_RE.fullmatch(label):
            continue
        href = a.get("href", "")
        onclick = a.get("onclick", "")
        surrounding = a.parent
        css = " ".join(str(x) for x in (
            (surrounding.get("class") or []) if surrounding else []
        )).lower() if surrounding else ""
        kind = (
            "javascript_postback" if "__doPostBack" in href or "__doPostBack" in onclick
            else "javascript_action" if href.lower().startswith("javascript:")
            else "button" if a.name == "button"
            else "same_host_link" if _path_of_href(href, source_url)
            else "no_href_or_external"
        )
        anchors.append({
            "label": label[:14],
            "kind": kind,
            "target_path": _path_of_href(href, source_url) if kind == "same_host_link" else None,
            "parent_class_has_paging_word": bool(re.search(r"pag|paging|pager", css)),
        })
        if len(anchors) > 40:
            raise ProbeRefused("unexpected amount of pagination-like controls")
    forms = []
    for form in soup.select("form"):
        action = form.get("action", "")
        forms.append({
            "method": (form.get("method") or "GET").upper(),
            "action_path": _path_of_href(action, source_url),
            "has_viewstate": bool(form.select('input[name="__VIEWSTATE"]')),
            "has_eventtarget": bool(form.select('input[name="__EVENTTARGET"]')),
            "has_eventvalidation": bool(form.select('input[name="__EVENTVALIDATION"]')),
            "input_name_count": len(form.select("input[name]")),
        })
        if len(forms) > 10:
            raise ProbeRefused("unexpected forms")
    return {
        "paging_like_controls": anchors,
        "forms": forms,
        "paging_controls_observed": bool(anchors),
        "pagination_route_verified": False,
        "historical_enumeration_proven": False,
    }


def snapshot_section(html, url, raw_digest):
    obs = parse_category_html(html, url)
    hints = sorted(x.date_hint for x in obs.candidates if x.date_hint is not None)
    identities = sorted(x.source_identity for x in obs.candidates)
    controls = inspect_controls(html, url)
    return obs, {
        "category": obs.category_page,
        "url": url,
        "response_sha256": raw_digest,
        "candidate_count": len(obs.candidates),
        "date_hint_count": len(hints),
        "earliest_observed_date_hint": hints[0] if hints else None,
        "latest_observed_date_hint": hints[-1] if hints else None,
        "identity_set_sha256": hashlib.sha256(("\n".join(identities)+"\n").encode("ascii")).hexdigest(),
        "link_identity_list_retained": False,
        "candidate_dates_article_verified": False,
        "controls": controls,
    }


def run_probe(session, sleeper=time.sleep):
    """Robots-gated, exactly six requests max; one-shot, no page-2 requests."""
    from core.collection.vietnam_identity import USER_AGENT
    from scraper.sources.vn_shadow_http import (
        parse_robots, robots_rules, robots_crawl_delay,
        robots_allows, rules_file_problem,
    )

    session.trust_env = False
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Encoding": "identity",
        "Accept": "text/plain,text/html",
    })
    get_count = 0

    def read(url, mime):
        nonlocal get_count
        if url not in URLS or get_count >= MAX_GET:
            raise ProbeRefused("unapproved URL/request count")
        get_count += 1
        response = None
        try:
            response = session.get(url, stream=True, allow_redirects=False, timeout=20)
            raw = bytearray()
            for chunk in response.iter_content(32768):
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE:
                    raise ProbeRefused("response larger than declared ceiling")
            if (response.status_code != 200 or response.url != url
                    or response.headers.get("Location") or response.headers.get("Cf-Mitigated")):
                raise ProbeRefused("HTTP refusal, redirect or challenge")
            if not response.headers.get("Content-Type", "").lower().startswith(mime):
                raise ProbeRefused("unexpected content type")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise ProbeRefused("unexpected compression")
            text = bytes(raw).decode("utf-8", "strict")
            if re.search(r"cf-chl|challenge-platform|just a moment|captcha", text[:3500], re.I):
                raise ProbeRefused("site challenge")
            return text, hashlib.sha256(raw).hexdigest()
        finally:
            if response is not None:
                response.close()
            session.cookies.clear()

    robots, digest = read(ROBOTS, "text/plain")
    if rules_file_problem(robots.encode("utf-8")) is not None:
        raise ProbeRefused("robots response not verifiable")
    groups = parse_robots(robots)
    rules = robots_rules(groups)
    delay = robots_crawl_delay(groups)
    delay = 2.0 if delay is None else max(2.0, delay)
    if delay > 60:
        raise ProbeRefused("robots delay exceeds finite run budget")
    report = {
        "schema": "ipr-vndj-history-controls/1",
        "investigation_issue": 154,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "robots_sha256": digest,
        "request_budget": MAX_GET,
        "request_count": None,
        "source_bytes_retained": False,
        "article_text_retained": False,
        "article_ids_retained": False,
        "source_enabled": False,
        "historical_completeness_proven": False,
        "rights_to_republish_proven": False,
        "category_pages": [],
        "keyword": None,
    }
    observations = []
    for url in URLS[1:]:
        if not robots_allows(rules, urlsplit(url).path):
            raise ProbeRefused("robots disallow declared page")
        sleeper(delay)
        html, sha = read(url, "text/html")
        if url == KEYWORD:
            report["keyword"] = {
                "url": url,
                "response_sha256": sha,
                "controls": inspect_controls(html, url),
                "keyword_query_not_an_exhaustive_archive": True,
            }
        else:
            obs, section = snapshot_section(html, url, sha)
            observations.append(obs)
            report["category_pages"].append(section)
        del html
    union = merge_category_observations(observations)
    if len(observations) != 4 or get_count != 6 or not union["all_four_categories_observed"]:
        raise ProbeRefused("four-category coverage / budget failed")
    report["request_count"] = get_count
    report["union_visible_id_count"] = union["unique_observed_article_count"]
    report["union_dated_hint_count"] = union["dated_hint_count"]
    report["interpretation"] = (
        "Rolling first-page windows; no demonstrated exhaustive dated enumeration. "
        "Keyword query pagination must not be promoted to complete category history. "
        "Date hints are locally printed clues, not article-verified release dates."
    )
    return report


def main():
    import os
    import requests

    report = run_probe(requests.Session())
    # Only scrubbed structural metadata is written, never HTML, prose,
    # page-specific text, full URLs with form tokens, or ID-level memberships.
    path = os.environ.get("REPORT")
    if not path:
        raise ProbeRefused("disposable runner REPORT path must be provided")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, sort_keys=True, indent=2)
        f.write("\n")
    print(json.dumps({
        "request_count": report["request_count"],
        "union_visible_id_count": report["union_visible_id_count"],
        "union_dated_hint_count": report["union_dated_hint_count"],
        "category_pages": [{
            k: p[k] for k in ("category", "candidate_count",
                              "earliest_observed_date_hint", "latest_observed_date_hint",
                              "date_hint_count", "identity_set_sha256")
        } for p in report["category_pages"]],
        "keyword_paging": report["keyword"]["controls"]["paging_like_controls"],
        "historical_completeness_proven": False,
        "source_enabled": False,
    }, indent=2))


if __name__ == "__main__":
    main()
