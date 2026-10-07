"""Bounded Vietnamese ministry publication families, for isolated shadow only.

MPS reads its published foreign-affairs RSS; MOIT reads the first published
energy or foundational-industry listing. Older script pagination is never
invented. A window touching the oldest item fails instead of claiming silence.
Article dates are the printed dates; RSS/metadata instants remain separate.
"""
import base64
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, DiscoveryResult, ExtractedDocument,
    ExtractionResult, SourceHealthResult)
from core.collection.vietnam_sources import SOURCES, content_sha256, visible_date
from scraper.sources.vn_shadow_http import (
    CHALLENGE_RE, MAX_BODY_BYTES, Refusal, ShadowHttpAdapter, squash)
# Only the HTML block walker is shared. Framing, dates, listing and identity
# rules below are independently measured for these publishers.
from scraper.sources.vn_vgp import _body

HANOI = timezone(timedelta(hours=7))


def one(nodes, label):
    if len(nodes) != 1:
        raise ValueError("expected one %s, found %d" % (label, len(nodes)))
    return nodes[0]


def meta(soup, name):
    nodes = soup.find_all("meta", attrs={"property": name})
    if not nodes:
        nodes = soup.find_all("meta", attrs={"name": name})
    if len(nodes) > 1:
        raise ValueError("ambiguous metadata: %s" % name)
    return nodes[0].get("content") if nodes else None


def framed(text, host):
    if CHALLENGE_RE.search(text) or re.search(
            r"document\.cookie\s*=.*location\.reload", text, re.I | re.S):
        raise ValueError("challenge markup")
    if not re.search(r"</html>\s*(?:<!--.*?-->\s*)*$", text, re.S):
        raise ValueError("incomplete HTML document")
    soup = BeautifulSoup(text, "html.parser")
    if soup.html is None or soup.html.get("lang") != "vi":
        raise ValueError("not the Vietnamese edition")
    if host == "moit.gov.vn" and meta(soup, "og:site_name") != host:
        raise ValueError("not the Ministry of Industry and Trade frame")
    return soup


