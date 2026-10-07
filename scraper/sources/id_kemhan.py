"""Kemhan's Berita institutional-news family, isolated shadow use only."""
import re
from datetime import date
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from core.collection.contract import ExtractedDocument
from scraper.sources.desk_shadow_http import ListingShadowAdapter, Page

HOST = "www.kemhan.go.id"
LISTING = "https://" + HOST + "/category/berita"
ARTICLE = re.compile(r"^/([0-9]{4})/([0-9]{2})/([0-9]{2})/[a-z0-9-]+\.html$")
MONTHS = dict(zip(("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
                   "Agustus", "September", "Oktober", "November", "Desember"), range(1, 13)))


def one(nodes, label):
    if len(nodes) != 1:
        raise ValueError("expected exactly one " + label)
    return nodes[0]


def stated_date(text):
    match = re.fullmatch(r"[A-Za-z]+,\s+([0-9]{1,2})\s+([A-Za-z]+)\s+([0-9]{4})", text.strip())
    if not match or match[2] not in MONTHS:
        raise ValueError("unrecognized Indonesian publication date")
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def article_url(url):
    parts = urlsplit(url)
    match = ARTICLE.fullmatch(parts.path)
    if parts.scheme != "https" or parts.netloc != HOST or parts.query or parts.fragment or not match:
        raise ValueError("not a discovered Kemhan article URL")
    return url, date(*map(int, match.groups())).isoformat()


class KemhanAdapter(ListingShadowAdapter):
    host, listing = HOST, LISTING

    def first_request(self, window):
        return self.listing, None

    def parse_listing(self, text, request, number):
        soup = BeautifulSoup(text, "html.parser")
        if one(soup.select("h1"), "ministry masthead").get_text(strip=True) != "KEMENTERIAN PERTAHANAN REPUBLIK INDONESIA":
            raise ValueError("wrong ministry page")
        rows = soup.select(".listing-news")
        if not rows:
            raise ValueError("missing institutional-news rows; never silence")
        items = []
        for row in rows:
            anchor = one(row.select("h4 a[href]"), "news link")
            url, slug_date = article_url(anchor["href"])
            published = stated_date(one(row.select("small"), "listed date").get_text())
            if published != slug_date:
                raise ValueError("listed date disagrees with dated URL")
            if not row.select('a[href="' + LISTING + '"]'):
                raise ValueError("listing contains a different publication family")
            title = anchor.get_text(" ", strip=True)
            if not title:
                raise ValueError("missing listed title")
            items.append({"url": url, "date": published, "title": title})
        active = one(soup.select("a.active"), "current listing page")
        if active.get_text(strip=True) != str(number):
            raise ValueError("wrong listing-page number")
        pagination = active.parent.parent
        expected = LISTING + "/page/" + str(number + 1)
        urls = {a["href"] for a in pagination.select("a[href]") if a["href"] == expected}
        # If later pages are advertised, the immediate next one must be linked.
        later = [a for a in pagination.select("a[href]") if re.fullmatch(
            re.escape(LISTING) + r"/page/[0-9]+", a["href"]) and int(a["href"].rsplit("/", 1)[1]) > number]
        if later and not urls:
            raise ValueError("pagination omits the next page")
        return Page(items, (expected, None) if urls else None)

    def parse_article(self, text, url):
        url, slug_date = article_url(url)
        soup = BeautifulSoup(text, "html.parser")
        canonical = one(soup.select('link[rel="canonical"]'), "canonical link").get("href")
        if canonical != url:
            raise ValueError("canonical URL disagrees with discovery")
        body = one(soup.select(".def-page.article"), "article body")
        title = one(body.select("h2"), "article title").get_text(" ", strip=True)
        published = stated_date(one(body.select("small"), "article date").get_text())
        if published != slug_date:
            raise ValueError("article date disagrees with URL")
        # The site's malformed img tags sometimes wrap prose. Do not remove img
        # descendants: get_text keeps that prose, while not collecting images.
        for node in body.select("script, style, noscript"):
            node.decompose()
        paragraphs = [p.get_text(" ", strip=True) for p in body.find_all(
            ["p", "ul", "ol", "table", "blockquote", "div"], recursive=False)]
        prose = "\n\n".join(p for p in paragraphs if p)
        if not title or not prose:
            raise ValueError("missing original article text")
        return ExtractedDocument(url, self.slug, title, prose, published, "id", {
            "source_identity": "kemhan:" + urlsplit(url).path,
            "publisher": "Kementerian Pertahanan Republik Indonesia",
            "issuer": None, "publication_kind": "institutional_news",
            "published_date_original": one(body.select("small"), "date").get_text(strip=True),
        })
