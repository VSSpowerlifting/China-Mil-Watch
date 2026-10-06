"""MND-labeled releases republished by Korea Policy Briefing; not an MND wire.

The government portal's own robots policy governs this separate host. No
request is made to mnd.go.kr. HWPX attachments are read as bounded ZIP/XML;
iframe shells and metadata summaries are never used as release bodies.
"""
import hashlib
import io
import re
import zipfile
from datetime import date
from urllib.parse import parse_qs, urljoin, urlsplit
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from core.collection import status as st
from core.collection.contract import ExtractedDocument
from scraper.sources.desk_shadow_http import ListingShadowAdapter, Page, Refused
from scraper.sources.id_kemhan import one

HOST = "www.korea.kr"
LISTING = "https://" + HOST + "/briefing/pressReleaseList.do"
ISSUER = "국방부"


def article_url(url):
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    ids = query.get("newsId", [])
    if (parts.scheme != "https" or parts.netloc != HOST or parts.fragment or
            parts.path != "/briefing/pressReleaseView.do" or len(ids) != 1 or
            not re.fullmatch(r"[0-9]+", ids[0])):
        raise ValueError("not a Policy Briefing release URL")
    return "https://" + HOST + parts.path + "?newsId=" + ids[0]


def hwpx_text(payload):
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) > 200 or len({i.filename for i in entries}) != len(entries):
                raise ValueError("oversized or duplicate-member HWPX archive")
            if sum(i.file_size for i in entries) > 10_000_000:
                raise ValueError("expanded HWPX archive exceeds limit")
            sections = sorted((i for i in entries if re.fullmatch(r"Contents/section[0-9]+\.xml", i.filename)),
                              key=lambda i: int(re.search(r"[0-9]+", i.filename)[0]))
            if not sections:
                raise ValueError("no HWPX document sections")
            paragraphs = []
            for section in sections:
                raw = archive.read(section)
                xml = raw.decode("utf-8", "strict")
                if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
                    raise ValueError("XML declarations refused")
                root = ET.fromstring(xml)
                for p in root.iter():
                    if p.tag.rsplit("}", 1)[-1] == "p":
                        # Direct runs only: table-cell paragraphs are visited in
                        # their own turn, never duplicated inside their parent.
                        strings = ["".join(t.itertext()) for run in p
                                   if run.tag.rsplit("}", 1)[-1] == "run" for t in run
                                   if t.tag.rsplit("}", 1)[-1] == "t"]
                        line = "".join(strings).strip()
                        if line:
                            paragraphs.append(line)
            if not paragraphs:
                raise ValueError("HWPX carries no original text")
            return "\n".join(paragraphs)
    except (zipfile.BadZipFile, ET.ParseError, RuntimeError, KeyError) as exc:
        raise ValueError("invalid HWPX document: " + type(exc).__name__)


