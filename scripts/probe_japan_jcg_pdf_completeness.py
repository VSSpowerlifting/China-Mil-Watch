"""Read-only, source-bounded JCG HTML/PDF completeness audit.

Research-only evidence, not original-document admission or shadow collection.
The three exact JCG English releases are fetched once with a declared client.
Their explicitly linked, same-host publisher PDFs are inspected in memory.
No article/PDF bytes or extracted prose leave the process; print metadata only.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from pypdf import PdfReader

HOST = "www.kaiho.mlit.go.jp"
PREFIX = "https://" + HOST
CLIENT = ("ChinaMilWatch/1.0 (non-commercial research; project: "
          "https://github.com/VSSpowerlifting/China-Mil-Watch)")
RELEASES = (
    ("jcg-en:9455", PREFIX + "/e/topics_archive/article9455.html"),
    ("jcg-en:9453", PREFIX + "/e/topics_archive/article9453.html"),
    ("jcg-en:9436", PREFIX + "/e/topics_archive/article9436.html"),
)
MAX_ROBOTS_BYTES = 32768
MAX_HTML_BYTES = 262144
MAX_PDF_BYTES = 2097152
MAX_PAGES = 12
TIMEOUT = 18
INTERVAL = 2.0
WORD = re.compile(r"[a-z0-9]{4,}", flags=re.I)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def official_pdf(article_url, raw):
    """Resolve exactly one linked same-origin publisher PDF in article body."""
    parts = urlsplit(article_url)
    if parts.scheme != "https" or parts.netloc != HOST or parts.query or parts.fragment:
        raise ValueError("unrecognized article origin")
    soup = BeautifulSoup(raw, "html.parser")
    sections = soup.select("main article.main-article section.topics.topics-article")
    if len(sections) != 1:
        raise ValueError("unexpected JCG article section")
    bodies = sections[0].select("div.topics-article__main.tich-text")
    if len(bodies) != 1:
        raise ValueError("missing exact JCG article body")
    found = []
    for a in bodies[0].select("a[href]"):
        url = urljoin(article_url, a["href"])
        p = urlsplit(url)
        if p.path.lower().endswith(".pdf"):
            if (p.scheme != "https" or p.netloc != HOST or p.query or p.fragment
                    or not p.path.startswith("/e/topics_archive/upload/")):
                raise ValueError("off-scope or mutable linked PDF reference")
            found.append(url)
    if len(set(found)) != 1 or len(found) != 1:
        raise ValueError("expected exactly one distinct official linked PDF")
    for bad in bodies[0].select("script, style, nav, form, svg, noscript"):
        bad.decompose()
    text = " ".join(
        p.get_text(" ", strip=True) for p in bodies[0].select("p, li, blockquote"))
    if len(text) < 180:
        raise ValueError("article HTML body is not substantive")
    return found[0], text


def _http_once(url, limit, *, opener):
    request = urllib.request.Request(url, headers={
        "User-Agent": CLIENT,
        "Accept": "text/html,application/pdf,text/plain,*/*;q=0.5",
    }, method="GET")
    try:
        response = opener.open(request, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "error": "http_not_served"}
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return {"status": None, "error": "transport_" + type(exc).__name__}
    with response:
        kind = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        data = response.read(limit + 1)
        if len(data) > limit:
            return {"status": response.status, "error": "response_over_limit"}
        return {"status": response.status, "mime": kind, "bytes": data}


def _read_policy(outcome):
    if outcome.get("status") == 404 and outcome.get("error") == "http_not_served":
        return None, "confirmed_absent_404"
    if (outcome.get("status") != 200 or outcome.get("mime") not in ("text/plain", "")
            or not isinstance(outcome.get("bytes"), bytes)):
        raise ValueError("robots policy unreadable/refused")
    text = outcome["bytes"].decode("utf-8-sig", errors="replace")
    if not any(line.strip().lower().startswith("user-agent:") for line in text.splitlines()):
        raise ValueError("robots response lacks directives")
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(text.splitlines())
    return parser, "parsed"


def _pdf_metrics(raw):
    if not raw.startswith(b"%PDF-"):
        raise ValueError("PDF signature missing")
    document = PdfReader(io.BytesIO(raw), strict=True)
    if document.is_encrypted or not 1 <= len(document.pages) <= MAX_PAGES:
        raise ValueError("encrypted or unbounded PDF")
    pages = [p.extract_text() or "" for p in document.pages]
    text = "\n".join(pages)
    return {"page_count": len(pages), "text": text,
            "pages_without_text": sum(len(p.strip()) < 20 for p in pages)}


def _bag(text):
    return Counter(WORD.findall(text.casefold()))


def _compare(original, companion):
    html, pdf = _bag(original), _bag(companion)
    overlap = sum(min(n, pdf.get(t, 0)) for t, n in html.items())
    html_count, pdf_count = sum(html.values()), sum(pdf.values())
    return {
        "html_word_tokens": html_count, "pdf_word_tokens": pdf_count,
        "html_tokens_observed_in_pdf": overlap,
        "html_coverage_ratio": round(overlap / html_count, 3) if html_count else None,
        "pdf_tokens_not_matched_to_html": pdf_count - overlap,
        "pdf_wordtypes_not_in_html": len(set(pdf) - set(html)),
    }


def audit(*, opener=None, fetch=_http_once, pdf_metrics=_pdf_metrics,
          sleep=time.sleep):
    opener = opener or urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect())
    sleep(INTERVAL)
    policy_reply = fetch(PREFIX + "/robots.txt", MAX_ROBOTS_BYTES, opener=opener)
    robots, policy = _read_policy(policy_reply)
    observations = []
    for identity, article in RELEASES:
        entry = {"id": identity, "article_url": article,
                 "assessment": "incomplete_not_reviewed"}
        observations.append(entry)
        if robots is not None and not robots.can_fetch(CLIENT, article):
            entry["failure"] = "article_robots_disallow"
            continue
        sleep(INTERVAL)
        html_reply = fetch(article, MAX_HTML_BYTES, opener=opener)
        if (html_reply.get("status") != 200 or
                html_reply.get("mime") not in ("text/html", "application/xhtml+xml") or
                not isinstance(html_reply.get("bytes"), bytes)):
            entry["failure"] = "html_unavailable_or_invalid"
            continue
        html_bytes = html_reply["bytes"]
        entry["html_sha256"] = hashlib.sha256(html_bytes).hexdigest()
        entry["html_bytes"] = len(html_bytes)
        try:
            linked, html_text = official_pdf(article, html_bytes)
        except ValueError as exc:
            entry["failure"] = str(exc)
            continue
        entry["pdf_url"] = linked
        if robots is not None and not robots.can_fetch(CLIENT, linked):
            entry["failure"] = "pdf_robots_disallow"
            continue
        sleep(INTERVAL)
        pdf_reply = fetch(linked, MAX_PDF_BYTES, opener=opener)
        if (pdf_reply.get("status") != 200 or
                pdf_reply.get("mime") != "application/pdf" or
                not isinstance(pdf_reply.get("bytes"), bytes)):
            entry["failure"] = "pdf_unavailable_or_invalid"
            continue
        raw_pdf = pdf_reply["bytes"]
        entry["pdf_bytes"] = len(raw_pdf)
        entry["pdf_sha256"] = hashlib.sha256(raw_pdf).hexdigest()
        try:
            metrics = pdf_metrics(raw_pdf)
            entry["pdf_pages"] = metrics["page_count"]
            entry["pdf_pages_without_text"] = metrics["pages_without_text"]
            entry["pdf_extracted_chars"] = len(metrics["text"])
            entry.update(_compare(html_text, metrics["text"]))
            entry["assessment"] = "ready_for_human_original_comparison"
        except (ValueError, IndexError, KeyError, TypeError) as exc:
            entry["failure"] = "pdf_parser_" + type(exc).__name__
    return {
        "schema": "japan-jcg-linked-pdf-completeness-audit/1",
        "status": "research_metadata_only_never_source_approval",
        "robots": policy,
        "records": observations,
        "complete_metadata_observations": sum(
            r["assessment"] == "ready_for_human_original_comparison"
            for r in observations),
        "human_original_document_review_completed": False,
        "source_promoted": False,
        "source_text_or_pdf_persisted": False,
    }


def main():
    try:
        outcome = audit()
    except ValueError as exc:
        print(json.dumps({"status": "stopped_before_articles",
                          "reason": str(exc)}))
        return 2
    print(json.dumps(outcome, indent=2, sort_keys=True))
    print("A metadata-only comparison is not evidence of PDF completeness.")
    return 0 if outcome["complete_metadata_observations"] == len(RELEASES) else 1


if __name__ == "__main__":
    sys.exit(main())
