"""Offline Korea DAPA policy-portal source identity and document-shape review.

No HTTP client, workflow, model, original bytes store or collector is created.
Inputs are operator-supplied publisher HTML *fixtures*, not proof of access,
copyright permission, HWPX/PDF capture or Korea production readiness.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import parse_qs, urlsplit, urljoin

from bs4 import BeautifulSoup

HOST = "www.korea.kr"
BASE = "https://" + HOST
ISSUER = "방위사업청"
REPCODE = "B00008"
LISTING = BASE + "/briefing/pressReleaseList.do"
KIND = "korea_dapa_policy_briefing_republished_candidate"
ALLOWED_TRACKING = frozenset((
    "newsId", "endDate", "pageIndex", "period", "repCode",
    "repCodeType", "srchWord", "startDate",
))
FILE_TYPE = {"hwpx", "pdf"}
DOWNLOAD = "/common/download.do"


class DAPASourceHold(ValueError):
    """A source-identity, issuer or attachment claim cannot be supported."""


def _check_host(value, path):
    p = urlsplit(value)
    if (p.scheme != "https" or p.netloc != HOST or p.path != path or
            p.fragment or p.username or p.password):
        raise DAPASourceHold("unexpected government publisher origin")
    return p


def _query(parts, allowed):
    qs = parse_qs(parts.query, keep_blank_values=True, strict_parsing=True)
    if set(qs) - set(allowed) or any(len(values) != 1 for values in qs.values()):
        raise DAPASourceHold("ambiguous query keys")
    return {key: values[0] for key, values in qs.items()}


def listing_filter(url):
    """Accept only the explicitly observed DAPA government press listing."""
    p = _check_host(url, "/briefing/pressReleaseList.do")
    q = _query(p, ("pWiseMinistry", "repCode", "repCodeType"))
    if (q.get("pWiseMinistry") != "ministryNews" or q.get("repCode") != REPCODE
            or q.get("repCodeType") != "정부부처"):
        raise DAPASourceHold("DAPA institutional listing filter not established")
    return {"source_host": HOST, "issuer_filter": ISSUER,
            "filter_code": REPCODE, "access_verified": False}


def article_identity(url):
    """Normalize publisher article link but never infer issuer from newsId."""
    p = _check_host(url, "/briefing/pressReleaseView.do")
    q = _query(p, ALLOWED_TRACKING)
    ident = q.get("newsId")
    if not ident or not re.fullmatch(r"[1-9][0-9]{5,19}", ident):
        raise DAPASourceHold("invalid portal document identity")
    if "repCode" in q and q["repCode"] != REPCODE:
        raise DAPASourceHold("explicit article query claims different issuer")
    if "repCodeType" in q and q["repCodeType"] != "정부부처":
        raise DAPASourceHold("issuer category changed")
    return {"source_identity": "korea-dapa-policy:" + ident,
            "canonical_url": BASE + p.path + "?newsId=" + ident,
            "publisher": "대한민국 정책브리핑",
            "issuer": ISSUER,
            "issuer_human_verification_required": True,
            "direct_dapa_website_original": False}


def _one(nodes, kind):
    if len(nodes) != 1:
        raise DAPASourceHold("missing or ambiguous " + kind)
    return nodes[0]


def download_identity(article_url, href):
    """Classify exact government download URL, never fetch attachment bytes."""
    url = urljoin(article_url, href)
    p = _check_host(url, DOWNLOAD)
    q = _query(p, ("fileId", "tblKey"))
    if (set(q) != {"fileId", "tblKey"} or
            not re.fullmatch(r"[1-9][0-9]{0,19}", q["fileId"]) or
            q["tblKey"] != "GMN"):
        raise DAPASourceHold("unreviewed portal download URL")
    return {"file_id": q["fileId"], "canonical_url": BASE + DOWNLOAD +
            "?fileId=" + q["fileId"] + "&tblKey=GMN"}


def _license_notice(soup):
    """Capture an observed claim of text-only KOGL; never approve a use."""
    # A reusable marker must be in the declared publisher license notice;
    # exclude unrelated navigation and article body mentioning KOGL.
    nodes = soup.select('[data-ipr-role="publisher-text-license"]')
    if len(nodes) != 1:
        return {"observed_text_license": "unverified",
                "text_only_notice_present": False}
    note = nodes[0].get_text(" ", strip=True)
    found = re.findall(r"공공누리\s*제\s*([0-4])\s*유형", note)
    if len(found) != 1 or "텍스트에 한하여" not in note:
        raise DAPASourceHold("ambiguous or missing text-only license declaration")
    return {"observed_text_license": "KOGL_type_" + found[0] + "_notice_only",
            "text_only_notice_present": True}


def inspect_provisional_article(html, article_url, expected_listing_date=None):
    """Strict synthetic article shape, not evidence of real publisher retrieval."""
    ident = article_identity(article_url)
    if not isinstance(html, str) or len(html) > 300000:
        raise DAPASourceHold("invalid bounded article fixture")
    soup = BeautifulSoup(html, "html.parser")
    title = _one(soup.select(".view_title h1"), "release title").get_text(" ", strip=True)
    if not title or len(title) > 500:
        raise DAPASourceHold("unusable original Korean title")
    info = _one(soup.select(".variety .info"), "official provenance")
    source = _one(info.select("a.gotosite"), "issuer link")
    p = urlsplit(source.get("href", ""))
    if (p.path != "/news/ministryNewsList.do" or
            _query(p, ("repCode",)) != {"repCode": REPCODE} or
            source.get_text(" ", strip=True) != ISSUER):
        raise DAPASourceHold("government release issuer not DAPA")
    stamp = _one(info.select("span:first-child"), "posting date").get_text(" ", strip=True)
    try:
        posted = date.fromisoformat(stamp.replace(".", "-")).isoformat()
    except ValueError:
        raise DAPASourceHold("invalid portal posting date") from None
    if expected_listing_date is not None and posted != expected_listing_date:
        raise DAPASourceHold("listing and article posting dates disagree")
    attached = []
    seen = set()
    container = _one(soup.select("div.files"), "explicit attachment list")
    for a in container.select("a[href]"):
        label = a.get_text(" ", strip=True).lower()
        match = re.search(r"\.(hwpx|pdf)$", label)
        if not match:
            # Another HWP/image/unsupported document must be reviewed rather
            # than silently called complete.
            raise DAPASourceHold("unsupported attachment type present")
        raw = download_identity(article_url, a["href"])
        fid = raw["file_id"]
        if fid in seen:
            raise DAPASourceHold("duplicate attachment URL/identity")
        seen.add(fid)
        attached.append({"format": match.group(1), "file_id": fid,
                         "download_url": raw["canonical_url"]})
    if not attached or len(attached) > 6:
        raise DAPASourceHold("missing or excessive text-document attachments")
    rights = _license_notice(soup)
    return {"identity": ident, "original_title": title, "portal_post_date": posted,
            "document_attachments": attached,
            "has_hwpx": any(x["format"] == "hwpx" for x in attached),
            "has_pdf": any(x["format"] == "pdf" for x in attached),
            "declared_issuer": ISSUER, "source_kind": KIND,
            **rights,
            "actual_publisher_access_verified": False,
            "document_bytes_verified": False,
            "content_text_verified": False,
            "publisher_permission_approved": False,
            "production_collection_enabled": False,
            "desk_registry_changed": False}


def main():
    raise SystemExit(
        "Offline fixture contract only; import inspection functions in tests. "
        "No live publisher or collector entry point.")


if __name__ == "__main__":
    main()
