"""DAPA-issued releases via the government Policy Briefing portal.

Distinct from MND (A00005): B00008 is a separate issuing institution and
source identity. This adapter only supplies the existing isolated collection
runner; it never admits public records or licenses originals for reuse.
"""
import re
from datetime import date
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from core.collection.contract import ExtractedDocument
from scraper.sources.desk_shadow_http import Page, ListingShadowAdapter
from scraper.sources.id_kemhan import one
from scraper.sources.kr_policy_briefing import (
    KoreaPolicyAdapter, LISTING, HOST, article_url, hwpx_text,
)

ISSUER = "방위사업청"
REPCODE = "B00008"
IDENTITY_PREFIX = "korea-dapa-policy:"
DOWNLOAD_PATH = "/common/download.do"


def observed_text_notice(html):
    """A publisher's apparent text notice, emphatically NOT permission."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    if "텍스트에 한하여" not in text:
        return "unverified"
    found = re.findall(r"공공누리\s*제\s*([0-4])\s*유형", text)
    if len(found) != 1:
        return "unverified"
    return "KOGL_type_" + found[0] + "_text_notice_only"


class KoreaDapaPolicyAdapter(KoreaPolicyAdapter):
    """Reuse proven bounded transport/HWPX extraction, isolate DAPA identity."""

    # MND has its own authorized timeout retry. DAPA does not inherit it.
    ROBOTS_TIMEOUT = 30

    def _request(self, url, form=None, robots=False, binary=False):
        return ListingShadowAdapter._request(
            self, url, form=form, robots=robots, binary=binary)

    def first_request(self, window):
        url, form = super().first_request(window)
        form["repCode"] = REPCODE
        return url, form

    def parse_listing(self, text, request, number):
        soup = BeautifulSoup(text, "html.parser")
        form = one(soup.select("form#mainForm"), "published search form")
        if (form.get("action") != "/briefing/pressReleaseList.do" or
                form.get("method", "").lower() != "post"):
            raise ValueError("DAPA search form contract changed")
        if request[0] != LISTING or request[1].get("repCode") != REPCODE:
            raise ValueError("DAPA listing request not strictly filtered")
        for key, value in request[1].items():
            if one(form.select('input[name="' + key + '"]'), key).get("value") != value:
                raise ValueError("DAPA search form lost its requested filter")
        label = one(soup.select('label[for="' + REPCODE + '"]'), "DAPA issuer filter")
        if label.get_text(strip=True) != ISSUER:
            raise ValueError("DAPA filter label changed")

        count = one(soup.select(".result strong"), "search result count").get_text(strip=True).replace(",", "")
        if not count.isdigit():
            raise ValueError("DAPA published listing total missing")
        total = int(count)
        items = []
        for anchor in soup.select('a[href*="pressReleaseView.do"][href*="pageIndex="]'):
            spans = one(anchor.select(".source"), "release source").find_all("span", recursive=False)
            if len(spans) != 2 or spans[1].get_text(strip=True) != ISSUER:
                raise ValueError("DAPA listing contains another issuer")
            published = date.fromisoformat(spans[0].get_text(strip=True).replace(".", "-")).isoformat()
            if not request[1]["startDate"] <= published <= request[1]["endDate"]:
                raise ValueError("DAPA release outside declared search window")
            title = one(anchor.select("strong"), "release original title").get_text(" ", strip=True)
            if not title:
                raise ValueError("DAPA release title missing")
            items.append({
                "url": article_url(urljoin(self.listing, anchor["href"])),
                "date": published, "title": title,
            })
        if not items:
            if not soup.select(".list_type .no_data") or total != 0:
                raise ValueError("missing DAPA rows without an explicit zero-result marker")
            return Page([], declared_total=0)
        one(soup.select(".paging"), "DAPA pagination")
        current = soup.select(".paging a.on")
        if current and (len(current) != 1 or current[0].get_text(strip=True) != str(number)):
            raise ValueError("DAPA pagination current page mismatch")
        pages = [
            int(m.group(1)) for a in soup.select(".paging a[onclick]")
            for m in [re.fullmatch(r"pageLink\(([0-9]+)\); return false;", a["onclick"])]
            if m
        ]
        if any(n > number for n in pages) and number + 1 not in pages:
            raise ValueError("DAPA next page missing")
        follow = dict(request[1], pageIndex=str(number + 1))
        return Page(items, (self.listing, follow) if number + 1 in pages else None, total)

    def metadata(self, text, url):
        soup = BeautifulSoup(text, "html.parser")
        if one(soup.select('link[rel="canonical"]'), "canonical DAPA link").get("href") != article_url(url):
            raise ValueError("DAPA article canonical identity changed")
        title = one(soup.select(".view_title h1"), "DAPA original title").get_text(" ", strip=True)
        info = one(soup.select(".variety .info"), "DAPA issuer/date")
        published = date.fromisoformat(
            one(info.select("span:first-child"), "DAPA posting date").get_text(strip=True).replace(".", "-")
        ).isoformat()
        issuer = one(
            info.select('a.gotosite[href="/news/ministryNewsList.do?repCode=B00008"]'),
            "DAPA issuer link",
        )
        if issuer.get_text(" ", strip=True) != ISSUER or not title:
            raise ValueError("DAPA article issuer or title changed")

        hwpx = set()
        for link in soup.select('a[href*="/common/download.do"]'):
            label = link.get_text(" ", strip=True).lower()
            # PDF is a parallel representation, not a second independent
            # original; we retrieve exactly one source HWPX, never the PDF.
            if not label.endswith((".hwpx", ".pdf")):
                raise ValueError("unsupported DAPA attachment format")
            download = urljoin(url, link["href"])
            p = urlsplit(download)
            q = parse_qs(p.query, keep_blank_values=True)
            if (p.scheme != "https" or p.netloc != HOST or
                    p.path != DOWNLOAD_PATH or p.fragment or
                    set(q) != {"fileId", "tblKey"} or
                    len(q["fileId"]) != 1 or
                    not re.fullmatch(r"[1-9][0-9]{0,19}", q["fileId"][0]) or
                    q["tblKey"] != ["GMN"]):
                raise ValueError("DAPA original document URL invalid")
            if label.endswith(".hwpx"):
                hwpx.add(download)
        if len(hwpx) != 1:
            raise ValueError("DAPA requires exactly one distinct HWPX original")
        return title, published, hwpx.pop()

    def parse_article(self, text, url):
        title, published, document_url = self.metadata(text, url)
        if url not in self.documents:
            raise ValueError("DAPA document was not captured; portal iframe is not original text")
        payload, evidence = self.documents[url]
        original = hwpx_text(payload)
        news_id = parse_qs(urlsplit(url).query)["newsId"][0]
        return ExtractedDocument(url, self.slug, title, original, published, "ko", {
            "source_identity": IDENTITY_PREFIX + news_id,
            "publisher": "대한민국 정책브리핑",
            "issuer": ISSUER,
            "publication_kind": "syndicated_press_release",
            "body_scope": "captured_hwpx_text_not_editorially_approved",
            "attachments_collected": True,
            "document_url": document_url,
            "document_capture_sha256": evidence["capture_sha256"],
            "document_retrieved_at": evidence["retrieved_at"],
            "publisher_text_license_notice": observed_text_notice(text),
            "document_reuse_approved": False,
            "third_party_media_approved": False,
            "korean_semantic_review_approved": False,
            "additional_issuers_review_required": True,
            "public_metadata_admission_approved": False,
            "public_full_text_approved": False,
        })
