"""Private, offline DAPA first-party listing-row ↔ article reconciliation.

No network, disk, CLI, publisher-body retention, official publication, source
rights admission, or editorial approval. A numerically matching JavaScript
argument is *provisional* and must be corroborated by a separately
authenticated original version and human issuer/rights review.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

HOST = "www.dapa.go.kr"
LISTING = "https://" + HOST + "/dapa/doc/selectDocList.do?bbsSeq=326&menuSeq=3069"
ARTICLE_PATH = "/dapa/doc/selectDoc.do"
SCHEMA = "ipr-dapa-first-party-private-row-article-reconciliation/1"
MAX_LISTING_BYTES = 350_000
MAX_ARTICLE_BYTES = 800_000
HASH = re.compile(r"[0-9a-f]{64}\Z")
DATE = re.compile(r"(?<![0-9])20[0-9]{2}[-.][01][0-9][-.][0-3][0-9](?![0-9])")
FUNC = re.compile(
    r"""(?:return\s+)?[a-zA-Z_$][a-zA-Z0-9_$]{0,63}\s*\(\s*(['"]?)([1-9][0-9]{0,19})\1\s*\)\s*;?\Z"""
)


class DAPAHold(ValueError):
    """Fixed, safe error codes only."""


def require(condition, code):
    if not condition:
        raise DAPAHold(code)


def bounded_utf8(raw, limit, code):
    require(type(raw) is bytes and 0 < len(raw) <= limit, code)
    try:
        body = raw.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise DAPAHold(code) from None
    require("<html" in body[:12000].lower(), code)
    require(not any(x in body[:12000].lower() for x in (
        "captcha", "access denied", "verify you are human", "just a moment",
        "cf-mitigated",
    )), "dapa_private_captive_or_challenged")
    return body


def canonical_article_identity(url):
    """Only the observed first-party article route, never arbitrary redirects."""
    require(type(url) is str and len(url) <= 2048, "dapa_private_article_url_invalid")
    try:
        parsed = urlsplit(url)
        q = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        raise DAPAHold("dapa_private_article_url_invalid") from None
    require(parsed.scheme == "https" and parsed.netloc == HOST
            and parsed.path == ARTICLE_PATH and not parsed.fragment
            and parsed.username is None and parsed.password is None,
            "dapa_private_article_origin_invalid")
    require(set(q) <= {"bbsSeq", "docSeq", "menuSeq", "currentPageNo",
                       "recordCountPerPage"} and
            all(len(v) == 1 for v in q.values()) and
            q.get("bbsSeq") == ["326"] and q.get("menuSeq") == ["3069"],
            "dapa_private_article_query_invalid")
    seq = q.get("docSeq", [""])[0]
    require(bool(re.fullmatch(r"[1-9][0-9]{0,19}", seq)),
            "dapa_private_article_docseq_invalid")
    for optional in ("currentPageNo", "recordCountPerPage"):
        if optional in q:
            require(bool(re.fullmatch(r"[1-9][0-9]{0,4}", q[optional][0])),
                    "dapa_private_navigation_parameter_invalid")
    return {
        "board": "326",
        "provisional_docseq": seq,
        "canonical_url": "https://" + HOST + ARTICLE_PATH +
                         "?bbsSeq=326&docSeq=" + seq + "&menuSeq=3069",
    }


def _literal_number(action):
    if not isinstance(action, str) or not action or len(action) > 512:
        return None
    action = action.strip()
    if action.lower().startswith("javascript:"):
        action = action[len("javascript:"):].strip()
    match = FUNC.fullmatch(action)
    return match.group(2) if match else None


def _iso_date(value):
    values = DATE.findall(value)
    if len(values) != 1:
        return None
    text = values[0].replace(".", "-")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


class ListingRows(HTMLParser):
    """Read date cells and click signatures; NEVER store a title or script."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_row = False
        self.in_cell = False
        self.in_script = False
        self.cell_chars = []
        self.row_dates = []
        self.row_actions = []
        self.rows = []
        self.seen_rows = 0

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if tag in ("script", "style"):
            self.in_script = True
        if tag == "tr":
            require(not self.in_row, "dapa_private_nested_row")
            self.in_row, self.in_cell = True, False
            self.row_dates, self.row_actions = [], []
            self.seen_rows += 1
            require(self.seen_rows <= 200, "dapa_private_too_many_rows")
        if self.in_row and tag == "td":
            self.in_cell = True
            self.cell_chars = []
        if self.in_row and tag == "a":
            action = attr.get("onclick")
            href = attr.get("href")
            if isinstance(action, str):
                self.row_actions.append(_literal_number(action))
            if isinstance(href, str) and href.lstrip().lower().startswith("javascript:"):
                self.row_actions.append(_literal_number(href))

    def handle_data(self, data):
        if self.in_row and self.in_cell and not self.in_script:
            # No article headings are retained: only a small rolling cell
            # substring necessary for recognizing a calendar date.
            remain = 96 - sum(map(len, self.cell_chars))
            if remain > 0:
                self.cell_chars.append(data[:remain])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.in_script = False
        if tag == "td" and self.in_row and self.in_cell:
            found = _iso_date(" ".join(self.cell_chars))
            if found:
                self.row_dates.append(found)
            self.in_cell = False
            self.cell_chars = []
        if tag == "tr" and self.in_row:
            if self.row_dates:
                # All date-bearing rows are reported as candidates. Multiple
                # observed dates or distinct numeric actions are ambiguous.
                distinct = set(self.row_dates)
                numbers = [n for n in self.row_actions if n is not None]
                valid = (
                    len(distinct) == 1 and len(self.row_dates) == 1 and
                    len(self.row_actions) == 1 and len(numbers) == 1
                )
                self.rows.append({
                    "posted_date": self.row_dates[0] if len(distinct) == 1 else None,
                    "provisional_docseq": numbers[0] if valid else None,
                    "navigation_unambiguous": valid,
                })
            self.in_row = False
            self.in_cell = False
            self.row_dates = []
            self.row_actions = []


class VisibleArticle(HTMLParser):
    """Keep only a bounded contiguous visible date/label signal."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []
        self.chars = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if self.hidden:
            return
        self.chars += len(data)
        require(self.chars <= MAX_ARTICLE_BYTES,
                "dapa_private_article_visible_text_overflow")
        self.parts.append(data)


def reconcile(listing_raw, article_raw, article_url):
    """Synthetic/offline consistency test, NOT an authenticated live approval.

    Captured bytes MUST stay in private operator custody. Matching a JS number
    to an article URL alone does not establish authentic publisher linkage.
    """
    listing = bounded_utf8(listing_raw, MAX_LISTING_BYTES,
                           "dapa_private_listing_invalid")
    article = bounded_utf8(article_raw, MAX_ARTICLE_BYTES,
                           "dapa_private_article_invalid")
    identity = canonical_article_identity(article_url)
    reader = ListingRows()
    reader.feed(listing)
    reader.close()
    page = VisibleArticle()
    page.feed(article)
    page.close()
    visible = " ".join(page.parts)
    # Never extract or echo any governmental original text or media.
    # A displayed date without the posting label is not sufficient.
    # The release body can legitimately mention other calendar dates.
    # Only the field directly following the visible "게시일" posting label
    # is relevant. Repeated/conflicting labels are not resolved by guessing.
    markers = list(re.finditer(r"게시일\s*[:：]?\s*", visible))
    page_date = (_iso_date(visible[markers[0].end():markers[0].end() + 48])
                 if len(markers) == 1 else None)
    matches = [row for row in reader.rows if
               row["navigation_unambiguous"] and
               row["provisional_docseq"] == identity["provisional_docseq"]]
    if len(matches) != 1:
        raise DAPAHold("dapa_private_row_identity_absent_or_ambiguous")
    require(page_date is not None and matches[0]["posted_date"] == page_date,
            "dapa_private_row_article_date_mismatch")
    return {
        "schema": SCHEMA,
        "status": "PRIVATE_SELF_CONSISTENT_UNVERIFIED",
        "listing_sha256": hashlib.sha256(listing_raw).hexdigest(),
        "article_sha256": hashlib.sha256(article_raw).hexdigest(),
        "provisional_article_url": identity["canonical_url"],
        "provisional_docseq": identity["provisional_docseq"],
        "provisional_posted_date": page_date,
        "listing_dated_rows_seen": len(reader.rows),
        "publisher_capture_attested": False,
        "real_js_handler_semantics_verified": False,
        "item_local_issuer_verified": False,
        "rights_cleared_for_republication": False,
        "original_document_bytes_verified": False,
        "attachment_reuse_cleared": False,
        "editorial_review_approved": False,
        "production_admission_authorized": False,
        "public_release_authorized": False,
    }
