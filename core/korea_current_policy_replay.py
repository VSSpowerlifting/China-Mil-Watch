"""Fetch and independently inspect *current* Korea text-reuse policy pages.

This supplies the standing-license gate's publisher-policy callback, NOT a
source-specific eligibility/exception verdict, a legal opinion, or a publisher.
Fail closed if the official sites, baseline clauses, or HTML identity change.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from core.standing_source_rights import POLICIES, StandingLicenseHold

PUBLISHER_POLICY = "https://www.korea.kr/guide/copyRight.do"
KOGL_TERMS = "https://www.kogl.or.kr/info/licenseType1.do"
MAX_BYTES = 2_000_000
SCHEMA = "ipr-korea-current-standing-text-rights/1"

# The official publisher's policy explicitly requires a mark on each work and
# protects photographs/images; KOGL Type 1 separately governs attribution,
# derivative uses and nonendorsement. These clauses are reviewed baseline
# contracts, not a generic "government content is public domain" assumption.
PUBLISHER_CLAUSES = (
    "저작권법 제24조의2",
    "공공누리 표시가 부착된 저작물인지를 확인한 이후에 텍스트는 자유롭게 이용",
    "이용자께서는 반드시 저작물의 출처를 구체적으로 표시",
    "본래 취지와 의도에서 벗어난 변경 및 이용에 대해 책임",
    "저작권 전부를 갖고 있지 아니한 자료도 있습니다",
    "사진 및 이미지를 사용하고자 할 경우에는",
    "사전에 협의한 이후 이용하여 주시기 바랍니다",
)
KOGL_CLAUSES = (
    "제 1유형: 출처 표시",
    "2차적 저작물로 변경하여 이용 가능",
    "영리 목적으로 이용할 수 있습니다",
    "공공기관이 후원한다거나",
    "출처 표시 의무",
    "하이퍼링크를 제공",
    "저작인격권의 존중",
    "이용허락이 자동으로 종료",
)

class PolicyHold(ValueError):
    """Fixed codes only; do not echo publisher response bytes."""


def must(ok, why):
    if not ok:
        raise PolicyHold(why)


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _page_contract(url, raw, clauses):
    must(type(raw) is bytes and 500 <= len(raw) <= MAX_BYTES,
         "official_policy_capture_missing_or_oversize")
    try:
        page = raw.decode("utf-8", "strict")
    except UnicodeError:
        raise PolicyHold("official_policy_capture_not_utf8") from None
    parsed = BeautifulSoup(page, "html.parser")
    for element in parsed(("script", "style", "noscript")):
        element.decompose()
    text = " ".join(parsed.get_text(" ", strip=True).split())
    must(all(clause in text for clause in clauses),
         "official_policy_terms_changed_or_incomplete")
    must(not any(x in text for x in (
        "본 페이지의 저작물은 전부 공공누리 제4유형",
        "공공누리 제1유형 사용을 전면 금지",
    )), "official_policy_contains_conflicting_restriction")
    must(url in (PUBLISHER_POLICY, KOGL_TERMS),
         "untrusted_policy_site")
    return _digest(raw)


def verify_policy_pair(publisher_bytes, kogl_bytes, observed_at_utc):
    """Verify both current standing notices and produce exact gate receipt."""
    must(type(observed_at_utc) is str
         and observed_at_utc.endswith("Z"),
         "untrusted_policy_observation_clock")
    try:
        when = datetime.strptime(observed_at_utc,
                                 "%Y-%m-%dT%H:%M:%SZ").replace(
                                     tzinfo=timezone.utc)
    except ValueError:
        raise PolicyHold("untrusted_policy_observation_clock") from None
    must(when.year >= 2026, "untrusted_policy_observation_clock")
    pub_sha = _page_contract(PUBLISHER_POLICY, publisher_bytes,
                             PUBLISHER_CLAUSES)
    _page_contract(KOGL_TERMS, kogl_bytes, KOGL_CLAUSES)
    return {
        "policy_id": "korea-policy-briefing-kogl-type1-text",
        "official_policy_url": PUBLISHER_POLICY,
        "observed_at_utc": observed_at_utc,
        "publisher_policy_sha256": pub_sha,
        "text_reproduction_permitted": True,
        "derivatives_permitted": True,
        "third_party_exclusions_preserved": True,
        "policy_changed_or_withdrawn": False,
    }


def _official_get(session, url):
    u = urlsplit(url)
    must(u.scheme == "https" and u.hostname in ("www.korea.kr", "www.kogl.or.kr")
         and u.username is None and u.password is None
         and u.port is None and not u.fragment,
         "nonofficial_policy_source")
    try:
        result = session.get(url, timeout=(10, 20), allow_redirects=False,
                             headers={"User-Agent": "IndoPacificRecord/1.0 (+source rights audit)"})
    except requests.RequestException:
        raise PolicyHold("official_policy_unavailable") from None
    must(result.status_code == 200 and result.url == url
         and not result.history,
         "official_policy_http_identity_failed")
    mime = result.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    must(mime in ("text/html", "application/xhtml+xml"),
         "official_policy_content_type_mismatch")
    raw = result.content
    must(type(raw) is bytes and 500 <= len(raw) <= MAX_BYTES,
         "official_policy_response_out_of_bounds")
    return raw


class CurrentKoreaPolicyReplay:
    """Actual HTTPS capture owned by this trusted code, not a caller receipt."""

    def __init__(self, *, session=None, clock=None):
        self._session = session if session is not None else requests.Session()
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self.last_policy_sha256 = None

    def __call__(self, policy):
        must(policy is POLICIES["kr_policy_mnd_releases"]
             or (type(policy) is dict
                 and policy == POLICIES["kr_policy_mnd_releases"]),
             "policy_family_not_korea")
        pub = _official_get(self._session, PUBLISHER_POLICY)
        terms = _official_get(self._session, KOGL_TERMS)
        now = self._clock()
        must(isinstance(now, datetime) and now.tzinfo is not None
             and now.utcoffset().total_seconds() == 0,
             "untrusted_policy_observation_clock")
        stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        receipt = verify_policy_pair(pub, terms, stamp)
        self.last_policy_sha256 = receipt["publisher_policy_sha256"]
        return receipt
