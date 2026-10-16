"""Manual robots-first availability observation for DAPA's OWN official site.

This is an independent OFF-BY-DEFAULT source lead, not an alternative way to
circumvent a failed korea.kr request. No crawling, retries, document requests,
file persistence, author attribution, reuse clearance, or production writes.
The one-time approval for korea.kr does NOT authorize this separate host.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlsplit

from scripts.probe_vietnam_mod_defrel_access import NoRedirect

HOST = "https://www.dapa.go.kr"
ROBOTS = HOST + "/robots.txt"
LISTING = HOST + "/dapa/doc/selectDocList.do?bbsSeq=326&menuSeq=3069"
USER_AGENT = "IndoPacificRecord/1.0 (+https://indopacificrecord.org; DAPA metadata-only source research)"
SCHEMA = "ipr-korea-dapa-native-listing-access/1"
MAX_ROBOTS = 32768
MAX_LISTING = 350000
MAX_SAMPLES = 6
TIMEOUT = 15
PAUSE = 2.0


class AccessHold(ValueError):
    """Fixed codes only. Never reveal source response bodies or secrets."""


def fetch_once(url, cap, *, opener=None):
    if (url, cap) not in ((ROBOTS, MAX_ROBOTS), (LISTING, MAX_LISTING)):
        raise AccessHold("unapproved_dapa_native_destination")
    client = opener or urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(url, method="GET", headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/plain" if url == ROBOTS else "text/html",
    })
    try:
        with client.open(req, timeout=TIMEOUT) as response:
            if response.status != 200 or response.geturl() != url:
                raise AccessHold("publisher_http_status_or_redirect")
            kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if kind != ("text/plain" if url == ROBOTS else "text/html"):
                raise AccessHold("publisher_content_type_unexpected")
            content = response.read(cap + 1)
            if not content or len(content) > cap:
                raise AccessHold("publisher_body_empty_or_oversize")
            return content
    except urllib.error.HTTPError:
        raise AccessHold("publisher_http_denied_or_redirected") from None
    except (TimeoutError, OSError, urllib.error.URLError):
        raise AccessHold("publisher_network_unavailable") from None


def robots_allow(data):
    try:
        body = data.decode("utf-8-sig")
    except UnicodeError:
        raise AccessHold("publisher_robots_not_utf8") from None
    if "<html" in body.lower() or not any(
        line.strip().lower().startswith("user-agent:") for line in body.splitlines()
    ):
        raise AccessHold("publisher_robots_unreadable_or_challenged")
    robots = urllib.robotparser.RobotFileParser()
    robots.parse(body.splitlines())
    if not robots.can_fetch(USER_AGENT, LISTING):
        raise AccessHold("publisher_robots_disallow_listing")
    return True


def provisional_doc_sequence(href):
    """Parser-only numeric lead; NEVER a confirmed item identity or issuer."""
    if not isinstance(href, str) or not (0 < len(href) < 2000):
        return None
    parsed = urlsplit(urljoin(LISTING, href))
    if (parsed.scheme != "https" or parsed.netloc != "www.dapa.go.kr"
            or parsed.path != "/dapa/doc/selectDoc.do"
            or parsed.fragment or parsed.username or parsed.password):
        return None
    try:
        query = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True)
    except ValueError:
        return None
    if (set(query) - {"bbsSeq", "docSeq", "menuSeq"}
            or any(len(values) != 1 for values in query.values())
            or query.get("bbsSeq") != ["326"]
            or ("menuSeq" in query and query["menuSeq"] != ["3069"])):
        return None
    number = query.get("docSeq", [""])[0]
    return number if re.fullmatch(r"[1-9][0-9]{0,19}", number) else None


class Anchors(HTMLParser):
    """Count safe structural shapes ONLY; never print href, JS, title or HTML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = 0
        self.docseq = set()
        self._row = None
        self._cell = None
        self._cell_chunks = []
        self.row_counts = {
            "table_rows": 0,
            "table_data_cells": 0,
            "table_rows_with_iso_date": 0,
            "dated_rows_with_any_anchor": 0,
            "dated_rows_with_js_or_click_activation": 0,
            "dated_rows_with_qualified_static_docseq": 0,
            "dated_rows_without_qualified_static_docseq": 0,
        }
        self.structures = {
            "anchors_missing_href": 0,
            "anchors_with_javascript_href": 0,
            "anchors_with_fragment_href": 0,
            "anchors_with_onclick": 0,
            "anchors_with_direct_detail_path": 0,
            "direct_detail_path_without_qualified_docseq": 0,
            "forms_get": 0,
            "forms_post": 0,
            "forms_other_or_missing_method": 0,
            "hidden_inputs": 0,
            "inputs_named_docseq": 0,
            "anchors_with_numeric_docseq_attribute": 0,
        }

    def handle_starttag(self, tag, attrs):
        vals = dict(attrs)
        if tag == "tr":
            # Count only table structure. A row number is NOT a docSeq.
            self.row_counts["table_rows"] += 1
            self._row = {
                "date": False, "anchor": False, "activation": False,
                "qualified": False,
            }
        elif tag == "td" and self._row is not None:
            self.row_counts["table_data_cells"] += 1
            self._cell = True
            self._cell_chunks = []
        if tag == "form":
            method = (vals.get("method") or "").strip().lower()
            key = {
                "get": "forms_get",
                "post": "forms_post",
            }.get(method, "forms_other_or_missing_method")
            self.structures[key] += 1
        elif tag == "input":
            if (vals.get("type") or "").strip().lower() == "hidden":
                self.structures["hidden_inputs"] += 1
            if (vals.get("name") or "").strip().lower() == "docseq":
                self.structures["inputs_named_docseq"] += 1
        if tag != "a":
            return
        self.links += 1
        if self._row is not None:
            self._row["anchor"] = True
            if "onclick" in vals or (
                isinstance(vals.get("href"), str) and
                (vals["href"].lstrip().lower().startswith("javascript:")
                 or vals["href"].lstrip().startswith("#"))
            ):
                self._row["activation"] = True
        href = vals.get("href")
        if href is None:
            self.structures["anchors_missing_href"] += 1
        elif isinstance(href, str):
            stripped = href.strip()
            if stripped.lower().startswith("javascript:"):
                self.structures["anchors_with_javascript_href"] += 1
            if stripped.startswith("#"):
                self.structures["anchors_with_fragment_href"] += 1
            if len(stripped) < 2000:
                # Only aggregate allowed *path shapes*, not full URLs or query
                # values from a publisher page; dynamic onclick IDs are not
                # promoted to source records by this diagnostic.
                try:
                    parsed = urlsplit(urljoin(LISTING, stripped))
                    detail = (parsed.scheme == "https"
                              and parsed.netloc == "www.dapa.go.kr"
                              and parsed.path == "/dapa/doc/selectDoc.do")
                except ValueError:
                    detail = False
                if detail:
                    self.structures["anchors_with_direct_detail_path"] += 1
        if "onclick" in vals:
            self.structures["anchors_with_onclick"] += 1
        if any(
            key.lower() in ("data-docseq", "data-doc-seq")
            and isinstance(value, str)
            and re.fullmatch(r"[1-9][0-9]{0,19}", value)
            for key, value in attrs
        ):
            self.structures["anchors_with_numeric_docseq_attribute"] += 1
        seq = provisional_doc_sequence(href)
        if seq is not None:
            self.docseq.add(seq)
            if self._row is not None:
                self._row["qualified"] = True
        elif href is not None and isinstance(href, str) and len(href) < 2000:
            try:
                parsed = urlsplit(urljoin(LISTING, href))
                if (parsed.netloc == "www.dapa.go.kr"
                        and parsed.path == "/dapa/doc/selectDoc.do"):
                    self.structures["direct_detail_path_without_qualified_docseq"] += 1
            except ValueError:
                pass


    def handle_data(self, data):
        # Inspect at most 80 characters per TD for a date-shape signal;
        # never persist or print any title/body text.
        if self._row is not None and self._cell:
            available = max(0, 80 - sum(map(len, self._cell_chunks)))
            if available:
                self._cell_chunks.append(data[:available])

    def handle_endtag(self, tag):
        if tag == "td" and self._row is not None and self._cell:
            date_text = "".join(self._cell_chunks).strip()
            if re.search(r"(?<![0-9])20[0-9]{2}[-.][01][0-9][-.][0-3][0-9](?![0-9])",
                         date_text):
                self._row["date"] = True
            self._cell = None
            self._cell_chunks = []
        elif tag == "tr" and self._row is not None:
            if self._row["date"]:
                self.row_counts["table_rows_with_iso_date"] += 1
                if self._row["anchor"]:
                    self.row_counts["dated_rows_with_any_anchor"] += 1
                if self._row["activation"]:
                    self.row_counts["dated_rows_with_js_or_click_activation"] += 1
                if self._row["qualified"]:
                    self.row_counts["dated_rows_with_qualified_static_docseq"] += 1
                else:
                    self.row_counts["dated_rows_without_qualified_static_docseq"] += 1
            self._row = None
            self._cell = None
            self._cell_chunks = []