class VNMinistryAdapter(ShadowHttpAdapter):
    def __init__(self, source, **kwargs):
        if source.slug not in SOURCES:
            raise ValueError("unknown ministry surface")
        self.profile = SOURCES[source.slug]
        if list(source.discovery_endpoints) != [self.profile.listing]:
            raise ValueError("manifest does not match the measured listing")
        super().__init__(source, **kwargs)
        self.robots_url = "https://" + self.profile.host + "/robots.txt"
        self._listing = {}
        self.listing_report = {}

    def _challenged(self, headers, text):
        return bool(CHALLENGE_RE.search(text) or re.search(
            r"document\.cookie\s*=.*location\.reload", text, re.I | re.S))

    def discover(self, window):
        self._listing, self.listing_report = {}, {}
        start = window.target_date - timedelta(days=window.lookback_days)
        try:
            self._load_robots(st.LISTING_FAILURE)
            if not self._permits(self.profile.listing):
                raise Refusal(st.AUTH_FAILURE, "robots.txt disallows the listing",
                              self.profile.listing)
            raw = self._get(self.profile.listing, MAX_BODY_BYTES, st.LISTING_FAILURE)
            self._gate(raw)
            self._keep("listing", raw)
            if self.profile.host == "bocongan.gov.vn":
                items, pager = self._rss(raw)
            else:
                items, pager = self._moit_listing(self._screen(raw, st.LISTING_FAILURE))
            if not items or len({i["url"] for i in items}) != len(items):
                raise ValueError("empty or repeating listing")
            dates = [i["date"] for i in items]
            if dates != sorted(dates, reverse=True):
                raise ValueError("listing is not newest-first by its printed date")
            self.listing_report = {
                "listing_url": self.profile.listing, "pages_read": 1,
                "items_listed": len(items), "newest_listed": dates[0],
                "oldest_listed": dates[-1], "window_start": start.isoformat(),
                "window_end": window.target_date.isoformat(), "pagination": pager,
                "coverage": "proven" if dates[-1] < start.isoformat() else "unprovable",
                "listed": [[self.profile.article_id(i["url"]), i["date"]] for i in items],
            }
            if not dates[-1] < start.isoformat():
                raise ValueError("window coverage unprovable on the published first page/feed")
            selected = [i for i in items if start.isoformat() <= i["date"]
                        <= window.target_date.isoformat()]
            self._listing = {i["url"]: i for i in selected}
            self.listing_report["selected"] = len(selected)
            self.listing_report["listed_after_window"] = sum(
                i["date"] > window.target_date.isoformat() for i in items)
            refs = [CandidateReference(i["url"], self.slug, self.profile.listing, i["date"])
                    for i in selected]
            return DiscoveryResult(self.slug, st.OK if refs else st.OK_NO_PUBLICATIONS, refs)
        except Refusal as exc:
            return DiscoveryResult(self.slug, exc.status, error_detail=exc.detail,
                                   failed_endpoints=[exc.endpoint] if exc.endpoint else [])
        except (ValueError, TypeError, KeyError, ET.ParseError, UnicodeError) as exc:
            return DiscoveryResult(self.slug, st.LISTING_FAILURE,
                                   error_detail=str(exc)[:200],
                                   failed_endpoints=[self.profile.listing])

    def _rss(self, raw):
        if raw.status in (401, 403):
            raise Refusal(st.AUTH_FAILURE, "RSS HTTP %d" % raw.status, raw.url, raw.status)
        if raw.status != 200:
            raise Refusal(st.LISTING_FAILURE, "RSS HTTP %d" % raw.status, raw.url, raw.status)
        ctype = raw.headers.get("content-type", "").split(";", 1)[0].lower()
        if ctype not in ("application/xml", "text/xml", "application/rss+xml"):
            raise ValueError("RSS was not served as XML")
        text = raw.body.decode("utf-8")
        if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
            raise ValueError("RSS contains a document type/entity declaration")
        root = ET.fromstring(text)
        channel = one(root.findall("channel"), "RSS channel")
        if (root.tag != "rss" or channel.findtext("generator") != self.profile.publisher
                or channel.findtext("title") != self.profile.family + " - " + self.profile.publisher
                or channel.findtext("link") != "https://" + self.profile.host):
            raise ValueError("RSS publisher/category frame changed")
        items = []
        for node in channel.findall("item"):
            fields = {k: one(node.findall(k), "RSS " + k).text
                      for k in ("link", "guid", "title", "pubDate")}
            if fields["link"] != fields["guid"] or not self.profile.article_id(fields["link"]):
                raise ValueError("RSS URL/guid identity conflict")
            if not fields["title"] or not fields["pubDate"]:
                raise ValueError("RSS title/date missing")
            stamp = parsedate_to_datetime(fields["pubDate"])
            if stamp.tzinfo is None:
                raise ValueError("RSS pubDate has no declared offset")
            items.append({"url": fields["link"], "title": fields["title"],
                          "date": stamp.astimezone(HANOI).date().isoformat(),
                          "rss_pubdate": fields["pubDate"],
                          "rss_instant_utc": stamp.astimezone(timezone.utc).isoformat()})
        return items, "finite RSS snapshot; no archive or older endpoint requested"

    def _moit_listing(self, text):
        soup = framed(text, self.profile.host)
        canonical = one(soup.select('link[rel="canonical"]'), "listing canonical").get("href")
        if canonical != self.profile.listing:
            raise ValueError("listing canonical conflict")
        module = one(soup.select('[modulerootid="%s"]' % self.profile.category_id),
                     "category listing module")
        configs = []
        for encoded in re.findall(r"decode64\('([A-Za-z0-9+/=]+)'\)", text):
            try:
                config = json.loads(base64.b64decode(encoded, validate=True))
            except (ValueError, UnicodeError):
                continue
            if (config.get("categoryId") == self.profile.category_id
                    and config.get("layout") == "Content.Article.News.default"):
                configs.append(config)
        config = one(configs, "published category pager configuration")
        if config.get("orderBy") != "publishTime DESC" or config.get("pageNo") != 1:
            raise ValueError("category ordering/page changed")
        rows = module.select("article.article-news-default")
        size, total = int(config["itemsPerPage"]), int(config["totalItems"])
        if size < 1 or total < 1 or len(rows) != min(size, total):
            raise ValueError("listing is truncated relative to its published pager")
        items = []
        for row in rows:
            anchor = one(row.select("a.article-title"), "listing title")
            url = urljoin(self.profile.listing, anchor.get("href", ""))
            if not self.profile.article_id(url):
                raise ValueError("listing contains a non-article URL")
            stamp = squash(one(row.select("span.article-date"), "listing date").get_text())
            title = squash(anchor.get_text())
            if not title:
                raise ValueError("listing title missing")
            items.append({"url": url, "title": title, "date": visible_date(stamp),
                          "listing_visible_date": stamp})
        return items, {"page": 1, "page_size": size, "total_items": total,
                       "older_pages": "script-only; not requested"}

    def fetch(self, reference):
        url = reference.url
        if reference.source_slug != self.slug or not self.profile.article_id(url):
            return CaptureResult(reference, st.FETCH_FAILURE, url,
                                 error_detail="foreign source or non-article URL refused")
        try:
            if self._rules is None:
                self._load_robots(st.FETCH_FAILURE)
            if not self._permits(url):
                raise Refusal(st.AUTH_FAILURE, "robots.txt disallows article", url)
            raw = self._get(url, MAX_BODY_BYTES, st.FETCH_FAILURE)
            text = self._screen(raw, st.FETCH_FAILURE)
            return CaptureResult(reference, st.OK, url, final_url=url, http_status=raw.status,
                                 content_type=raw.headers.get("content-type"),
                                 payload_bytes=len(raw.body),
                                 payload_sha256=hashlib.sha256(raw.body).hexdigest(),
                                 retrieved_at=raw.retrieved_at, body=text)
        except Refusal as exc:
            return CaptureResult(reference, exc.status, url, http_status=exc.http_status,
                                 error_detail=exc.detail)

    def extract(self, capture):
        try:
            url = capture.reference.url
            if (not capture.ok or not capture.body or capture.reference.source_slug != self.slug
                    or not self.profile.article_id(url) or capture.final_url != url):
                raise ValueError("capture identity/body invalid")
            soup = framed(capture.body, self.profile.host)
            if self.profile.host == "bocongan.gov.vn":
                title_node = one(soup.select("h1"), "article title")
                lead_node = title_node.find_next_sibling("p")
                container = one(soup.select(".tinymce-content"), "article body")
                column = container.parent
                stamp = squash(one(column.select("div > p.text-bca-gray-400"),
                                   "visible publication date").get_text())
                canonical = meta(soup, "og:url")
                byline = meta(soup, "author")
                if meta(soup, "og:title") != squash(title_node.get_text()):
                    raise ValueError("article title metadata conflicts")
            else:
                title_node = one(soup.select("h1.article-title"), "article title")
                lead_node = one(soup.select("div.article-brief.font-size-text"), "article lead")
                container = one(soup.select("div.article-content.common-content"), "article body")
                stamp = squash(one(soup.select("span.post-date"), "printed publication date").get_text())
                canonical = one(soup.select('link[rel="canonical"]'), "article canonical").get("href")
                byline = None  # generic Author names the portal, not an individual writer
            if canonical != url or lead_node is None:
                raise ValueError("canonical conflict or missing lead")
            title, lead = squash(title_node.get_text()), squash(lead_node.get_text())
            blocks, media, related, unknown = _body(container)
            if not title or unknown or (not blocks and not media):
                raise ValueError("missing title/body or unrecognised embedded block")
            published = visible_date(stamp)
            selected = self._listing.get(url, {})
            anomalies = []
            if capture.reference.hint_published_date not in (None, published):
                anomalies.append("listing_date_differs: %s / %s" %
                                 (capture.reference.hint_published_date, published))
            if selected.get("title") not in (None, title):
                anomalies.append("listing_title_differs")
            metadata = {"publisher": self.profile.publisher, "issuer": None,
                        "language": "vi", "family": self.profile.family,
                        "visible_publication_stamp": stamp,
                        "article_published_time": meta(soup, "article:published_time"),
                        "article_modified_time": meta(soup, "article:modified_time"),
                        "legal_effective_date": None,
                        "rss_pubdate": selected.get("rss_pubdate"),
                        "rss_instant_utc": selected.get("rss_instant_utc")}
            raw_meta = metadata["article_published_time"]
            if raw_meta:
                meta_stamp = datetime.fromisoformat(raw_meta.replace("Z", "+00:00"))
                if meta_stamp.date().isoformat() != published:
                    anomalies.append("metadata_date_differs: visible %s / metadata %s" %
                                     (published, raw_meta))
            extra = {
                "source_identity": self.profile.identity(url), "canonical_url": canonical,
                "published_at_original": stamp, "published_at_utc": None,
                "modified_at_original": metadata["article_modified_time"], "modified_at_utc": None,
                "visible_published": stamp, "byline": byline, "byline_jsonld": None,
                "publisher_jsonld": None, "category": self.profile.family, "tags": [],
                "lead_original": lead, "blocks": [list(b) for b in blocks],
                "body_status": "text" if blocks else "media_only", "media_count": media,
                "related_boxes_excluded": related, "publication_kind": self.profile.publication_kind,
                "listing_title": selected.get("title"), "listing_local_time": selected.get("date"),
                "content_hash_rule": self.profile.hash_rule,
                "content_sha256": content_sha256(self.profile.hash_rule, title, lead, blocks),
                "anomalies": anomalies, "source_metadata": metadata,
            }
            doc = ExtractedDocument(url, self.slug, title,
                                    "\n".join(([lead] if lead else []) + [t for _, t in blocks]),
                                    published, "vi", extra)
            return ExtractionResult(self.slug, st.OK, [doc])
        except (ValueError, TypeError, AttributeError) as exc:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE, error_detail=str(exc)[:200])

    def healthcheck(self):
        return SourceHealthResult(self.slug, st.OK if self.source.enabled is True
                                  else st.SKIPPED_DISABLED,
                                  "isolated Vietnamese ministry family; no production admission")
