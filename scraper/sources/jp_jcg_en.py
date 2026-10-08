"""Japan Coast Guard English press-release HTML family; shadow candidate only.

Institution: Japan Coast Guard (maritime law enforcement), NOT Japan MOD.
Uses the existing isolated ListingShadowAdapter transport: named client,
robots checks, no redirect/challenge bypass, bounded fetches, capture hashes.
No production manifest or authorization to publish is present in this module.

Document scope: publisher's HTML release text, not embedded PDF attachments,
photos or any broader JCG publications. Every listed article stays distinguishable
by its published canonical URL, never its title.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from core.collection.contract import ExtractedDocument
from scraper.sources.desk_shadow_http import ListingShadowAdapter, Page

HOST = "www.kaiho.mlit.go.jp"
LISTING = "https://" + HOST + "/e/topics_archive/index.html"
RELEASE = re.compile(r"^/e/topics_archive/article([0-9]+)\.html$")
# Initial bounded pilot scope; older publisher rows are counted as discovery
# history but are not admitted until their URL/document families are reviewed.
PILOT_BEGIN = "2026-09-01"
DATE_DMY = re.compile(r"^(\d{1,2})\s+(\d{1,2})\s+(\d{4})$")
DATE_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
DATE_DOTTED = re.compile(r"^(\d{4})[./](\d{1,2})[./](\d{1,2})$")
DATE_ENGLISH = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y")


def one(nodes, purpose):
    nodes = list(nodes)
    if len(nodes) != 1:
        raise ValueError("expected one " + purpose + ", observed " + str(len(nodes)))
    return nodes[0]


def canon(url):
    """Accept only an explicitly linked first-party release on this hostname."""
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != HOST or parts.query
            or parts.fragment or not RELEASE.fullmatch(parts.path)):
        raise ValueError("URL is not a JCG English release identity")
    return "https://" + HOST + parts.path


def source_date(value):
    text = " ".join(value.replace("\u3000", " ").strip().split())
    m = DATE_DMY.fullmatch(text)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1])).isoformat()
    m = DATE_ISO.fullmatch(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    m = DATE_DOTTED.fullmatch(text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    for fmt in DATE_ENGLISH:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError("unrecognized JCG publisher date (no inferred fallback)")


class JCGEnglishAdapter(ListingShadowAdapter):
    host, listing = HOST, LISTING

    def first_request(self, window):
        return self.listing, None

    def discover(self, window):
        outcome = super().discover(window)
        if outcome.ok and hasattr(self, "listing_observation"):
            self.listing_report.update(self.listing_observation)
        return outcome

    def parse_listing(self, text, request, number):
        if request != (LISTING, None) or number != 1:
            raise ValueError("only the publisher's complete English index is scoped")
        soup = BeautifulSoup(text, "html.parser")
        section = one(soup.select("main article.main-article section.topics.has-pd"),
                      "JCG press-release listing section")
        date_nodes = section.select("dl.topics-list p.topics-date")
        links = section.select("dl.topics-list a.arrow-link[href]")
        if not date_nodes or len(date_nodes) != len(links):
            raise ValueError("publisher listing date/article pairs incomplete")
        items = []
        seen = set()
        all_dates = []
        excluded_earlier = 0
        for dnode, link in zip(date_nodes, links):
            if dnode.find_parent("dl") is not link.find_parent("dl"):
                raise ValueError("date paired across different publisher year groups")
            stated = source_date(dnode.get_text(" ", strip=True))
            all_dates.append(stated)
            if stated < PILOT_BEGIN:
                excluded_earlier += 1
                continue
            url = canon(urljoin(LISTING, link["href"]))
            title = link.get_text(" ", strip=True)
            if not title or url in seen:
                raise ValueError("missing title or repeated publisher article identity")
            seen.add(url)
            items.append({"url": url, "date": stated, "title": title})
        if all_dates != sorted(all_dates, reverse=True):
            raise ValueError("JCG source listing chronology changed")
        self.listing_observation = {
            "publisher_index_rows_total": len(all_dates),
            "outside_declared_pilot_scope": excluded_earlier,
            "pilot_source_begin": PILOT_BEGIN,
        }
        return Page(items, None)

    def parse_article(self, text, url):
        url = canon(url)
        soup = BeautifulSoup(text, "html.parser")
        section = one(soup.select("main article.main-article section.topics.topics-article"),
                      "JCG original release section")
        title = one(section.select("h1.entry-title"), "release title").get_text(" ", strip=True)
        time = one(section.select("time"), "publisher release date")
        raw_date = time.get_text(" ", strip=True)
        candidates = [source_date(raw_date)]
        if time.get("datetime"):
            candidates.append(source_date(time["datetime"]))
        if len(set(candidates)) != 1:
            raise ValueError("publisher release date labels disagree")
        body = one(section.select("div.topics-article__main.tich-text"),
                   "official release body")
        for node in body.select("script, style, noscript, nav, form, iframe, svg"):
            node.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in body.select("p, li, blockquote")]
        paragraphs = [p for p in paragraphs if p]
        if not title or len(" ".join(paragraphs)) < 180:
            raise ValueError("body too short for a substantive original HTML release")
        if not any(len(p) > 70 for p in paragraphs):
            raise ValueError("no substantive paragraph (possibly links-only page)")
        # If the publisher links an additional PDF, do not pretend to have
        # captured it or that its text is part of this original HTML body.
        pdf_links = []
        for link in body.select("a[href]"):
            href = urljoin(url, link["href"])
            p = urlsplit(href)
            if p.path.lower().endswith(".pdf"):
                if p.scheme != "https" or p.netloc != HOST:
                    raise ValueError("release references off-host PDF; requires separate review")
                pdf_links.append(href)
        prose = "\n\n".join(paragraphs)
        return ExtractedDocument(
            url=url, source_slug=self.slug, title_original=title,
            text_original=prose, published_date=candidates[0],
            language_tag="en", extra={
                "source_identity": "jcg-en:" + RELEASE.fullmatch(urlsplit(url).path)[1],
                "publisher": "Japan Coast Guard",
                "issuer": "Japan Coast Guard",
                "publication_kind": "english_official_press_release",
                "published_date_original": raw_date,
                "body_scope": "published_html_text_only",
                "attachments_collected": False,
                "attachment_urls": sorted(set(pdf_links)),
                "derivation": "first_party_english_original_not_translated",
            })