def inspect_listing(data):
    try:
        body = data.decode("utf-8-sig")
    except UnicodeError:
        raise AccessHold("publisher_listing_not_utf8") from None
    first = body[:18000].lower()
    if any(marker in first for marker in (
        "captcha", "verify you are human", "cf-mitigated", "just a moment",
        "access denied",
    )):
        raise AccessHold("publisher_listing_challenge")
    if "<html" not in first or "<a " not in body.lower():
        raise AccessHold("publisher_listing_unrecognized_markup")
    parser = Anchors()
    try:
        parser.feed(body)
        parser.close()
    except (ValueError, TypeError):
        raise AccessHold("publisher_listing_invalid_markup") from None
    ids = sorted(parser.docseq, key=lambda value: int(value))
    return {
        "observed_anchor_count": parser.links,
        "structure_counts": parser.structures,
        "date_row_shape_counts": parser.row_counts,
        "provisional_docseq_count": len(ids),
        "sample_unverified_docseq": ids[:MAX_SAMPLES],
        "zero_matching_links_is_not_zero_publications": len(ids) == 0,
    }


def probe(*, fetch=fetch_once, sleep=time.sleep):
    record = {
        "schema": SCHEMA,
        "publisher": "www.dapa.go.kr",
        "surface": "dapa_native_press_releases_bbsSeq_326",
        "state": "blocked",
        "requests_attempted": 0,
        "robots_checked": False,
        "listing_checked": False,
        "article_requests": 0,
        "attachment_requests": 0,
        "original_text_saved": False,
        "dapa_issuer_per_article_verified": False,
        "rights_cleared": False,
        "collector_enabled": False,
        "production_published": False,
    }
    try:
        record["requests_attempted"] = 1
        robots_allow(fetch(ROBOTS, MAX_ROBOTS))
        record["robots_checked"] = True
        sleep(PAUSE)
        record["requests_attempted"] = 2
        record.update(inspect_listing(fetch(LISTING, MAX_LISTING)))
        record["listing_checked"] = True
        record["state"] = "listing_shape_observed_unverified"
    except AccessHold as exc:
        record["reason_code"] = str(exc)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--approve-one-time-direct-dapa-access", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_one_time_direct_dapa_access:
        parser.error("separate first-party DAPA host permission required")
    report = probe()
    print(json.dumps(report, sort_keys=True, ensure_ascii=True))
    return 0 if report["state"] == "listing_shape_observed_unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
