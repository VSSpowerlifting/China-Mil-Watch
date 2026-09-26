"""
Shared fixtures for the Philippines (AFP) shadow adapter and runner tests.

Not a test module: it is named so `unittest discover` does not collect it.

Everything here is built from responses saved from `api.afp.mil.ph` on
2026-09-26 (see tests/fixtures/ph_afp). Where a test needs a defect the live
API did not show on that day — a foreign `next` link, a draft status, a
timestamp with no offset — the defect is DERIVED by editing a real response in
memory, and the derivation is visible at the call site. No network, no
tracked-database access, no writes outside a temporary directory.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scraper.sources import ph_afp as ph                        # noqa: E402

FIX = REPO_ROOT / "tests" / "fixtures" / "ph_afp"

#: Real detail payloads. 1384/1378/1312 are current-CMS press items; 1211 is a
#: Joomla-migrated 2022 item whose intro and body are complementary; 1331/1330
#: are the same statement published twice as an image alone (empty body);
#: 1365 is another image-only statement; 834 is a misfiled site page in
#: `uncategorised`; 949 is a site page in `afp-logos`.
DETAIL_IDS = (1384, 1378, 1312, 1211, 1331, 1330, 1365, 834, 949)

ROBOTS_WWW = (FIX / "robots_www.txt").read_text(encoding="utf-8")
ROBOTS_API_404 = (FIX / "robots_api_404.html").read_text(encoding="utf-8")
ROBOTS_DENY_ALL = "User-agent: *\nDisallow: /\n"
ROBOTS_DENY_ARTICLES = "User-agent: *\nDisallow: /articles/\nAllow: /\n"
CHALLENGE_HTML = ("<!DOCTYPE html><html><head><title>Just a moment...</title>"
                  "</head><body>challenge-platform</body></html>")


def detail_bytes(ident: int) -> bytes:
    return (FIX / ("detail_%d.json" % ident)).read_bytes()


def detail_obj(ident: int) -> dict:
    return json.loads(detail_bytes(ident).decode("utf-8"))


def list_entry(detail: dict) -> dict:
    """The listing shape of an article, derived from its real detail."""
    keys = ("id", "title", "slug", "category", "category_name", "category_slug",
            "intro_html", "featured_image", "image_caption", "is_featured",
            "published_at", "hits")
    return {k: detail[k] for k in keys}


def list_page(entries, count=None, next_url=None, previous=None) -> bytes:
    return json.dumps({
        "count": len(entries) if count is None else count,
        "next": next_url, "previous": previous,
        "results": list(entries)}).encode("utf-8")


def real_list_from_details(ids=DETAIL_IDS, exclude_categories=()) -> list:
    out = []
    for i in ids:
        d = detail_obj(i)
        if d["category_slug"] in exclude_categories:
            continue
        out.append(list_entry(d))
    return out


class FakeResponse:
    def __init__(self, body=b"", status_code=200, headers=None, url=""):
        if isinstance(body, str):
            self.content = body.encode("utf-8")
        else:
            self.content = body
        self.text = self.content.decode("utf-8", "replace")
        self.status_code = status_code
        self.headers = headers if headers is not None else {
            "Content-Type": "application/json"}
        self.url = url


class Boom(Exception):
    """A transport failure, as requests would raise one."""


class BoomTimeout(Exception):
    """Named so the adapter's timeout classification recognises it."""


BoomTimeout.__name__ = "ReadTimeout"


class FakeSession:
    """
    Serves saved fixtures by URL and records every URL it was asked for.

    `pages` maps a listing URL to the bytes to serve; any listing URL not in
    the map is answered with the real DRF "Invalid page." 404. `details` maps a
    slug to the bytes to serve, or to a FakeResponse for a special case.
    """

    def __init__(self, pages=None, details=None, robots_www=ROBOTS_WWW,
                 robots_www_status=200, robots_api=ROBOTS_API_404,
                 robots_api_status=404, api_robots_headers=None,
                 raise_on=None, list_headers=None, detail_headers=None,
                 final_url=None):
        self.pages = pages or {}
        self.details = details or {}
        self.robots_www = robots_www
        self.robots_www_status = robots_www_status
        self.robots_api = robots_api
        self.robots_api_status = robots_api_status
        self.api_robots_headers = api_robots_headers if (
            api_robots_headers is not None) else {
            "Content-Type": "text/html", "X-Robots-Tag": "noindex, nofollow"}
        #: {url substring: exception class} — a transport failure on match.
        self.raise_on = dict(raise_on or {})
        self.list_headers = list_headers if list_headers is not None else {
            "Content-Type": "application/json",
            "X-Robots-Tag": "noindex, nofollow"}
        self.detail_headers = detail_headers if detail_headers is not None \
            else {"Content-Type": "application/json"}
        self.final_url = final_url
        self.calls = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append(url)
        for token, exc in self.raise_on.items():
            if token in url:
                raise exc("connection reset")
        if url == ph.ROBOTS_WWW:
            return FakeResponse(self.robots_www, self.robots_www_status,
                                {"Content-Type": "text/plain"})
        if url == ph.ROBOTS_API:
            return FakeResponse(self.robots_api, self.robots_api_status,
                                dict(self.api_robots_headers))
        if url in self.pages:
            served = self.pages[url]
            if isinstance(served, FakeResponse):
                return served
            return FakeResponse(served, 200, dict(self.list_headers))
        if url.startswith(ph.LIST_URL) and "?" in url:
            return FakeResponse(b'{"detail":"Invalid page."}', 404,
                                {"Content-Type": "application/json"})
        for slug, served in self.details.items():
            if url == ph.detail_url(slug):
                if isinstance(served, FakeResponse):
                    return served
                return FakeResponse(served, 200, dict(self.detail_headers),
                                    url=self.final_url or url)
        return FakeResponse(b'{"detail":"Not found."}', 404,
                            {"Content-Type": "application/json"})


def page_url(n: int, size: int = ph.PAGE_SIZE) -> str:
    return "%s?page_size=%d&page=%d" % (ph.LIST_URL, size, n)


def session_for(details_ids=DETAIL_IDS, exclude_categories=(),
                mutate=None, **kw) -> FakeSession:
    """
    A one-page listing plus the matching real detail payloads.

    `mutate(detail_dict)` may edit a real detail before it is served, which is
    how a derived defect is introduced without a hand-written response.
    """
    details = {}
    entries = []
    for i in details_ids:
        d = detail_obj(i)
        if d["category_slug"] in exclude_categories:
            continue
        entries.append(list_entry(d))
        served = copy.deepcopy(d)
        if mutate:
            mutate(served)
        details[d["slug"]] = json.dumps(served).encode("utf-8")
    pages = {page_url(1): list_page(entries)}
    return FakeSession(pages=pages, details=details, **kw)


class FakeSource:
    slug = "ph_afp_articles"
    enabled = False
    base_url = "https://www.afp.mil.ph"
    language_tag = "en"


class EnabledFakeSource(FakeSource):
    enabled = True


def adapter(session, cap=0, **kw):
    kw.setdefault("sleeper", lambda s: None)
    return ph.PHAfpAdapter(FakeSource(), session=session, cap=cap, **kw)
