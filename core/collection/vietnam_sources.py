"""Offline identity and scope rules for the three bounded ministry surfaces.

Shared by collection and review; no transport or production imports. Each
surface has isolated state and a separate clock, even when two share a host.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse


@dataclass(frozen=True)
class MinistrySource:
    slug: str
    host: str
    listing: str
    prefix: str
    publisher: str
    family: str
    hash_rule: str
    state_branch: str
    category_id: str = ""
    language: str = "vi"
    publication_kind: str = "ministry portal report"

    def article_id(self, url):
        try:
            p = urlparse(url or "")
        except ValueError:
            return None
        if (p.scheme, p.netloc) != ("https", self.host) or p.query or p.fragment or p.params:
            return None
        if self.host == "bocongan.gov.vn":
            m = re.fullmatch(r"/bai-viet/[a-z0-9-]+-(\d{10})", p.path)
            return m.group(1) if m else None
        if re.fullmatch(r"/tin-tuc/(?:[a-z0-9-]+/)*[a-z0-9-]+\.html", p.path):
            return p.path
        return None

    def identity(self, url):
        ident = self.article_id(url)
        return self.prefix + ident if ident is not None else None


SOURCES = {
    "vn_mps_foreign_affairs_vi": MinistrySource(
        "vn_mps_foreign_affairs_vi", "bocongan.gov.vn",
        "https://bocongan.gov.vn/api/rss/34.xml", "mps-vi:",
        "Cổng thông tin điện tử Bộ Công an", "Thông tin Đối ngoại",
        "mps-vi-content-v1", "shadow/vietnam-mps-foreign-affairs"),
    "vn_moit_energy_vi": MinistrySource(
        "vn_moit_energy_vi", "moit.gov.vn",
        "https://moit.gov.vn/tin-tuc/phat-trien-nang-luong", "moit-energy-vi:",
        "Cổng thông tin điện tử Bộ Công Thương", "Phát triển năng lượng",
        "moit-vi-content-v1", "shadow/vietnam-moit-energy", "5238390"),
    "vn_moit_foundational_industry_vi": MinistrySource(
        "vn_moit_foundational_industry_vi", "moit.gov.vn",
        "https://moit.gov.vn/tin-tuc/phat-trien-cong-nghiep/cong-nghiep-nen-tang",
        "moit-industry-vi:", "Cổng thông tin điện tử Bộ Công Thương",
        "Công nghiệp nền tảng", "moit-vi-content-v1",
        "shadow/vietnam-moit-foundational-industry", "5238380"),
}


def content_sha256(rule, title, lead, blocks):
    payload = json.dumps({"rule": rule, "title": title, "lead": lead,
                          "blocks": [[k, t] for k, t in blocks]},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def visible_date(stamp):
    """Date explicitly printed by the article; no instant or offset invented."""
    match = re.search(r"(?<!\d)(\d{2}/\d{2}/\d{4})(?!\d)", stamp or "")
    if not match:
        raise ValueError("article has no printed day/month/year date")
    return datetime.strptime(match.group(1), "%d/%m/%Y").date().isoformat()
