"""One-time, owner-gated first-party DAPA article identity evidence canary.

No prior listing or catalogue permission authorizes this article GET. No
pagination, attachments, source-text capture, mirror, translation, inference
of DAPA authorship, or public admission. A successful test is NOT a collector.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

from scripts.probe_vietnam_mod_defrel_access import NoRedirect

HOST = "https://www.dapa.go.kr"
ROBOTS = HOST + "/robots.txt"
ARTICLE = HOST + "/dapa/doc/selectDoc.do?bbsSeq=326&docSeq=59180&menuSeq=3069"
EXPECTED_DOCSEQ = "59180"
EXPECTED_POSTED_DATE = "2026-09-18"
AGENT = "IndoPacificRecord/1.0 (+https://indopacificrecord.org; single-source official DAPA metadata audit)"
ROBOT_BYTES = 32768
ARTICLE_BYTES = 800000
TIMEOUT = 15
PAUSE = 2.0
SCHEMA = "ipr-korea-dapa-first-party-one-article-identity-observation/1"


class Hold(ValueError):
    """Static failure reason only: never include publisher body or request URL."""


class VisibleText(HTMLParser):
    """Discard scripts and style; retain only short in-memory date evidence."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden_depth = 0
        self.text = []
        self.visible_chars = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data):
        if not self.hidden_depth:
            self.visible_chars += len(data)
            if self.visible_chars > ARTICLE_BYTES:
                raise Hold("dapa_article_visible_text_oversize")
            self.text.append(data)


def get_once(url, limit, *, opener=None):
    if (url, limit) not in ((ROBOTS, ROBOT_BYTES), (ARTICLE, ARTICLE_BYTES)):
        raise Hold("dapa_article_destination_not_allowlisted")
    client = opener or urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": AGENT,
        "Accept": "text/plain" if url == ROBOTS else "text/html",
    })
    try:
        with client.open(req, timeout=TIMEOUT) as response:
            if response.status != 200 or response.geturl() != url:
                raise Hold("dapa_article_http_status_or_redirect")
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind != ("text/plain" if url == ROBOTS else "text/html"):
                raise Hold("dapa_article_unexpected_content_type")
            raw = response.read(limit + 1)
            if not raw or len(raw) > limit:
                raise Hold("dapa_article_empty_or_oversized_response")
            return raw
    except urllib.error.HTTPError:
        raise Hold("dapa_article_http_denied") from None
    except (OSError, TimeoutError, urllib.error.URLError):
        raise Hold("dapa_article_publisher_unavailable") from None


def check_robots(raw):
    try:
        body = raw.decode("utf-8-sig")
    except UnicodeError:
        raise Hold("dapa_article_robots_not_utf8") from None
    if "<html" in body.lower() or not any(
        line.strip().lower().startswith("user-agent:") for line in body.splitlines()
    ):
        raise Hold("dapa_article_robots_not_readable") from None
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    if not parser.can_fetch(AGENT, ARTICLE):
        raise Hold("dapa_article_robots_denies_document")
    return True


def inspect_article(raw):
    try:
        html = raw.decode("utf-8-sig")
    except UnicodeError:
        raise Hold("dapa_article_html_not_utf8") from None
    prefix = html[:20000].lower()
    if "<html" not in prefix or any(x in prefix for x in (
        "captcha", "cf-mitigated", "verify you are human",
        "just a moment", "access denied",
    )):
        raise Hold("dapa_article_challenge_or_non_html")
    parser = VisibleText()
    try:
        parser.feed(html)
        parser.close()
    except (TypeError, ValueError):
        raise Hold("dapa_article_unparseable") from None
    visible = " ".join(parser.text)
    # A document body can refer to the indexed date even when the actual
    # publisher posting date differs. Require one unambiguous "게시일" field,
    # immediately followed by its own date; never search the whole body.
    # This is still a page-local observation, NOT a live listing-row match.
    labels = list(re.finditer(r"게시일\s*[:：]?\s*", visible))
    tail = visible[labels[0].end():].lstrip() if len(labels) == 1 else ""
    posted = re.match(
        r"^(20[0-9]{2}[-.][01][0-9][-.][0-3][0-9])(?![0-9])", tail
    )
    has_expected_date = bool(
        posted and posted.group(1).replace(".", "-") == EXPECTED_POSTED_DATE
    )
    return {
        "date_marker_matches_indexed_item": has_expected_date,
        "date_label_observed": bool(labels),
        "title_or_publisher_text_saved": False,
        "document_sha256": hashlib.sha256(raw).hexdigest(),
    }


def observe(*, fetch=None, sleep=time.sleep):
    if fetch is None:
        fetch = get_once  # Late-bind so synthetic tests cannot escape mocks.
    result = {
        "schema": SCHEMA,
        "state": "HOLD",
        "publisher": "www.dapa.go.kr",
        "board": "326",
        "provisional_docseq": EXPECTED_DOCSEQ,
        "expected_posted_date_from_public_index": EXPECTED_POSTED_DATE,
        "requests_attempted": 0,
        "robots_checked": False,
        "single_article_checked": False,
        "article_linked_to_live_listing_row": False,
        "individual_dapa_issuer_verified": False,
        "source_content_licensed": False,
        "article_text_captured": False,
        "file_or_attachment_requests": 0,
        "collection_enabled": False,
        "production_published": False,
    }
    try:
        result["requests_attempted"] = 1
        check_robots(fetch(ROBOTS, ROBOT_BYTES))
        result["robots_checked"] = True
        sleep(PAUSE)
        result["requests_attempted"] = 2
        proof = inspect_article(fetch(ARTICLE, ARTICLE_BYTES))
        result["single_article_checked"] = True
        result.update(proof)
        if not proof["date_marker_matches_indexed_item"]:
            raise Hold("dapa_article_expected_date_not_proven")
        result["state"] = "DAPA_ONE_OFFICIAL_DOCUMENT_ROUTE_AND_DATE_MARKER_OBSERVED"
    except Hold as exc:
        result["reason_code"] = str(exc)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--authorize-one-item-official-article-get", action="store_true")
    args = parser.parse_args(argv)
    if not args.authorize_one_item_official_article_get:
        parser.error("a separate explicit article GET authorization is required")
    receipt = observe()
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=True))
    return 0 if receipt["state"] == "DAPA_ONE_OFFICIAL_DOCUMENT_ROUTE_AND_DATE_MARKER_OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