class KoreaPolicyAdapter(ListingShadowAdapter):
    host, listing = HOST, LISTING

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.documents = {}

    def first_request(self, window):
        from datetime import timedelta
        self.documents = {}
        return self.listing, {"repCode": "A00005", "pageIndex": "1",
                              "startDate": (window.target_date - timedelta(days=window.lookback_days)).isoformat(),
                              "endDate": window.target_date.isoformat()}

    def parse_listing(self, text, request, number):
        soup = BeautifulSoup(text, "html.parser")
        form = one(soup.select("form#mainForm"), "published search form")
        if form.get("action") != "/briefing/pressReleaseList.do" or form.get("method", "").lower() != "post":
            raise ValueError("search-form contract changed")
        for key, value in request[1].items():
            if one(form.select('input[name="' + key + '"]'), key).get("value") != value:
                raise ValueError("server did not retain requested search filter")
        if one(soup.select('label[for="A00005"]'), "ministry filter").get_text(strip=True) != ISSUER:
            raise ValueError("ministry code changed")
        items = []
        total_text = one(soup.select(".result strong"), "search-result count").get_text(strip=True).replace(",", "")
        if not total_text.isdigit():
            raise ValueError("unknown search-result count")
        total = int(total_text)
        for anchor in soup.select('a[href*="pressReleaseView.do"][href*="pageIndex="]'):
            source = one(anchor.select(".source"), "listing source").find_all("span", recursive=False)
            if len(source) != 2 or source[1].get_text(strip=True) != ISSUER:
                raise ValueError("ministry filter returned another issuer")
            published = date.fromisoformat(source[0].get_text(strip=True).replace(".", "-")).isoformat()
            if not request[1]["startDate"] <= published <= request[1]["endDate"]:
                raise ValueError("search returned a date outside the requested window")
            title = one(anchor.select("strong"), "release title").get_text(" ", strip=True)
            items.append({"url": article_url(urljoin(self.listing, anchor["href"])),
                          "date": published, "title": title})
        if not items:
            # A missing list alone is a failure; the site's explicit empty-state
            # marker is required (checked against the captured empty response).
            if (not soup.select(".list_type .no_data") or
                    one(soup.select(".result strong"), "result count").get_text(strip=True) != "0"):
                raise ValueError("missing release list without explicit empty marker")
            return Page([], declared_total=0)
        paging = one(soup.select(".paging"), "pagination")
        current = paging.select("a.on")
        if current and (len(current) != 1 or current[0].get_text(strip=True) != str(number)):
            raise ValueError("wrong search-page number")
        pages = [int(m[1]) for a in paging.select("a[onclick]")
                 for m in [re.fullmatch(r"pageLink\(([0-9]+)\); return false;", a["onclick"])] if m]
        if any(n > number for n in pages) and number + 1 not in pages:
            raise ValueError("search pagination omits next page")
        form_data = dict(request[1], pageIndex=str(number + 1))
        return Page(items, (self.listing, form_data) if number + 1 in pages else None, total)

    def metadata(self, text, url):
        soup = BeautifulSoup(text, "html.parser")
        canonical = one(soup.select('link[rel="canonical"]'), "canonical release link").get("href")
        if canonical != article_url(url):
            raise ValueError("canonical release identity disagrees")
        title = one(soup.select(".view_title h1"), "release title").get_text(" ", strip=True)
        info = one(soup.select(".variety .info"), "release provenance")
        published = date.fromisoformat(one(info.select("span:first-child"), "release date").get_text(strip=True).replace(".", "-")).isoformat()
        issuer = one(info.select('a.gotosite[href="/news/ministryNewsList.do?repCode=A00005"]'), "release issuer")
        if not issuer.get_text(strip=True).startswith(ISSUER):
            raise ValueError("release issuer changed")
        links = {urljoin(url, a["href"]) for a in soup.select('a[href*="/common/download.do"]')
                 if a.get_text(strip=True).lower().endswith(".hwpx")}
        if len(links) != 1:
            raise ValueError("exactly one published HWPX attachment required; other formats unmeasured")
        document_url = links.pop()
        parts = urlsplit(document_url)
        query = parse_qs(parts.query)
        if (parts.netloc != HOST or parts.scheme != "https" or parts.path != "/common/download.do" or
                set(query) != {"fileId", "tblKey"} or query["tblKey"] != ["GMN"] or
                len(query["fileId"]) != 1 or not query["fileId"][0].isdigit()):
            raise ValueError("unexpected document link")
        return title, published, document_url

    def fetch(self, reference):
        capture = super().fetch(reference)
        if capture.status == st.OK:
            try:
                title, published, url = self.metadata(capture.body, reference.url)
                hint = self.references[reference.url]
                if title != hint["title"] or published != hint["date"]:
                    raise ValueError("release metadata disagrees with listing")
                payload = self._request(url, binary=True)
                self.documents[reference.url] = (payload, dict(self.evidence[-1]))
            except (Refused, ValueError) as exc:
                capture.status = exc.status if isinstance(exc, Refused) else st.EXTRACTION_FAILURE
                capture.error_detail = str(exc)
        return capture

    def parse_article(self, text, url):
        title, published, document_url = self.metadata(text, url)
        if url not in self.documents:
            raise ValueError("release attachment not retrieved; iframe is not body text")
        payload, evidence = self.documents[url]
        prose = hwpx_text(payload)
        return ExtractedDocument(url, self.slug, title, prose, published, "ko", {
            "source_identity": "korea-policy:" + parse_qs(urlsplit(url).query)["newsId"][0],
            "publisher": "대한민국 정책브리핑", "issuer": ISSUER,
            "publication_kind": "syndicated_press_release", "body_scope": "published_hwpx_text",
            "attachments_collected": True, "document_url": document_url,
            "document_capture_sha256": evidence["capture_sha256"],
            "document_retrieved_at": evidence["retrieved_at"],
        })
