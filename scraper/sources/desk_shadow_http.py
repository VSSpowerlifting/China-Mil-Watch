"""Bounded, identifiable transport for the Indonesia and Korea shadow candidates.

Only these new adapters use this module. No production adapter is changed.
Redirects, retries, cookies and browser challenges are never followed.
"""
from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit

import requests

from core.collection import status as st
from core.collection.contract import (
    CandidateReference, CaptureResult, DiscoveryResult, ExtractionResult, SourceAdapter,
)

USER_AGENT = ("IndoPacificRecord-ShadowCollector/0.1 "
              "(+https://indopacificrecord.org; research archive; contact via site)")
MAX_BYTES = 2_000_000
MAX_PAGES = 10


class Refused(ValueError):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status


def robots_policy(text):
    """Combine the most specific matching groups; Allow wins equal-length ties.

    Crawl-delay is honored, including fractional seconds. Encoded non-ASCII
    paths are compared as Unicode; encoded reserved delimiters stay encoded.
    Unknown/malformed delay values fail closed.
    """
    groups, agents, rules, delays = [], [], [], []
    in_rules = False
    for line in text.lstrip("\ufeff").splitlines():
        field, sep, value = line.split("#", 1)[0].partition(":")
        field, value = field.strip().lower(), value.strip()
        if not sep:
            continue
        if field == "user-agent":
            if in_rules:
                groups.append((agents, rules, delays))
                agents, rules, delays, in_rules = [], [], [], False
            agents.append(value.lower())
        elif agents and field in ("allow", "disallow", "crawl-delay"):
            in_rules = True
            if field == "crawl-delay":
                try:
                    delay = float(value)
                    if not math.isfinite(delay) or delay < 0:
                        raise ValueError()
                    delays.append(delay)
                except ValueError:
                    raise Refused(st.AUTH_FAILURE, "invalid robots Crawl-delay")
            elif value:
                rules.append((field == "allow", value))
    if agents:
        groups.append((agents, rules, delays))
    token = USER_AGENT.split("/", 1)[0].lower()
    matches = [(max((len(a) for a in g[0] if a != "*" and a in token), default=0), g)
               for g in groups]
    specificity = max((n for n, _ in matches), default=0)
    chosen = [g for n, g in matches if n == specificity and
              (n > 0 or "*" in g[0])]
    return ([rule for _, rules, _ in chosen for rule in rules],
            max([2.0] + [d for _, _, delays in chosen for d in delays]))


def _robots_path(value):
    # RFC 9309: decode unreserved/non-ASCII bytes, retain reserved delimiters.
    value = re.sub(r"%[0-9a-fA-F]{2}", lambda m: m.group().upper(), value)
    value = re.sub(r"%(?:2F|3F|23|25|26|3D|3A|3B|2B|24|2C|40)",
                   lambda m: "%25" + m.group()[1:], value)
    return unquote(value, errors="strict")


def robots_allows(rules, url):
    parts = urlsplit(url)
    target = _robots_path(parts.path + ("?" + parts.query if parts.query else ""))
    best = (-1, True)
    for allow, pattern in rules:
        pattern = _robots_path(pattern)
        end = pattern.endswith("$")
        body = pattern[:-1] if end else pattern
        regex = re.escape(body).replace(r"\*", ".*") + ("$" if end else "")
        if re.match(regex, target):
            best = max(best, (len(body.replace("*", "").encode("utf-8")), allow))
    return best[1]


@dataclass
class Page:
    items: list
    next_request: object = None  # (published URL, optional published form fields)
    declared_total: object = None


class ListingShadowAdapter(SourceAdapter):
    def __init__(self, source, session=None, sleeper=time.sleep):
        super().__init__(source)
        self.session = session or requests.Session()
        self.session.trust_env = False  # no environment proxies or .netrc credentials
        self.sleep = sleeper
        self.rules = None
        self.delay = 2.0
        self.last_request = None
        self.robots_status = None
        self.listing_report = {}
        self.evidence = []
        self.references = {}

    def _request(self, url, form=None, robots=False, binary=False):
        parts = urlsplit(url)
        if parts.scheme != "https" or parts.netloc != self.host or parts.fragment:
            raise Refused(st.DISALLOWED_REDIRECT, "off-source URL refused")
        if not robots and (self.rules is None or not robots_allows(self.rules, url)):
            raise Refused(st.AUTH_FAILURE, "robots.txt does not permit " + url)
        if self.last_request is not None:
            self.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        response = None
        try:
            response = self.session.request(
                "POST" if form is not None else "GET", url, data=form,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
                stream=True, allow_redirects=False, timeout=30)
            headers = {k.lower(): v for k, v in response.headers.items()}
            if headers.get("content-encoding", "identity").lower() != "identity":
                raise Refused(st.UNEXPECTED_CONTENT_TYPE, "encoded response refused")
            payload = bytearray()
            limit = 512_000 if robots else MAX_BYTES
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > limit:
                    raise Refused(st.OVERSIZED_RESPONSE, "response exceeds byte cap")
            payload = bytes(payload)
            evidence = {"requested_url": url, "final_url": response.url,
                        "method": "POST" if form is not None else "GET", "form": form,
                        "http_status": response.status_code, "headers": headers,
                        "retrieved_at": datetime.now(timezone.utc).isoformat(),
                        "capture_sha256": hashlib.sha256(payload).hexdigest(), "payload": payload}
            self.evidence.append(evidence)
            if response.url != url or 300 <= response.status_code < 400:
                raise Refused(st.DISALLOWED_REDIRECT, "redirect was not followed")
            probe = payload.decode("utf-8", "replace")
            if (headers.get("cf-mitigated") == "challenge" or re.search(
                    r'<title>\s*(?:Just a moment|Access Denied)|id=["\']challenge-form|'
                    r'_cf_chl_opt\s*=|cf-browser-verification', probe, re.I)):
                raise Refused(st.ACCESS_CHALLENGED, "access challenge refused")
            if response.status_code in (401, 403):
                raise Refused(st.AUTH_FAILURE, "HTTP %d" % response.status_code)
            if robots and response.status_code in (404, 410):
                self.robots_status, self.rules = "absent", []
                return ""
            if response.status_code != 200:
                raise Refused(st.FETCH_FAILURE, "HTTP %d" % response.status_code)
            ctype = headers.get("content-type", "").lower()
            if binary:
                if not ctype.startswith(("application/zip", "application/octet-stream",
                                         "application/haansofthwpx", "application/hwp",
                                         "application/x-download")):
                    raise Refused(st.UNEXPECTED_CONTENT_TYPE, "unexpected document type")
                return payload
            if not ctype.startswith("text/plain" if robots else "text/html"):
                raise Refused(st.UNEXPECTED_CONTENT_TYPE, "unexpected content type")
            text = payload.decode("utf-8", "strict")
            if robots and text.lstrip().startswith("<"):
                raise Refused(st.AUTH_FAILURE, "robots response is HTML")
            if not robots and "</html>" not in text.lower():
                raise Refused(st.EXTRACTION_FAILURE, "incomplete HTML document")
            return text
        except requests.Timeout:
            raise Refused(st.TIMEOUT, "request timed out; no retry")
        except requests.RequestException as exc:
            raise Refused(st.FETCH_FAILURE, "transport failed: " + type(exc).__name__)
        except UnicodeError:
            raise Refused(st.UNEXPECTED_CONTENT_TYPE, "invalid UTF-8 response")
        finally:
            if response is not None:
                response.close()
            if hasattr(self.session, "cookies"):
                self.session.cookies.clear()
            self.last_request = time.monotonic()

    def discover(self, window):
        self.references, self.evidence, self.listing_report = {}, [], {}
        self.rules, self.robots_status = None, None
        start = window.target_date - timedelta(days=window.lookback_days)
        try:
            text = self._request("https://" + self.host + "/robots.txt", robots=True)
            if self.rules is None:
                self.rules, self.delay = robots_policy(text)
                self.robots_status = "read"
            request = self.first_request(window)
            items, visited, declared_total = [], set(), None
            for number in range(1, MAX_PAGES + 1):
                url, form = request
                key = (url, tuple(sorted((form or {}).items())))
                if key in visited:
                    raise Refused(st.LISTING_FAILURE, "pagination loop")
                visited.add(key)
                page = self.parse_listing(self._request(url, form), request, number)
                if page.declared_total is not None:
                    if declared_total is not None and declared_total != page.declared_total:
                        raise Refused(st.LISTING_FAILURE, "search result count changed during traversal")
                    declared_total = page.declared_total
                for item in page.items:
                    if item["url"] in self.references:
                        raise Refused(st.LISTING_FAILURE, "listing repeats an identity")
                    self.references[item["url"]] = item
                items.extend(page.items)
                dates = [i["date"] for i in items]
                if dates != sorted(dates, reverse=True):
                    raise Refused(st.LISTING_FAILURE, "listing is not newest-first")
                if (dates and date.fromisoformat(dates[-1]) < start) or page.next_request is None:
                    if declared_total is not None and len(items) != declared_total:
                        raise Refused(st.LISTING_FAILURE, "listed identities disagree with declared search total")
                    break
                request = page.next_request
            else:
                raise Refused(st.LISTING_FAILURE, "window exceeds listing-page cap")
            selected = [i for i in items if start.isoformat() <= i["date"] <= window.target_date.isoformat()]
            self.listing_report = {"pages_walked": number, "items_listed": len(items),
                                   "window_start": start.isoformat(), "window_end": window.target_date.isoformat(),
                                   "window_proven": True}
            # Only selected references may subsequently be fetched.
            self.references = {i["url"]: i for i in selected}
            refs = [CandidateReference(i["url"], self.slug, self.listing,
                                       i["date"]) for i in selected]
            return DiscoveryResult(self.slug, st.OK if refs else st.OK_NO_PUBLICATIONS, refs)
        except (Refused, ValueError) as exc:
            self.references = {}
            status = exc.status if isinstance(exc, Refused) else st.LISTING_FAILURE
            return DiscoveryResult(self.slug, status, error_detail=str(exc))

    def fetch(self, reference):
        result = CaptureResult(reference, st.FETCH_FAILURE, reference.url)
        try:
            if reference.source_slug != self.slug or reference.url not in self.references:
                raise Refused(st.AUTH_FAILURE, "reference was not admitted by discovery")
            text = self._request(reference.url)
            e = self.evidence[-1]
            result.status, result.body = st.OK, text
            result.final_url, result.http_status = e["final_url"], e["http_status"]
            result.content_type = e["headers"]["content-type"]
            result.payload_bytes, result.payload_sha256 = len(e["payload"]), e["capture_sha256"]
            result.retrieved_at = e["retrieved_at"]
        except Refused as exc:
            result.status, result.error_detail = exc.status, str(exc)
        return result

    def extract(self, capture):
        try:
            if capture.status != st.OK or not capture.body:
                raise ValueError("no successful capture to extract")
            if hashlib.sha256(capture.body.encode("utf-8")).hexdigest() != capture.payload_sha256:
                raise ValueError("capture hash mismatch")
            doc = self.parse_article(capture.body, capture.reference.url)
            if capture.reference.hint_published_date != doc.published_date:
                raise ValueError("listing and article dates disagree")
            hint = self.references.get(doc.url)
            if hint is None or hint["title"] != doc.title_original:
                raise ValueError("listing and article titles/identities disagree")
            doc.extra.update(capture_sha256=capture.payload_sha256,
                             content_sha256=hashlib.sha256(doc.text_original.encode("utf-8")).hexdigest(),
                             date_precision="day")
            doc.extra.setdefault("body_scope", "published_html_text")
            doc.extra.setdefault("attachments_collected", False)
            return ExtractionResult(self.slug, st.OK, [doc])
        except ValueError as exc:
            return ExtractionResult(self.slug, st.EXTRACTION_FAILURE, error_detail=str(exc))
